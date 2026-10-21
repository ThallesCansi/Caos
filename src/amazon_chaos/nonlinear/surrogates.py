"""FT/IAAFT constrained randomizations; ranks test specific stationary nulls.

IAAFT calibration is approximate: empirical amplitudes are exact, spectra are not.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def validate_series(series, min_length=8):
    """Reject missing/constant signals and irregular, duplicated time indices.

    Arrays carry no sampling metadata; callers must establish regular sampling.
    No sorting, imputation, or removal of observations is performed here.
    """
    if isinstance(series, pd.Series) and isinstance(series.index, pd.DatetimeIndex):
        idx = series.index
        if idx.hasnans or idx.has_duplicates or not idx.is_monotonic_increasing:
            raise ValueError("Datas ausentes, duplicadas ou fora de ordem")
        delta = np.diff(idx.asi8)
        if len(delta) and (delta[0] <= 0 or not np.all(delta == delta[0])):
            raise ValueError("Fourier requer amostragem temporal regular")
    x = np.asarray(series, dtype=float)
    if x.ndim != 1 or len(x) < min_length:
        raise ValueError(f"Série unidimensional com pelo menos {min_length} pontos requerida")
    if not np.isfinite(x).all():
        raise ValueError("Série contém valores ausentes ou infinitos")
    if np.std(x) == 0:
        raise ValueError("Série constante: estatística normalizada indefinida")
    return x


def phase_randomized_surrogate(series, rng: np.random.Generator | None = None):
    """Preserve periodogram and circular ACF to floating point precision.

    DC and signed real Nyquist (even n) are retained; rfft enforces symmetry.
    Marginal amplitudes need not be preserved.
    """
    x = validate_series(series)
    rng = rng if rng is not None else np.random.default_rng()
    spectrum = np.fft.rfft(x)
    stop = len(spectrum) - 1 if len(x) % 2 == 0 else len(spectrum)
    spectrum[1:stop] *= np.exp(1j * rng.uniform(0, 2 * np.pi, stop - 1))
    return np.fft.irfft(spectrum, n=len(x))


def spectral_error(original, surrogate):
    """Relative L2 discrepancy of non-DC Fourier amplitudes (not power)."""
    a = np.abs(np.fft.rfft(validate_series(original)))[1:]
    b = np.abs(np.fft.rfft(validate_series(surrogate)))[1:]
    if len(original) != len(surrogate):
        raise ValueError("Comprimentos diferentes")
    return float(np.linalg.norm(a - b) / np.linalg.norm(a))


@dataclass(frozen=True)
class IAAFTResult:
    values: np.ndarray
    iterations: int
    spectral_error: float
    converged: bool
    stop_reason: str
    error_history: np.ndarray


def iaaft_surrogate(series, rng=None, *, max_iter=1000, tolerance=1e-8):
    """Alternate spectral and rank projections, returning exact empirical ranks.

    Stop on target tolerance, unchanged ranks, or iteration limit. A fixed
    point does NOT imply a small residual. Ties use stable sorting.
    """
    x = validate_series(series)
    if not isinstance(max_iter, (int, np.integer)) or max_iter < 1:
        raise ValueError("max_iter deve ser inteiro positivo")
    if not np.isfinite(tolerance) or tolerance < 0:
        raise ValueError("tolerance deve ser finita e não negativa")
    rng = rng if rng is not None else np.random.default_rng()
    ordered = np.sort(x)
    original = np.fft.rfft(x)
    target = np.abs(original)
    target_norm = np.linalg.norm(target[1:])
    y = rng.permutation(x)
    history = []
    reason = "max_iter"
    for _iteration in range(1, max_iter + 1):
        projected = target * np.exp(1j * np.angle(np.fft.rfft(y)))
        projected[0] = original[0]
        z = np.fft.irfft(projected, n=len(x))
        new = np.empty_like(y)
        new[np.argsort(z, kind="stable")] = ordered
        error = float(np.linalg.norm(np.abs(np.fft.rfft(new))[1:] - target[1:]) / target_norm)
        history.append(error)
        unchanged = np.array_equal(new, y)
        y = new
        if error <= tolerance:
            reason = "tolerance"
            break
        if unchanged:
            reason = "fixed_ranks"
            break
    return IAAFTResult(y, len(history), error, error <= tolerance, reason, np.array(history))


def monte_carlo_pvalue(observed, null, alternative="greater"):
    """Inclusive ranks (+1); ties are conservative.

    `absolute` ranks |T| about a prespecified zero (reversal asymmetry).
    `two-sided` doubles the smaller inclusive tail, capped at one.
    """
    null = np.asarray(null, dtype=float)
    if null.ndim != 1 or not len(null) or not np.isfinite(null).all():
        raise ValueError("Distribuição nula vazia ou não finita")
    if not np.isfinite(observed):
        raise ValueError("Estatística observada não finita")
    upper = (1 + np.count_nonzero(null >= observed)) / (len(null) + 1)
    lower = (1 + np.count_nonzero(null <= observed)) / (len(null) + 1)
    if alternative == "greater":
        return float(upper)
    if alternative == "less":
        return float(lower)
    if alternative == "two-sided":
        return float(min(1, 2 * min(upper, lower)))
    if alternative == "absolute":
        return float((1 + np.count_nonzero(abs(null) >= abs(observed))) / (len(null) + 1))
    raise ValueError("alternative desconhecida")
