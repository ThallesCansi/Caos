"""Teste de substitutas na série média de cada bacia (caderno 06), análise complementar (D-016).

A série é a mesma do lote por célula (anomalia padronizada, 2001–2024), mas da média
ponderada pela área da bacia inteira. Com uma só série por bacia e variável, cabem 199
substitutas, o que dá um p mínimo de 0,005 (unilateral), e cabem as duas hipóteses nulas:
FT (processo linear gaussiano) e IAAFT (o mesmo, visto através de uma transformação
monotônica). Os parâmetros (τ, m, w) são escolhidos na série observada e mantidos nas
substitutas, como no lote. Uma terceira variante repete o IAAFT depois de retirar a
tendência linear, que o pré-registro mantém na série: as séries das bacias sobem quase um
desvio-padrão em 24 anos, e uma tendência é uma não estacionariedade que nenhuma das duas
hipóteses nulas contempla.
"""

from __future__ import annotations

import hashlib
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.diagnostic import breaks_cusumolsresid
from statsmodels.stats.multitest import multipletests
from statsmodels.tsa.stattools import acf, adfuller, kpss

from amazon_chaos import regions
from amazon_chaos.nonlinear.batch import NORMAL
from amazon_chaos.nonlinear.suite import batch_hash, surrogate_suite
from amazon_chaos.nonlinear.surrogates import validate_series
from amazon_chaos.regional import regional_frame, standardized_anomalies, summarize

N_SURROGATES = 199
METHODS = ("FT", "IAAFT", "IAAFT sem tendência")
VARIABLES = ("t2m", "vpd")


def basin_series(cfg, variable: str, spec: dict, detrend: bool = False) -> pd.Series:
    """Anomalia padronizada da média diária da bacia, na janela completa do pré-registro."""
    raw = regional_frame(summarize(cfg))[variable]
    z, _ = standardized_anomalies(raw, NORMAL)
    first, last = (str(d) for d in spec["series"]["period"])
    z = z.loc[first:last]
    if detrend:
        t = np.arange(len(z))
        z = z - np.polyval(np.polyfit(t, z.to_numpy(), 1), t)
    return z


def output_dir(cfg, spec) -> Path:
    return regions.processed_dir(cfg) / "substitutas_bacia" / batch_hash(spec)


def _seed(spec, *parts) -> int:
    key = "|".join(map(str, (spec["surrogates"]["seed"], "bacia", *parts)))
    return int.from_bytes(hashlib.sha256(key.encode()).digest()[:4], "little")


def _file(target, variable, method) -> Path:
    return target / f"{variable}_{method.replace(' ', '_')}.parquet"


def _task(args):
    cfg, spec, variable, method, path = args
    surrogate = method.split()[0]
    x = basin_series(cfg, variable, spec, detrend="tendência" in method).to_numpy(dtype=float)
    spec = {**spec, "surrogates": {**spec["surrogates"], "method": surrogate}}
    result = surrogate_suite(x, spec, n_surrogates=N_SURROGATES,
                             seed=_seed(spec, cfg["slug"], variable, method))
    labels = {"region": cfg["slug"], "variable": variable, "method": method}
    null = pd.DataFrame([{**labels, "descriptor": k, "surrogate": i, "value": v}
                         for k, values in result.null.items() for i, v in enumerate(values)])
    table = result.table(**labels)
    # nulas e resultado no mesmo arquivo: kind distingue as linhas
    pd.concat([table.assign(kind="teste"), null.assign(kind="nula")],
              ignore_index=True).to_parquet(path, index=False)
    return path


def run(cfg, spec, *, workers: int | None = None, report=print) -> Path:
    """Calcula o que faltar: duas variáveis × (FT, IAAFT, IAAFT sem tendência)."""
    target = output_dir(cfg, spec)
    target.mkdir(parents=True, exist_ok=True)
    tasks = [(cfg, spec, v, m, _file(target, v, m)) for v in VARIABLES for m in METHODS]
    tasks = [t for t in tasks if not t[-1].exists()]
    if not tasks:
        return target
    report(f"🎭 {cfg['name']}: {len(tasks)} testes × {N_SURROGATES} substitutas")
    with ProcessPoolExecutor(workers or len(tasks)) as pool:
        list(pool.map(_task, tasks))
    report(f"✅ {cfg['name']}: teste na série da bacia pronto")
    return target


def load(cfg, spec) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Resultado com Holm sobre os descritores primários de cada bacia × método, e as nulas."""
    target = output_dir(cfg, spec)
    rows = pd.concat([pd.read_parquet(_file(target, v, m)) for v in VARIABLES
                      for m in METHODS], ignore_index=True)
    table = rows[rows.kind == "teste"].dropna(axis=1, how="all").reset_index(drop=True)
    null = rows[rows.kind == "nula"][["region", "variable", "method", "descriptor",
                                      "surrogate", "value"]]
    primary = spec["families"]["primary"]
    table["holm"] = np.nan
    for _, part in table[table.descriptor.isin(primary)].groupby(["region", "method"]):
        table.loc[part.index, "holm"] = multipletests(part.pvalue.fillna(1), method="holm")[1]
    return table, null


def stationarity_diagnostics(series, blocks=4, hac_lags=14):
    """Complementary diagnostics, never a certificate of stationarity.

    ADF fixed lag 14 and KPSS automatic bandwidth; trend HAC and CUSUM are
    descriptive with serial-dependence caveats. Thresholds are protocol flags,
    not calibrated stationarity tests. No detrending follows these diagnostics.
    """
    x = validate_series(series, min_length=64)
    chunks = np.array_split(x, blocks)
    block = pd.DataFrame([{"block": i + 1, "n": len(y), "mean": y.mean(),
                           "std": y.std(), "acf1": acf(y, nlags=1, fft=True)[1]}
                          for i, y in enumerate(chunks)])
    # Scale time to the whole record; slope is total change in original units.
    trend = sm.OLS(x, sm.add_constant(np.linspace(0, 1, len(x)))).fit(
        cov_type="HAC", cov_kwds={"maxlags": hac_lags})
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        adf_p = adfuller(x, maxlag=min(hac_lags, len(x) // 4), autolag=None)[1]
        kpss_p = kpss(x, regression="c", nlags="auto")[1]
    # CUSUM around a constant mean, not around an automatically detrended signal.
    cusum_p = breaks_cusumolsresid(x - x.mean(), ddof=1)[1]
    variance_ratio = float(block["std"].max() / max(block["std"].min(), 1e-15))
    mean_range = float(np.ptp(block["mean"]) / x.std())
    acf_range = float(np.ptp(block["acf1"]))
    flags = []
    if trend.pvalues[1] < .05:
        flags.append("tendência HAC")
    if kpss_p < .05:
        flags.append("KPSS rejeita nível estacionário")
    if adf_p >= .05:
        flags.append("ADF não rejeita raiz unitária")
    if variance_ratio > 1.5:
        flags.append("heterogeneidade de variância")
    if mean_range > .5:
        flags.append("heterogeneidade de média")
    if acf_range > .25:
        flags.append("heterogeneidade de ACF")
    return {"adf_p": adf_p, "kpss_p": kpss_p, "trend_hac_p": trend.pvalues[1],
            "trend_total": trend.params[1], "cusum_p_descriptive": cusum_p,
            "block_std_ratio": variance_ratio, "block_mean_range_sigma": mean_range,
            "block_acf1_range": acf_range, "flags": "; ".join(flags),
            "status": "exploratório" if flags else "sem alerta; premissas não comprovadas",
            "warnings": "; ".join(str(w.message) for w in caught)}, block
