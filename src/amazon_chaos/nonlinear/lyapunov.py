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
