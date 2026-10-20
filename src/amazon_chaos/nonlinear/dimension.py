"""Dimensão de correlação D2 (Grassberger e Procaccia, 1983), com janela de Theiler.

C(r) é a fração de pares (fora da janela de Theiler) a distância ≤ r; D2 é a inclinação
de ln C × ln r na região de escala. Com cerca de 9 mil pontos e ruído, um platô estável ao
aumentar m é raro: sem platô, D2 não é interpretado como dimensão do atrator. A janela
de C usada no ajuste é pré-registrada (D-010).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree

from amazon_chaos.nonlinear.embedding import _finite, delay_embedding


@dataclass(frozen=True)
class D2Result:
    dimensions: np.ndarray
    d2: np.ndarray  # inclinação na janela de C, uma por dimensão
    radii: np.ndarray  # (n_dim, n_radii)
    correlation: np.ndarray  # C(r), (n_dim, n_radii)
    window: tuple[float, float]


def correlation_sum(vectors: np.ndarray, radii: np.ndarray, theiler: int) -> np.ndarray:
    """C(r) para cada raio, sem a diagonal e sem pares com |i − j| ≤ theiler."""
    n = len(vectors)
    tree = cKDTree(vectors)
    ordered = tree.count_neighbors(tree, radii).astype(float)  # pares ordenados, com i = j
    near = np.zeros(len(radii))
    for k in range(1, theiler + 1):
        d = np.sort(np.linalg.norm(vectors[k:] - vectors[:-k], axis=1))
        near += 2 * np.searchsorted(d, radii, side="right")
    m = n - theiler - 1
    pairs = m * (m + 1)  # pares ordenados fora da janela
    return (ordered - n - near) / pairs


def correlation_dimension(series, dimensions, delay: int, theiler: int, *,
                          window: tuple[float, float] = (1e-4, 1e-2),
                          n_radii: int = 40) -> D2Result:
    """D2 por dimensão de imersão, ajustado onde C(r) está dentro de `window`."""
    x = _finite(series)
    dims = np.asarray(list(dimensions))
    radii_all, c_all, d2 = [], [], []
    for m in dims:
        vectors = delay_embedding(x, int(m), delay)
        rng = np.random.default_rng(0)
        sample = vectors[rng.integers(0, len(vectors), (2, 50_000))]
        spread = np.linalg.norm(sample[0] - sample[1], axis=1)
        spread = spread[spread > 0]
        radii = np.geomspace(np.quantile(spread, 1e-5), np.quantile(spread, 0.5), n_radii)
        c = correlation_sum(vectors, radii, theiler)
        inside = (c >= window[0]) & (c <= window[1])
        if inside.sum() >= 3:
            slope = np.polyfit(np.log(radii[inside]), np.log(c[inside]), 1)[0]
        else:
            slope = np.nan
        radii_all.append(radii)
        c_all.append(c)
        d2.append(slope)
    return D2Result(dims, np.array(d2), np.array(radii_all), np.array(c_all), window)
