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
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests

from amazon_chaos import regions
from amazon_chaos.nonlinear.batch import NORMAL
from amazon_chaos.nonlinear.suite import batch_hash, surrogate_suite
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
