"""Sensibilidade do lote por célula numa subamostra estratificada (D-024).

Três variantes da regra do lote, só nos descritores primários e na janela 2001–2024, em
cerca de 60 células elegíveis por bacia, sorteadas por estrato (latitude × perda antecedente):

- `199 substitutas`: a regra, com 199 substitutas IAAFT em vez de 39 (p mínimo de 0,005,
  sem o piso de D-013);
- `τ = 2`: o atraso de imersão fixado em 2 dias, com m pelos falsos vizinhos nesse atraso
  e a janela de Theiler recalculada; a regra deu τ = 1 em quase todas as células;
- `ruído EDH`: a série diária somada a um ruído gaussiano do dobro da diferença RMS medida
  entre o Earth Data Hub e o CDS (D-007: 0,015 °C na temperatura média; para o VPD,
  0,005 kPa, propagado da umidade relativa), antes da anomalia, com 39 substitutas.

Cada variante é comparada, nas mesmas células, com o lote original.
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
from amazon_chaos.nonlinear.batch import NORMAL, VARIABLES, _commit, _seed, load_cubes, windows
from amazon_chaos.nonlinear.embedding import fnn_dimension
from amazon_chaos.nonlinear.suite import embedding_parameters, surrogate_suite
from amazon_chaos.regional import standardized_anomalies

NOISE_SD = {"t2m": 0.030, "vpd": 0.010}  # 2 × a diferença RMS diária EDH × CDS (D-007)
VARIANTS = ("199 substitutas", "τ = 2", "ruído EDH")
STRATA = 3  # terços de latitude × terços de perda antecedente


def output_dir(cfg) -> Path:
    return regions.processed_dir(cfg) / "sensibilidade"


def subsample(cells: pd.DataFrame, n: int = 60, seed: int = 20261023) -> list[str]:
    """Células elegíveis sorteadas em partes iguais por estrato de latitude × perturbação."""
    e = cells[cells.elegivel].copy()
    e["lat_q"] = pd.qcut(e.latitude.rank(method="first"), STRATA, labels=False)
    e["pert_q"] = pd.qcut(e.perda_antecedente.rank(method="first"), STRATA, labels=False)
    per = int(np.ceil(n / STRATA**2))
    picked = (e.groupby(["lat_q", "pert_q"], group_keys=False)
              .apply(lambda g: g.sample(min(per, len(g)), random_state=seed)))
    return sorted(picked.index)


def cell_task(spec: dict, cell_id: str, series: dict[str, pd.Series]) -> pd.DataFrame:
    primary = spec["families"]["primary"]
    start, end = next(iter(windows(spec).values()))
    rows = []
    for var, raw in series.items():
        labels = {"cell_id": cell_id, "variable": var, "window": "2001_2024"}
        z = standardized_anomalies(raw, NORMAL)[0].loc[start:end].to_numpy(dtype=float)
        base = embedding_parameters(z, spec)
        rules = spec["embedding"]
        tau2 = {"tau": 2}
        tau2["m"] = fnn_dimension(z, 2, rules["dimension"]["max_dimension"],
                                  rules["dimension"]["threshold"],
                                  theiler=max(rules["theiler"]["minimum"], 2))
        tau2["theiler"] = max(rules["theiler"]["minimum"], 2 * tau2["m"])
        rng = np.random.default_rng(_seed(spec, cell_id, var, "ruido"))
        noisy = raw + rng.normal(0, NOISE_SD[var], len(raw))
        zn = standardized_anomalies(noisy, NORMAL)[0].loc[start:end].to_numpy(dtype=float)
        seed = _seed(spec, cell_id, var, "2001_2024")  # a mesma semente do lote original
        runs = {"199 substitutas": (z, base, 199),
                "τ = 2": (z, tau2, None),
                "ruído EDH": (zn, base, None)}
        for variant, (x, params, n) in runs.items():
            result = surrogate_suite(x, spec, n_surrogates=n, seed=seed, names=primary,
                                     params=dict(params))
            rows.append(result.table(**labels, variant=variant))
    return pd.concat(rows, ignore_index=True)


def run(cfg, spec, cells: pd.DataFrame, *, n: int = 60, workers=None, report=print) -> Path:
    """Executa (ou retoma, por célula) a sensibilidade da região."""
    out = output_dir(cfg)
    (out / "celulas").mkdir(parents=True, exist_ok=True)
    chosen = subsample(cells, n)
    todo = [c for c in chosen if not (out / "celulas" / f"{c}.parquet").exists()]
    # ordem embaralhada: se o job parar no meio, as células prontas seguem estratificadas
    todo = list(np.random.default_rng(len(chosen)).permutation(todo))
    report(f"🔬 Sensibilidade · {cfg['name']}: {len(todo)} de {len(chosen)} células")
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
                    report(f"📊 Sensibilidade · {cfg['name']}: {k}/{len(todo)} células")
    table = pd.concat([pd.read_parquet(out / "celulas" / f"{c}.parquet") for c in chosen],
                      ignore_index=True)
    target = out / "sensibilidade.parquet"
    table.to_parquet(target)
    (out / "execucao.json").write_text(json.dumps({
        "region": cfg["slug"], "cells": len(chosen), "rows": len(table),
        "variants": list(VARIANTS), "noise_sd": NOISE_SD, "commit": _commit(),
        "finished_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }, indent=2, ensure_ascii=False))
    return target
