"""Chuva: descritores ordinais por célula, no ERA5 e no CHIRPS (exploratório; D-021).

O pré-registro põe a chuva na família exploratória e restringe os métodos aos ordinais
(entropia de permutação e complexidade estatística), por ela ser intermitente. O que ele não
fixava, decidido antes de calcular e registrado em D-021:

- a série é a chuva diária bruta (mm), sem anomalia: os padrões ordinais não mudam com
  transformações monotônicas, e a anomalia padronizada ordenaria os dias secos pela
  climatologia de cada dia do ano, criando padrões que não estão na chuva;
- os empates (dias secos seguidos, sobretudo no CHIRPS) são desfeitos por um ruído uniforme
  de no máximo 10⁻⁶ mm, com semente fixa, antes das substitutas; sem isso, a ordenação
  estável transformaria cada sequência seca num padrão crescente artificial;
- as duas fontes passam pelo mesmo cálculo, com 39 substitutas IAAFT, nas mesmas janelas
  do lote principal; a diferença entre elas é a resposta à pergunta de detectabilidade.

Os blocos de cada fonte são gravados à parte; uma fonte ausente (CHIRPS ainda não baixado)
não impede a outra.
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
from amazon_chaos.features.chirps import out_path as chirps_path
from amazon_chaos.io.chirps import PRODUCT
from amazon_chaos.nonlinear.batch import _commit, _seed, load_cubes, windows
from amazon_chaos.nonlinear.suite import spec_hash, surrogate_suite

DESCRIPTORS = ["pe_entropy", "pe_complexity"]
RULES = {"version": 1, "transform": "chuva diária bruta (mm)", "dither_mm": 1e-6,
         "descriptors": DESCRIPTORS, "chirps_product": PRODUCT,
         "sources": {"precip_era5": "ERA5 precip_mm_sum (dia local UTC−03:00)",
                     "precip_chirps": "CHIRPS v3 sat, quadrado inteiro da célula (dia UTC)"}}
SOURCES = tuple(RULES["sources"])


def precip_hash(spec) -> str:
    part = {"rules": RULES, "series": spec["series"], "surrogates": spec["surrogates"],
            "descriptors": {k: spec["descriptors"][k] for k in DESCRIPTORS}}
    return spec_hash(part)


def output_dir(cfg, spec) -> Path:
    return regions.processed_dir(cfg) / "descritores_chuva" / precip_hash(spec)


def dither(x: np.ndarray, seed: int, amplitude: float = RULES["dither_mm"]) -> np.ndarray:
    """Desfaz empates com ruído uniforme em [0, amplitude).

    Valores que diferem por mais de `amplitude` mantêm a ordem; abaixo disso (10⁻⁶ mm, o
    arredondamento do float32 numa chuva de poucos mm), eles já são empates na prática.
    """
    return x + np.random.default_rng(seed).uniform(0, amplitude, len(x))


def cell_task(spec: dict, cell_id: str, series: dict[str, pd.Series]) -> pd.DataFrame:
    rows = []
    order, delay = spec["descriptors"]["pe_entropy"]["order"], spec["descriptors"][
        "pe_entropy"]["delay"]
    params = {"tau": delay, "m": order, "theiler": 0}  # padrões de ordem 5, atraso 1
    for source, raw in series.items():
        for window, (start, end) in windows(spec).items():
            x = raw.loc[start:end].to_numpy(dtype=float)
            labels = {"cell_id": cell_id, "variable": source, "window": window, "n": len(x)}
            if not np.isfinite(x).all():
                rows.append(pd.DataFrame([{**labels, "descriptor": "erro",
                                           "error": "lacunas na série"}]))
                continue
            try:
                y = dither(x, _seed(spec, cell_id, source, window, "dither"))
                result = surrogate_suite(y, spec, names=DESCRIPTORS, params=params,
                                         seed=_seed(spec, cell_id, source, window))
                rows.append(result.table(**labels, kind="teste").assign(
                    zero_fraction=float(np.mean(x == 0))))
            except ValueError as error:
                rows.append(pd.DataFrame([{**labels, "descriptor": "erro",
                                           "error": str(error)}]))
    return pd.concat(rows, ignore_index=True)


def load_series(cfg, source: str) -> pd.DataFrame | None:
    """Chuva diária (dias × cell_id) da fonte, ou None se ela ainda não existe."""
    cells = regions.cells(cfg)[["cell_id", "latitude", "longitude"]]
    if source == "precip_chirps":
        path = chirps_path(cfg)
        return pd.read_parquet(path) if path.exists() else None
    cube = load_cubes(cfg, {source: "precip_mm_sum"})[source]
    frame = cube.stack(point=("latitude", "longitude")).to_pandas()
    frame.columns = [f"ERA5_{lat:+07.2f}_{lon:+08.2f}" for lat, lon in frame.columns]
    return frame[cells.cell_id]


def run(cfg, spec, *, sources=SOURCES, workers=None, block=25, report=print,
        limit=None) -> Path:
    """Executa (ou retoma) o lote da chuva e consolida `descritores.parquet`."""
    if spec["status"] != "congelado":
        raise RuntimeError("O lote só roda com o pré-registro congelado (D-010)")
    out = output_dir(cfg, spec)
    out.mkdir(parents=True, exist_ok=True)
    cells = regions.cells(cfg).cell_id.tolist()[:limit]
    blocks = [cells[i:i + block] for i in range(0, len(cells), block)]
    for source in sources:
        todo = [k for k in range(len(blocks))
                if not (out / f"bloco_{source}_{k:04d}.parquet").exists()]
        if not todo:
            continue
        frame = load_series(cfg, source)
        if frame is None:
            report(f"⏭️ Chuva · {cfg['name']}: {source} ainda não existe, fica para depois")
            continue
        report(f"🌧️ Chuva · {cfg['name']} · {source}: {len(todo)} de {len(blocks)} blocos")
        with ProcessPoolExecutor(workers or os.cpu_count()) as pool:
            futures = {pool.submit(cell_task, spec, c, {source: frame[c]}): k
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
                        out / f"bloco_{source}_{k:04d}.parquet")
                    done += 1
                    if done % max(1, len(todo) // 10) == 0 or done == len(todo):
                        hours = (datetime.now(UTC) - started).total_seconds() / 3600
                        eta = hours / done * (len(todo) - done)
                        report(f"📊 Chuva · {cfg['name']} · {source}: {done}/{len(todo)} "
                               f"blocos ({100 * done / len(todo):.0f}%) · {hours:.1f} h · "
                               f"faltam ≈ {eta:.1f} h")
    files = sorted(out.glob("bloco_*.parquet"))
    if not files:
        raise RuntimeError("Nenhum bloco calculado")
    table = pd.concat([pd.read_parquet(p) for p in files], ignore_index=True)
    target = out / "descritores.parquet"
    table.to_parquet(target)
    (out / "execucao.json").write_text(json.dumps({
        "region": cfg["slug"], "cells": len(cells), "rows": len(table),
        "sources": sorted(table.variable.unique().tolist()),
        "errors": int((table.descriptor == "erro").sum()), "precip_hash": precip_hash(spec),
        "rules": RULES, "spec_version": spec["version"], "commit": _commit(),
        "finished_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }, indent=2, ensure_ascii=False))
    return target


# ── leitura (caderno 09) ────────────────────────────────────────────────────


def load(cfg, spec) -> pd.DataFrame:
    """Linhas do lote da chuva com q de BH dentro da família exploratória (D-021)."""
    from amazon_chaos.nonlinear.results import TOLERANCE, benjamini_hochberg

    table = pd.read_parquet(output_dir(cfg, spec) / "descritores.parquet")
    tests = table.kind == "teste"
    table.loc[tests, "q"] = table[tests].groupby(["variable", "window"]).pvalue.transform(
        lambda s: benjamini_hochberg(s.to_numpy()))
    table["rejects"] = table.q <= spec["surrogates"]["alpha"] + TOLERANCE
    return table


def climatology(cfg, first: str = "2001", last: str = "2024") -> pd.DataFrame:
    """Por célula e fonte: chuva anual (mm), fração de dias com < 0,1 mm e meses < 100 mm."""
    out = {}
    for source in SOURCES:
        rain = load_series(cfg, source).loc[first:last]
        years = int(last) - int(first) + 1
        monthly = rain.resample("MS").sum()
        normal = monthly.groupby(monthly.index.month).mean()
        short = source.removeprefix("precip_")
        out[f"chuva_anual_{short}"] = rain.sum() / years
        out[f"dias_secos_{short}"] = (rain < 0.1).mean()
        out[f"meses_secos_{short}"] = (normal < 100).sum()
    return pd.DataFrame(out)


def cell_table(cfg, spec) -> pd.DataFrame:
    """Tabela do caderno 08 com a climatologia e os descritores da chuva das duas fontes."""
    from amazon_chaos import gradient as G

    table = G.cell_table(cfg, spec).join(climatology(cfg))
    table["natural_nao_florestal_2000"] = (
        1 - table.floresta_frac_2000 - table.agro_frac_2000).clip(lower=0)
    tests = load(cfg, spec)
    tests = tests[tests.kind == "teste"]
    for column, prefix in [("z", "z"), ("observed", "obs"), ("null_mean", "nulo")]:
        wide = tests[tests.window == "2001_2024"].pivot_table(
            index="cell_id", columns=["variable", "descriptor"], values=column)
        wide.columns = [f"{prefix}_{v}_{d}" for v, d in wide.columns]
        table = table.join(wide)
    halves = tests[tests.window != "2001_2024"].pivot_table(
        index="cell_id", columns=["variable", "descriptor", "window"], values="observed")
    for source in SOURCES:
        for d in DESCRIPTORS:
            table[f"delta_{source}_{d}"] = (halves[(source, d, "2013_2024")]
                                            - halves[(source, d, "2001_2012")])
    return table
