"""Gate F4: os descritores pré-registrados distinguem caos de nulos lineares?

Roda `suite.surrogate_suite` em cada controle sintético × comprimento × ruído ×
repetição, com os parâmetros de `configs/analysis/descriptors.yaml`, e grava uma linha
por descritor. O veredito (`verdict`) aplica o critério pré-registrado em `gate.criterion`.
Chamado por `amazon-chaos gate run` (local ou `scripts/hpc/gate.sbatch`).
"""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import subprocess
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest

from amazon_chaos.nonlinear.suite import ews_test, gate_hash, surrogate_suite
from amazon_chaos.nonlinear.synthetic import ar1, control

GATE_DIR = Path("data/processed/gate")


def tasks(spec: dict) -> list[dict]:
    g = spec["gate"]
    kinds = [(k, "positivo") for k in g["positive"]] + [(k, "negativo") for k in g["negative"]]
    return [{"control": k, "group": grp, "n": n, "noise": noise, "rep": rep}
            for (k, grp), n, noise, rep in itertools.product(
                kinds, g["lengths"], g["noise"], range(g["repetitions"]))]


def _seed(spec, task):
    """Semente própria por tarefa, derivada do texto inteiro da chave (SHA-256)."""
    parts = (spec["gate"]["seed"], task["control"], task["n"], task.get("noise", 0), task["rep"])
    key = "|".join(map(str, parts))
    return int.from_bytes(hashlib.sha256(key.encode()).digest()[:4], "little")


def run_task(spec: dict, task: dict) -> pd.DataFrame:
    seed = _seed(spec, task)
    x = control(task["control"], task["n"], seed=seed, noise=task["noise"])
    try:
        result = surrogate_suite(x, spec, seed=seed)
        return result.table(**task)
    except ValueError as error:  # série inadequada para algum descritor: registrado
        return pd.DataFrame([{**task, "descriptor": "erro", "error": str(error)}])


def ews_tasks(spec: dict) -> list[dict]:
    g = spec["gate"]
    return [{"control": kind, "n": 8766, "rep": rep}
            for kind in ("ar1_estacionario", "ar1_rampa") for rep in range(g["repetitions"])]


def run_ews_task(spec: dict, task: dict) -> pd.DataFrame:
    """AR(1) estacionário (nulo verdadeiro) e com φ subindo de 0,2 a 0,95 (slowing down)."""
    seed = _seed(spec, task)
    n = task["n"]
    if task["control"] == "ar1_estacionario":
        x = ar1(phi=0.6, n=n + 512, seed=seed)[512:]
    else:
        rng = np.random.default_rng(seed)
        phi = np.linspace(0.2, 0.95, n)
        x = np.zeros(n)
        for i in range(1, n):
            x[i] = phi[i] * x[i - 1] + rng.normal()
    return ews_test(x, spec, seed=seed).assign(**task)


def _git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "desconhecido"


def run_gate(spec: dict, workers: int | None = None, quick: bool = False,
             progress=print) -> Path:
    """Executa o gate e grava `data/processed/gate/<hash>/` (resultados e proveniência)."""
    if quick:  # só para testar o código: nunca usado como resultado
        spec = json.loads(json.dumps(spec, default=str))
        spec["gate"].update(lengths=[1024], noise=[0.0], repetitions=2)
        spec["surrogates"]["per_cell"] = 9
        spec["ews"]["surrogates"] = 9
    out = GATE_DIR / (("quick_" if quick else "") + gate_hash(spec))
    out.mkdir(parents=True, exist_ok=True)
    work = tasks(spec)
    workers = workers or os.cpu_count()
    frames = []
    with ProcessPoolExecutor(workers) as pool:
        futures = [pool.submit(run_task, spec, t) for t in work]
        ews_futures = [pool.submit(run_ews_task, spec, t) for t in ews_tasks(spec)]
        for i, future in enumerate(futures, 1):
            frames.append(future.result())
            if i % max(1, len(futures) // 10) == 0:
                progress(f"gate: {i}/{len(futures)} séries")
        ews = pd.concat([f.result() for f in ews_futures], ignore_index=True)
    results = pd.concat(frames, ignore_index=True)
    results.to_csv(out / "descritores.csv", index=False)
    ews.to_csv(out / "ews.csv", index=False)
    (out / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2, default=str))
    (out / "execucao.json").write_text(json.dumps({
        "commit": _git_commit(), "hash": gate_hash(spec), "quick": quick,
        "workers": workers, "series": len(work),
        "finished_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }, indent=2))
    return out


def _seasonal_variants(x, period=365, smooth=15):
    """Anomalia (sem média sazonal), padronizada (÷ desvio sazonal) e padronizada sem tendência."""
    from scipy.ndimage import gaussian_filter1d

    phase = np.arange(len(x)) % period
    anomaly = x - pd.Series(x).groupby(phase).transform("mean").to_numpy()
    var = pd.Series(anomaly**2).groupby(phase).mean().to_numpy()
    standardized = anomaly / np.sqrt(gaussian_filter1d(var, smooth, mode="wrap"))[phase]
    t = np.arange(len(x))
    detrended = standardized - np.polyval(np.polyfit(t, standardized, 1), t)
    return {"anomalia": anomaly, "padronizada": standardized,
            "padronizada+sem tendência": detrended}


def _standardization_task(spec, kind, rep, names):
    x = control(kind, 8766, seed=1000 + rep, noise=0.2)
    rows = []
    for variant, series in _seasonal_variants(x).items():
        result = surrogate_suite(series, spec, n_surrogates=39, seed=rep, names=names)
        rows += [{"controle": kind, "variante": variant, "descritor": k,
                  "rejeita": p <= spec["surrogates"]["alpha"]} for k, p in result.pvalues.items()]
    return rows


def standardization_check(spec: dict, workers: int | None = None, repetitions: int = 10,
                          names=("d2", "lyapunov", "pe_complexity", "rqa_det")) -> pd.DataFrame:
    """Falso positivo por variância sazonal: anomalia × padronizada × sem tendência.

    Reproduz o teste que motivou a anomalia padronizada no pré-registro (D-010):
    `padronizacao.csv` na pasta do gate. Leva cerca de 1 h em 10 núcleos.
    """
    jobs = [(k, r) for k in ["seasonal_trend", "sine_noise", "lorenz", "ar1"]
            for r in range(repetitions)]
    with ProcessPoolExecutor(workers or os.cpu_count()) as pool:
        parts = pool.map(_standardization_task, *zip(*[(spec, k, r, list(names))
                                                        for k, r in jobs], strict=True))
        rows = [row for part in parts for row in part]
    frame = pd.DataFrame(rows)
    return (frame.groupby(["controle", "variante", "descritor"]).rejeita
            .agg(taxa="mean", repeticoes="size").reset_index())


def rejection_rates(results: pd.DataFrame, alpha: float) -> pd.DataFrame:
    """Fração de repetições que rejeitam H0, com IC 95% exato (Clopper–Pearson)."""
    ok = results[results.descriptor != "erro"].copy()
    ok["reject"] = ok.pvalue <= alpha
    rows = []
    for key, group in ok.groupby(["descriptor", "control", "group", "n", "noise"]):
        k, total = int(group.reject.sum()), int(group.pvalue.notna().sum())
        ci = binomtest(k, total).proportion_ci() if total else None
        rows.append(dict(zip(["descriptor", "control", "group", "n", "noise"], key, strict=True),
                         rejections=k, total=total, rate=k / total if total else np.nan,
                         ci_low=ci.low if ci else np.nan, ci_high=ci.high if ci else np.nan))
    return pd.DataFrame(rows)


def verdict(rates: pd.DataFrame, spec: dict) -> pd.DataFrame:
    """Critério pré-registrado, avaliado no maior comprimento e no maior ruído do gate."""
    g = spec["gate"]
    c = g["criterion"]
    final = rates[(rates.n == max(g["lengths"])) & (rates.noise == max(g["noise"]))]
    rows = []
    for name, group in final.groupby("descriptor"):
        pos = group[group.group == "positivo"].set_index("control").rate
        size = group[group.control.isin(c["size_controls"])].set_index("control").rate
        powered = int((pos >= c["power"]).sum())
        passed = powered >= c["positives_required"] and bool((size <= c["size"]).all())
        alert = group[group.control == "seasonal_trend"].rate
        rows.append({"descriptor": name, "positivos com poder": f"{powered}/{len(pos)}",
                     **{f"poder {k}": v for k, v in pos.items()},
                     **{f"rejeição {k}": v for k, v in size.items()},
                     "rejeição seasonal_trend": float(alert.iloc[0]) if len(alert) else np.nan,
                     "passa": passed})
    return pd.DataFrame(rows)
