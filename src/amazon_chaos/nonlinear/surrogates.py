from __future__ import annotations

import numpy as np


def phase_randomized_surrogate(series: np.ndarray, rng: np.random.Generator | None = None) -> np.ndarray:
    """Generate a simple Fourier phase-randomized surrogate.

    This preserves the power spectrum approximately but not the marginal distribution.
    It is suitable as an initial control, not a complete substitute for validated
    AAFT/IAAFT protocols in final inference.
    """
    rng = rng or np.random.default_rng()
    x = np.asarray(series, dtype=float)
    centered = x - np.mean(x)
    spectrum = np.fft.rfft(centered)
    phases = rng.uniform(0, 2 * np.pi, len(spectrum))
    phases[0] = 0.0
    if len(x) % 2 == 0:
        phases[-1] = 0.0
    randomized = np.abs(spectrum) * np.exp(1j * (np.angle(spectrum) + phases))
    return np.fft.irfft(randomized, n=len(x)) + np.mean(x)
