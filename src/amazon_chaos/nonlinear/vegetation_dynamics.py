"""Dinâmica da vegetação isolada e com a atmosfera (D-031, etapas 1 e 2).

Etapa 1: em cada célula da subamostra e para LAI e NDMI, os descritores do pré-registro de
8 dias (`configs/analysis/vegetation.yaml`), Wolf, Kantz e Cao e o S-map, contra 99
substitutas IAAFT que recebem o mesmo tratamento de lacunas da série observada.

Etapa 2: a atmosfera alinhada ao dia de observação de cada composição (VPD e temperatura do
ERA5, média dos 8 dias que terminam nele; chuva do CHIRPS acumulada em 32 e 96 dias), a
previsão de V(t+1) por três conjuntos de preditores, o CCM contra substitutas sazonais e
a dependência do estado no S-map conjunto.

Chamado por `amazon-chaos vegetation dynamics <região>`.
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from amazon_chaos import regions
from amazon_chaos.features import vegetation as V
from amazon_chaos.nonlinear import coupling as C
from amazon_chaos.nonlinear import estimators, smap
from amazon_chaos.nonlinear.batch import _commit, _seed
from amazon_chaos.nonlinear.suite import (
    descriptor_values,
    embedding_parameters,
    spec_hash,
    surrogates,
)
from amazon_chaos.nonlinear.surrogates import monte_carlo_pvalue

VARIABLES = ("lai", "ndmi")
ATMOSPHERE = ("vpd", "t2m", "chuva_32d", "chuva_96d")
FORCINGS = ("vpd", "chuva_32d", "chuva_96d")  # H e D da D-031
# versão 2 (emenda da D-031, 31/10): cobertura mínima de 5% dos pixels por composição; entram
# as células com até 35% de lacunas, e a leitura principal fica nas com até 20%
RULES = {"version": 2, "atmosphere_window_days": 8, "rain_windows_days": [32, 96],
         "ccm": {"lags": list(C.LAGS), "surrogates": 99, "samples": 30},
         "train_fraction": C.TRAIN_FRACTION, "min_valid": V.MIN_VALID, "max_missing": 0.35,
         "primary_max_missing": 0.2}


def full_grid(table: pd.DataFrame) -> pd.DataFrame:
    """Células × composições (todas, inclusive as vazias) × variáveis: as lacunas ficam como
    NaN no lugar certo, em vez de sumirem da série."""
    wide = table.pivot_table(index=["cell_id", "composicao"], columns="variavel",
                             values="valor", dropna=False)
    full = pd.MultiIndex.from_product([table.cell_id.unique(),
                                       np.sort(table.composicao.unique())],
                                      names=["cell_id", "composicao"])
    return wide.reindex(full)


def dynamics_hash(spec) -> str:
    return spec_hash({"rules": RULES, "spec": spec})


def series_path(cfg) -> Path:
    return regions.processed_dir(cfg) / "vegetacao" / "series.parquet"


def output_dir(cfg, spec) -> Path:
    return regions.processed_dir(cfg) / "vegetacao" / dynamics_hash(spec)


# ── etapa 1 ─────────────────────────────────────────────────────────────────


def _values(x, params, spec):
    out = descriptor_values(x, params, spec)
    extra = estimators.extra_values(x, params)
    return out | {k: extra[k] for k in estimators.ALTERNATIVE}



def isolated(x: np.ndarray, missing: np.ndarray, spec: dict, seed: int, **labels):
    """Uma linha por descritor (observado, nula, z, p) e o S-map, na série preenchida."""
    params = embedding_parameters(x, spec)
    observed = _values(x, params, spec)
    nulls = {k: [] for k in observed}
    for y in surrogates(x, spec["surrogates"]["per_cell"], method="IAAFT", seed=seed,
                        max_iter=spec["surrogates"]["max_iter"]):
        for k, v in _values(C.refill(y, missing), params, spec).items():
            nulls[k].append(v)
    alternatives = {k: d["alternative"] for k, d in spec["descriptors"].items()}
    alternatives |= estimators.ALTERNATIVE
    rows = []
    for k, value in observed.items():
        null = np.array(nulls[k], float)
        ok = null[np.isfinite(null)]
        sd = ok.std(ddof=1) if len(ok) > 1 else np.nan
        rows.append({**labels, **params, "descriptor": k, "observed": value,
                     "null_mean": ok.mean() if len(ok) else np.nan, "null_sd": sd,
                     "z": (value - ok.mean()) / sd if sd and np.isfinite(sd) else np.nan,
                     "pvalue": monte_carlo_pvalue(value, ok, alternatives[k])
                     if np.isfinite(value) and len(ok) else np.nan, "n_null": len(ok)})
    sm = smap.smap_series(x, params["m"], params["tau"], params["theiler"])
    sm = sm[sm.horizon == 1].iloc[0]
    rows.append({**labels, **params, "descriptor": "smap", "observed": sm.gain,
                 "pvalue": sm.pvalue, "theta": sm.theta})
    return pd.DataFrame(rows)


# ── etapa 2: atmosfera alinhada ao dia de observação ────────────────────────


def atmosphere(cfg, cells: pd.DataFrame, dates: pd.DataFrame) -> pd.DataFrame:
    """VPD e t2m (média dos 8 dias até o dia de observação) e chuva do CHIRPS acumulada em
    32 e 96 dias, por célula e composição. `dates`: cell_id, composicao, dia (Timestamp)."""
    from amazon_chaos.nonlinear.batch import load_cubes
    from amazon_chaos.nonlinear.precip import load_series

    cubes = load_cubes(cfg, {"t2m": "t2m_c_mean", "vpd": "vpd_kpa_mean"})
    rain = load_series(cfg, "precip_chirps")
    out = []
    for cell in cells.itertuples():
        daily = pd.DataFrame({v: cube.sel(latitude=cell.latitude, longitude=cell.longitude)
                              .to_series() for v, cube in cubes.items()})
        daily.index = pd.DatetimeIndex(daily.index).normalize()
        roll = daily.rolling(8, min_periods=6).mean()
        r = rain[cell.cell_id]
        acc = {f"chuva_{w}d": r.rolling(w, min_periods=int(0.8 * w)).sum() for w in (32, 96)}
        d = dates[dates.cell_id == cell.cell_id]
        when = pd.DatetimeIndex(d.dia)
        row = pd.DataFrame({"cell_id": cell.cell_id, "composicao": d.composicao.to_numpy(),
                            "vpd": roll.vpd.reindex(when).to_numpy(),
                            "t2m": roll.t2m.reindex(when).to_numpy(),
                            **{k: v.reindex(when).to_numpy() for k, v in acc.items()}})
        out.append(row)
    return pd.concat(out, ignore_index=True)


def coupled(series: dict[str, np.ndarray], target: str, spec: dict, seed: int, **labels):
    """Previsão por conjuntos de preditores, CCM e dependência do estado de uma célula."""
    params = embedding_parameters(series[target], spec)
    m, tau, w = params["m"], params["tau"], params["theiler"]
    fc = C.compare_forecasts(series, target, list(FORCINGS), m=m, tau=tau, theiler=w)
    rows = [fc.assign(**labels, analise="previsao")]
    ccm = []
    for forcing in FORCINGS:
        for direction, (lib, tgt) in {"atmosfera→vegetação": (target, forcing),
                                      "vegetação→atmosfera": (forcing, target)}.items():
            res = C.ccm_test(series[lib], series[tgt], E=m, tau=tau, theiler=w,
                             n_surrogates=RULES["ccm"]["surrogates"],
                             samples=RULES["ccm"]["samples"], seed=seed)
            ccm.append({**labels, "analise": "ccm", "forcante": forcing, "sentido": direction,
                        **res})
    theta = fc[(fc.preditores == "conjunto") & (fc.modelo == "smap")].theta.iloc[0]
    state = [{**labels, "analise": "estado", "forcante": f,
              "rho_estado": C.state_dependence(series, target, f, m=m, tau=tau, theta=theta)}
             for f in FORCINGS]
    return pd.concat(rows + [pd.DataFrame(ccm), pd.DataFrame(state)], ignore_index=True)


def cell_task(spec: dict, cell_id: str, frame: pd.DataFrame) -> pd.DataFrame | None:
    """As duas etapas de uma célula. `frame`: composições × (lai, ndmi, atmosfera)."""
    prepared, missing, ok = {}, {}, {}
    for v in (*VARIABLES, *ATMOSPHERE):
        x, miss, good = V.prepare(frame[v].to_numpy(), frame.index,
                                  max_missing=RULES["max_missing"])
        prepared[v], missing[v], ok[v] = x, miss, good
    out = []
    for v in VARIABLES:
        labels = {"cell_id": cell_id, "variable": v, "lacunas": float(missing[v].mean())}
        if not ok[v]:
            out.append(pd.DataFrame([{**labels, "descriptor": "excluida"}]))
            continue
        seed = _seed(spec, cell_id, v, "vegetacao")
        out.append(isolated(prepared[v], missing[v], spec, seed, **labels).assign(etapa=1))
        series = {v: prepared[v], **{a: prepared[a] for a in FORCINGS}}
        out.append(coupled(series, v, spec, seed, **labels).assign(etapa=2))
    return pd.concat(out, ignore_index=True)


def run(cfg, spec, *, workers=None, report=print) -> Path:
    """Executa (ou retoma, por célula) as etapas 1 e 2 na subamostra."""
    out = output_dir(cfg, spec)
    parts = out / "celulas"
    parts.mkdir(parents=True, exist_ok=True)
    table = V.with_coverage(pd.read_parquet(series_path(cfg)), RULES["min_valid"])
    wide = full_grid(table)
    days = table[table.variavel == "ndmi"][["cell_id", "composicao", "dia_obs"]].copy()
    comp = pd.to_datetime(days.composicao)
    fallback = comp + pd.Timedelta(days=4)
    day = pd.to_datetime(comp.dt.year.astype(str), format="%Y") + pd.to_timedelta(
        days.dia_obs - 1, unit="D")
    days["dia"] = day.where(days.dia_obs.notna() & (day >= comp - pd.Timedelta(days=1)),
                            fallback)
    cells = regions.cells(cfg).set_index("cell_id").loc[table.cell_id.unique()].reset_index()
    atm = atmosphere(cfg, cells, days).set_index(["cell_id", "composicao"])
    wide = wide.join(atm)
    todo = [c for c in cells.cell_id if not (parts / f"{c}.parquet").exists()]
    report(f"🌳 Vegetação (D-031) · {cfg['name']}: {len(todo)} de {len(cells)} células")
    started = datetime.now(UTC)
    with ProcessPoolExecutor(workers or os.cpu_count()) as pool:
        futures = {pool.submit(cell_task, spec, c,
                               wide.loc[c].sort_index().set_axis(
                                   pd.DatetimeIndex(wide.loc[c].sort_index().index))): c
                   for c in todo}
        for i, future in enumerate(as_completed(futures), 1):
            future.result().to_parquet(parts / f"{futures[future]}.parquet")
            if i % max(1, len(todo) // 5) == 0:
                report(f"📊 Vegetação · {cfg['name']}: {i}/{len(todo)} células")
    result = pd.concat([pd.read_parquet(p) for p in sorted(parts.glob("*.parquet"))],
                       ignore_index=True)
    result.to_parquet(out / "resultados.parquet")
    (out / "execucao.json").write_text(json.dumps({
        "region": cfg["slug"], "hash": dynamics_hash(spec), "rules": RULES,
        "commit": _commit(), "started_utc": started.isoformat(timespec="seconds"),
        "finished_utc": datetime.now(UTC).isoformat(timespec="seconds")}, indent=2,
        default=str))
    return out
