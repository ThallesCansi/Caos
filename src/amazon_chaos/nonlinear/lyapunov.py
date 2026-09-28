from __future__ import annotations

import numpy as np
import nolds


def largest_lyapunov_rosenstein(
    series: np.ndarray,
    emb_dim: int,
    lag: int,
    min_tsep: int | None = None,
) -> float:
    """Preliminary Rosenstein-style largest Lyapunov estimate via nolds.

    This wrapper is intentionally thin. Final inference must include parameter
    sensitivity, synthetic validation and surrogate tests; do not interpret the
    returned scalar in isolation.
    """
    x = np.asarray(series, dtype=float)
    if np.isnan(x).any():
        raise ValueError("Lyapunov estimation requires an explicit missing-data decision")
    if len(x) < 10 * emb_dim * lag:
        raise ValueError("Series is too short for this provisional embedding request")
    kwargs = {"emb_dim": emb_dim, "lag": lag}
    if min_tsep is not None:
        kwargs["min_tsep"] = min_tsep
    return float(nolds.lyap_r(x, **kwargs))
