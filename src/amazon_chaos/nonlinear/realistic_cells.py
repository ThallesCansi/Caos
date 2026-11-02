"""Nulas realistas ajustadas em cada célula da subamostra (G2b; complementa F2f e D-029).

No gate realista (`realistic.py`), as quatro nulas são ajustadas na série média de cada bacia,
e a média espacial aumenta a memória e suaviza a não linearidade. Aqui, cada célula da
subamostra de D-024 tem as suas: o mesmo procedimento fixo (`synthetic.fit_realistic`) na
série bruta da célula, com o GARCH estimado por máxima verossimilhança (`fit_garch`) no lugar
de α = 0,10 e β = 0,85. Uma realização por célula × variável × nula, simulada em 1990–2024,
passada pela anomalia padronizada e cortada em 2001–2024, como os dados; os oito descritores
com 39 IAAFT e o S-map. A taxa de rejeição de cada nula, por variável, dá o limite da regra
da D-029 com nulas do tamanho de uma célula.

Chamado por `amazon-chaos gate cells <região>` (`scripts/hpc/nulas_celulas.sbatch`).
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
from amazon_chaos.nonlinear import realistic as RL
from amazon_chaos.nonlinear import smap
from amazon_chaos.nonlinear import synthetic as S
from amazon_chaos.nonlinear.batch import _commit, _seed, load_cubes
from amazon_chaos.nonlinear.suite import spec_hash, surrogate_suite

RULES = {"version": 1, "nulls": list(S.REALISTIC), "garch": "máxima verossimilhança",
         "variables": {"t2m": "t2m_c_mean", "vpd": "vpd_kpa_mean"},
         "fit_period": RL.RULES["fits"]["period"], "simulation": RL.RULES["simulation"],
         "window": RL.RULES["window"], "repetitions": 1, "surrogates": 39,
         "subsample": {"n": 60, "seed": 20261023}, "smap": smap.RULES}


def cells_hash(spec) -> str:
    return spec_hash({"rules": RULES, "embedding": spec["embedding"],
                      "descriptors": spec["descriptors"], "surrogates": spec["surrogates"]})


def output_dir(cfg, spec) -> Path:
    return regions.processed_dir(cfg) / "nulas_celulas" / cells_hash(spec)


def cell_task(spec: dict, cell_id: str, series: dict[str, pd.Series]) -> dict:
    """Ajuste e as quatro nulas de uma célula, nas duas variáveis."""
    desc, smaps, fits = [], [], {}
    for var, raw in series.items():
        params = S.fit_realistic(raw, tuple(RULES["fit_period"]), garch=True)
        fits[var] = params
        for kind in S.REALISTIC:
            seed = _seed(spec, cell_id, var, kind, "nula_celula")
            labels = {"cell_id": cell_id, "variable": var, "control": kind}
            x = RL.null_series(kind, params, seed)
            try:
                suite = surrogate_suite(x, spec, n_surrogates=RULES["surrogates"], seed=seed)
                desc.append(suite.table(**labels))
                p = suite.params
                smaps.append(smap.smap_series(x, p["m"], p["tau"], p["theiler"]).assign(
                    **labels, **p))
            except (ValueError, np.linalg.LinAlgError) as error:
                desc.append(pd.DataFrame([{**labels, "descriptor": "erro",
                                           "error": str(error)}]))
    return {"descritores": pd.concat(desc, ignore_index=True),
            "smap": pd.concat(smaps, ignore_index=True) if smaps else None, "ajustes": fits}


def run(cfg, spec, cells: pd.DataFrame, *, workers=None, report=print) -> Path:
    """Executa (ou retoma, por célula) as nulas da subamostra e consolida os resultados."""
    from amazon_chaos.nonlinear.sensitivity import subsample

    if spec["status"] != "congelado":
        raise RuntimeError("O lote só roda com o pré-registro congelado (D-010)")
    out = output_dir(cfg, spec)
    parts = out / "celulas"
    parts.mkdir(parents=True, exist_ok=True)
    chosen = subsample(cells, RULES["subsample"]["n"], RULES["subsample"]["seed"])
    grid = regions.cells(cfg).set_index("cell_id").loc[chosen]
    todo = [c for c in grid.itertuples() if not (parts / f"{c.Index}.pkl").exists()]
    report(f"🧪 Nulas por célula (G2b) · {cfg['name']}: {len(todo)} de {len(grid)} células")
    started = datetime.now(UTC)
    if todo:
        cubes = load_cubes(cfg, RULES["variables"])
        with ProcessPoolExecutor(workers or os.cpu_count()) as pool:
            futures = {pool.submit(cell_task, spec, c.Index, {
                v: cube.sel(latitude=c.latitude, longitude=c.longitude).to_series()
                for v, cube in cubes.items()}): c.Index for c in todo}
            for i, future in enumerate(as_completed(futures), 1):
                pd.to_pickle(future.result(), parts / f"{futures[future]}.pkl")
                if i % max(1, len(todo) // 10) == 0 or i == len(todo):
                    hours = (datetime.now(UTC) - started).total_seconds() / 3600
                    report(f"📊 Nulas por célula (G2b) · {cfg['name']}: {i}/{len(todo)} "
                           f"células · {hours:.1f} h · faltam ≈ "
                           f"{hours / i * (len(todo) - i):.1f} h")
    results = [pd.read_pickle(parts / f"{c}.pkl") for c in grid.index]
    pd.concat([r["descritores"] for r in results], ignore_index=True).to_csv(
        out / "descritores.csv", index=False)
    pd.concat([r["smap"] for r in results if r["smap"] is not None], ignore_index=True).to_csv(
        out / "smap.csv", index=False)
    (out / "ajustes.json").write_text(json.dumps(
        {c: r["ajustes"] for c, r in zip(grid.index, results, strict=True)}))
    (out / "execucao.json").write_text(json.dumps({
        "region": cfg["slug"], "hash": cells_hash(spec), "cells": len(grid), "rules": RULES,
        "commit": _commit(), "started_utc": started.isoformat(timespec="seconds"),
        "finished_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }, indent=2, ensure_ascii=False, default=str))
    return out


# ── leitura (caderno 07) ────────────────────────────────────────────────────


def null_rates(spec, slugs=("xingu", "tapajos"), horizon: int = 1) -> pd.DataFrame:
    """Taxa de rejeição de cada nula por variável, juntando as células das duas bacias, com
    IC de Clopper–Pearson; mesmas colunas de `realistic.null_rates(by=("variable",))`."""
    from scipy.stats import binomtest

    from amazon_chaos.config import load_region
    from amazon_chaos.nonlinear.results import TOLERANCE

    alpha = spec["surrogates"]["alpha"] + TOLERANCE
    frames = []
    for slug in slugs:
        out = output_dir(load_region(slug), spec)
        desc = pd.read_csv(out / "descritores.csv")
        sm = pd.read_csv(out / "smap.csv")
        frames += [desc[desc.descriptor != "erro"],
                   sm[sm.horizon == horizon].assign(descriptor="smap")]
    table = pd.concat(frames, ignore_index=True)
    rows = []
    for (desc, control, var), part in table.groupby(["descriptor", "control", "variable"]):
        k, n = int((part.pvalue <= alpha).sum()), int(part.pvalue.notna().sum())
        ci = binomtest(k, n).proportion_ci()
        rows.append({"descriptor": desc, "control": control, "variable": var,
                     "rejections": k, "total": n, "rate": k / n, "ci_low": ci.low,
                     "ci_high": ci.high})
    return pd.DataFrame(rows)
