"""Kantz nos quatro raios e diagnósticos do Wolf (G5; complementa F2d, D-027 e D-029).

A D-027 previa o Kantz com os raios dos quantis de 1%, 2%, 5% e 10% das distâncias, mas o lote
do F2d só calculou o de 2%. Aqui, os quatro, cada um com o número de pontos que tiveram ao
menos 5 vizinhos, na série observada e nas mesmas substitutas IAAFT do F2d (mesmas sementes):
199 nas séries das bacias e 39 na subamostra de D-024. O Wolf ganha os diagnósticos da série
observada (substituições pedidas e feitas, casos sem candidato e ângulo médio).

Chamado por `amazon-chaos descriptors checks <região>` (`scripts/hpc/estimadores_checagem.sbatch`).
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from amazon_chaos import regions
from amazon_chaos.nonlinear import estimators as E
from amazon_chaos.nonlinear.batch import NORMAL, _commit, _seed, load_cubes, windows
from amazon_chaos.nonlinear.lyapunov import KANTZ_QUANTILES, kantz_profile, wolf
from amazon_chaos.nonlinear.suite import embedding_parameters, spec_hash, surrogates
from amazon_chaos.nonlinear.surrogates import monte_carlo_pvalue
from amazon_chaos.regional import standardized_anomalies

RULES = {"version": 1, "kantz": {"quantiles": list(KANTZ_QUANTILES), "fit": [0, 5],
                                 "min_neighbors": 5},
         "wolf": E.RULES["wolf"], "basin_surrogates": 199, "subsample_surrogates": 39,
         "subsample": E.RULES["subsample"]}
KANTZ = [f"kantz_{100 * q:g}" for q in KANTZ_QUANTILES]


def checks_hash(spec) -> str:
    return spec_hash({"rules": RULES, "series": spec["series"], "embedding": spec["embedding"],
                      "surrogates": spec["surrogates"]})


def output_dir(cfg, spec) -> Path:
    return regions.processed_dir(cfg) / "estimadores_checagem" / checks_hash(spec)


def _profile(args):
    y, p = args
    return kantz_profile(y, p["m"], p["tau"], p["theiler"], fit=tuple(RULES["kantz"]["fit"]))


def series_checks(x: np.ndarray, params: dict, n_surrogates: int, seed: int, spec: dict,
                  pool=None, **labels) -> pd.DataFrame:
    """Uma linha por raio do Kantz (observado, nula, z, p bilateral e pontos usados), com os
    diagnósticos do Wolf da série observada repetidos em cada linha."""
    observed = _profile((x, params))
    diag = wolf(x, params["m"], params["tau"], params["theiler"], diagnostics=True,
                **RULES["wolf"])
    ys = [(y, params) for y in surrogates(x, n_surrogates, method=spec["surrogates"]["method"],
                                          seed=seed, max_iter=spec["surrogates"]["max_iter"])]
    nulls = list(pool.map(_profile, ys)) if pool else [_profile(a) for a in ys]
    rows = []
    for name in KANTZ:
        null = np.array([n[name] for n in nulls], dtype=float)
        ok = null[np.isfinite(null)]
        value = observed[name]
        sd = ok.std(ddof=1) if len(ok) > 1 else np.nan
        rows.append({**labels, **params, "descriptor": name, "observed": value,
                     "pontos": observed[f"{name}_pontos"],
                     "pontos_nulo": float(np.mean([n[f"{name}_pontos"] for n in nulls])),
                     "null_mean": ok.mean() if len(ok) else np.nan, "null_sd": sd,
                     "z": (value - ok.mean()) / sd if sd and np.isfinite(sd) else np.nan,
                     "pvalue": (monte_carlo_pvalue(value, ok, "two-sided")
                                if np.isfinite(value) and len(ok) else np.nan),
                     "n_null": len(ok), **{f"wolf_{k}": v for k, v in diag.items()}})
    return pd.DataFrame(rows)


def _cell_task(spec, cell_id, series):
    start, end = windows(spec)["2001_2024"]
    frames = []
    for var, raw in series.items():
        z, _ = standardized_anomalies(raw, NORMAL)
        x = z.loc[start:end].to_numpy(dtype=float)
        params = embedding_parameters(x, spec)
        frames.append(series_checks(x, params, RULES["subsample_surrogates"],
                                    _seed(spec, cell_id, var, "2001_2024"), spec,
                                    cell_id=cell_id, variable=var, window="2001_2024"))
    return pd.concat(frames, ignore_index=True)


def run(cfg, spec, cells: pd.DataFrame, *, workers=None, report=print) -> Path:
    """Séries da bacia (199 IAAFT) e subamostra (39 IAAFT), retomável por célula."""
    from amazon_chaos.nonlinear.basin_test import _seed as basin_seed
    from amazon_chaos.nonlinear.basin_test import basin_series
    from amazon_chaos.nonlinear.sensitivity import subsample

    if spec["status"] != "congelado":
        raise RuntimeError("O lote só roda com o pré-registro congelado (D-010)")
    out = output_dir(cfg, spec)
    parts = out / "celulas"
    parts.mkdir(parents=True, exist_ok=True)
    started = datetime.now(UTC)
    with ProcessPoolExecutor(workers or os.cpu_count()) as pool:
        if not (out / "bacia.parquet").exists():
            frames = []
            for var in ("t2m", "vpd"):
                x = basin_series(cfg, var, spec).to_numpy(dtype=float)
                frames.append(series_checks(
                    x, embedding_parameters(x, spec), RULES["basin_surrogates"],
                    basin_seed(spec, cfg["slug"], var, "IAAFT"), spec, pool=pool,
                    region=cfg["slug"], variable=var))
            pd.concat(frames, ignore_index=True).to_parquet(out / "bacia.parquet")
            report(f"🧭 Kantz e Wolf (G5) · {cfg['name']}: séries da bacia prontas")
        chosen = subsample(cells, RULES["subsample"]["n"], RULES["subsample"]["seed"])
        grid = regions.cells(cfg).set_index("cell_id").loc[chosen]
        todo = [c for c in grid.itertuples() if not (parts / f"{c.Index}.parquet").exists()]
        if todo:
            cubes = load_cubes(cfg, {"t2m": "t2m_c_mean", "vpd": "vpd_kpa_mean"})
            futures = {pool.submit(_cell_task, spec, c.Index, {
                v: cube.sel(latitude=c.latitude, longitude=c.longitude).to_series()
                for v, cube in cubes.items()}): c.Index for c in todo}
            for i, (future, cell_id) in enumerate(futures.items(), 1):
                future.result().to_parquet(parts / f"{cell_id}.parquet")
                if i % max(1, len(todo) // 5) == 0:
                    report(f"📊 Kantz e Wolf (G5) · {cfg['name']}: {i}/{len(todo)} células")
        pd.concat([pd.read_parquet(parts / f"{c}.parquet") for c in grid.index],
                  ignore_index=True).to_parquet(out / "subamostra.parquet")
    (out / "execucao.json").write_text(json.dumps({
        "region": cfg["slug"], "checks_hash": checks_hash(spec), "rules": RULES,
        "commit": _commit(), "started_utc": started.isoformat(timespec="seconds"),
        "finished_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }, indent=2, ensure_ascii=False, default=str))
    return out
