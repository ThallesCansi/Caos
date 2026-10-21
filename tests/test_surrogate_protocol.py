import numpy as np
import pandas as pd
import pytest

from amazon_chaos.nonlinear.basin_test import stationarity_diagnostics
from amazon_chaos.nonlinear.statistics import (
    nonlinear_prediction_error,
    time_reversal_asymmetry,
)
from amazon_chaos.nonlinear.surrogates import (
    iaaft_surrogate,
    monte_carlo_pvalue,
    phase_randomized_surrogate,
    spectral_error,
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


def test_stationarity_flags_do_not_hide_trend():
    x = np.linspace(0, 10, 512) + np.random.default_rng(8).normal(size=512)
    report, blocks = stationarity_diagnostics(x)
    assert report["status"] == "exploratório" and "tendência" in report["flags"]
    assert len(blocks) == 4 and report["trend_total"] > 8
