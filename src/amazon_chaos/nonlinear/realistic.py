"""Gate com nulas realistas e os estimadores novos nos controles (F2f, F2d, F2g e F2h; D-027).

Relatado ao lado do gate congelado (`1c2fb37657`), sem substituí-lo. Duas partes:

- nulas: as quatro de `synthetic.REALISTIC`, ajustadas na série média de cada bacia ×
  variável (t2m, VPD) em 1991–2020, simuladas em 1990–2024, passadas pela anomalia
  padronizada e cortadas em 2001–2024; 20 repetições por nula × ajuste, sem ruído de
  observação. Os oito descritores pré-registrados com 39 IAAFT, mais Wolf, Kantz e Cao
  (`estimators.extra_suite`) e o S-map (`smap.smap_series`);
- controles: as séries do gate (`gate.tasks`, mesmas sementes), só com os estimadores novos,
  já que os oito descritores estão no gate congelado.

Chamado por `amazon-chaos gate realistic` (`scripts/hpc/gate_realista.sbatch`).
"""

from __future__ import annotations

import hashlib
import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from amazon_chaos.nonlinear import estimators, smap
from amazon_chaos.nonlinear import synthetic as S
from amazon_chaos.nonlinear.batch import NORMAL
from amazon_chaos.nonlinear.gate import GATE_DIR, _git_commit, tasks
from amazon_chaos.nonlinear.gate import _seed as gate_seed
from amazon_chaos.nonlinear.suite import embedding_parameters, spec_hash, surrogate_suite
from amazon_chaos.regional import standardized_anomalies

RULES = {"version": 1, "nulls": list(S.REALISTIC), "garch": S.GARCH,
         "fits": {"regions": ["xingu", "tapajos"], "variables": ["t2m", "vpd"],
                  "period": ["1991-01-01", "2020-12-31"]},
         "simulation": ["1990-01-01", "2024-12-31"], "window": ["2001-01-01", "2024-12-31"],
         "repetitions": 20, "surrogates": 39, "noise": 0.0,
         "estimators": estimators.RULES, "smap": smap.RULES}


def realistic_hash(spec) -> str:
    return spec_hash({"rules": RULES, "embedding": spec["embedding"],
                      "descriptors": spec["descriptors"], "surrogates": spec["surrogates"],
                      "gate_seed": spec["gate"]["seed"]})


def output_dir(spec) -> Path:
    return GATE_DIR / f"realista_{realistic_hash(spec)}"


def fits(load=None) -> dict[str, dict]:
    """Parâmetros das nulas por bacia × variável, das séries médias das bacias."""
    from amazon_chaos.config import load_region
    from amazon_chaos.regional import regional_frame, summarize

    out = {}
    for slug in RULES["fits"]["regions"]:
        frame = regional_frame(summarize(load_region(slug))) if load is None else load(slug)
        for var in RULES["fits"]["variables"]:
            out[f"{slug}_{var}"] = S.fit_realistic(frame[var], tuple(RULES["fits"]["period"]))
    return out


def null_series(kind: str, params: dict, seed: int) -> np.ndarray:
    raw = S.simulate_realistic(kind, params, seed, *RULES["simulation"])
    z, _ = standardized_anomalies(raw, NORMAL)
    return z.loc[RULES["window"][0]:RULES["window"][1]].to_numpy(dtype=float)


def _smap_rows(x, params, labels):
    return smap.smap_series(x, params["m"], params["tau"], params["theiler"]).assign(
        **labels, **params)


def null_task(spec: dict, kind: str, fit: str, params: dict, rep: int) -> dict:
    task = {"control": f"{kind}|{fit}", "n": 8766, "noise": 0.0, "rep": rep}
    seed = gate_seed(spec, task)
    labels = {"group": "nula", "control": kind, "fit": fit, "n": 8766, "noise": 0.0,
              "rep": rep}
    x = null_series(kind, params, seed)
    try:
        suite = surrogate_suite(x, spec, n_surrogates=RULES["surrogates"], seed=seed)
        p = suite.params
        desc = pd.concat([suite.table(**labels),
                          estimators.extra_suite(x, p, RULES["surrogates"], seed, spec,
                                                 **labels)], ignore_index=True)
        return {"descritores": desc, "smap": _smap_rows(x, p, labels)}
    except (ValueError, np.linalg.LinAlgError) as error:
        return {"descritores": pd.DataFrame([{**labels, "descriptor": "erro",
                                              "error": str(error)}]), "smap": None}


def control_task(spec: dict, task: dict) -> dict:
    seed = gate_seed(spec, task)
    labels = {"group": "positivo" if task["control"] in S.POSITIVE else "negativo", **task}
    x = S.control(task["control"], task["n"], seed=seed, noise=task["noise"])
    try:
        p = embedding_parameters(x, spec)
        desc = estimators.extra_suite(x, p, RULES["surrogates"], seed, spec, **labels)
        return {"descritores": desc, "smap": _smap_rows(x, p, labels)}
    except (ValueError, np.linalg.LinAlgError) as error:
        return {"descritores": pd.DataFrame([{**labels, "descriptor": "erro",
                                              "error": str(error)}]), "smap": None}


def _key(job) -> str:
    return hashlib.sha256(json.dumps(job, sort_keys=True).encode()).hexdigest()[:12]


def run(spec: dict, *, workers=None, report=print, quick=False) -> Path:
    """Executa (ou retoma, por tarefa) as nulas e os controles e consolida os resultados."""
    out = output_dir(spec)
    if quick:  # só para testar o código: nunca usado como resultado
        out = out.with_name("quick_" + out.name)
    parts = out / "partes"
    parts.mkdir(parents=True, exist_ok=True)
    params_path = out / "parametros.json"
    if not params_path.exists():
        params_path.write_text(json.dumps(fits(), indent=1))
    params = json.loads(params_path.read_text())
    reps = 1 if quick else RULES["repetitions"]
    jobs = [{"kind": "nula", "null": k, "fit": f, "rep": r}
            for k in S.REALISTIC for f in params for r in range(reps)]
    controls = tasks(spec)
    if quick:
        controls = [t for t in controls if t["n"] == min(t["n"] for t in controls)
                    and t["rep"] == 0 and t["noise"] == 0]
    jobs += [{"kind": "controle", **t} for t in controls]
    todo = [j for j in jobs if not (parts / f"{_key(j)}.pkl").exists()]
    report(f"🧪 Gate com nulas realistas (F2f): {len(todo)} de {len(jobs)} séries")
    started, done = datetime.now(UTC), 0
    with ProcessPoolExecutor(workers or os.cpu_count()) as pool:
        futures = {}
        for job in todo:
            if job["kind"] == "nula":
                f = pool.submit(null_task, spec, job["null"], job["fit"], params[job["fit"]],
                                job["rep"])
            else:
                f = pool.submit(control_task, spec, {k: v for k, v in job.items()
                                                     if k != "kind"})
            futures[f] = job
        for future in as_completed(futures):
            pd.to_pickle(future.result(), parts / f"{_key(futures[future])}.pkl")
            done += 1
            if done % max(1, len(todo) // 10) == 0 or done == len(todo):
                hours = (datetime.now(UTC) - started).total_seconds() / 3600
                report(f"📊 Gate realista (F2f): {done}/{len(todo)} séries "
                       f"({100 * done / len(todo):.0f}%) · {hours:.1f} h · faltam ≈ "
                       f"{hours / done * (len(todo) - done):.1f} h")
    results = [pd.read_pickle(parts / f"{_key(j)}.pkl") for j in jobs]
    desc = pd.concat([r["descritores"] for r in results], ignore_index=True)
    smaps = pd.concat([r["smap"] for r in results if r["smap"] is not None],
                      ignore_index=True)
    desc.to_csv(out / "descritores.csv", index=False)
    smaps.to_csv(out / "smap.csv", index=False)
    (out / "execucao.json").write_text(json.dumps({
        "commit": _git_commit(), "hash": realistic_hash(spec), "quick": quick,
        "series": len(jobs), "rules": RULES,
        "errors": int((desc.descriptor == "erro").sum()),
        "finished_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }, indent=2, ensure_ascii=False, default=str))
    return out


# ── leitura (cadernos 05 e 07) ──────────────────────────────────────────────


def load(spec, alpha: float | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(descritores, S-map) do gate realista, com a coluna `rejects` (p ≤ α)."""
    from amazon_chaos.nonlinear.results import TOLERANCE

    alpha = (alpha or spec["surrogates"]["alpha"]) + TOLERANCE
    out = output_dir(spec)
    desc = pd.read_csv(out / "descritores.csv")
    smaps = pd.read_csv(out / "smap.csv")
    desc["rejects"] = desc.pvalue <= alpha
    smaps["rejects"] = smaps.pvalue <= alpha
    return desc, smaps


def null_rates(spec, horizon: int = 1) -> pd.DataFrame:
    """Taxa de rejeição em cada nula realista (80 séries), com IC de Clopper–Pearson.

    Inclui o S-map (teste de Diebold–Mariano no horizonte `horizon`) como mais um descritor.
    """
    from scipy.stats import binomtest

    desc, smaps = load(spec)
    nulls = desc[(desc.group == "nula") & (desc.descriptor != "erro")]
    sm = smaps[(smaps.group == "nula") & (smaps.horizon == horizon)].assign(descriptor="smap")
    rows = []
    for (name, control), part in pd.concat([nulls, sm]).groupby(["descriptor", "control"]):
        k, n = int(part.rejects.sum()), int(part.pvalue.notna().sum())
        ci = binomtest(k, n).proportion_ci()
        rows.append({"descriptor": name, "control": control, "rejections": k, "total": n,
                     "rate": k / n, "ci_low": ci.low, "ci_high": ci.high})
    return pd.DataFrame(rows)
