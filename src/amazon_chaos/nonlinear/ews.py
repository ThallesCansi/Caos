"""Sinais precoces de transição (early warning signals; Dakos et al., 2012).

Perto de uma bifurcação, a recuperação de perturbações fica mais lenta (*critical slowing
down*): a variância e a autocorrelação de atraso 1 sobem. Mede-se a tendência desses
indicadores em janela móvel pelo τ de Kendall, com significância contra substitutas.
Não é evidência de caos, e uma tendência positiva não prova aproximação de transição:
mudanças no forçamento ou na amostragem produzem o mesmo sinal.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d
from scipy.stats import kendalltau

from amazon_chaos.nonlinear.embedding import _finite


def detrend(series, bandwidth: float) -> np.ndarray:
    """Resíduo de uma suavização gaussiana com desvio `bandwidth` (em amostras)."""
    x = _finite(series)
    return x - gaussian_filter1d(x, bandwidth, mode="nearest")


def indicators(series, window: int, bandwidth: float | None = None) -> pd.DataFrame:
    """Variância e AR(1) em janela móvel (alinhada ao fim da janela)."""
    x = _finite(series)
    if not 10 <= window < len(x):
        raise ValueError("window deve ter ao menos 10 amostras e ser menor que a série")
    residual = pd.Series(detrend(x, bandwidth) if bandwidth else x)
    return pd.DataFrame({
        "variance": residual.rolling(window).var(),
        "ar1": residual.rolling(window).corr(residual.shift(1)),
    })


def ews_trends(series, window_fraction: float = 0.5,
               bandwidth: float | None = None) -> dict[str, float]:
    """τ de Kendall da variância e do AR(1) contra o tempo."""
    x = _finite(series)
    frame = indicators(x, int(window_fraction * len(x)), bandwidth).dropna()
    t = np.arange(len(frame))
    return {name: float(kendalltau(t, frame[name]).statistic) for name in frame}
