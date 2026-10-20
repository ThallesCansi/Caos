"""Reconstrução por atrasos (Takens) e escolha de τ (AMI) e m (falsos vizinhos)."""

from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree


def delay_embedding(series: np.ndarray, dimension: int, delay: int) -> np.ndarray:
    """Takens-style delay embedding with shape (n_vectors, dimension)."""
    x = np.asarray(series, dtype=float)
    if x.ndim != 1:
        raise ValueError("series must be one-dimensional")
    if dimension < 1 or delay < 1:
        raise ValueError("dimension and delay must be positive integers")
    n_vectors = len(x) - (dimension - 1) * delay
    if n_vectors <= 0:
        raise ValueError("series is too short for requested embedding")
    return np.column_stack([x[i * delay : i * delay + n_vectors] for i in range(dimension)])


def _finite(series) -> np.ndarray:
    x = np.asarray(series, dtype=float)
    if x.ndim != 1 or not np.isfinite(x).all():
        raise ValueError("Série unidimensional e sem lacunas requerida")
    return x


def temporal_neighbors(vectors: np.ndarray, theiler: int):
    """Vizinho mais próximo de cada vetor fora da janela de Theiler |i − j| ≤ `theiler`.

    Basta pedir 2·theiler + 2 vizinhos: no máximo 2·theiler + 1 pontos (o próprio incluso)
    caem na janela, então ao menos um candidato está fora dela.
    """
    n = len(vectors)
    k = min(n, 2 * theiler + 2)
    dist, idx = cKDTree(vectors).query(vectors, k=k)
    allowed = np.abs(idx - np.arange(n)[:, None]) > theiler
    if not allowed.any(axis=1).all():
        raise ValueError("Série curta demais para esta janela de Theiler")
    col = allowed.argmax(axis=1)
    rows = np.arange(n)
    return idx[rows, col], dist[rows, col]


def average_mutual_information(series, max_lag: int, bins: int | None = None) -> np.ndarray:
    """Informação mútua média I(x_t; x_{t+τ}) em nats, τ = 0…max_lag (Fraser e Swinney, 1986).

    Caixas equiprováveis (por quantis), robustas a caudas; padrão: regra de Sturges.
    """
    x = _finite(series)
    n = len(x)
    if not 1 <= max_lag < n // 2:
        raise ValueError("max_lag deve estar entre 1 e metade da série")
    bins = bins or int(np.ceil(np.log2(n) + 1))
    edges = np.quantile(x, np.linspace(0, 1, bins + 1)[1:-1])
    codes = np.searchsorted(edges, x, side="right")
    out = np.empty(max_lag + 1)
    for lag in range(max_lag + 1):
        a, b = codes[: n - lag], codes[lag:]
        joint = np.bincount(a * bins + b, minlength=bins * bins).reshape(bins, bins) / len(a)
        outer = joint.sum(1)[:, None] * joint.sum(0)[None, :]
        nz = joint > 0
        out[lag] = float(np.sum(joint[nz] * np.log(joint[nz] / outer[nz])))
    return out


def ami_delay(series, max_lag: int = 60, bins: int | None = None) -> int:
    """τ = menor valor entre o primeiro mínimo local da AMI e o primeiro τ com AMI < AMI(0)/e.

    Só o mínimo local falha em mapas: a AMI decai devagar e o "mínimo" cai no ruído de
    estimativa (τ = 8 no logístico). O critério 1/e limita esse caso; em fluxos (Lorenz,
    clima diário) o mínimo local costuma vir antes e prevalece.
    """
    ami = average_mutual_information(series, max_lag, bins)
    candidates = [lag for lag in range(1, max_lag)
                  if ami[lag] < ami[lag - 1] and ami[lag] <= ami[lag + 1]][:1]
    below = np.flatnonzero(ami < ami[0] / np.e)
    candidates += [int(below[0])] if len(below) else []
    if not candidates:
        raise ValueError(f"A AMI não cai até τ = {max_lag}; aumente max_lag")
    return int(max(1, min(candidates)))


def false_nearest_neighbors(series, delay: int, max_dimension: int = 10, *,
                            rtol: float = 10.0, atol: float = 2.0,
                            theiler: int = 0) -> np.ndarray:
    """Fração de falsos vizinhos para m = 1…max_dimension (Kennel et al., 1992).

    Um vizinho é falso se, ao acrescentar a coordenada x_{i+mτ}, a distância cresce mais de
    `rtol` vezes ou passa de `atol` desvios-padrão da série.
    """
    x = _finite(series)
    sd = x.std()
    fractions = []
    for m in range(1, max_dimension + 1):
        n = len(x) - m * delay
        if n < 2 * theiler + 10:
            raise ValueError("Série curta demais para max_dimension e delay pedidos")
        vectors = delay_embedding(x, m, delay)[:n]
        following = x[m * delay : m * delay + n]
        j, d = temporal_neighbors(vectors, theiler)
        ok = d > 0
        i = np.flatnonzero(ok)
        gap = np.abs(following[i] - following[j[ok]])
        false = (gap / d[ok] > rtol) | (np.sqrt(d[ok] ** 2 + gap**2) / sd > atol)
        fractions.append(float(false.mean()))
    return np.array(fractions)


def fnn_dimension(series, delay: int, max_dimension: int = 10, threshold: float = 0.05,
                  theiler: int = 0) -> int:
    """Menor m com fração de falsos vizinhos abaixo de `threshold`.

    Com ruído, a fração pode nunca cair: devolve então o m de menor fração, e quem chama
    deve tratar isso como indício de dinâmica estocástica, não como dimensão do atrator.
    """
    fractions = false_nearest_neighbors(series, delay, max_dimension, theiler=theiler)
    below = np.flatnonzero(fractions < threshold)
    return int(below[0] + 1) if len(below) else int(np.argmin(fractions) + 1)
