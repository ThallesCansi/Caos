"""Análise de quantificação de recorrência (RQA; Marwan et al., 2007).

O limiar ε é escolhido para uma **taxa de recorrência fixa** (padrão 5%), e não como uma
distância fixa: assim séries de amplitudes diferentes ficam comparáveis. A matriz de
recorrência nunca é montada inteira; só os pares recorrentes (cKDTree), o que cabe na
memória para cerca de 9 mil vetores. Pares dentro da janela de Theiler, incluindo a
diagonal principal, são excluídos.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from scipy.spatial import cKDTree

from amazon_chaos.nonlinear.embedding import _finite, delay_embedding


@dataclass(frozen=True)
class RQAResult:
    rr: float  # taxa de recorrência efetiva
    det: float  # fração de pontos recorrentes em diagonais ≥ lmin
    l_mean: float
    l_max: int
    entr: float  # entropia de Shannon das diagonais ≥ lmin (nats)
    lam: float  # fração em verticais ≥ vmin
    tt: float  # comprimento médio das verticais ≥ vmin
    epsilon: float
    vectors: int

    def as_dict(self):
        return asdict(self)


def _runs(groups: np.ndarray, positions: np.ndarray) -> np.ndarray:
    """Comprimentos de sequências consecutivas de `positions` dentro de cada grupo.

    As entradas precisam estar ordenadas por (grupo, posição).
    """
    if not len(groups):
        return np.zeros(0, dtype=int)
    breaks = np.ones(len(groups), dtype=bool)
    breaks[1:] = (groups[1:] != groups[:-1]) | (positions[1:] != positions[:-1] + 1)
    starts = np.flatnonzero(breaks)
    return np.diff(np.append(starts, len(groups)))


def _off_window_pairs(n: int, theiler: int) -> int:
    """Pares não ordenados (i < j) com j − i > theiler."""
    m = n - theiler - 1
    return m * (m + 1) // 2 if m > 0 else 0


def recurrence_threshold(vectors: np.ndarray, rate: float, theiler: int,
                         sample: int = 200_000, seed: int = 0) -> float:
    """ε cuja fração de pares (fora da janela de Theiler) com distância ≤ ε é `rate`."""
    n = len(vectors)
    rng = np.random.default_rng(seed)
    i = rng.integers(0, n, sample)
    j = rng.integers(0, n, sample)
    ok = np.abs(i - j) > theiler
    d = np.linalg.norm(vectors[i[ok]] - vectors[j[ok]], axis=1)
    return float(np.quantile(d, rate))


def rqa(series, dimension: int, delay: int, *, rate: float = 0.05, theiler: int = 1,
        lmin: int = 2, vmin: int = 2, seed: int = 0) -> RQAResult:
    """Medidas de RQA de uma série reconstruída com (dimension, delay)."""
    if not 0 < rate < 0.5:
        raise ValueError("rate deve estar entre 0 e 0,5")
    vectors = delay_embedding(_finite(series), dimension, delay)
    n = len(vectors)
    epsilon = recurrence_threshold(vectors, rate, theiler, seed=seed)
    pairs = cKDTree(vectors).query_pairs(epsilon, output_type="ndarray")
    if len(pairs):
        pairs = pairs[pairs[:, 1] - pairs[:, 0] > theiler]
    total = len(pairs)
    rr = total / max(_off_window_pairs(n, theiler), 1)
    if total == 0:
        return RQAResult(rr, np.nan, np.nan, 0, np.nan, np.nan, np.nan, epsilon, n)

    # Diagonais: no triângulo superior (a matriz é simétrica), agrupadas por j − i.
    i, j = pairs[:, 0], pairs[:, 1]
    offset = j - i
    order = np.lexsort((i, offset))
    diagonals = _runs(offset[order], i[order])
    long_d = diagonals[diagonals >= lmin]
    det = long_d.sum() / total
    if len(long_d):
        counts = np.bincount(long_d)[lmin:]
        p = counts[counts > 0] / counts.sum()
        entr = float(-np.sum(p * np.log(p)))
        l_mean, l_max = float(long_d.mean()), int(long_d.max())
    else:
        entr, l_mean, l_max = np.nan, np.nan, 0

    # Verticais: precisam dos dois triângulos (coluna j com linhas i consecutivas).
    rows = np.concatenate([i, j])
    cols = np.concatenate([j, i])
    order = np.lexsort((rows, cols))
    verticals = _runs(cols[order], rows[order])
    long_v = verticals[verticals >= vmin]
    lam = long_v.sum() / (2 * total)
    tt = float(long_v.mean()) if len(long_v) else np.nan
    return RQAResult(float(rr), float(det), l_mean, l_max, entr, float(lam), tt, epsilon, n)
