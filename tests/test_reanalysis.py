"""Bloco G: regra da D-029, n efetivo de uma fração, Kantz e Wolf, IAAFT multivariada,
GARCH por máxima verossimilhança e a chuva separada em ocorrência e intensidade."""

import numpy as np
import pandas as pd
import pytest

from amazon_chaos import gradient as G
from amazon_chaos.nonlinear import multivariate as M
from amazon_chaos.nonlinear import precip_split as P
from amazon_chaos.nonlinear import realistic as RL
from amazon_chaos.nonlinear import synthetic as S
from amazon_chaos.nonlinear.lyapunov import kantz, kantz_profile, wolf


def test_compare_rule():
    assert RL.compare(1.0, 700, 0.997) == "indistinguível"
    assert RL.compare(0.74, 700, 0.36) == "acima"
    assert RL.compare(0.74, 4, 0.36) == "dentro"  # poucas observações independentes
    assert RL.compare(0.30, 700, 0.36) == "dentro"


def test_permissive_picks_the_largest_upper_bound_per_variable():
    rates = pd.DataFrame({"descriptor": ["d"] * 4, "control": ["a", "b", "a", "b"],
                          "variable": ["t2m", "t2m", "vpd", "vpd"],
                          "rate": [0.1, 0.2, 0.9, 0.5], "ci_high": [0.2, 0.35, 0.99, 0.6]})
    top = RL.permissive(rates)
    assert top.loc[("d", "t2m"), "null"] == "b" and top.loc[("d", "vpd"), "limit"] == 0.99


def test_effective_n_mean_drops_with_spatial_smoothness():
    rng = np.random.default_rng(0)
    lat, lon = np.meshgrid(np.arange(20) * 0.25, np.arange(20) * 0.25)
    lat, lon = lat.ravel(), lon.ravel()
    noise = rng.normal(size=lat.size)
    smooth = np.sin(lat) + np.cos(lon) + 0.1 * noise
    assert G.effective_n_mean(noise, lat, lon) > 200
    assert G.effective_n_mean(smooth, lat, lon) < 50
    assert G.effective_n_mean(np.ones(lat.size), lat, lon) == lat.size


def test_kantz_profile_matches_kantz_at_two_percent():
    x = S.logistic_map(4.0, 0.4, n=1500)
    prof = kantz_profile(x, 2, 1, 1)
    assert prof["kantz_2"] == pytest.approx(kantz(x, 2, 1, 1, quantile=0.02))
    assert prof["kantz_1_pontos"] <= prof["kantz_10_pontos"]
    assert set(prof) == {f"kantz_{q}{s}" for q in ("1", "2", "5", "10") for s in ("", "_pontos")}


def test_wolf_diagnostics_are_consistent():
    x = S.logistic_map(4.0, 0.3, n=2000)
    diag = wolf(x, 2, 1, 1, diagnostics=True)
    assert diag["wolf"] == pytest.approx(wolf(x, 2, 1, 1))
    assert diag["substituicoes"] + diag["sem_candidato"] == diag["substituicoes_pedidas"]
    assert 0 <= diag["angulo_medio"] <= 1.2 + 1e-9


def _coupled(n=4000, seed=1):
    rng = np.random.default_rng(seed)
    e = rng.normal(size=(n, 2))
    x = np.zeros((n, 2))
    for t in range(1, n):
        x[t] = [0.8 * x[t - 1, 0] + e[t, 0], 0.5 * x[t - 1, 1] + 0.6 * x[t - 1, 0] + e[t, 1]]
    return np.column_stack([x[:, 0], np.exp(x[:, 1] / 2)])


def test_cross_diagnostics_ft_exact_and_iaaft_weaker_at_all_lags():
    data = _coupled()
    ft = M.cross_diagnostics(data, M.multivariate_ft(data, np.random.default_rng(2)))
    assert ft["erro_espectral_0"] < 1e-10 and abs(ft["razao_cruzada"] - 1) < 0.01
    ia = M.cross_diagnostics(data, M.multivariate_iaaft(data, np.random.default_rng(2)))
    assert ia["razao_cruzada"] < 0.97  # a IAAFT multivariada enfraquece a dependência cruzada


def test_fit_garch_recovers_parameters():
    rng = np.random.default_rng(0)
    a, b, n = 0.12, 0.80, 6000
    h, e = 1.0, np.zeros(n)
    for t in range(1, n):
        h = (1 - a - b) + a * e[t - 1] ** 2 + b * h
        e[t] = np.sqrt(h) * rng.normal()
    fit = S.fit_garch(e)
    assert abs(fit["alpha"] - a) < 0.05 and abs(fit["beta"] - b) < 0.1


def test_simulation_uses_fitted_garch_when_present():
    days = pd.date_range("1990-01-01", "2000-12-31", freq="D")
    params = {"phi": 0.6, "sd_doy": [1.0] * 366, "garch": {"alpha": 0.0, "beta": 0.0}}
    z = S.simulate_realistic("ar1_garch", params, 1, "1990-01-01", "2000-12-31").to_numpy()
    e = z[1:] - 0.6 * z[:-1]
    assert len(z) == len(days)
    assert abs(np.corrcoef(e[1:] ** 2, e[:-1] ** 2)[0, 1]) < 0.05  # sem variância condicional


def test_ar1_doy_fit_recovers_seasonal_memory():
    days = pd.date_range("1985-01-01", "2024-12-31", freq="D")
    phi = 0.5 + 0.3 * np.cos(2 * np.pi * (np.arange(366)) / 366)
    raw = S.simulate_realistic("ar1_doy", {"phi_doy": phi, "sd_doy": [1.0] * 366}, 3,
                               "1985-01-01", "2024-12-31")
    fit = S.fit_realistic(raw + 10 * np.sin(2 * np.pi * days.day_of_year / 365.25))
    est = np.asarray(fit["phi_doy"])
    assert np.corrcoef(est, phi)[0, 1] > 0.8 and est.max() > est.min() + 0.3


def test_word_entropy_limits():
    assert P.word_entropy(np.zeros(500, bool)) == 0
    rng = np.random.default_rng(0)
    assert P.word_entropy(rng.random(20000) < 0.5) == pytest.approx(1, abs=0.01)
    alternating = np.arange(1000) % 2 == 0
    assert P.word_entropy(alternating) == pytest.approx(1 / 5, abs=0.01)


def test_shuffle_wet_keeps_occurrence_and_amounts():
    rng = np.random.default_rng(1)
    x = np.where(rng.random(400) < 0.4, rng.gamma(2, 5, 400) + 1, 0.0)
    wet = x >= 1
    y = P.shuffle_wet(x, wet, rng)
    assert ((y >= 1) == wet).all() and np.allclose(np.sort(y), np.sort(x))


def test_contrast_with_one_block_matches_years_only():
    from amazon_chaos.features import fire_weather as F

    rng = np.random.default_rng(3)
    ev = pd.DataFrame({"ano": rng.integers(2003, 2015, 300),
                       "terco": rng.choice(["preservada", "perturbada"], 300),
                       "bloco": "b"})
    for name in F.MEASURES:
        ev[f"{name}_percentil"] = rng.random(300)
    years = F.contrast(ev, n=199)
    blocks = F.contrast(ev, n=199, blocks="bloco")
    assert np.allclose(years.diferenca, blocks.diferenca)
    assert np.allclose(years.ic_inf, blocks.ic_inf) and np.allclose(years.ic_sup, blocks.ic_sup)


def test_contrast_with_blocks_is_wider_when_blocks_differ():
    from amazon_chaos.features import fire_weather as F

    rng = np.random.default_rng(4)
    rows = []
    for b in range(8):
        shift = rng.normal(0, 0.1)  # cada bloco tem o seu nível
        for year in range(2003, 2023):
            for third in ("preservada", "perturbada"):
                rows.append({"ano": year, "terco": third, "bloco": b,
                             "v": 0.5 + shift * (third == "preservada") + rng.normal(0, 0.02)})
    ev = pd.DataFrame(rows)
    for name in F.MEASURES:
        ev[f"{name}_percentil"] = ev.v
    years, blocks = F.contrast(ev, n=299), F.contrast(ev, n=299, blocks="bloco")
    assert ((blocks.ic_sup - blocks.ic_inf) > 2 * (years.ic_sup - years.ic_inf)).all()


def test_block_sensitivity_and_degrees_of_freedom():
    rng = np.random.default_rng(5)
    lat, lon = np.meshgrid(np.arange(16) * 0.25, np.arange(16) * 0.25)
    frame = pd.DataFrame({"latitude": lat.ravel(), "longitude": lon.ravel()})
    frame["x"] = rng.normal(size=len(frame))
    frame["y"] = frame.x + rng.normal(size=len(frame))
    frame["agua_frac_2000"], frame["altitude_m"] = rng.random(len(frame)), rng.random(len(frame))
    out = G.block_sensitivity(frame, "x", "y")
    assert set(out) == {f"{k}_{s}" for k in ("ic_inf", "ic_sup", "p_blocos")
                        for s in ("1", "2", "2.5")}
    assert all(out[f"ic_inf_{s}"] > 0 for s in ("1", "2", "2.5"))
    with_controls = G.spatial_inference(frame, "x", "y")
    without = G.spatial_inference(frame, "x", "y", controls=())
    assert with_controls["p_n_efetivo"] < 0.05 and without["p_n_efetivo"] < 0.05


def test_series_seasonality_sees_seasonal_memory():
    from amazon_chaos.features.seasonality import series_seasonality

    days = pd.date_range("1985-01-01", "2024-12-31", freq="D")
    flat = S.simulate_realistic("ar1_doy", {"phi_doy": [0.6] * 366, "sd_doy": [1.0] * 366},
                                1, "1985-01-01", "2024-12-31")
    phi = 0.5 + 0.35 * np.cos(2 * np.pi * np.arange(366) / 366)
    seasonal = S.simulate_realistic("ar1_doy", {"phi_doy": phi, "sd_doy": [1.0] * 366}, 1,
                                    "1985-01-01", "2024-12-31")
    cycle = 5 * np.sin(2 * np.pi * days.day_of_year / 365.25)
    a, b = series_seasonality(flat + cycle), series_seasonality(seasonal + cycle)
    assert b["phi_amplitude"] > a["phi_amplitude"] + 0.3
    assert 0.8 < a["ciclo_frac"] < 1 and abs(a["phi_media"] - 0.6) < 0.05


def test_rain_split_cell_task_shapes():
    from amazon_chaos.nonlinear.suite import load_spec

    rng = np.random.default_rng(6)
    days = pd.date_range("2000-01-01", "2024-12-31", freq="D")
    rain = pd.Series(np.where(rng.random(len(days)) < 0.4, rng.gamma(2, 5, len(days)), 0.0),
                     index=days)
    out = P.cell_task(load_spec(), "c", {"precip_chirps": rain})
    assert set(out.teste) == {"intensidade", "chuvosos"} and len(out) == 4
    assert out.pvalue.between(0, 1).all()
    assert abs(out.fracao_chuvosos.iloc[0] - (rain.loc["2001":] >= 1).mean()) < 1e-12
