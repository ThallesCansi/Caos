from __future__ import annotations

import numpy as np


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
