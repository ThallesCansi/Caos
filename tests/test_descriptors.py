import math

import numpy as np
import pytest

from amazon_chaos.nonlinear.dimension import correlation_dimension, correlation_sum
from amazon_chaos.nonlinear.embedding import (
    ami_delay,
    average_mutual_information,
    delay_embedding,
    fnn_dimension,
    temporal_neighbors,
)
from amazon_chaos.nonlinear.ews import ews_trends, indicators
from amazon_chaos.nonlinear.lyapunov import rosenstein
from amazon_chaos.nonlinear.ordinal import (
    complexity_entropy,
    ordinal_distribution,
    permutation_entropy,
)
from amazon_chaos.nonlinear.recurrence import rqa
from amazon_chaos.nonlinear.synthetic import NEGATIVE, POSITIVE, control


@pytest.mark.parametrize("kind", POSITIVE + NEGATIVE)
def test_controls_are_standardized_and_seeded(kind):
    x = control(kind, 2000, seed=4)
    assert x.mean() == pytest.approx(0, abs=1e-9) and x.std() == pytest.approx(1)
    assert np.array_equal(x, control(kind, 2000, seed=4))
    assert not np.array_equal(x, control(kind, 2000, seed=5))


def test_temporal_neighbors_respect_theiler_window():
    x = np.sin(np.arange(500) / 5)
    vectors = delay_embedding(x, 2, 3)
    idx, dist = temporal_neighbors(vectors, theiler=20)
    assert (np.abs(idx - np.arange(len(vectors))) > 20).all() and (dist >= 0).all()


def test_ami_is_entropy_at_zero_and_picks_short_delays():
    x = control("white", 4000, seed=1)
    ami = average_mutual_information(x, 5, bins=8)
    assert ami[0] == pytest.approx(math.log(8), rel=1e-3)
    assert ami[1:].max() < 0.02 and ami_delay(x, 20) == 1
    assert 1 <= ami_delay(control("lorenz", 4000, seed=1), 60) <= 3


def test_fnn_recovers_low_dimension_of_lorenz():
    assert fnn_dimension(control("lorenz", 4000, seed=2), delay=2, max_dimension=6,
                         theiler=10) == 3


@pytest.mark.parametrize("kind, expected, rel", [
    ("logistic", math.log(2), 0.05), ("henon", 0.419, 0.08),
])
def test_rosenstein_recovers_known_exponents_of_maps(kind, expected, rel):
    result = rosenstein(control(kind, 6000, seed=3), 2, 1, theiler=10, fit=(0, 5))
    assert result.exponent == pytest.approx(expected, rel=rel) and result.r2 > 0.99


def test_rosenstein_lorenz_per_step_and_noise_has_no_linear_region():
    lorenz = rosenstein(control("lorenz", 6000, seed=3), 3, 2, theiler=10, fit=(0, 30))
    assert lorenz.exponent == pytest.approx(0.0906, rel=0.2)
    noise = rosenstein(control("white", 6000, seed=3), 3, 1, theiler=10, fit=(0, 6))
    assert noise.r2 < 0.8  # salta e satura: inclinação positiva sem trecho linear


def _brute_force_rqa(x, m, tau, epsilon, theiler, lmin=2):
    v = delay_embedding(x, m, tau)
    n = len(v)
    d = np.linalg.norm(v[:, None] - v[None, :], axis=2)
    r = (d <= epsilon) & (np.abs(np.arange(n)[:, None] - np.arange(n)[None, :]) > theiler)
    diag = []
    for k in range(theiler + 1, n):
        line = np.diagonal(r, k).astype(int)
        runs = np.diff(np.flatnonzero(np.diff(np.r_[0, line, 0])))[::2]
        diag += list(runs)
    diag = np.array(diag)
    det = diag[diag >= lmin].sum() / np.triu(r).sum()
    vert = []
    for col in r.T:
        runs = np.diff(np.flatnonzero(np.diff(np.r_[0, col.astype(int), 0])))[::2]
        vert += list(runs)
    vert = np.array(vert)
    lam = vert[vert >= 2].sum() / r.sum()
    return det, lam


def test_rqa_matches_full_recurrence_matrix():
    x = control("lorenz", 400, seed=1)
    result = rqa(x, 3, 2, rate=0.08, theiler=3)
    assert result.rr == pytest.approx(0.08, abs=0.01)
    # ε é o quantil das distâncias sorteadas e costuma coincidir com a distância de um par;
    # cKDTree e np.linalg.norm arredondam esse par de modos diferentes conforme a máquina.
    # A matriz completa vale com o par no limiar dentro ou fora.
    brute = [_brute_force_rqa(x, 3, 2, result.epsilon * f, theiler=3)
             for f in (1 - 1e-12, 1 + 1e-12)]
    assert any(result.det == pytest.approx(det) and result.lam == pytest.approx(lam)
               for det, lam in brute)


def test_correlation_sum_excludes_diagonal_and_theiler_pairs():
    v = np.arange(10, dtype=float)[:, None]  # distância = |i − j|
    c = correlation_sum(v, np.array([1.0, 2.0, 100.0]), theiler=1)
    assert c[0] == 0  # pares a distância 1 estão todos na janela de Theiler
    assert c[-1] == pytest.approx(1.0)


def test_correlation_dimension_of_maps_and_noise():
    logistic = correlation_dimension(control("logistic", 5000, seed=1), [2, 3], 1, 10)
    assert np.allclose(logistic.d2, 1.0, atol=0.15)
    noise = correlation_dimension(control("white", 5000, seed=1), [2, 4], 1, 10)
    assert noise.d2[1] > noise.d2[0] + 1.5  # sem platô: cresce com m


def test_ordinal_measures_limits():
    p = ordinal_distribution(np.arange(1000.0), order=4)
    assert p.max() == 1 and len(p) == 24
    assert permutation_entropy(np.arange(1000.0), 4) == 0
    h, c = complexity_entropy(control("white", 20_000, seed=1), order=4)
    assert h > 0.99 and c < 0.02
    h, c = complexity_entropy(control("logistic", 20_000, seed=1), order=4)
    assert h < 0.8 and c > 0.2


def test_ews_detects_slowing_down():
    rng = np.random.default_rng(0)
    n = 3000
    phi = np.linspace(0.2, 0.95, n)
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = phi[i] * x[i - 1] + rng.normal()
    trends = ews_trends(x, 0.5, bandwidth=100)
    assert trends["ar1"] > 0.8 and trends["variance"] > 0.8
    frame = indicators(x, 500)
    assert frame.ar1.iloc[-1] > frame.ar1.iloc[600]


def test_moisture_vegetation_threshold_matches_stability_change():
    from amazon_chaos.nonlinear.models import MoistureVegetation

    model = MoistureVegetation()
    assert model.critical_p == pytest.approx(0.8 * 0.45 * 0.25 / (1.6 - 0.45))
    bare_stable, vegetated, _ = model.equilibria([model.critical_p * 0.8,
                                                  model.critical_p * 1.2])
    assert bare_stable.tolist() == [True, False]
    assert np.isnan(vegetated[0]) and vegetated[1] > 0


def test_memory_map_lyapunov_from_equation_matches_rosenstein():
    from amazon_chaos.nonlinear.models import MemoryMap

    model = MemoryMap()
    assert model.lyapunov(7.0) < 0  # ponto fixo estável
    exact = model.lyapunov(11.5)
    series = model.simulate(11.5, n=5500, discard=1000)[:, 0]
    estimate = rosenstein(series, 3, 1, theiler=20, fit=(1, 8)).exponent
    assert exact > 0.2 and estimate == pytest.approx(exact, rel=0.15)
