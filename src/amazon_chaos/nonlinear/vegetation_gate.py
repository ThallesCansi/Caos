"""Portão das séries de vegetação de 8 dias (D-031, etapa 1), antes dos dados.

Os mesmos controles do gate congelado (caóticos e lineares), com o tamanho das séries de
vegetação (`configs/analysis/vegetation.yaml`, cerca de 1.100 pontos), os descritores do
pré-registro de 8 dias com as suas substitutas e, como no gate realista, Wolf, Kantz e Cao
(`estimators.extra_suite`) e o S-map (`smap.smap_series`). As nulas realistas ajustadas às
séries de vegetação entram depois, quando os dados existirem.

Chamado por `amazon-chaos vegetation gate` (`scripts/hpc/vegetacao_gate.sbatch`).
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from amazon_chaos.config import load_config
from amazon_chaos.nonlinear import estimators, smap
from amazon_chaos.nonlinear import synthetic as S
from amazon_chaos.nonlinear.gate import GATE_DIR, _git_commit, _seed, tasks
from amazon_chaos.nonlinear.suite import gate_hash, surrogate_suite
from amazon_chaos.paths import project_root

SPEC_PATH = Path("configs/analysis/vegetation.yaml")


def load_vegetation_spec() -> dict:
    return load_config(project_root() / SPEC_PATH)


def output_dir(spec) -> Path:
    return GATE_DIR / f"vegetacao_{gate_hash(spec)}"


def control_task(spec: dict, task: dict) -> dict:
    seed = _seed(spec, task)
    x = S.control(task["control"], task["n"], seed=seed, noise=task["noise"])
    try:
        suite = surrogate_suite(x, spec, seed=seed)
        p = suite.params
        desc = pd.concat([suite.table(**task), estimators.extra_suite(
            x, p, spec["surrogates"]["per_cell"], seed, spec, **task)], ignore_index=True)
        return {"descritores": desc, "smap": smap.smap_series(
            x, p["m"], p["tau"], p["theiler"]).assign(**task, **p)}
    except (ValueError, np.linalg.LinAlgError) as error:
        return {"descritores": pd.DataFrame([{**task, "descriptor": "erro",
                                              "error": str(error)}]), "smap": None}


def run(spec: dict, *, workers=None, report=print) -> Path:
    out = output_dir(spec)
    parts = out / "partes"
    parts.mkdir(parents=True, exist_ok=True)
    work = tasks(spec)
    key = {i: "_".join(str(t[k]) for k in ("control", "n", "noise", "rep"))
           for i, t in enumerate(work)}
    todo = [i for i in key if not (parts / f"{key[i]}.pkl").exists()]
    report(f"🧪 Portão da vegetação (D-031): {len(todo)} de {len(work)} séries")
    with ProcessPoolExecutor(workers or os.cpu_count()) as pool:
        futures = {pool.submit(control_task, spec, work[i]): i for i in todo}
        for done, future in enumerate(as_completed(futures), 1):
            pd.to_pickle(future.result(), parts / f"{key[futures[future]]}.pkl")
            if done % max(1, len(todo) // 5) == 0:
                report(f"📊 Portão da vegetação: {done}/{len(todo)} séries")
    results = [pd.read_pickle(parts / f"{key[i]}.pkl") for i in key]
    pd.concat([r["descritores"] for r in results], ignore_index=True).to_csv(
        out / "descritores.csv", index=False)
    pd.concat([r["smap"] for r in results if r["smap"] is not None], ignore_index=True).to_csv(
        out / "smap.csv", index=False)
    (out / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2, default=str))
    (out / "execucao.json").write_text(json.dumps({
        "commit": _git_commit(), "hash": gate_hash(spec), "series": len(work),
        "finished_utc": datetime.now(UTC).isoformat(timespec="seconds")}, indent=2))
    return out
