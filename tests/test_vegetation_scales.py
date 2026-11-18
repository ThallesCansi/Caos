"""Testes da D-032: anomalia só com o treino, preenchimento causal, permutação de anos,
S-map e a comparação de uma célula sintética."""

import numpy as np
import pandas as pd
import pytest

from amazon_chaos.nonlinear import vegetation_scales as S


def _dates():
    days = [pd.Timestamp(y, 1, 1) + pd.Timedelta(days=8 * k)
            for y in range(S.FIRST_YEAR, S.LAST_YEAR + 1) for k in range(S.SLOTS)]
    return pd.DatetimeIndex(days)


def test_anomaly_uses_only_the_fit_rows():
    idx = _dates()
    year, slot = S.calendar(idx)
    raw = np.where(year >= 2013, 10.0, 0.0)[:, None] + np.random.default_rng(0).normal(
        size=(len(idx), 1))
    z = S.anomaly(raw, slot, year < 2013)
    assert abs(np.nanmean(z[year < 2013])) < 0.05
    assert np.nanmean(z[year >= 2013]) > 5  # o salto do teste não vaza para a climatologia


def test_causal_fill_never_looks_ahead():
    z = np.array([[1.0], [np.nan], [np.nan], [np.nan], [5.0]])
    out = S.causal_fill(z)[:, 0]
    assert out.tolist() == [1.0, 1.0, 1.0, 0.0, 5.0]


def test_targets_mean_needs_half_the_window():
    x = np.arange(20, dtype=float)
    x[10:13] = np.nan
    t, y = S.targets(x, 4, mean=True)
    assert t[0] == S.MAX_LAG
    i = list(t).index(9)  # janela 10..13: só o 13 observado (1 de 4)
    assert np.isnan(y[i])
    j = list(t).index(8)  # janela 9..12: 9 observado; 10..12 vazios → 1 de 4
    assert np.isnan(y[j])
    k = list(t).index(12)  # janela 13..16, toda observada
    assert y[k] == pytest.approx(14.5)


def test_permute_years_moves_whole_years_and_keeps_the_rest():
    idx = _dates()
    year, slot = S.calendar(idx)
    raw = np.column_stack([year * 100.0 + slot, year * 1.0])
    order = S.year_orders(1)[0]
    out = S.permute_years(raw, [0], year, slot, order)
    assert np.array_equal(out[:, 1], raw[:, 1])
    first = year == S.FIRST_YEAR
    assert np.array_equal(out[first, 0], order[S.FIRST_YEAR] * 100.0 + slot[first])
    assert all(k != v for k, v in order.items())


def test_smap_theta_zero_is_least_squares():
    rng = np.random.default_rng(1)
    x = rng.normal(size=(200, 3))
    y = x @ [1.0, -2.0, 0.5] + 0.3 + 0.1 * rng.normal(size=200)
    q = rng.normal(size=(20, 3))
    pred = S.smap_predictions(x, y, q, thetas=(0,))[0]
    design = np.column_stack([np.ones(200), x])
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    assert np.allclose(pred, np.column_stack([np.ones(20), q]) @ beta, atol=1e-6)


def _frame(beta, seed=0):
    rng = np.random.default_rng(seed)
    idx = _dates()
    _, slot = S.calendar(idx)
    season = np.sin(2 * np.pi * slot / S.SLOTS)
    n = len(idx)
    d = np.zeros(n)
    for t in range(1, n):
        d[t] = 0.7 * d[t - 1] + rng.normal()
    frame = pd.DataFrame({"lai": 4 + season + 0.3 * rng.normal(size=n), "ndmi": np.nan,
                          "vpd": 1 + season + 0.3 * d,
                          "chuva_32d": 100 - 50 * season + rng.normal(size=n),
                          "chuva_96d": 300 - 150 * season + rng.normal(size=n)}, index=idx)
    return S.synthetic_frame(frame, beta=beta, lag=4, noise=0.5, seed=seed)


def test_synthetic_coupling_is_found_at_the_planted_lag_and_absent_without_it():
    orders = S.year_orders(4)
    coupled = S.cell_task("x", _frame(0.5), {"lai": 0.0, "ndmi": 1.0}, orders,
                          horizons=(4,), variants=("estrita",), surrogate_variants=("estrita",))
    gain = coupled[(coupled.analise == "ganho") & (coupled.sentido == S.DIRECTIONS[0])
                   & (coupled.modelo == "linear")]
    observed = gain[gain.substituta == 0].ganho.iloc[0]
    assert observed > 0.05
    assert observed > gain[gain.substituta > 0].ganho.max()
    chosen = coupled[coupled.analise == "escolha"].escolha.iloc[0]
    # V(t + 4) responde a D(t − 1) e, pela memória, aos anteriores: k_D = 0 ou 2
    assert "vpd@0" in chosen or "vpd@2" in chosen

    null = S.cell_task("x", _frame(0.0), {"lai": 0.0, "ndmi": 1.0}, orders[:1],
                       horizons=(4,), variants=("estrita",), surrogate_variants=())
    g0 = null[(null.analise == "ganho") & (null.sentido == S.DIRECTIONS[0])
              & (null.modelo == "linear")].ganho.iloc[0]
    assert abs(g0) < 0.03
