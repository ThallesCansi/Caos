from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp


def logistic_map(r: float = 4.0, x0: float = 0.2, n: int = 10_000, burn: int = 1_000) -> np.ndarray:
    x = np.empty(n + burn, dtype=float)
    x[0] = x0
    for i in range(1, len(x)):
        x[i] = r * x[i - 1] * (1.0 - x[i - 1])
    return x[burn:]


def ar1(phi: float = 0.8, sigma: float = 1.0, n: int = 10_000, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = np.zeros(n, dtype=float)
    eps = rng.normal(scale=sigma, size=n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + eps[i]
    return x


def periodic_signal(
    n: int = 10_000, period: int = 24, noise: float = 0.0, seed: int = 0
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    return np.sin(2 * np.pi * t / period) + rng.normal(scale=noise, size=n)


def lorenz(
    n: int = 20_000,
    dt: float = 0.01,
    sigma: float = 10.0,
    rho: float = 28.0,
    beta: float = 8.0 / 3.0,
    initial: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> np.ndarray:
    def rhs(_t, state):
        x, y, z = state
        return [sigma * (y - x), x * (rho - z) - y, x * y - beta * z]

    t_eval = np.arange(n) * dt
    sol = solve_ivp(rhs, (0.0, t_eval[-1]), list(initial), t_eval=t_eval, rtol=1e-9, atol=1e-12)
    return sol.y.T


def henon(n: int = 10_000, a: float = 1.4, b: float = 0.3, burn: int = 1_000) -> np.ndarray:
    """Coordenada x do mapa de Hénon; λ₁ ≈ 0,419 por iteração nos parâmetros clássicos."""
    x, y = 0.1, 0.0
    out = np.empty(n + burn)
    for i in range(n + burn):
        x, y = 1 - a * x * x + y, b * x
        out[i] = x
    return out[burn:]


def add_noise(x: np.ndarray, level: float, seed: int = 0) -> np.ndarray:
    """Ruído de observação gaussiano com desvio `level` × desvio-padrão da série."""
    rng = np.random.default_rng(seed)
    return x + level * np.std(x) * rng.normal(size=len(x))


# Controles do gate F4 (docs/metodologia.md §8.1): positivos têm dinâmica determinística
# caótica; negativos são lineares estocásticos ou periódicos.
POSITIVE = ("logistic", "henon", "lorenz")
NEGATIVE = ("white", "ar1", "sine_noise", "seasonal_trend")


def control(kind: str, n: int, seed: int = 0, noise: float = 0.0) -> np.ndarray:
    """Série de controle padronizada (média 0, desvio 1), com ruído de observação opcional.

    `seasonal_trend` reproduz o controle do protocolo de substitutas: AR(1) com variância
    e média sazonais (período 365) e tendência linear, fora das hipóteses nulas.
    """
    rng = np.random.default_rng(seed)
    if kind == "white":
        x = rng.normal(size=n)
    elif kind == "ar1":
        x = ar1(phi=0.8, n=n + 512, seed=seed)[512:]
    elif kind == "logistic":
        x = logistic_map(x0=rng.uniform(0.1, 0.9), n=n)
    elif kind == "henon":
        x = henon(n=n, burn=1_000 + int(rng.integers(0, 1_000)))
    elif kind == "lorenz":
        # x(t) amostrado a cada 0,1 unidade de tempo: λ₁ ≈ 0,906 por unidade → ≈ 0,09 por passo
        start = tuple(1.0 + rng.normal(scale=0.1, size=3))
        x = lorenz(n=n + 500, dt=0.1, initial=start)[500:, 0]
    elif kind == "sine_noise":
        x = periodic_signal(n=n, period=365, noise=0.3, seed=seed)
    elif kind == "seasonal_trend":
        t = np.arange(n)
        x = (control("ar1", n, seed) * (1 + 0.7 * np.sin(2 * np.pi * t / 365))
             + 3 * np.sin(2 * np.pi * t / 365) + 5 * t / n)
    else:
        raise ValueError(f"Controle desconhecido: {kind}")
    if noise:
        x = add_noise(x, noise, seed + 1)
    return (x - x.mean()) / x.std()


# ── Nulas realistas do gate (F2f, D-027): estocásticas, sazonais, sem caos ───

REALISTIC = ("ar1_doy", "ar1_trend", "setar", "ar1_garch")
GARCH = {"alpha": 0.10, "beta": 0.85}


def _lag1(a: np.ndarray, b: np.ndarray) -> float:
    ok = np.isfinite(a) & np.isfinite(b)
    return float(np.corrcoef(a[ok], b[ok])[0, 1])


def fit_realistic(raw: pd.Series, normal=("1991-01-01", "2020-12-31"),
                  trend_period=("2001-01-01", "2024-12-31"), half_window: int = 15) -> dict:
    """Parâmetros das quatro nulas, por um procedimento fixo, numa série diária bruta.

    φ(dia do ano): autocorrelação de passo 1 da anomalia padronizada em janela circular de
    ±`half_window` dias, na normal; φ fixo: a mesma sem janela; desvio sazonal: o da anomalia
    bruta (`standardized_anomalies`); tendência: inclinação por mínimos quadrados da anomalia
    bruta em `trend_period`, por dia; SETAR: mínimos quadrados em cada regime (z_{t−1} ≤ 0
    e > 0) da anomalia padronizada na normal.
    """
    from amazon_chaos.regional import anomalies, standardized_anomalies

    z_all, sd = standardized_anomalies(raw, normal)
    z = z_all.loc[normal[0]:normal[1]]
    prev, now = z.to_numpy()[:-1], z.to_numpy()[1:]
    doy = z.index.day_of_year.to_numpy()[1:]
    phi_doy = np.empty(366)
    for d in range(1, 367):
        gap = np.abs(doy - d)
        near = np.minimum(gap, 366 - gap) <= half_window
        phi_doy[d - 1] = _lag1(prev[near], now[near])
    anomaly, _ = anomalies(raw, normal)
    part = anomaly.loc[trend_period[0]:trend_period[1]]
    slope = float(np.polyfit(np.arange(len(part)), part.to_numpy(), 1)[0])
    setar = []
    for regime in (prev <= 0, prev > 0):
        x, y = prev[regime], now[regime]
        b, a = np.polyfit(x, y, 1)
        setar.append({"a": float(a), "b": float(b), "s": float(np.std(y - (a + b * x)))})
    return {"phi_doy": phi_doy.tolist(), "phi": _lag1(prev, now), "sd_doy": sd.tolist(),
            "trend_per_day": slope, "setar": setar}


def simulate_realistic(kind: str, params: dict, seed: int, start="1990-01-01",
                       end="2024-12-31", burn: int = 365) -> pd.Series:
    """Série diária bruta de uma nula realista: z sem caos × desvio sazonal (+ tendência)."""
    days = pd.date_range(start, end, freq="D")
    n = len(days) + burn
    rng = np.random.default_rng(seed)
    eps = rng.normal(size=n)
    doy = np.r_[days.day_of_year[-burn:], days.day_of_year] - 1
    z = np.zeros(n)
    if kind == "ar1_doy":
        phi = np.asarray(params["phi_doy"])[doy]
        for t in range(1, n):
            z[t] = phi[t] * z[t - 1] + np.sqrt(1 - phi[t] ** 2) * eps[t]
    elif kind in ("ar1_trend", "ar1_garch"):
        phi = params["phi"]
        if kind == "ar1_trend":
            for t in range(1, n):
                z[t] = phi * z[t - 1] + np.sqrt(1 - phi**2) * eps[t]
        else:
            alpha, beta = GARCH["alpha"], GARCH["beta"]
            omega = (1 - alpha - beta) * (1 - phi**2)
            h, e = 1 - phi**2, 0.0
            for t in range(1, n):
                h = omega + alpha * e**2 + beta * h
                e = np.sqrt(h) * eps[t]
                z[t] = phi * z[t - 1] + e
    elif kind == "setar":
        low, high = params["setar"]
        for t in range(1, n):
            r = low if z[t - 1] <= 0 else high
            z[t] = r["a"] + r["b"] * z[t - 1] + r["s"] * eps[t]
    else:
        raise ValueError(f"Nula desconhecida: {kind}")
    raw = z[burn:] * np.asarray(params["sd_doy"])[days.day_of_year - 1]
    if kind == "ar1_trend":
        raw = raw + params["trend_per_day"] * np.arange(len(days))
    return pd.Series(raw, index=days)
