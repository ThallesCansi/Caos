from __future__ import annotations

import numpy as np
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


def periodic_signal(n: int = 10_000, period: int = 24, noise: float = 0.0, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    return np.sin(2 * np.pi * t / period) + rng.normal(scale=noise, size=n)


def lorenz(
    n: int = 20_000,
    dt: float = 0.01,
    sigma: float = 10.0,
    rho: float = 28.0,
    beta: float = 8.0 / 3.0,
) -> np.ndarray:
    def rhs(_t, state):
        x, y, z = state
        return [sigma * (y - x), x * (rho - z) - y, x * y - beta * z]

    t_eval = np.arange(n) * dt
    sol = solve_ivp(rhs, (0.0, t_eval[-1]), [1.0, 1.0, 1.0], t_eval=t_eval, rtol=1e-9, atol=1e-12)
    return sol.y.T
