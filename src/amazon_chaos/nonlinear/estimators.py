"""Wolf, Kantz e Cao contra substitutas, ao lado de Rosenstein (F2d e F2h, D-027; comparativo).

Os três usam o (τ, m, w) da regra do pré-registro, escolhido na série observada e mantido
nas substitutas, como no lote. Wolf e Kantz são testados como o Lyapunov de Rosenstein
(bilateral); o afastamento D_E2 = max |1 − E2| de Cao, unilateral (maior que nas
substitutas indica dependência determinística). A dimensão de saturação de Cao só é
registrada na série observada.

Onde: as séries das bacias (199 IAAFT, as mesmas sementes de D-016) e a subamostra de D-024
(39 IAAFT, as mesmas sementes do lote), aqui; os controles do gate e as nulas realistas, em
`nonlinear/realistic.py`.
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
from amazon_chaos.nonlinear.batch import NORMAL, _commit, _seed, load_cubes, windows
from amazon_chaos.nonlinear.embedding import cao, cao_indices
from amazon_chaos.nonlinear.lyapunov import kantz, wolf
from amazon_chaos.nonlinear.suite import embedding_parameters, spec_hash, surrogates
from amazon_chaos.nonlinear.surrogates import monte_carlo_pvalue
from amazon_chaos.regional import standardized_anomalies

ALTERNATIVE = {"wolf": "two-sided", "kantz": "two-sided", "cao_de2": "greater"}
RULES = {"version": 1, "wolf": {"evolve": 3, "max_scale": 0.10, "min_scale": 0.001,
                                "angle": 0.3, "max_angle": 1.2},
         "kantz": {"quantile": 0.02, "fit": [0, 5]},
         "cao": {"max_dimension": 10, "level": 0.9, "change": 0.05},
         "alternative": ALTERNATIVE, "basin_surrogates": 199, "subsample_surrogates": 39,
         "subsample": {"n": 60, "seed": 20261023}}


def extra_values(x: np.ndarray, params: dict) -> dict[str, float]:
    """λ de Wolf e de Kantz, dimensão de saturação e D_E2 de Cao com (τ, m, w) fixos."""
    tau, m, w = params["tau"], params["m"], params["theiler"]
    e1, e2 = cao(x, tau, RULES["cao"]["max_dimension"], theiler=w)
    return {"wolf": wolf(x, m, tau, w, **RULES["wolf"]),
            "kantz": kantz(x, m, tau, w, quantile=RULES["kantz"]["quantile"],
                           fit=tuple(RULES["kantz"]["fit"])),
            **cao_indices(e1, e2, RULES["cao"]["level"], RULES["cao"]["change"])}


def _null_values(args):
    y, params = args
    out = extra_values(y, params)
    return {k: out[k] for k in ALTERNATIVE}


def extra_suite(x: np.ndarray, params: dict, n_surrogates: int, seed: int, spec: dict,
                pool=None, **labels) -> pd.DataFrame:
    """Uma linha por estatística: observado, nula, z e p de Monte Carlo."""
    observed = extra_values(x, params)
    ys = [(y, params) for y in surrogates(x, n_surrogates, method=spec["surrogates"]["method"],
                                          seed=seed, max_iter=spec["surrogates"]["max_iter"])]
    nulls = list(pool.map(_null_values, ys)) if pool else [_null_values(a) for a in ys]
    rows = []
    for name, alternative in ALTERNATIVE.items():
        null = np.array([n[name] for n in nulls], dtype=float)
        ok = null[np.isfinite(null)]
        value = observed[name]
        sd = ok.std(ddof=1) if len(ok) > 1 else np.nan
        p = (monte_carlo_pvalue(value, ok, alternative)
             if np.isfinite(value) and len(ok) else np.nan)
        rows.append({**labels, **params, "descriptor": name, "observed": value,
                     "null_mean": ok.mean() if len(ok) else np.nan, "null_sd": sd,
                     "z": (value - ok.mean()) / sd if sd and np.isfinite(sd) else np.nan,
                     "pvalue": p, "n_null": len(ok), "cao_m": observed["cao_m"]})
    return pd.DataFrame(rows)


# ── séries das bacias e subamostra ──────────────────────────────────────────


def estimators_hash(spec) -> str:
    return spec_hash({"rules": RULES, "series": spec["series"], "embedding": spec["embedding"],
                      "surrogates": spec["surrogates"]})


def output_dir(cfg, spec) -> Path:
    return regions.processed_dir(cfg) / "estimadores" / estimators_hash(spec)


def _cell_task(spec, cell_id, series):
    start, end = windows(spec)["2001_2024"]
    frames = []
    for var, raw in series.items():
        z, _ = standardized_anomalies(raw, NORMAL)
        x = z.loc[start:end].to_numpy(dtype=float)
        params = embedding_parameters(x, spec)
        frames.append(extra_suite(x, params, RULES["subsample_surrogates"],
                                  _seed(spec, cell_id, var, "2001_2024"), spec,
                                  cell_id=cell_id, variable=var, window="2001_2024"))
    return pd.concat(frames, ignore_index=True)


def run(cfg, spec, cells: pd.DataFrame, *, workers=None, report=print) -> Path:
    """Séries da bacia (199 IAAFT) e subamostra (39 IAAFT), retomável por parte."""
    from amazon_chaos.nonlinear.basin_test import _seed as basin_seed
    from amazon_chaos.nonlinear.basin_test import basin_series
    from amazon_chaos.nonlinear.sensitivity import subsample

    if spec["status"] != "congelado":
        raise RuntimeError("O lote só roda com o pré-registro congelado (D-010)")
    out = output_dir(cfg, spec)
    out.mkdir(parents=True, exist_ok=True)
    workers = workers or os.cpu_count()
    started = datetime.now(UTC)
    with ProcessPoolExecutor(workers) as pool:
        if not (out / "bacia.parquet").exists():
            frames = []
            for var in ("t2m", "vpd"):
                x = basin_series(cfg, var, spec).to_numpy(dtype=float)
                params = embedding_parameters(x, spec)
                frames.append(extra_suite(
                    x, params, RULES["basin_surrogates"],
                    basin_seed(spec, cfg["slug"], var, "IAAFT"), spec, pool=pool,
                    region=cfg["slug"], variable=var))
                report(f"🧭 Wolf, Kantz e Cao · {cfg['name']}: série da bacia, {var} pronta")
            pd.concat(frames, ignore_index=True).to_parquet(out / "bacia.parquet")
        if not (out / "subamostra.parquet").exists():
            chosen = subsample(cells, RULES["subsample"]["n"], RULES["subsample"]["seed"])
            grid = regions.cells(cfg).set_index("cell_id").loc[chosen]
            cubes = load_cubes(cfg, {"t2m": "t2m_c_mean", "vpd": "vpd_kpa_mean"})
            futures = []
            for cell in grid.itertuples():
                series = {v: cube.sel(latitude=cell.latitude, longitude=cell.longitude)
                          .to_series() for v, cube in cubes.items()}
                futures.append(pool.submit(_cell_task, spec, cell.Index, series))
            frames = []
            for i, future in enumerate(futures, 1):
                frames.append(future.result())
                if i % max(1, len(futures) // 5) == 0:
                    report(f"📊 Wolf, Kantz e Cao · {cfg['name']}: {i}/{len(futures)} células "
                           "da subamostra")
            pd.concat(frames, ignore_index=True).to_parquet(out / "subamostra.parquet")
    (out / "execucao.json").write_text(json.dumps({
        "region": cfg["slug"], "estimators_hash": estimators_hash(spec), "rules": RULES,
        "commit": _commit(), "started_utc": started.isoformat(timespec="seconds"),
        "finished_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }, indent=2, ensure_ascii=False))
    return out
