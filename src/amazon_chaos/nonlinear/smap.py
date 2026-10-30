"""S-map (Sugihara, 1994): ganho da previsão local sobre a linear (F2g, D-027; comparativo).

Para cada ponto a prever, uma regressão linear dos valores futuros sobre o vetor de atrasos,
com pesos exp(−θ d / d̄) que favorecem os estados parecidos com o atual. Com θ = 0 todos os
pesos são iguais e o S-map é um AR(m) linear; se a dinâmica depende do estado, algum θ > 0
prevê melhor. O índice G = 1 − RMSE(θ escolhido)/RMSE(θ = 0) não depende da nula IAAFT.

Treino nos primeiros 60% da série e teste nos últimos 40%; θ é escolhido só no treino,
deixando um de fora com exclusão de Theiler; nenhum alvo do teste entra na biblioteca. A
significância é o teste de Diebold–Mariano unilateral (variância HAC com h − 1 defasagens).
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from amazon_chaos import regions
from amazon_chaos.nonlinear.batch import NORMAL, _commit, load_cubes, windows
from amazon_chaos.nonlinear.embedding import _finite, delay_embedding
from amazon_chaos.nonlinear.suite import embedding_parameters, spec_hash
from amazon_chaos.regional import standardized_anomalies

RULES = {"version": 1, "thetas": [0, 0.25, 0.5, 1, 2, 4, 8], "train_fraction": 0.6,
         "horizons": [1, 3, 7], "selection": "loo_theiler", "test": "diebold_mariano",
         "variables": {"t2m": "t2m_c_mean", "vpd": "vpd_kpa_mean"}, "window": "2001_2024"}


def _weighted_fit(lib_x, lib_y, query, theta, mask=None, chunk=128):
    """Previsões do S-map para cada linha de `query`; `mask` zera pesos (Theiler)."""
    n_lib, p = lib_x.shape
    design = np.column_stack([np.ones(n_lib), lib_x])
    out = np.empty((len(query), lib_y.shape[1]))
    for start in range(0, len(query), chunk):
        q = query[start:start + chunk]
        d = np.sqrt(((q[:, None, :] - lib_x[None, :, :]) ** 2).sum(-1))
        ok = np.ones_like(d, dtype=bool) if mask is None else mask[start:start + chunk]
        mean = np.where(ok, d, 0).sum(1) / ok.sum(1)
        w = np.where(ok, np.exp(-theta * d / np.where(mean > 0, mean, 1)[:, None]), 0.0)
        weighted = design[None, :, :] * w[:, :, None]
        a = np.einsum("qnp,nr->qpr", weighted, design)
        b = np.einsum("qnp,nh->qph", weighted, lib_y)
        a += 1e-8 * np.eye(p + 1)[None]
        beta = np.linalg.solve(a, b)
        out[start:start + chunk] = np.einsum("qp,qph->qh",
                                             np.column_stack([np.ones(len(q)), q]), beta)
    return out


def diebold_mariano(e_base, e_model, horizon: int) -> tuple[float, float]:
    """DM unilateral (o modelo erra menos que a base), perda quadrática, HAC com h − 1."""
    d = np.asarray(e_base) ** 2 - np.asarray(e_model) ** 2
    t = len(d)
    centered = d - d.mean()
    var = centered @ centered / t
    for lag in range(1, horizon):
        var += 2 * (centered[lag:] @ centered[:-lag]) / t
    if var <= 0:
        var = centered @ centered / t
    if var <= 0:
        return np.nan, 1.0
    stat = d.mean() / np.sqrt(var / t)
    return float(stat), float(norm.sf(stat))


def smap_series(series, dimension: int, delay: int, theiler: int,
                rules: dict = RULES) -> pd.DataFrame:
    """Uma linha por horizonte: θ escolhido, RMSE no teste, referências, G e DM."""
    x = _finite(series)
    horizons = rules["horizons"]
    h_max = max(horizons)
    vectors = delay_embedding(x, dimension, delay)
    now = np.arange(len(vectors)) + (dimension - 1) * delay  # tempo do valor mais recente
    valid = now + h_max < len(x)
    vectors, now = vectors[valid], now[valid]
    targets = np.column_stack([x[now + h] for h in horizons])
    split = int(rules["train_fraction"] * len(x))
    train = now + h_max < split
    test = now >= split
    lib_x, lib_y, lib_t = vectors[train], targets[train], now[train]
    near = np.abs(lib_t[:, None] - lib_t[None, :]) <= theiler
    loo = {}
    for theta in rules["thetas"]:
        pred = _weighted_fit(lib_x, lib_y, lib_x, theta, mask=~near)
        loo[theta] = np.sqrt(((pred - lib_y) ** 2).mean(axis=0))
    rows = []
    q_x, q_y = vectors[test], targets[test]
    base = q_y - _weighted_fit(lib_x, lib_y, q_x, 0.0)
    cache = {0.0: base}
    persistence = q_y - x[now[test]][:, None]
    for k, h in enumerate(horizons):
        scores = np.array([loo[t][k] for t in rules["thetas"]])
        theta = float(rules["thetas"][int(np.flatnonzero(scores <= scores.min())[0])])
        if theta not in cache:
            cache[theta] = q_y - _weighted_fit(lib_x, lib_y, q_x, theta)
        err, err0 = cache[theta][:, k], base[:, k]
        rmse, rmse0 = float(np.sqrt(np.mean(err**2))), float(np.sqrt(np.mean(err0**2)))
        stat, p = diebold_mariano(err0, err, h) if theta > 0 else (np.nan, 1.0)
        rows.append({"horizon": h, "theta": theta, "rmse": rmse, "rmse_linear": rmse0,
                     "rmse_persistence": float(np.sqrt(np.mean(persistence[:, k] ** 2))),
                     "rmse_climatology": float(np.sqrt(np.mean(q_y[:, k] ** 2))),
                     "gain": 1 - rmse / rmse0, "dm": stat, "pvalue": p,
                     "loo_rmse": json.dumps(dict(zip(map(str, rules["thetas"]),
                                                     scores.round(5).tolist(), strict=True)))})
    return pd.DataFrame(rows)


# ── lote em todas as células ────────────────────────────────────────────────


def smap_hash(spec) -> str:
    return spec_hash({"rules": RULES, "series": spec["series"],
                      "embedding": spec["embedding"]})


def output_dir(cfg, spec) -> Path:
    return regions.processed_dir(cfg) / "smap" / smap_hash(spec)


def cell_task(spec: dict, cell_id: str, series: dict[str, pd.Series]) -> pd.DataFrame:
    start, end = windows(spec)[RULES["window"]]
    rows = []
    for var, raw in series.items():
        z, _ = standardized_anomalies(raw, NORMAL)
        x = z.loc[start:end].to_numpy(dtype=float)
        labels = {"cell_id": cell_id, "variable": var, "window": RULES["window"]}
        try:
            params = embedding_parameters(x, spec)
            rows.append(smap_series(x, params["m"], params["tau"], params["theiler"])
                        .assign(**labels, **params))
        except (ValueError, np.linalg.LinAlgError) as error:
            rows.append(pd.DataFrame([{**labels, "horizon": np.nan, "error": str(error)}]))
    return pd.concat(rows, ignore_index=True)


def run(cfg, spec, *, workers=None, block=25, report=print, limit=None) -> Path:
    """Executa (ou retoma, por bloco) o S-map nas células e consolida `smap.parquet`."""
    if spec["status"] != "congelado":
        raise RuntimeError("O lote só roda com o pré-registro congelado (D-010)")
    out = output_dir(cfg, spec)
    out.mkdir(parents=True, exist_ok=True)
    grid = regions.cells(cfg)[["cell_id", "latitude", "longitude"]].iloc[:limit]
    blocks = [grid.iloc[i:i + block] for i in range(0, len(grid), block)]
    todo = [k for k in range(len(blocks)) if not (out / f"bloco_{k:04d}.parquet").exists()]
    report(f"🔭 S-map (F2g) · {cfg['name']}: {len(todo)} de {len(blocks)} blocos")
    if todo:
        cubes = load_cubes(cfg, RULES["variables"])
        started, done = datetime.now(UTC), 0
        with ProcessPoolExecutor(workers or os.cpu_count()) as pool:
            futures = {}
            for k in todo:
                for cell in blocks[k].itertuples():
                    series = {v: cube.sel(latitude=cell.latitude, longitude=cell.longitude)
                              .to_series() for v, cube in cubes.items()}
                    futures[pool.submit(cell_task, spec, cell.cell_id, series)] = k
            parts: dict[int, list] = {k: [] for k in todo}
            pending = {k: len(blocks[k]) for k in todo}
            for future in as_completed(futures):
                k = futures[future]
                parts[k].append(future.result())
                pending[k] -= 1
                if pending[k] == 0:
                    pd.concat(parts.pop(k), ignore_index=True).to_parquet(
                        out / f"bloco_{k:04d}.parquet")
                    done += 1
                    if done % max(1, len(todo) // 10) == 0 or done == len(todo):
                        hours = (datetime.now(UTC) - started).total_seconds() / 3600
                        eta = hours / done * (len(todo) - done)
                        report(f"📊 S-map (F2g) · {cfg['name']}: {done}/{len(todo)} blocos "
                               f"({100 * done / len(todo):.0f}%) · {hours:.1f} h · "
                               f"faltam ≈ {eta:.1f} h")
    table = pd.concat([pd.read_parquet(p) for p in sorted(out.glob("bloco_*.parquet"))],
                      ignore_index=True)
    target = out / "smap.parquet"
    table.to_parquet(target)
    errors = int(table["error"].notna().sum()) if "error" in table else 0
    (out / "execucao.json").write_text(json.dumps({
        "region": cfg["slug"], "cells": len(grid), "rows": len(table), "errors": errors,
        "smap_hash": smap_hash(spec), "rules": RULES, "commit": _commit(),
        "finished_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }, indent=2, ensure_ascii=False))
    return target


def load(cfg, spec, alpha: float = 0.05) -> pd.DataFrame:
    """Resultado com q de BH sobre as células, por variável × horizonte."""
    from amazon_chaos.nonlinear.results import benjamini_hochberg

    table = pd.read_parquet(output_dir(cfg, spec) / "smap.parquet")
    table = table[table.horizon.notna()].copy()
    table["q"] = table.groupby(["variable", "horizon"]).pvalue.transform(
        lambda s: benjamini_hochberg(s.to_numpy()))
    table["rejects"] = table.q <= alpha
    return table
