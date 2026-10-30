"""Chuva: dither em cada substituta e erro espectral do IAAFT (F2i, D-027; comparativo).

No lote da chuva (D-021), só a série observada recebe o ruído de 10⁻⁶ mm que desfaz os
empates; as substitutas IAAFT são geradas dessa série já com ruído. Aqui, a série observada
recebe o mesmo ruído, com a mesma semente, e as substitutas são geradas da série **sem**
ruído, cada uma recebendo depois o seu próprio, de modo que original e nula tenham o mesmo
tratamento dos empates. As substitutas usam a semente do lote da chuva.

O erro espectral é o erro relativo final de cada substituta IAAFT (`IAAFTResult`), na
subamostra de D-024, para a chuva das duas fontes e para t2m e VPD.
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
from amazon_chaos.nonlinear.precip import DESCRIPTORS, SOURCES, dither, load_series
from amazon_chaos.nonlinear.suite import descriptor_values, spec_hash
from amazon_chaos.nonlinear.surrogates import iaaft_surrogate, monte_carlo_pvalue
from amazon_chaos.regional import standardized_anomalies

RULES = {"version": 1, "window": "2001_2024", "descriptors": DESCRIPTORS,
         "dither": "observada com a semente de D-021; cada substituta com a sua",
         "spectral": {"variables": ["precip_era5", "precip_chirps", "t2m", "vpd"],
                      "subsample": {"n": 60, "seed": 20261023}}}


def dither_hash(spec) -> str:
    return spec_hash({"rules": RULES, "series": spec["series"],
                      "surrogates": spec["surrogates"],
                      "descriptors": {k: spec["descriptors"][k] for k in DESCRIPTORS}})


def output_dir(cfg, spec) -> Path:
    return regions.processed_dir(cfg) / "chuva_dither" / dither_hash(spec)


def iaaft_set(x: np.ndarray, n: int, seed: int, max_iter: int):
    """As mesmas substitutas de `suite.surrogates`, com o resultado completo do IAAFT."""
    for child in np.random.SeedSequence(seed).spawn(n):
        yield iaaft_surrogate(x, np.random.default_rng(child), max_iter=max_iter)


def full_window(spec) -> tuple[str, tuple[str, str]]:
    """A janela completa do lote (a primeira de `windows`), 2001_2024 no pré-registro."""
    return next(iter(windows(spec).items()))


def _params(spec):
    d = spec["descriptors"]["pe_entropy"]
    return {"tau": d["delay"], "m": d["order"], "theiler": 0}


def cell_task(spec: dict, cell_id: str, series: dict[str, pd.Series]) -> pd.DataFrame:
    window, (start, end) = full_window(spec)
    params = _params(spec)
    n, max_iter = spec["surrogates"]["per_cell"], spec["surrogates"]["max_iter"]
    rows = []
    for source, raw in series.items():
        x = raw.loc[start:end].to_numpy(dtype=float)
        labels = {"cell_id": cell_id, "variable": source, "window": window}
        if not np.isfinite(x).all():
            rows.append({**labels, "descriptor": "erro", "error": "lacunas na série"})
            continue
        observed = descriptor_values(dither(x, _seed(spec, cell_id, source, window, "dither")),
                                     params, spec, DESCRIPTORS)
        null = {k: [] for k in DESCRIPTORS}
        for i, s in enumerate(iaaft_set(x, n, _seed(spec, cell_id, source, window), max_iter)):
            y = dither(s.values, _seed(spec, cell_id, source, window, "dither", i))
            for k, v in descriptor_values(y, params, spec, DESCRIPTORS).items():
                null[k].append(v)
        for k in DESCRIPTORS:
            values = np.array(null[k])
            sd = values.std(ddof=1)
            rows.append({**labels, "descriptor": k, "observed": observed[k],
                         "null_mean": values.mean(), "null_sd": sd,
                         "z": (observed[k] - values.mean()) / sd if sd > 0 else np.nan,
                         "pvalue": monte_carlo_pvalue(observed[k], values,
                                                      spec["descriptors"][k]["alternative"]),
                         "n_null": len(values), "kind": "teste"})
    return pd.DataFrame(rows)


def spectral_task(spec: dict, cell_id: str, series: dict[str, np.ndarray]) -> pd.DataFrame:
    n, max_iter = spec["surrogates"]["per_cell"], spec["surrogates"]["max_iter"]
    window, _ = full_window(spec)
    rows = []
    for var, x in series.items():
        seed = _seed(spec, cell_id, var, window)
        if var.startswith("precip"):
            x = dither(x, _seed(spec, cell_id, var, window, "dither"))
        errors = [s.spectral_error for s in iaaft_set(x, n, seed, max_iter)]
        rows.append({"cell_id": cell_id, "variable": var, "mediana": float(np.median(errors)),
                     "maximo": float(np.max(errors)), "n": len(errors)})
    return pd.DataFrame(rows)


def run(cfg, spec, cells: pd.DataFrame, *, workers=None, block=25, report=print) -> Path:
    """Dither repetido em todas as células e fontes; erro espectral na subamostra."""
    from amazon_chaos.nonlinear.sensitivity import subsample

    if spec["status"] != "congelado":
        raise RuntimeError("O lote só roda com o pré-registro congelado (D-010)")
    out = output_dir(cfg, spec)
    out.mkdir(parents=True, exist_ok=True)
    ids = regions.cells(cfg).cell_id.tolist()
    blocks = [ids[i:i + block] for i in range(0, len(ids), block)]
    frames = {s: load_series(cfg, s) for s in SOURCES}
    with ProcessPoolExecutor(workers or os.cpu_count()) as pool:
        todo = [k for k in range(len(blocks)) if not (out / f"bloco_{k:04d}.parquet").exists()]
        report(f"🌧️ Dither da chuva (F2i) · {cfg['name']}: {len(todo)} de {len(blocks)} blocos")
        futures = {pool.submit(cell_task, spec, c, {s: f[c] for s, f in frames.items()}): k
                   for k in todo for c in blocks[k]}
        parts: dict[int, list] = {k: [] for k in todo}
        pending = {k: len(blocks[k]) for k in todo}
        started, done = datetime.now(UTC), 0
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
                    report(f"📊 Dither da chuva (F2i) · {cfg['name']}: {done}/{len(todo)} "
                           f"blocos · {hours:.1f} h · faltam ≈ "
                           f"{hours / done * (len(todo) - done):.1f} h")
        if not (out / "espectro.parquet").exists():
            rule = RULES["spectral"]["subsample"]
            chosen = subsample(cells, rule["n"], rule["seed"])
            grid = regions.cells(cfg).set_index("cell_id").loc[chosen]
            cubes = load_cubes(cfg, {"t2m": "t2m_c_mean", "vpd": "vpd_kpa_mean"})
            _, (start, end) = full_window(spec)
            futures = []
            for cell in grid.itertuples():
                series = {s: f[cell.Index].loc[start:end].to_numpy(dtype=float)
                          for s, f in frames.items()}
                for var, cube in cubes.items():
                    z, _ = standardized_anomalies(cube.sel(
                        latitude=cell.latitude, longitude=cell.longitude).to_series(), NORMAL)
                    series[var] = z.loc[start:end].to_numpy(dtype=float)
                futures.append(pool.submit(spectral_task, spec, cell.Index, series))
            pd.concat([f.result() for f in futures], ignore_index=True).to_parquet(
                out / "espectro.parquet")
            report(f"📈 Erro espectral do IAAFT (F2i) · {cfg['name']}: pronto")
    table = pd.concat([pd.read_parquet(p) for p in sorted(out.glob("bloco_*.parquet"))],
                      ignore_index=True)
    table.to_parquet(out / "descritores.parquet")
    (out / "execucao.json").write_text(json.dumps({
        "region": cfg["slug"], "cells": len(ids), "rows": len(table),
        "errors": int((table.descriptor == "erro").sum()), "dither_hash": dither_hash(spec),
        "rules": RULES, "commit": _commit(),
        "finished_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }, indent=2, ensure_ascii=False))
    return out
