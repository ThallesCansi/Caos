"""Modelos didáticos do laboratório (caderno 01), com equações conhecidas.

- `MoistureVegetation`: sistema contínuo de feedback umidade–vegetação,
  ṁ = P + αv − βm,  v̇ = v[r(1 − v)·m/(h + m) − d], com limiar P_c = βdh/(r − d).
- `MemoryMap`: mapa com memória x_{n+1} = S[b + μx_n(1 − x_n) − κx_{n−1}], S sigmoide.

Não representam a Amazônia quantitativamente: servem para estudar estabilidade,
bifurcação e Lyapunov onde a resposta certa é conhecida.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import root


@dataclass(frozen=True)
class MoistureVegetation:
    alpha: float = 0.10
    beta: float = 0.80
    r: float = 1.60
    h: float = 0.25
    d: float = 0.45

    @property
    def critical_p(self) -> float:
        """P em que o equilíbrio sem vegetação E0 = (P/β, 0) troca de estabilidade."""
        return self.beta * self.d * self.h / (self.r - self.d)

    def rhs(self, _t, z, p):
        m, v = z
        return np.array([p + self.alpha * v - self.beta * m,
                         v * (self.r * (1 - v) * m / (self.h + m) - self.d)])

    def jacobian(self, z, p):
        m, v = z
        return np.array([
            [-self.beta, self.alpha],
            [self.r * v * (1 - v) * self.h / (self.h + m) ** 2,
             self.r * (1 - 2 * v) * m / (self.h + m) - self.d],
        ])

    def simulate(self, p, z0=(0.45, 0.35), t_max=40.0, n=1000):
        t = np.linspace(0, t_max, n)
        sol = solve_ivp(self.rhs, (0, t_max), z0, args=(p,), t_eval=t, rtol=1e-9, atol=1e-11)
        return sol.t, sol.y

    def equilibria(self, p_values):
        """Ramo vegetado (seguido de P alto para baixo) e estabilidade dos dois ramos."""
        p_values = np.asarray(p_values, float)
        bare_stable = np.array([
            np.max(np.real(np.linalg.eigvals(self.jacobian((p / self.beta, 0.0), p)))) < 0
            for p in p_values])
        vegetated = np.full(len(p_values), np.nan)
        stable = np.zeros(len(p_values), bool)
        guess = np.array([0.4, 0.5])
        for i in range(len(p_values) - 1, -1, -1):
            p = p_values[i]
            sol = root(lambda z, p=p: self.rhs(0, z, p), guess)
            if sol.success and sol.x[1] > 1e-6:
                guess = sol.x
                vegetated[i] = sol.x[1]
                stable[i] = np.max(np.real(np.linalg.eigvals(self.jacobian(sol.x, p)))) < 0
        return bare_stable, vegetated, stable


@dataclass(frozen=True)
class MemoryMap:
    kappa: float = 1.0
    b: float = -0.40
    a: float = 2.0

    def step(self, z, mu):
        x, y = z
        q = self.b + mu * x * (1 - x) - self.kappa * y
        return np.array([1 / (1 + np.exp(-self.a * q)), x])

    def jacobian(self, z, mu):
        x, y = z
        q = self.b + mu * x * (1 - x) - self.kappa * y
        s = 1 / (1 + np.exp(-self.a * q))
        slope = self.a * s * (1 - s)
        return np.array([[slope * mu * (1 - 2 * x), -slope * self.kappa], [1.0, 0.0]])

    def simulate(self, mu, z0=(0.30, 0.31), n=2500, discard=0):
        z = np.array(z0, float)
        out = np.empty((n, 2))
        for i in range(n):
            out[i] = z
            z = self.step(z, mu)
        return out[discard:]

    def fixed_point(self, mu, guess=0.5):
        """x* (com x* = S[b + μx*(1 − x*) − κx*]) e os autovalores da Jacobiana nele."""
        def fun(x):
            return x - 1 / (1 + np.exp(-self.a * (self.b + mu * x * (1 - x) - self.kappa * x)))

        x = float(root(lambda q: fun(q[0]), [guess]).x[0])
        return x, np.linalg.eigvals(self.jacobian((x, x), mu))

    def lyapunov(self, mu, z0=(0.30, 0.31), n=7000, transient=1000):
        """λ₁ pela dinâmica tangente (Benettin): média de ln‖J·v‖ com v renormalizado."""
        z, v = np.array(z0, float), np.array([1.0, 0.0])
        total = 0.0
        for i in range(n):
            w = self.jacobian(z, mu) @ v
            z = self.step(z, mu)
            norm = max(np.linalg.norm(w), 1e-300)
            v = w / norm
            if i >= transient:
                total += np.log(norm)
        return total / (n - transient)
