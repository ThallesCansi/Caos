"""Maior expoente de Lyapunov pelo método de Rosenstein et al. (1993).

Para cada vetor reconstruído, toma o vizinho mais próximo fora da janela de Theiler e
acompanha ⟨ln d(k)⟩, a distância média (em log) após k passos. Num sistema caótico a
curva sobe linearmente até saturar; λ₁ é a inclinação na região de ajuste, que precisa
ser fixada antes de olhar os dados reais (D-010). Uma inclinação positiva também aparece
em processos estocásticos (AR(1)), por isso o valor só é interpretado contra substitutas.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree

from amazon_chaos.nonlinear.embedding import _finite, delay_embedding, temporal_neighbors


@dataclass(frozen=True)
class LyapunovResult:
    exponent: float  # por unidade de `dt`
    divergence: np.ndarray  # ⟨ln d(k)⟩, k = 0…max_steps
    fit: tuple[int, int]  # passos inicial e final do ajuste, inclusivos
    intercept: float
    r2: float
    pairs: int


def divergence_curve(series, dimension: int, delay: int, theiler: int,
                     max_steps: int) -> tuple[np.ndarray, int]:
    """⟨ln d(k)⟩ para k = 0…max_steps e o número de pares de vizinhos usados."""
    x = _finite(series)
    vectors = delay_embedding(x, dimension, delay)
    n = len(vectors)
    if n <= max_steps + 2 * theiler + 10:
        raise ValueError("Série curta demais para max_steps e a janela de Theiler")
    neighbor, dist = temporal_neighbors(vectors, theiler)
    keep = dist > 0
    i = np.flatnonzero(keep)
    j = neighbor[keep]
    curve = np.empty(max_steps + 1)
    for k in range(max_steps + 1):
        ok = (i + k < n) & (j + k < n)
        d = np.linalg.norm(vectors[i[ok] + k] - vectors[j[ok] + k], axis=1)
        d = d[d > 0]
        curve[k] = np.mean(np.log(d)) if len(d) else np.nan
    return curve, len(i)


def rosenstein(series, dimension: int, delay: int, theiler: int, *,
               fit: tuple[int, int], max_steps: int | None = None,
               dt: float = 1.0) -> LyapunovResult:
    """λ₁ como inclinação de ⟨ln d(k)⟩ × k·dt entre os passos `fit` (inclusivos)."""
    first, last = fit
    if not 0 <= first < last:
        raise ValueError("fit deve ser (início, fim) com início < fim")
    max_steps = max(last, max_steps or last)
    curve, pairs = divergence_curve(series, dimension, delay, theiler, max_steps)
    k = np.arange(first, last + 1)
    y = curve[first : last + 1]
    slope, intercept = np.polyfit(k * dt, y, 1)
    residual = y - (slope * k * dt + intercept)
    total = np.sum((y - y.mean()) ** 2)
    r2 = 1 - np.sum(residual**2) / total if total > 0 else np.nan
    return LyapunovResult(float(slope), curve, (first, last), float(intercept), float(r2),
                          pairs)


def largest_lyapunov(series, dimension: int, delay: int, theiler: int,
                     fit: tuple[int, int], dt: float = 1.0) -> float:
    """Atalho que devolve só λ₁, para uso como estatística de teste com substitutas."""
    return rosenstein(series, dimension, delay, theiler, fit=fit, dt=dt).exponent


# ── Kantz e Wolf, ao lado de Rosenstein (F2d, D-027) ────────────────────────

KANTZ_QUANTILES = (0.01, 0.02, 0.05, 0.10)


def pair_distance_quantiles(vectors: np.ndarray, theiler: int, quantiles,
                            pairs: int = 200_000, seed: int = 0) -> np.ndarray:
    """Quantis das distâncias entre pares fora da janela de Theiler, por amostra de pares."""
    rng = np.random.default_rng(seed)
    n = len(vectors)
    i, j = rng.integers(0, n, pairs), rng.integers(0, n, pairs)
    ok = np.abs(i - j) > theiler
    d = np.linalg.norm(vectors[i[ok]] - vectors[j[ok]], axis=1)
    return np.quantile(d, quantiles)


def kantz_curve(vectors: np.ndarray, radius: float, theiler: int, max_steps: int,
                min_neighbors: int = 5) -> tuple[np.ndarray, int]:
    """S(k) = ⟨ln da distância média, após k passos, a todos os vizinhos dentro do raio⟩."""
    n = len(vectors) - max_steps
    tree = cKDTree(vectors[:n])
    sums = np.zeros((n, max_steps + 1))
    counts = np.zeros(n)
    for i, found in enumerate(tree.query_ball_point(vectors[:n], radius)):
        j = np.asarray(found, dtype=int)
        j = j[np.abs(j - i) > theiler]
        if len(j) < min_neighbors:
            continue
        counts[i] = len(j)
        for k in range(max_steps + 1):
            sums[i, k] = np.linalg.norm(vectors[j + k] - vectors[i + k], axis=1).mean()
    used = counts > 0
    if not used.any():
        return np.full(max_steps + 1, np.nan), 0
    with np.errstate(divide="ignore"):
        logs = np.log(sums[used])
    logs[~np.isfinite(logs)] = np.nan
    return np.nanmean(logs, axis=0), int(used.sum())


def kantz(series, dimension: int, delay: int, theiler: int, *, quantile: float = 0.02,
          fit: tuple[int, int] = (0, 5), seed: int = 0) -> float:
    """λ de Kantz (1994): inclinação de S(k) em `fit`, no raio do quantil `quantile`."""
    vectors = delay_embedding(_finite(series), dimension, delay)
    radius = pair_distance_quantiles(vectors, theiler, [quantile], seed=seed)[0]
    curve, _ = kantz_curve(vectors, radius, theiler, fit[1])
    k = np.arange(fit[0], fit[1] + 1)
    y = curve[fit[0] : fit[1] + 1]
    return float(np.polyfit(k, y, 1)[0]) if np.isfinite(y).all() else np.nan


def wolf(series, dimension: int, delay: int, theiler: int, *, evolve: int = 3,
         max_scale: float = 0.10, min_scale: float = 0.001, angle: float = 0.3,
         max_angle: float = 1.2) -> float:
    """λ de Wolf et al. (1985), com tempo de evolução fixo, por passo.

    Um par (fiducial, vizinho) é evoluído `evolve` passos e soma ln(d_final/d_inicial).
    Se a distância final passar de `max_scale` × diâmetro (diagonal da caixa do atrator
    reconstruído), o vizinho é trocado pelo ponto mais próximo do fiducial entre
    `min_scale` e `max_scale` × diâmetro, fora da janela de Theiler, com ângulo menor que
    `angle` em relação à separação antiga; sem candidato, o ângulo é relaxado em degraus de
    0,3 rad até `max_angle`, e, se ainda faltar, o vizinho evoluído é mantido.
    """
    vectors = delay_embedding(_finite(series), dimension, delay)
    n = len(vectors)
    diameter = float(np.linalg.norm(vectors.max(axis=0) - vectors.min(axis=0)))
    low, high = min_scale * diameter, max_scale * diameter
    tree = cKDTree(vectors)

    def candidates(i, radius):
        j = np.asarray(tree.query_ball_point(vectors[i], radius), dtype=int)
        j = j[(np.abs(j - i) > theiler) & (j + evolve < n)]
        d = np.linalg.norm(vectors[j] - vectors[i], axis=1)
        keep = d > low
        return j[keep], d[keep]

    j, d = candidates(0, diameter)
    if not len(j):
        return np.nan
    i, j = 0, int(j[np.argmin(d)])
    total, steps = 0.0, 0
    while i + evolve < n and j + evolve < n:
        start = np.linalg.norm(vectors[j] - vectors[i])
        i, j = i + evolve, j + evolve
        sep = vectors[j] - vectors[i]
        end = np.linalg.norm(sep)
        if start > 0 and end > 0:
            total += np.log(end / start)
            steps += evolve
        if end <= high or i + evolve >= n:
            continue
        cand, dist = candidates(i, high)
        if not len(cand):
            continue
        cosine = ((vectors[cand] - vectors[i]) @ sep) / (dist * end)
        angles = np.arccos(np.clip(cosine, -1, 1))
        limit = angle
        while limit <= max_angle + 1e-9:
            ok = angles < limit
            if ok.any():
                j = int(cand[ok][np.argmin(dist[ok])])
                break
            limit += 0.3
    return total / steps if steps else np.nan
