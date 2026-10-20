"""Conjunto pré-registrado de descritores, calculado da mesma forma em controles e dados.

`configs/analysis/descriptors.yaml` define as regras de τ, m e Theiler e os parâmetros de
cada descritor. `surrogate_suite` escolhe (τ, m, w) na série observada, gera as
substitutas uma só vez e calcula todos os descritores com esses mesmos parâmetros em cada
uma. Este é o motor do gate F4 e do lote por célula.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from amazon_chaos.config import load_config
from amazon_chaos.nonlinear.dimension import correlation_dimension
from amazon_chaos.nonlinear.embedding import ami_delay, fnn_dimension
from amazon_chaos.nonlinear.ews import ews_trends
from amazon_chaos.nonlinear.lyapunov import largest_lyapunov
from amazon_chaos.nonlinear.ordinal import complexity_entropy
from amazon_chaos.nonlinear.recurrence import rqa
from amazon_chaos.nonlinear.statistics import nonlinear_prediction_error, time_reversal_asymmetry
from amazon_chaos.nonlinear.surrogates import (
    iaaft_surrogate,
    monte_carlo_pvalue,
    phase_randomized_surrogate,
    validate_series,
)
from amazon_chaos.paths import project_root

SPEC_PATH = Path("configs/analysis/descriptors.yaml")


def load_spec(path: str | Path | None = None) -> dict:
    return load_config(Path(path) if path else project_root() / SPEC_PATH)


GATE_KEYS = ("embedding", "descriptors", "surrogates", "ews", "gate")


def spec_hash(spec: dict, keys: tuple[str, ...] | None = None) -> str:
    """Identificador curto e estável do pré-registro (ou só das seções `keys`)."""
    part = {k: spec[k] for k in keys} if keys else spec
    text = json.dumps(part, sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()[:10]


BATCH_KEYS = ("series", "embedding", "descriptors", "surrogates", "ews")


def batch_hash(spec: dict) -> str:
    """Hash só do que entra no cálculo por célula: famílias, células e exposição não o mudam."""
    return spec_hash(spec, BATCH_KEYS)


def gate_hash(spec: dict) -> str:
    """Hash só do que o gate usa: mudar séries, famílias ou exposição não o invalida."""
    return spec_hash(spec, GATE_KEYS)


def embedding_parameters(x: np.ndarray, spec: dict) -> dict[str, int]:
    """(τ, m, w) pelas regras pré-registradas, escolhidos na série observada."""
    rules = spec["embedding"]
    tau = ami_delay(x, rules["delay"]["max_lag"])
    theiler = max(rules["theiler"]["minimum"], tau)
    m = fnn_dimension(x, tau, rules["dimension"]["max_dimension"],
                      rules["dimension"]["threshold"], theiler=theiler)
    return {"tau": tau, "m": m, "theiler": max(rules["theiler"]["minimum"], tau * m)}


def descriptor_values(x: np.ndarray, params: dict, spec: dict,
                      names: list[str] | None = None) -> dict[str, float]:
    """Todos os descritores (ou `names`) com parâmetros fixos."""
    d = spec["descriptors"]
    tau, m, w = params["tau"], params["m"], params["theiler"]
    names = names or list(d)
    out: dict[str, float] = {}
    if "lyapunov" in names:
        out["lyapunov"] = largest_lyapunov(x, m, tau, w, tuple(d["lyapunov"]["fit"]))
    if {"rqa_det", "rqa_lam"} & set(names):
        r = rqa(x, m, tau, rate=d["rqa_det"]["rate"], theiler=w, lmin=d["rqa_det"]["lmin"],
                vmin=d["rqa_lam"]["vmin"])
        out["rqa_det"], out["rqa_lam"] = r.det, r.lam
    if "d2" in names:
        out["d2"] = float(correlation_dimension(x, [m], tau, w,
                                                window=tuple(d["d2"]["window"])).d2[0])
    if {"pe_entropy", "pe_complexity"} & set(names):
        h, c = complexity_entropy(x, d["pe_entropy"]["order"], d["pe_entropy"]["delay"])
        out["pe_entropy"], out["pe_complexity"] = h, c
    if "asymmetry" in names:
        out["asymmetry"] = time_reversal_asymmetry(x, d["asymmetry"]["lag"])
    if "prediction" in names:
        p = d["prediction"]
        out["prediction"] = nonlinear_prediction_error(
            x, dimension=m, delay=tau, horizon=p["horizon"], neighbors=p["neighbors"],
            theiler=w, train_fraction=p["train_fraction"])
    return {k: out[k] for k in names}


def surrogates(x: np.ndarray, n: int, *, method: str = "IAAFT", seed: int = 0,
               max_iter: int = 200):
    """Gera `n` substitutas reprodutíveis (FT ou IAAFT), uma por vez."""
    for child in np.random.SeedSequence(seed).spawn(n):
        rng = np.random.default_rng(child)
        if method == "IAAFT":
            yield iaaft_surrogate(x, rng, max_iter=max_iter).values
        elif method == "FT":
            yield phase_randomized_surrogate(x, rng)
        else:
            raise ValueError("method deve ser FT ou IAAFT")


@dataclass(frozen=True)
class SuiteResult:
    params: dict
    observed: dict[str, float]
    null: dict[str, np.ndarray]
    pvalues: dict[str, float]

    def table(self, **labels) -> pd.DataFrame:
        rows = []
        for name, value in self.observed.items():
            null = self.null[name]
            ok = null[np.isfinite(null)]
            sd = ok.std(ddof=1) if len(ok) > 1 else np.nan
            rows.append({**labels, **self.params, "descriptor": name, "observed": value,
                         "null_mean": ok.mean() if len(ok) else np.nan, "null_sd": sd,
                         "z": (value - ok.mean()) / sd if sd and np.isfinite(sd) else np.nan,
                         "pvalue": self.pvalues[name], "n_null": len(ok)})
        return pd.DataFrame(rows)


def surrogate_suite(series, spec: dict, *, n_surrogates: int | None = None,
                    seed: int | None = None, names: list[str] | None = None,
                    params: dict | None = None) -> SuiteResult:
    """Descritores observados, distribuições nulas e p de Monte Carlo de cada um."""
    x = validate_series(series, min_length=256)
    cfg = spec["surrogates"]
    n_surrogates = n_surrogates or cfg["per_cell"]
    seed = cfg["seed"] if seed is None else seed
    params = params or embedding_parameters(x, spec)
    observed = descriptor_values(x, params, spec, names)
    null = {k: [] for k in observed}
    for y in surrogates(x, n_surrogates, method=cfg["method"], seed=seed,
                        max_iter=cfg["max_iter"]):
        for k, v in descriptor_values(y, params, spec, list(observed)).items():
            null[k].append(v)
    null = {k: np.array(v, dtype=float) for k, v in null.items()}
    pvalues = {}
    for k, v in observed.items():
        finite = null[k][np.isfinite(null[k])]
        alternative = spec["descriptors"][k]["alternative"]
        pvalues[k] = (monte_carlo_pvalue(v, finite, alternative)
                      if np.isfinite(v) and len(finite) else np.nan)
    return SuiteResult(params, observed, null, pvalues)


def ews_test(series, spec: dict, *, seed: int | None = None) -> pd.DataFrame:
    """Tendência de Kendall da variância e do AR(1) contra substitutas IAAFT."""
    x = validate_series(series, min_length=256)
    cfg, base = spec["ews"], spec["surrogates"]
    seed = base["seed"] if seed is None else seed

    def trends(y):
        return ews_trends(y, cfg["window_fraction"], cfg["bandwidth"])

    observed = trends(x)
    null = [trends(y) for y in surrogates(x, cfg["surrogates"], method=base["method"],
                                          seed=seed, max_iter=base["max_iter"])]
    return pd.DataFrame([{
        "indicator": k, "tau": v,
        "pvalue": monte_carlo_pvalue(v, np.array([n[k] for n in null]), cfg["alternative"]),
    } for k, v in observed.items()])
