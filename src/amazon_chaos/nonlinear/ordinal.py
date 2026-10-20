"""Padrões ordinais: entropia de permutação e complexidade estatística.

Bandt e Pompe (2002); plano complexidade–entropia de Rosso et al. (2007). Ruído branco
fica em H ≈ 1 e C ≈ 0; dinâmica determinística caótica, em H intermediário com C alto;
ruído correlacionado, numa faixa própria. A ordem (d) e o atraso são pré-registrados.
"""

from __future__ import annotations

import math

import numpy as np

from amazon_chaos.nonlinear.embedding import _finite, delay_embedding


def ordinal_distribution(series, order: int = 5, delay: int = 1) -> np.ndarray:
    """Probabilidade de cada um dos order! padrões ordinais (padrões ausentes valem zero)."""
    if not 2 <= order <= 8:
        raise ValueError("order deve estar entre 2 e 8")
    vectors = delay_embedding(_finite(series), order, delay)
    if len(vectors) < 5 * math.factorial(order):
        raise ValueError("Série curta para esta ordem: use pelo menos 5·order! pontos")
    ranks = np.argsort(vectors, axis=1, kind="stable")
    codes = ranks @ (order ** np.arange(order))
    _, counts = np.unique(codes, return_counts=True)
    p = np.zeros(math.factorial(order))
    p[: len(counts)] = counts / counts.sum()
    return p


def _shannon(p: np.ndarray) -> float:
    p = p[p > 0]
    return float(-np.sum(p * np.log(p)))


def permutation_entropy(series, order: int = 5, delay: int = 1) -> float:
    """Entropia de permutação normalizada, H ∈ [0, 1]."""
    p = ordinal_distribution(series, order, delay)
    return _shannon(p) / math.log(len(p))


def complexity_entropy(series, order: int = 5, delay: int = 1) -> tuple[float, float]:
    """(H, C): entropia normalizada e complexidade estatística de Jensen–Shannon."""
    p = ordinal_distribution(series, order, delay)
    n = len(p)
    uniform = np.full(n, 1 / n)
    h = _shannon(p) / math.log(n)
    js = _shannon((p + uniform) / 2) - _shannon(p) / 2 - _shannon(uniform) / 2
    q0 = -2 / ((n + 1) / n * math.log(n + 1) - 2 * math.log(2 * n) + math.log(n))
    return h, float(q0 * js * h)
