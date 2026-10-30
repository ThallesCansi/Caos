"""Atrasos de imersão e atrasos ordinais na subamostra de D-024 (F2a, D-027; comparativo).

A regra do pré-registro (o menor entre o 1º mínimo local da AMI e o 1º τ com AMI abaixo de
AMI(0)/e) deu τ = 1 em quase todas as células, e isso vem do limiar 1/e, não da dinâmica.
Aqui os descritores primários são recalculados, nas mesmas células e com as mesmas
substitutas do lote (mesma semente), variando um parâmetro de cada vez:

- τ ∈ {1, 2, 3, 5, 7} na RQA·DET e no erro de previsão, com m pelos falsos vizinhos em
  cada τ e w = max(10, τ·m); mais o 1º mínimo local da AMI, sem a regra 1/e, quando existe;
- o atraso ordinal L ∈ {1, 2, 4, 7} na entropia e na complexidade (ordem 5: 4L dias).

τ = 1 e L = 1 reproduzem o lote nas células em que a regra deu τ = 1.
"""

from __future__ import annotations

import copy
import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from amazon_chaos import regions
from amazon_chaos.nonlinear.batch import NORMAL, VARIABLES, _commit, _seed, load_cubes, windows
from amazon_chaos.nonlinear.embedding import ami_first_minimum, fnn_dimension
from amazon_chaos.nonlinear.sensitivity import against_batch, subsample
from amazon_chaos.nonlinear.suite import spec_hash, surrogate_suite
from amazon_chaos.regional import standardized_anomalies

RULES = {"version": 1, "delays": [1, 2, 3, 5, 7], "ordinal_delays": [1, 2, 4, 7],
         "ami_minimum": True, "embedding_descriptors": ["rqa_det", "prediction"],
         "ordinal_descriptors": ["pe_entropy", "pe_complexity"],
         "subsample": {"n": 60, "seed": 20261023}}


def delays_hash(spec) -> str:
    return spec_hash({"rules": RULES, "series": spec["series"], "embedding": spec["embedding"],
                      "descriptors": spec["descriptors"], "surrogates": spec["surrogates"]})


def output_dir(cfg, spec) -> Path:
    return regions.processed_dir(cfg) / "atrasos" / delays_hash(spec)


def params_for(z: np.ndarray, tau: int, spec: dict) -> dict:
    """(τ, m, w) com τ fixo: m pelos falsos vizinhos nesse τ, como na regra do pré-registro."""
    rules = spec["embedding"]
    minimum = rules["theiler"]["minimum"]
    m = fnn_dimension(z, tau, rules["dimension"]["max_dimension"],
                      rules["dimension"]["threshold"], theiler=max(minimum, tau))
    return {"tau": tau, "m": m, "theiler": max(minimum, tau * m)}


def cell_task(spec: dict, cell_id: str, series: dict[str, pd.Series]) -> pd.DataFrame:
    window, (start, end) = next(iter(windows(spec).items()))
    rows = []
    for var, raw in series.items():
        z = standardized_anomalies(raw, NORMAL)[0].loc[start:end].to_numpy(dtype=float)
        seed = _seed(spec, cell_id, var, window)  # as mesmas substitutas do lote
        ami_min = ami_first_minimum(z, spec["embedding"]["delay"]["max_lag"])
        labels = {"cell_id": cell_id, "variable": var, "window": window,
                  "ami_minimo": ami_min if ami_min is not None else np.nan}
        taus = [(f"τ = {t}", t) for t in RULES["delays"]]
        if ami_min is not None:
            taus.append(("τ = mínimo da AMI", ami_min))
        for variant, tau in taus:
            result = surrogate_suite(z, spec, seed=seed, params=params_for(z, tau, spec),
                                     names=RULES["embedding_descriptors"])
            rows.append(result.table(**labels, variant=variant, grade="τ", valor=tau))
        for delay in RULES["ordinal_delays"]:
            local = copy.deepcopy(spec)
            for name in RULES["ordinal_descriptors"]:
                local["descriptors"][name]["delay"] = delay
            result = surrogate_suite(z, local, seed=seed, params={"tau": 1, "m": 2, "theiler": 0},
                                     names=RULES["ordinal_descriptors"])
            rows.append(result.table(**labels, variant=f"atraso ordinal {delay}",
                                     grade="atraso ordinal", valor=delay))
    return pd.concat(rows, ignore_index=True)


def run(cfg, spec, cells: pd.DataFrame, *, workers=None, report=print) -> Path:
    """Executa (ou retoma, por célula) a grade de atrasos na subamostra da região."""
    out = output_dir(cfg, spec)
    (out / "celulas").mkdir(parents=True, exist_ok=True)
    chosen = subsample(cells, RULES["subsample"]["n"], RULES["subsample"]["seed"])
    todo = [c for c in chosen if not (out / "celulas" / f"{c}.parquet").exists()]
    todo = list(np.random.default_rng(len(chosen)).permutation(todo))
    report(f"⏱️ Atrasos (F2a) · {cfg['name']}: {len(todo)} de {len(chosen)} células")
    if todo:
        cubes = load_cubes(cfg, VARIABLES)
        where = regions.cells(cfg).set_index("cell_id")
        with ProcessPoolExecutor(workers or os.cpu_count()) as pool:
            futures = {}
            for c in todo:
                lat, lon = where.loc[c, ["latitude", "longitude"]]
                series = {v: cube.sel(latitude=lat, longitude=lon).to_series()
                          for v, cube in cubes.items()}
                futures[pool.submit(cell_task, spec, c, series)] = c
            for k, future in enumerate(as_completed(futures), 1):
                future.result().to_parquet(out / "celulas" / f"{futures[future]}.parquet")
                if k % max(1, len(todo) // 5) == 0:
                    report(f"📊 Atrasos (F2a) · {cfg['name']}: {k}/{len(todo)} células")
    table = pd.concat([pd.read_parquet(out / "celulas" / f"{c}.parquet") for c in chosen],
                      ignore_index=True)
    target = out / "atrasos.parquet"
    table.to_parquet(target)
    (out / "execucao.json").write_text(json.dumps({
        "region": cfg["slug"], "cells": len(chosen), "rows": len(table), "rules": RULES,
        "delays_hash": delays_hash(spec), "commit": _commit(),
        "finished_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }, indent=2, ensure_ascii=False))
    return target


def compare(cfg, spec, cells: pd.DataFrame) -> pd.DataFrame:
    """Cada ponto da grade ao lado do lote original, nas mesmas células (caderno 07)."""
    table = pd.read_parquet(output_dir(cfg, spec) / "atrasos.parquet")
    return against_batch(cfg, spec, cells, table)
