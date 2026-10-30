import numpy as np
import pandas as pd

from amazon_chaos import gradient as G


def grid(n=20, step=0.25):
    lat, lon = np.meshgrid(np.arange(n) * step, np.arange(n) * step, indexing="ij")
    return lat.ravel(), lon.ravel()


def test_partial_spearman_removes_a_shared_control():
    rng = np.random.default_rng(1)
    z = rng.normal(size=500)
    x, y = z + 0.1 * rng.normal(size=500), z + 0.1 * rng.normal(size=500)
    assert G.partial_spearman(x, y) > 0.9
    assert abs(G.partial_spearman(x, y, z[:, None])) < 0.15


def test_bootstrap_p_matches_the_percentile_interval():
    assert G.bootstrap_p(np.full(999, 0.3)) == 2 / 1000
    assert G.bootstrap_p(np.linspace(-1, 1, 999)) == 1.0
    values = np.r_[np.full(10, -0.1), np.full(989, 0.2)]
    assert G.bootstrap_p(values) == 2 * 11 / 1000


def test_moran_and_correlogram_see_a_smooth_field_but_not_noise():
    lat, lon = grid()
    rng = np.random.default_rng(2)
    smooth = np.sin(lat) + np.cos(lon)
    noise = rng.normal(size=len(lat))
    i, p = G.moran_test(smooth, lat, lon, n=199)
    assert i > 0.9 and p == 1 / 200
    i, p = G.moran_test(noise, lat, lon, n=199)
    assert abs(i) < 0.15 and p > 0.05
    curve = G.correlogram(smooth, lat, lon)
    assert curve.moran.iloc[0] > curve.moran.iloc[-1]
    assert (curve.pares > 0).all()


def test_effective_n_shrinks_with_shared_spatial_structure():
    lat, lon = grid()
    rng = np.random.default_rng(3)
    a, b = rng.normal(size=len(lat)), rng.normal(size=len(lat))
    assert 0.6 * len(lat) < G.effective_n(a, b, lat, lon) < 1.6 * len(lat)
    sa, sb = np.sin(lat / 1.5) + 0.1 * a, np.cos(lon / 1.5) + 0.1 * b
    assert G.effective_n(sa, sb, lat, lon) < 0.2 * len(lat)


def test_spatial_inference_and_holm():
    lat, lon = grid(12)
    rng = np.random.default_rng(4)
    frame = pd.DataFrame({"latitude": lat, "longitude": lon,
                          "agua_frac_2000": rng.uniform(size=len(lat)),
                          "altitude_m": rng.normal(size=len(lat))})
    frame["x"] = rng.normal(size=len(lat))
    frame["y"] = frame.x + rng.normal(size=len(lat))
    out = G.spatial_inference(frame, "x", "y")
    assert out["p_n_efetivo"] < 0.01 and out["n_efetivo"] > 50
    assert np.allclose(G.adjust([0.01, 0.04, 0.03], "holm"), [0.03, 0.06, 0.06])
