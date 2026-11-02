"""Chuva: ocorrência separada da intensidade (G6; complementa D-021 e F2i).

O lote da chuva (D-021) mede os padrões ordinais da série diária inteira, em que a maior parte
dos dias é seca e empatada em zero. Uma diferença entre células pode vir de quantos dias são
secos e de como eles se agrupam (ocorrência), ou da ordem das quantidades nos dias de chuva
(intensidade). Aqui, por célula e fonte, em 2001–2024, com dia chuvoso a partir de 1 mm:

- ocorrência: entropia de Shannon das palavras binárias de 5 dias (seco/chuvoso), normalizada
  por 5 bits, e a fração de dias chuvosos; descritiva, sem nula;
- intensidade na série inteira: entropia e complexidade ordinais (com o dither de D-021)
  contra 39 nulas que preservam a sequência de ocorrência e permutam as quantidades entre os
  dias chuvosos; rejeitar diz que a ordem das intensidades tem estrutura além da ocorrência;
- dias chuvosos: os mesmos descritores só na sequência dos dias chuvosos, contra 39
  permutações dela.

Chamado por `amazon-chaos descriptors rain-split <região>`.
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
from amazon_chaos.nonlinear.batch import _commit, _seed
from amazon_chaos.nonlinear.precip import DESCRIPTORS, SOURCES, dither, load_series
from amazon_chaos.nonlinear.precip_dither import _params, full_window
from amazon_chaos.nonlinear.suite import descriptor_values, spec_hash
from amazon_chaos.nonlinear.surrogates import monte_carlo_pvalue

RULES = {"version": 1, "wet_mm": 1.0, "word": 5, "surrogates": 39, "descriptors": DESCRIPTORS,
         "nulls": {"intensidade": "permuta as quantidades entre os dias chuvosos",
                   "chuvosos": "permuta a sequência dos dias chuvosos"}}


def split_hash(spec) -> str:
    return spec_hash({"rules": RULES, "series": spec["series"],
                      "descriptors": {k: spec["descriptors"][k] for k in DESCRIPTORS}})


def output_dir(cfg, spec) -> Path:
    return regions.processed_dir(cfg) / "chuva_ocorrencia" / split_hash(spec)


def word_entropy(wet: np.ndarray, length: int = RULES["word"]) -> float:
    """Entropia de Shannon (bits) das palavras binárias de `length` dias, dividida por
    `length`: 1 para dias independentes com chuva em metade deles, 0 para uma sequência fixa."""
    w = np.asarray(wet, dtype=int)
    codes = np.lib.stride_tricks.sliding_window_view(w, length) @ (1 << np.arange(length))
    p = np.bincount(codes, minlength=1 << length) / len(codes)
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum() / length)


def shuffle_wet(x: np.ndarray, wet: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """A mesma série com as quantidades dos dias chuvosos permutadas entre eles."""
    y = x.copy()
    y[wet] = rng.permutation(x[wet])
    return y


def _test(observed, nulls, spec, labels):
    rows = []
    for k in DESCRIPTORS:
        values = np.array([n[k] for n in nulls])
        sd = values.std(ddof=1)
        rows.append({**labels, "descriptor": k, "observed": observed[k],
                     "null_mean": values.mean(), "null_sd": sd,
                     "z": (observed[k] - values.mean()) / sd if sd > 0 else np.nan,
                     "pvalue": monte_carlo_pvalue(observed[k], values,
                                                  spec["descriptors"][k]["alternative"]),
                     "n_null": len(values)})
    return rows


def cell_task(spec: dict, cell_id: str, series: dict[str, pd.Series]) -> pd.DataFrame:
    window, (start, end) = full_window(spec)
    params = _params(spec)
    rows = []
    for source, raw in series.items():
        x = raw.loc[start:end].to_numpy(dtype=float)
        if not np.isfinite(x).all():
            rows.append({"cell_id": cell_id, "variable": source, "teste": "erro"})
            continue
        wet = x >= RULES["wet_mm"]
        base = {"cell_id": cell_id, "variable": source, "window": window,
                "fracao_chuvosos": float(wet.mean()), "entropia_ocorrencia": word_entropy(wet)}
        rng = np.random.default_rng(_seed(spec, cell_id, source, window, "ocorrencia"))
        observed = descriptor_values(dither(x, _seed(spec, cell_id, source, window, "dither")),
                                     params, spec, DESCRIPTORS)
        nulls = [descriptor_values(dither(shuffle_wet(x, wet, rng),
                                          _seed(spec, cell_id, source, window, "dither", i)),
                                   params, spec, DESCRIPTORS)
                 for i in range(RULES["surrogates"])]
        rows += _test(observed, nulls, spec, {**base, "teste": "intensidade"})
        rain = dither(x[wet], _seed(spec, cell_id, source, window, "chuvosos"))
        observed = descriptor_values(rain, params, spec, DESCRIPTORS)
        nulls = [descriptor_values(rng.permutation(rain), params, spec, DESCRIPTORS)
                 for _ in range(RULES["surrogates"])]
        rows += _test(observed, nulls, spec, {**base, "teste": "chuvosos"})
    return pd.DataFrame(rows)


def run(cfg, spec, *, workers=None, report=print) -> Path:
    """Todas as células, nas duas fontes; consolida `descritores.parquet`."""
    out = output_dir(cfg, spec)
    out.mkdir(parents=True, exist_ok=True)
    cells = regions.cells(cfg).cell_id.tolist()
    started = datetime.now(UTC)
    frames = []
    for source in SOURCES:
        frame = load_series(cfg, source)
        if frame is None:
            report(f"⏭️ Chuva (G6) · {cfg['name']}: {source} não existe")
            continue
        with ProcessPoolExecutor(workers or os.cpu_count()) as pool:
            frames += list(pool.map(cell_task, [spec] * len(cells), cells,
                                    [{source: frame[c]} for c in cells], chunksize=8))
        report(f"🌧️ Chuva (G6) · {cfg['name']}: {source} pronta")
    table = pd.concat(frames, ignore_index=True)
    table.to_parquet(out / "descritores.parquet")
    (out / "execucao.json").write_text(json.dumps({
        "region": cfg["slug"], "hash": split_hash(spec), "cells": len(cells), "rules": RULES,
        "errors": int((table.teste == "erro").sum()), "commit": _commit(),
        "started_utc": started.isoformat(timespec="seconds"),
        "finished_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }, indent=2, ensure_ascii=False))
    return out
