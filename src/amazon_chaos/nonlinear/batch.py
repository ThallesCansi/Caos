"""Lote por célula: descritores pré-registrados contra substitutas em cada célula ERA5.

Para cada célula, variável primária (t2m, VPD) e janela (2001–2024, 2001–2012, 2013–2024):
anomalia padronizada (regional.standardized_anomalies, normal 1991–2020), (τ, m, w) pelas
regras, `suite.surrogate_suite` com todos os descritores e 39 substitutas IAAFT, EWS na
janela completa e a grade de sensibilidade (τ·{0,5; 2}, m ± 1, sem substitutas).

O trabalho é dividido em blocos de células, gravados à medida que terminam: reenviar o
job retoma do primeiro bloco que falta. Só roda com o pré-registro congelado (D-010).
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from amazon_chaos import regions
from amazon_chaos.nonlinear.suite import (
    batch_hash,
    descriptor_values,
    ews_test,
    gate_hash,
    spec_hash,
    surrogate_suite,
)
from amazon_chaos.regional import daily_files, standardized_anomalies

VARIABLES = {"t2m": "t2m_c_mean", "vpd": "vpd_kpa_mean"}
NORMAL = ("1991-01-01", "2020-12-31")


def output_dir(cfg, spec) -> Path:
    return regions.processed_dir(cfg) / "descritores" / batch_hash(spec)


def load_cubes(cfg, variables=VARIABLES) -> dict[str, xr.DataArray]:
    """Cubos diários (tempo × lat × lon) de 1990–2024, só com as variáveis pedidas."""
    files = daily_files(cfg, 1990, 2024)
    out = {}
    for short, name in variables.items():
        parts = []
        for path in files:
            with xr.open_dataset(path) as ds:
                parts.append(ds[name].astype("float32").load())
        out[short] = xr.concat(parts, "time")
    return out


def windows(spec) -> dict[str, tuple[str, str]]:
    first, last = (str(d) for d in spec["series"]["period"])
    out = {f"{first[:4]}_{last[:4]}": (first, last)}  # a primeira é a janela completa
    for start, end in spec["series"]["windows"]:
        out[f"{str(start)[:4]}_{str(end)[:4]}"] = (str(start), str(end))
    return out


def _seed(spec, *parts) -> int:
    key = "|".join(map(str, (spec["surrogates"]["seed"], *parts)))
    return int.from_bytes(hashlib.sha256(key.encode()).digest()[:4], "little")


def cell_task(spec: dict, cell_id: str, series: dict[str, pd.Series]) -> pd.DataFrame:
    """Todas as medidas de uma célula; erros viram linhas registradas, não falhas do lote."""
    rows = []
    full = next(iter(windows(spec)))
    for var, raw in series.items():
        z, _ = standardized_anomalies(raw, NORMAL)
        for window, (start, end) in windows(spec).items():
            x = z.loc[start:end].to_numpy(dtype=float)
            labels = {"cell_id": cell_id, "variable": var, "window": window, "n": len(x)}
            if not np.isfinite(x).all():
                rows.append(pd.DataFrame([{**labels, "descriptor": "erro",
                                           "error": "lacunas na série"}]))
                continue
            try:
                result = surrogate_suite(x, spec, seed=_seed(spec, cell_id, var, window))
                rows.append(result.table(**labels, kind="teste"))
                if window != full:
                    continue
                ews = ews_test(x, spec, seed=_seed(spec, cell_id, var, "ews"))
                rows.append(ews.rename(columns={"indicator": "descriptor", "tau": "observed"})
                            .assign(**labels, kind="ews"))
                sens = spec["embedding"]["sensitivity"]
                base = result.params
                grid = [{**base, "tau": max(1, round(base["tau"] * f))}
                        for f in sens["delay_factors"]]
                grid += [{**base, "m": base["m"] + o} for o in sens["dimension_offsets"]
                         if base["m"] + o >= 2]
                for params in grid:
                    params["theiler"] = max(spec["embedding"]["theiler"]["minimum"],
                                            params["tau"] * params["m"])
                    values = descriptor_values(x, params, spec)
                    rows.append(pd.DataFrame([{**labels, **params, "descriptor": k,
                                               "observed": v, "kind": "sensibilidade"}
                                              for k, v in values.items()]))
            except ValueError as error:
                rows.append(pd.DataFrame([{**labels, "descriptor": "erro",
                                           "error": str(error)}]))
    return pd.concat(rows, ignore_index=True)


def _commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "desconhecido"


def run(cfg, spec, *, workers=None, block=25, report=print, limit=None) -> Path:
    """Executa (ou retoma) o lote da região e consolida `descritores.parquet`."""
    if spec["status"] != "congelado":
        raise RuntimeError("O lote só roda com o pré-registro congelado (D-010)")
    out = output_dir(cfg, spec)
    out.mkdir(parents=True, exist_ok=True)
    cells = regions.cells(cfg)[["cell_id", "latitude", "longitude"]].reset_index(drop=True)
    if limit:
        cells = cells.iloc[:limit]
    blocks = [cells.iloc[i:i + block] for i in range(0, len(cells), block)]
    todo = [k for k in range(len(blocks)) if not (out / f"bloco_{k:04d}.parquet").exists()]
    report(f"🧮 Descritores · {cfg['name']}: {len(cells)} células em {len(blocks)} blocos "
           f"({len(blocks) - len(todo)} já prontos) · lote {batch_hash(spec)}")
    if todo:
        cubes = load_cubes(cfg)
        workers = workers or os.cpu_count()
        started = datetime.now(UTC)
        with ProcessPoolExecutor(workers) as pool:
            futures = {}
            for k in todo:
                for _, cell in blocks[k].iterrows():
                    series = {v: cube.sel(latitude=cell.latitude, longitude=cell.longitude)
                              .to_series() for v, cube in cubes.items()}
                    futures[pool.submit(cell_task, spec, cell.cell_id, series)] = k
            pending = {k: len(blocks[k]) for k in todo}
            parts: dict[int, list] = {k: [] for k in todo}
            done = 0
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
                        report(f"📊 {cfg['name']}: {done}/{len(todo)} blocos "
                               f"({100 * done / len(todo):.0f}%) · {hours:.1f} h · "
                               f"faltam ≈ {eta:.1f} h")
    table = pd.concat([pd.read_parquet(p) for p in sorted(out.glob("bloco_*.parquet"))],
                      ignore_index=True)
    target = out / "descritores.parquet"
    table.to_parquet(target)
    (out / "execucao.json").write_text(json.dumps({
        "region": cfg["slug"], "cells": len(cells), "rows": len(table),
        "errors": int((table.descriptor == "erro").sum()), "batch_hash": batch_hash(spec),
        "spec_hash": spec_hash(spec), "spec_version": spec["version"],
        "gate_hash": gate_hash(spec), "commit": _commit(),
        "finished_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }, indent=2))
    return target
