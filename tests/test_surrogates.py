import numpy as np

from amazon_chaos.nonlinear.surrogates import phase_randomized_surrogate


def test_surrogate_preserves_length_and_mean_approximately():
    rng = np.random.default_rng(42)
    x = rng.normal(loc=3.0, scale=2.0, size=1000)
    s = phase_randomized_surrogate(x, np.random.default_rng(1))
    assert len(s) == len(x)
    assert abs(s.mean() - x.mean()) < 1e-10
