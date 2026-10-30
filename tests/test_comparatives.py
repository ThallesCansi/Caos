"""Extensões complementares de D-027 (F2a, F2b, ...): regras e reprodução do lote."""

import numpy as np
import pandas as pd
import pytest

from amazon_chaos.nonlinear.suite import load_spec


@pytest.fixture(scope="module")
def small():
    spec = load_spec()
    spec = {**spec, "surrogates": {**spec["surrogates"], "per_cell": 3},
            "ews": {**spec["ews"], "surrogates": 3},
            "series": {**spec["series"], "period": ["2001-01-01", "2004-12-31"],
                       "windows": [["2001-01-01", "2002-12-31"]]}}
    days = pd.date_range("1990-01-01", "2004-12-31")
    rng = np.random.default_rng(0)
    noise = np.zeros(len(days))
    for i in range(1, len(days)):
        noise[i] = 0.7 * noise[i - 1] + rng.normal()
    raw = pd.Series(25 + np.sin(2 * np.pi * days.dayofyear / 365.25) + noise, index=days)
    return spec, raw


def test_ami_first_minimum_finds_quarter_period_and_keeps_ami_delay():
    from amazon_chaos.nonlinear.embedding import ami_delay, ami_first_minimum

    t = np.arange(4000)
    sine = np.sin(2 * np.pi * t / 40) + 0.05 * np.random.default_rng(1).normal(size=len(t))
    assert 5 <= ami_first_minimum(sine, 30) <= 12  # perto de um quarto do período
    assert ami_delay(sine, 30) == min(ami_first_minimum(sine, 30), ami_delay(sine, 30))


def test_params_for_fixes_tau_and_recomputes_theiler(small):
    from amazon_chaos.nonlinear.delays import params_for

    spec, raw = small
    p = params_for(raw.to_numpy()[-1461:], 5, spec)
    assert p["tau"] == 5 and p["theiler"] == max(10, 5 * p["m"])


def test_delay_grid_reproduces_batch_at_tau_one(small):
    from amazon_chaos.nonlinear import batch, delays

    spec, raw = small
    grid = delays.cell_task(spec, "ERA5_teste", {"t2m": raw})
    variants = set(grid.variant)
    assert {f"τ = {t}" for t in delays.RULES["delays"]} <= variants
    assert {f"atraso ordinal {d}" for d in delays.RULES["ordinal_delays"]} <= variants
    ref = batch.cell_task(spec, "ERA5_teste", {"t2m": raw})
    ref = ref[(ref.kind == "teste") & (ref.window == "2001_2004")].set_index("descriptor")
    assert (ref.tau == 1).all()  # a regra deu τ = 1, como nas células reais
    for variant, names in [("τ = 1", ["rqa_det", "prediction"]),
                           ("atraso ordinal 1", ["pe_entropy", "pe_complexity"])]:
        got = grid[grid.variant == variant].set_index("descriptor")
        for name in names:
            assert got.loc[name, "observed"] == pytest.approx(ref.loc[name, "observed"])
            assert got.loc[name, "pvalue"] == pytest.approx(ref.loc[name, "pvalue"])
            assert got.loc[name, "null_mean"] == pytest.approx(ref.loc[name, "null_mean"])
    longer = grid[grid.variant == "atraso ordinal 7"].set_index("descriptor")
    assert longer.loc["pe_entropy", "observed"] != pytest.approx(
        ref.loc["pe_entropy", "observed"])


def test_extremes_cell_task_full_only_in_subsample_and_first_window(small):
    from amazon_chaos.nonlinear import extremes

    spec, raw = small
    series = {"tmax": raw, "amplitude": raw * 0.5 + 3}
    cell = extremes.cell_task(spec, "ERA5_teste", series, full=True)
    assert set(cell.variable) == {"tmax", "amplitude"}
    first = cell[cell.window == "2001_2004"]
    assert set(first.descriptor) == {"pe_entropy", "pe_complexity", "rqa_det", "prediction"}
    assert set(cell[cell.window == "2001_2002"].descriptor) == {"pe_entropy", "pe_complexity"}
    plain = extremes.cell_task(spec, "ERA5_teste", series, full=False)
    assert set(plain.descriptor) == {"pe_entropy", "pe_complexity"}
    # a anomalia padronizada tira escala e média: a amplitude afim de tmax dá o mesmo padrão,
    # mas a semente própria de cada variável muda as substitutas
    t = cell.set_index(["variable", "window", "descriptor"])
    obs = t.observed
    assert obs[("tmax", "2001_2004", "pe_entropy")] == pytest.approx(
        obs[("amplitude", "2001_2004", "pe_entropy")])
    assert t.null_mean[("tmax", "2001_2004", "pe_entropy")] != pytest.approx(
        t.null_mean[("amplitude", "2001_2004", "pe_entropy")])


# ── F2d, F2f, F2g e F2h ──────────────────────────────────────────────────────


def test_cao_separates_a_map_from_noise():
    from amazon_chaos.nonlinear.embedding import cao, cao_indices
    from amazon_chaos.nonlinear.synthetic import control

    e1, e2 = cao(control("henon", 3000, seed=1), 1, 6, theiler=10)
    henon = cao_indices(e1, e2)
    e1, e2 = cao(control("white", 3000, seed=1), 1, 6, theiler=10)
    white = cao_indices(e1, e2)
    assert henon["cao_m"] == 2 and henon["cao_de2"] > 0.8
    assert white["cao_de2"] < 0.1


def test_kantz_and_wolf_recover_the_logistic_exponent():
    from amazon_chaos.nonlinear.lyapunov import kantz, wolf
    from amazon_chaos.nonlinear.synthetic import control

    x = control("logistic", 4000, seed=2)
    assert abs(kantz(x, 2, 1, 10) - np.log(2)) < 0.1
    assert abs(wolf(x, 2, 1, 10) - np.log(2)) < 0.15


def test_smap_gains_on_a_map_and_not_on_a_linear_process():
    from amazon_chaos.nonlinear.smap import diebold_mariano, smap_series
    from amazon_chaos.nonlinear.synthetic import control

    rules = {"thetas": [0, 1, 4], "train_fraction": 0.6, "horizons": [1, 2]}
    chaos = smap_series(control("logistic", 1200, seed=3), 2, 1, 10, rules)
    linear = smap_series(control("ar1", 1200, seed=3), 2, 1, 10, rules)
    assert chaos.gain.iloc[0] > 0.5 and chaos.pvalue.iloc[0] < 0.01
    assert abs(linear.gain.iloc[0]) < 0.02
    rng = np.random.default_rng(0)
    e = rng.normal(size=500)
    assert diebold_mariano(e, 0.5 * e, 1)[1] < 1e-6
    assert diebold_mariano(e, e + 0.0, 1)[1] == 1.0


def test_realistic_nulls_are_fitted_and_simulated_on_the_calendar():
    from amazon_chaos.nonlinear import realistic as RL
    from amazon_chaos.nonlinear import synthetic as S

    days = pd.date_range("1990-01-01", "2024-12-31", freq="D")
    rng = np.random.default_rng(4)
    season = 1 + 0.5 * np.sin(2 * np.pi * days.day_of_year / 365.25)
    z = np.zeros(len(days))
    for t in range(1, len(days)):
        z[t] = 0.7 * z[t - 1] + np.sqrt(1 - 0.49) * rng.normal()
    raw = pd.Series(25 + 3 * np.cos(2 * np.pi * days.day_of_year / 365.25) + season * z,
                    index=days)
    params = S.fit_realistic(raw)
    assert abs(params["phi"] - 0.7) < 0.03 and len(params["phi_doy"]) == 366
    assert params["setar"][0]["b"] > 0.5 and abs(params["trend_per_day"]) < 1e-4
    for kind in S.REALISTIC:
        x = RL.null_series(kind, params, seed=5)
        assert len(x) == 8766 and np.isfinite(x).all() and 0.8 < x.std() < 1.2
    assert RL.null_series("ar1_doy", params, 6)[:10].tolist() == \
        RL.null_series("ar1_doy", params, 6)[:10].tolist()


def test_extra_suite_reports_three_statistics():
    from amazon_chaos.nonlinear.estimators import ALTERNATIVE, extra_suite
    from amazon_chaos.nonlinear.suite import load_spec
    from amazon_chaos.nonlinear.synthetic import control

    spec = load_spec()
    x = control("henon", 1500, seed=7)
    out = extra_suite(x, {"tau": 1, "m": 2, "theiler": 10}, 3, 11, spec)
    assert out.descriptor.tolist() == list(ALTERNATIVE)
    assert (out.n_null == 3).all() and out.cao_m.iloc[0] == 2
    assert out.set_index("descriptor").z["cao_de2"] > 3


def test_multivariate_surrogates_keep_cross_structure():
    from amazon_chaos.nonlinear import multivariate as M

    rng = np.random.default_rng(8)
    a = np.convolve(rng.normal(size=1100), np.ones(5) / 5, "same")[:1024]
    b = 0.6 * np.roll(a, 2) + 0.4 * rng.normal(size=1024)
    data = np.column_stack([a, b])
    ft = M.multivariate_ft(data, np.random.default_rng(1))
    cross = np.fft.rfft(data[:, 0]) * np.conj(np.fft.rfft(data[:, 1]))
    cross_ft = np.fft.rfft(ft[:, 0]) * np.conj(np.fft.rfft(ft[:, 1]))
    assert np.allclose(cross, cross_ft)
    iaaft = M.multivariate_iaaft(data, np.random.default_rng(2))
    assert np.allclose(np.sort(iaaft, axis=0), np.sort(data, axis=0))
    assert abs(np.corrcoef(iaaft.T)[0, 1] - np.corrcoef(data.T)[0, 1]) < 0.05
    assert not np.allclose(iaaft, data)


def test_forecast_errors_use_the_other_channel():
    from amazon_chaos.nonlinear import multivariate as M
    from amazon_chaos.nonlinear.synthetic import henon

    x = henon(n=1500)
    data = np.column_stack([x[1:], x[:-1]])  # o segundo canal é o passado do primeiro
    params = [{"tau": 1, "m": 1}, {"tau": 1, "m": 1}]
    out = M.forecast_errors(data, params, 10, smap=False)
    assert out["alvo0_nn_conjunto"] < 0.1 < out["alvo0_nn_proprio"]
    assert out["alvo0_nn_ganho"] > 0.1


def test_rain_dither_treats_surrogates_like_the_original():
    from amazon_chaos.nonlinear import precip_dither as PD

    spec = load_spec()
    rng = np.random.default_rng(9)
    rain = np.where(rng.uniform(size=800) < 0.6, 0.0, rng.gamma(0.8, 8, 800))
    days = pd.date_range("2001-01-01", periods=800, freq="D")
    small = {**spec, "surrogates": {**spec["surrogates"], "per_cell": 5}}
    small["series"] = {**spec["series"], "period": ["2001-01-01", "2003-03-11"]}
    out = PD.cell_task(small, "c", {"precip_x": pd.Series(rain, index=days)})
    assert out.descriptor.tolist() == ["pe_entropy", "pe_complexity"]
    assert (out.n_null == 5).all() and out.z.notna().all()
    spectral = PD.spectral_task(small, "c", {"precip_x": rain, "t2m": rng.normal(size=800)})
    assert (spectral.maximo >= spectral.mediana).all() and (spectral.n == 5).all()
