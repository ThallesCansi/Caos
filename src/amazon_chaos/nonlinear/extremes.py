"""Mínima, máxima e amplitude térmica diárias por célula (F2b, D-027; comparativo).

As três vêm das 24 amostras horárias de cada dia local (`t2m_c_min`, `t2m_c_max`,
`t2m_c_range`, já nos `daily_*.nc`). Cada uma vira anomalia padronizada própria (normal
1991–2020), como as variáveis primárias. Em todas as células e nas três janelas, a
entropia e a complexidade ordinais contra 39 substitutas IAAFT, no molde do lote da chuva
(`nonlinear/precip.py`); na subamostra de D-024, na janela completa, também RQA·DET e erro
de previsão, com (τ, m, w) pela regra. O ERA5 tem vegetação fixa (D-011): um resultado
nulo é o esperado, e é informativo.
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
from amazon_chaos.nonlinear.batch import NORMAL, _commit, _seed, load_cubes, windows
from amazon_chaos.nonlinear.sensitivity import subsample
from amazon_chaos.nonlinear.suite import spec_hash, surrogate_suite
from amazon_chaos.regional import standardized_anomalies

VARIABLES = {"tmin": "t2m_c_min", "tmax": "t2m_c_max", "amplitude": "t2m_c_range"}
ORDINAL = ["pe_entropy", "pe_complexity"]
RULES = {"version": 1, "variables": VARIABLES, "transform": "standardized_anomaly",
         "ordinal": ORDINAL, "subsample_only": ["rqa_det", "prediction"],
         "subsample": {"n": 60, "seed": 20261023}, "seed_label": "extremos"}


def extremes_hash(spec) -> str:
    return spec_hash({"rules": RULES, "series": spec["series"], "embedding": spec["embedding"],
                      "descriptors": spec["descriptors"], "surrogates": spec["surrogates"]})


def output_dir(cfg, spec) -> Path:
    return regions.processed_dir(cfg) / "descritores_extremos" / extremes_hash(spec)


def cell_task(spec: dict, cell_id: str, series: dict[str, pd.Series],
              full: bool = False) -> pd.DataFrame:
    """Ordinais nas três janelas; com `full`, os quatro primários na janela completa."""
    rows = []
    first = next(iter(windows(spec)))
    for var, raw in series.items():
        z, _ = standardized_anomalies(raw, NORMAL)
        for window, (start, end) in windows(spec).items():
            x = z.loc[start:end].to_numpy(dtype=float)
            labels = {"cell_id": cell_id, "variable": var, "window": window, "n": len(x)}
            if not np.isfinite(x).all():
                rows.append(pd.DataFrame([{**labels, "descriptor": "erro",
                                           "error": "lacunas na série"}]))
                continue
            names = ORDINAL + (RULES["subsample_only"] if full and window == first else [])
            try:
                result = surrogate_suite(x, spec, names=names, seed=_seed(
                    spec, cell_id, var, window, RULES["seed_label"]))
                rows.append(result.table(**labels, kind="teste"))
            except ValueError as error:
                rows.append(pd.DataFrame([{**labels, "descriptor": "erro",
                                           "error": str(error)}]))
    return pd.concat(rows, ignore_index=True)


def run(cfg, spec, cells: pd.DataFrame, *, workers=None, block=25, report=print,
        limit=None) -> Path:
    """Executa (ou retoma, por bloco) o lote das extremas e consolida `descritores.parquet`."""
    if spec["status"] != "congelado":
        raise RuntimeError("O lote só roda com o pré-registro congelado (D-010)")
    out = output_dir(cfg, spec)
    out.mkdir(parents=True, exist_ok=True)
    grid = regions.cells(cfg)[["cell_id", "latitude", "longitude"]].iloc[:limit]
    chosen = set(subsample(cells, RULES["subsample"]["n"], RULES["subsample"]["seed"]))
    blocks = [grid.iloc[i:i + block] for i in range(0, len(grid), block)]
    todo = [k for k in range(len(blocks)) if not (out / f"bloco_{k:04d}.parquet").exists()]
    report(f"🌡️ Mínima, máxima e amplitude (F2b) · {cfg['name']}: {len(todo)} de "
           f"{len(blocks)} blocos")
    if todo:
        cubes = load_cubes(cfg, VARIABLES)
        started, done = datetime.now(UTC), 0
        with ProcessPoolExecutor(workers or os.cpu_count()) as pool:
            futures = {}
            for k in todo:
                for cell in blocks[k].itertuples():
                    series = {v: cube.sel(latitude=cell.latitude, longitude=cell.longitude)
                              .to_series() for v, cube in cubes.items()}
                    futures[pool.submit(cell_task, spec, cell.cell_id, series,
                                        cell.cell_id in chosen)] = k
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
                        report(f"📊 Extremas (F2b) · {cfg['name']}: {done}/{len(todo)} "
                               f"blocos ({100 * done / len(todo):.0f}%) · {hours:.1f} h · "
                               f"faltam ≈ {eta:.1f} h")
    table = pd.concat([pd.read_parquet(p) for p in sorted(out.glob("bloco_*.parquet"))],
                      ignore_index=True)
    target = out / "descritores.parquet"
    table.to_parquet(target)
    (out / "execucao.json").write_text(json.dumps({
        "region": cfg["slug"], "cells": len(grid), "subsample": len(chosen),
        "rows": len(table), "errors": int((table.descriptor == "erro").sum()),
        "extremes_hash": extremes_hash(spec), "rules": RULES, "commit": _commit(),
        "finished_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }, indent=2, ensure_ascii=False))
    return target


# ── leitura (cadernos 07 e 08) ──────────────────────────────────────────────


def load(cfg, spec) -> pd.DataFrame:
    """Linhas do lote com q de BH na família exploratória (os dois ordinais), por variável ×
    janela; os primários da subamostra ficam sem q (lidos pela fração com p ≤ 0,05)."""
    from amazon_chaos.nonlinear.results import TOLERANCE, benjamini_hochberg

    table = pd.read_parquet(output_dir(cfg, spec) / "descritores.parquet")
    ordinal = (table.kind == "teste") & table.descriptor.isin(ORDINAL)
    table.loc[ordinal, "q"] = table[ordinal].groupby(["variable", "window"]).pvalue.transform(
        lambda s: benjamini_hochberg(s.to_numpy()))
    table["rejects"] = table.q <= spec["surrogates"]["alpha"] + TOLERANCE
    return table


def cell_table(cfg, spec) -> pd.DataFrame:
    """Tabela do caderno 08 com z, valor observado, média nula, excesso e mudança entre as
    metades de cada descritor das extremas."""
    from amazon_chaos import gradient as G

    table = G.cell_table(cfg, spec)
    tests = load(cfg, spec)
    tests = tests[tests.kind == "teste"].assign(excess=lambda t: t.observed - t.null_mean)
    full = tests[tests.window == "2001_2024"]
    for column, prefix in [("z", "z"), ("observed", "obs"), ("null_mean", "nulo"),
                           ("excess", "excesso")]:
        wide = full.pivot_table(index="cell_id", columns=["variable", "descriptor"],
                                values=column)
        wide.columns = [f"{prefix}_{v}_{d}" for v, d in wide.columns]
        table = table.join(wide)
    halves = tests[tests.window != "2001_2024"].pivot_table(
        index="cell_id", columns=["variable", "descriptor", "window"], values="observed")
    for var in VARIABLES:
        for d in ORDINAL:
            table[f"delta_{var}_{d}"] = (halves[(var, d, "2013_2024")]
                                         - halves[(var, d, "2001_2012")])
    return table
