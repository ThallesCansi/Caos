import numpy as np
import pandas as pd
import pytest
import xarray as xr

from amazon_chaos.nonlinear.statistics import (
    nonlinear_prediction_error,
    time_reversal_asymmetry,
)
from amazon_chaos.nonlinear.surrogate_study import (
    adjust_results,
    load_local_region,
    local_inventory,
    prepare_climate_series,
    stationarity_diagnostics,
)
from amazon_chaos.nonlinear.surrogates import (
    iaaft_surrogate,
    monte_carlo_pvalue,
    phase_randomized_surrogate,
    spectral_error,
    surrogate_test,
    validate_series,
)
from amazon_chaos.nonlinear.synthetic import logistic_map


@pytest.mark.parametrize("n", [255, 256])
def test_ft_exact_periodogram_dc_nyquist_circular_acf(n):
    x = np.random.default_rng(5).normal(3, 2, n)
    y = phase_randomized_surrogate(x, np.random.default_rng(3))
    assert len(y) == n and y.mean() == pytest.approx(x.mean(), abs=1e-12)
    a, b = np.fft.rfft(x), np.fft.rfft(y)
    np.testing.assert_allclose(abs(a) ** 2, abs(b) ** 2, rtol=1e-11, atol=1e-10)
    np.testing.assert_allclose(np.fft.irfft(abs(a) ** 2, n=n),
                               np.fft.irfft(abs(b) ** 2, n=n), atol=1e-10)
    if n % 2 == 0:
        assert a[-1].real == pytest.approx(b[-1].real, abs=1e-12)
    assert not np.allclose(x, y)


@pytest.mark.parametrize("n", [255, 256])
def test_iaaft_distribution_residual_reproducibility(n):
    x = np.random.default_rng(2).exponential(size=n)
    result = iaaft_surrogate(x, np.random.default_rng(9))
    np.testing.assert_array_equal(np.sort(result.values), np.sort(x))
    assert result.values.mean() == pytest.approx(x.mean())
    assert result.spectral_error < .1
    assert result.spectral_error == pytest.approx(spectral_error(x, result.values))
    assert len(result.error_history) == result.iterations
    again = iaaft_surrogate(x, np.random.default_rng(9))
    np.testing.assert_array_equal(result.values, again.values)
    limited = iaaft_surrogate(x, np.random.default_rng(9), max_iter=1, tolerance=0)
    assert limited.iterations == 1 and not limited.converged
    assert limited.stop_reason == "max_iter"


def test_rain_ties_preserved_and_negative_mean():
    x = np.repeat([0., 0., 1., 3., 7.], 20) - 4
    result = iaaft_surrogate(x, np.random.default_rng(1))
    np.testing.assert_array_equal(np.sort(result.values), np.sort(x))
    assert result.values.mean() == pytest.approx(x.mean())


@pytest.mark.parametrize("x", [np.ones(20), np.arange(4), [1., 2., np.nan] * 5,
                               [1., 2., np.inf] * 5, np.ones((4, 4))])
def test_invalid_signals(x):
    for function in [phase_randomized_surrogate, iaaft_surrogate, time_reversal_asymmetry]:
        with pytest.raises(ValueError):
            function(x)


@pytest.mark.parametrize("kind", ["gap", "duplicate", "unordered", "missing"])
def test_invalid_time_index(kind):
    index = list(pd.date_range("2000-01-01", periods=20))
    if kind == "gap":
        index[-1] += pd.Timedelta(days=1)
    elif kind == "duplicate":
        index[-1] = index[-2]
    elif kind == "unordered":
        index = index[::-1]
    else:
        index[-1] = pd.NaT
    with pytest.raises(ValueError):
        validate_series(pd.Series(np.arange(20.), index=pd.DatetimeIndex(index)))


def test_mc_inclusive_tails_absolute_and_resolution():
    assert monte_carlo_pvalue(3, [0, 1, 2, 3]) == 2 / 5
    assert monte_carlo_pvalue(-3, [-3, -2, -1, 0], "less") == 2 / 5
    assert monte_carlo_pvalue(-3, [-3, -2, 1, 3], "absolute") == 3 / 5
    assert monte_carlo_pvalue(3, [0, 1, 2, 3], "two-sided") == 4 / 5
    assert monte_carlo_pvalue(9, np.zeros(199)) == .005
    assert monte_carlo_pvalue(0, [0, 0, 0], "two-sided") == 1
    for null in [[], [np.nan], [[1, 2]]]:
        with pytest.raises(ValueError):
            monte_carlo_pvalue(1, null)


def test_reversal_sign_and_prediction_controls():
    x = logistic_map(n=512)
    assert time_reversal_asymmetry(x[::-1]) == pytest.approx(-time_reversal_asymmetry(x))
    assert time_reversal_asymmetry(2 * x + 3) == pytest.approx(time_reversal_asymmetry(x))
    assert nonlinear_prediction_error(x) < .15
    assert nonlinear_prediction_error(np.random.default_rng(2).normal(size=512)) > .8
    with pytest.raises(ValueError):
        nonlinear_prediction_error(x, theiler=1000)


def test_ensemble_reproducible_and_varied():
    x = np.random.default_rng(9).normal(size=128)
    for method in ["FT", "IAAFT"]:
        a = surrogate_test(x, time_reversal_asymmetry, method=method, n_surrogates=9)
        b = surrogate_test(x, time_reversal_asymmetry, method=method, n_surrogates=9)
        np.testing.assert_array_equal(a.null_statistics, b.null_statistics)
        assert not np.array_equal(a.examples[0], a.examples[1])


def test_complete_day_aggregation_rain_sum_temperature_mean():
    idx = pd.date_range("2001-01-01", periods=71)
    s = pd.Series(np.arange(1., 72), index=idx)
    options = {"version": "original", "resolution": "7D",
               "period": ("2001-01-01", "2001-03-12")}
    rain = prepare_climate_series(s, variable="precip", **options)
    temp = prepare_climate_series(s, variable="t2m", **options)
    assert len(rain) == 10 and rain.iloc[0] == 28 and temp.iloc[0] == 4
    assert rain.iloc[-1] == s.iloc[63:70].sum()
    with pytest.raises(ValueError):
        prepare_climate_series(s.drop(s.index[30]), **options)
    with pytest.raises(ValueError):
        prepare_climate_series(s, period=options["period"], version="anomaly")


def test_stationarity_flags_do_not_hide_trend():
    x = np.linspace(0, 10, 512) + np.random.default_rng(8).normal(size=512)
    report, blocks = stationarity_diagnostics(x)
    assert report["status"] == "exploratório" and "tendência" in report["flags"]
    assert len(blocks) == 4 and report["trend_total"] > 8


def test_holm_keeps_blocked_primary_and_bh_separate():
    frame = pd.DataFrame({"family": ["primary", "primary", "exploratory"],
                          "p_raw": [.03, np.nan, .03]})
    result = adjust_results(frame)
    assert result.p_adjusted.iloc[0] == .06
    assert result.p_adjusted.iloc[2] == .03
    assert result.decision.iloc[1] == "não executado"


def test_inventory_reports_actual_files():
    inventory = local_inventory(".")
    assert sum(inventory.kind == "daily") == 70
    assert inventory.path.str.contains("summary_1990_2024.nc").sum() == 2


def test_transferred_cache_reuses_units_and_marks_unverified(tmp_path):
    # A small synthetic fixture exercises the adapter; it is never ERA5 output.
    config_dir = tmp_path / "configs"
    (config_dir / "regions").mkdir(parents=True)
    (config_dir / "study.yaml").write_text("time: {}\n", encoding="utf-8")
    (config_dir / "regions" / "tapajos_caixa.yaml").write_text(
        "name: teste\nexperiment_id: test\nboundary: {source: bbox}\n"
        "spatial:\n  area: [-2, -56, -3, -54]\n  pilot_point: [-2.5, -55]\n",
        encoding="utf-8")
    base = tmp_path / "data/processed/test"
    base.mkdir(parents=True)
    times = pd.date_range("2001-01-01", periods=100)
    ds = xr.Dataset({"region_t2m": ("time", np.arange(100.) + 20),
                     "region_precip": ("time", np.arange(100.))}, coords={"time": times})
    ds.region_t2m.attrs["units"] = "degC"
    ds.region_precip.attrs["units"] = "mm"
    ds.to_netcdf(base / "summary_1990_2024.nc")
    frame, units, provenance = load_local_region(tmp_path, "tapajos")
    assert units == {"t2m": "degC", "precip": "mm"}
    assert frame.index.equals(times) and len(frame) == 100
    assert "não verificáveis" in provenance


def test_complete_climatology_reuses_project_and_missing_baseline_fails():
    times = pd.date_range("1991-01-01", "2024-12-31")
    x = pd.Series(25 + 3 * np.sin(2 * np.pi * times.dayofyear / 365.25), index=times)
    result = prepare_climate_series(x)
    assert len(result) == 8766 and abs(result).max() < .05
    with pytest.raises(ValueError):
        prepare_climate_series(x.drop(times[15]))


def test_generated_notebook_cells_compile_and_follow_required_order():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "legacy/jupyter/build_surrogate_notebook.py"
    spec = importlib.util.spec_from_file_location("surrogate_notebook_builder", path)
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    notebook = builder.build()
    titles = []
    for i, cell in enumerate(notebook.cells):
        if cell.cell_type == "code":
            compile(cell.source, f"cell_{i}", "exec")
        else:
            titles.extend(line for line in cell.source.splitlines() if line.startswith("## "))
    assert len(titles) == 11
    assert [title.split('.')[0].removeprefix('## ') for title in titles] == [
        str(i) for i in range(1, 12)]
