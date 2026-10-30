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


def _first_local_minimum(ami: np.ndarray) -> int | None:
    lags = [lag for lag in range(1, len(ami) - 1)
            if ami[lag] < ami[lag - 1] and ami[lag] <= ami[lag + 1]]
    return lags[0] if lags else None


def ami_first_minimum(series, max_lag: int = 60, bins: int | None = None) -> int | None:
    """Primeiro mínimo local da AMI até `max_lag`, sem o critério 1/e (F2a, D-027)."""
    return _first_local_minimum(average_mutual_information(series, max_lag, bins))


def ami_delay(series, max_lag: int = 60, bins: int | None = None) -> int:
    """τ = menor valor entre o primeiro mínimo local da AMI e o primeiro τ com AMI < AMI(0)/e.

    Só o mínimo local falha em mapas: a AMI decai devagar e o "mínimo" cai no ruído de
    estimativa (τ = 8 no logístico). O critério 1/e limita esse caso. Em fluxos amostrados
    finamente (Lorenz) o mínimo local costuma vir antes; nas anomalias diárias do clima, ao
    contrário, a AMI cai abaixo de 1/e já no primeiro dia e o critério 1/e prevalece (τ = 1),
    com o primeiro mínimo em 10 a 12 dias (F2a, D-027).
    """
    ami = average_mutual_information(series, max_lag, bins)
    first = _first_local_minimum(ami)
    candidates = [first] if first is not None else []
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


def _neighbors_max_norm(vectors: np.ndarray, theiler: int):
    """Vizinho mais próximo (norma do máximo) fora da janela de Theiler, como em Cao (1997)."""
    n = len(vectors)
    k = min(n, 2 * theiler + 2)
    dist, idx = cKDTree(vectors).query(vectors, k=k, p=np.inf)
    allowed = (np.abs(idx - np.arange(n)[:, None]) > theiler) & (dist > 0)
    if not allowed.any(axis=1).all():
        # pontos repetidos podem esgotar os k candidatos: busca mais longe só para eles
        dist, idx = cKDTree(vectors).query(vectors, k=min(n, 4 * k), p=np.inf)
        allowed = (np.abs(idx - np.arange(n)[:, None]) > theiler) & (dist > 0)
    ok = allowed.any(axis=1)
    col = allowed.argmax(axis=1)
    rows = np.arange(n)
    return idx[rows, col], dist[rows, col], ok


def cao(series, delay: int, max_dimension: int = 10, theiler: int = 0):
    """E1(m) e E2(m) de Cao (1997), m = 1…max_dimension (F2h, D-027).

    E(m) é a média de a(i, m) = ‖y_i(m+1) − y_n(m+1)‖ / ‖y_i(m) − y_n(m)‖, com o vizinho n
    de i escolhido em dimensão m (norma do máximo); E1(m) = E(m+1)/E(m) satura perto de 1
    quando m basta. E*(m) é a média de |x_{i+mτ} − x_{n+mτ}| e E2(m) = E*(m+1)/E*(m): num
    processo estocástico os valores futuros não dependem do passado reconstruído, e E2 fica
    perto de 1 em todo m.
    """
    x = _finite(series)
    e, e_star = [], []
    for m in range(1, max_dimension + 2):
        n = len(x) - m * delay
        if n < 2 * theiler + 10:
            raise ValueError("Série curta demais para max_dimension e delay pedidos")
        vectors = delay_embedding(x, m, delay)[:n]
        following = x[m * delay : m * delay + n]
        j, d, ok = _neighbors_max_norm(vectors, theiler)
        i = np.flatnonzero(ok)
        j = j[ok]
        gap = np.abs(following[i] - following[j])
        e.append(np.mean(np.maximum(d[ok], gap) / d[ok]))
        e_star.append(np.mean(gap))
    e, e_star = np.array(e), np.array(e_star)
    return e[1:] / e[:-1], e_star[1:] / e_star[:-1]


def cao_indices(e1, e2, level: float = 0.9, change: float = 0.05) -> dict:
    """Dimensão de saturação (E1 ≥ `level` e variação < `change`) e D_E2 = max |1 − E2|."""
    e1, e2 = np.asarray(e1), np.asarray(e2)
    saturated = [m + 1 for m in range(len(e1) - 1)
                 if e1[m] >= level and abs(e1[m + 1] - e1[m]) < change]
    return {"cao_m": saturated[0] if saturated else np.nan,
            "cao_de2": float(np.max(np.abs(1 - e2)))}
