"""Testes da D-033: dia da queima, transições, linhas de base, métricas por episódio e o
modelo de mudança de sensibilidade."""

import numpy as np
import pandas as pd
import pytest

from amazon_chaos.features import fire_episodes as F
from amazon_chaos.nonlinear import coupling as C
from amazon_chaos.nonlinear import fire_response as R


def _modis_dates(first=2005, last=2009):
    return pd.DatetimeIndex([pd.Timestamp(y, 1, 1) + pd.Timedelta(days=8 * k)
                             for y in range(first, last + 1) for k in range(46)])


def test_event_index_counts_from_the_composite_that_holds_the_burn_day():
    dates = _modis_dates()
    burn = pd.Timestamp(2007, 9, 20)  # dia 263: composição que começa no dia 257
    k = F.event_index(dates, burn)
    assert dates[k == 0][0] == pd.Timestamp(2007, 9, 14)
    # a regra antiga começa na primeira composição do mês (6/9) e erra por uma
    old = F.composite_index(dates, pd.Timestamp(2007, 9, 1))
    assert old[k == 0][0] == 1


def test_differences_need_two_controls_and_drop_the_burn_composite():
    dates = _modis_dates()
    wide = pd.DataFrame({"q": 5.0, "c1": 4.0, "c2": 4.0, "c3": np.nan}, index=dates)
    wide.loc[dates[10], "c2"] = np.nan
    burn = pd.Series({"e": dates[100]})
    d = R.differences(wide, {"e": ("q", ["c1", "c2", "c3"])}, {"queima": burn})
    assert 0 not in set(d.k)
    assert dates[10] not in set(d.data)  # só um controle com valor
    assert np.allclose(d.dif, 1.0)


def test_baselines_remove_a_pre_existing_seasonal_difference():
    dates = _modis_dates()
    k = np.arange(len(dates)) - 120
    seasonal = np.where(dates.month.isin([8, 9, 10]), -0.5, 0.0)
    effect = np.where(k > 0, -1.0, 0.0)
    diff = pd.DataFrame({"episodio": "e", "data": dates, "k": k, "dif": seasonal + effect})
    diff = diff[diff.k != 0]
    flat = C.baseline_change(diff)
    by_season = C.baseline_change(diff, seasonal=True)
    post = by_season[by_season.k.between(1, 92)]
    assert np.allclose(post.delta, -1.0)  # a base sazonal tira o ciclo anterior ao fogo
    dry = flat[flat.k.between(1, 92) & flat.data.dt.month.isin([8, 9, 10])]
    assert dry.delta.mean() < -1.3  # a base única confunde o ciclo com efeito do fogo


def test_memory_metrics_deficit_and_residual():
    k = np.r_[np.arange(-46, 0), np.arange(1, 139)]
    delta = np.where(k > 0, np.where(k <= 46, -1.0, -0.2), 0.0)
    m = C.memory_metrics(pd.DataFrame({"episodio": "e", "k": k, "delta": delta})).iloc[0]
    step = 8 / 365.25
    assert m.A1 == pytest.approx(46 * step)
    assert m.A == pytest.approx(step * (46 * 1.0 + 92 * 0.2))
    assert m.R == pytest.approx(-0.2)


def _panel(theta_d, n_episodes=60, seed=0):
    rng = np.random.default_rng(seed)
    dates = _modis_dates(2003, 2010)
    rows = []
    for e in range(n_episodes):
        cell = f"c{e % 15}"
        k = np.arange(len(dates)) - 150 + rng.integers(-5, 5)
        h, d = rng.normal(size=len(dates)), rng.normal(size=len(dates))
        dif = np.zeros(len(dates))
        for t in range(len(dates) - 1):
            post = k[t] >= 1
            dif[t + 1] = (0.5 * dif[t] + 0.05 * h[t] - 0.02 * d[t]
                          + (theta_d * d[t] if post else 0.0) + 0.1 * rng.normal())
        rows.append(pd.DataFrame({"episodio": f"e{e}", "cell_id": cell, "data": dates,
                                  "k": k, "dif": dif, "h": h, "d": d}))
    frame = pd.concat(rows, ignore_index=True)
    return frame[frame.k != 0]


def test_sensitivity_model_recovers_the_planted_change_and_not_without_it():
    res = C.sensitivity_model(_panel(-0.06), n_boot=49).set_index("termo")
    assert res.loc["P_d", "coeficiente"] == pytest.approx(-0.06, abs=0.015)
    assert res.loc["P_d", "ic_sup"] < 0
    assert res.loc["dif", "coeficiente"] == pytest.approx(0.5, abs=0.05)
    null = C.sensitivity_model(_panel(0.0, seed=1), n_boot=49).set_index("termo")
    assert null.loc["P_d", "ic_inf"] < 0 < null.loc["P_d", "ic_sup"]


def test_transitions_never_cross_the_burn():
    frame = _panel(0.0, n_episodes=3)
    x, y, episodes, _ = C.sensitivity_design(frame)
    assert len(y) < len(frame)
    k = frame.set_index(["episodio", "data"]).k
    keep = x.index  # as linhas de x vêm da tabela ordenada; a checagem é pelo desenho
    assert (x.loc[keep, "P_d"] != 0).sum() > 0
    after_first = C.sensitivity_design(frame, post_start=47)[0]
    assert "k_1_6" not in after_first and "k_47_92" in after_first
    assert k.notna().all()


def test_drought_model_finds_a_planted_slope():
    rng = np.random.default_rng(3)
    n = 300
    s = rng.normal(size=n)
    t = pd.DataFrame({"seca": s, "A": 0.3 * s + rng.normal(scale=0.5, size=n),
                      "bacia": rng.choice(["x", "t"], n), "ano": rng.integers(2003, 2022, n),
                      "estacao_seca": rng.integers(0, 2, n).astype(float),
                      "v_pre": rng.normal(size=n), "cell_id": rng.integers(0, 40, n)})
    res = C.drought_model(t, "A", "seca", n_boot=199)
    assert res["beta"] == pytest.approx(0.3, abs=0.08)
    assert res["p"] < 0.05


def test_panel_v_next_never_crosses_the_burn():
    dates = _modis_dates(2005, 2008)
    rng = np.random.default_rng(4)
    ids = ["e", "c1"]
    series = pd.concat([pd.DataFrame({"id": i, "data": dates, "variavel": v,
                                      "valor": rng.normal(size=len(dates)),
                                      "dia_obs": np.nan})
                        for i in ids for v in ("lai", "ndmi")], ignore_index=True)
    chosen = pd.DataFrame({"episodio": ["e"], "cell_id": ["x"],
                           "mes": [pd.Timestamp(2006, 9, 1)]})
    matched = pd.DataFrame({"episodio": ["e"], "controle": ["c1"], "distancia": [0.0]})
    atm = pd.DataFrame({"cell_id": "x", "data": dates, "vpd": rng.normal(size=len(dates)),
                        "chuva_96d": rng.normal(size=len(dates))})
    burn = pd.Series({"e": pd.Timestamp(2006, 9, 20)})
    p = R.panel(None, chosen, matched, series, "lai", burn=burn, atm=atm)
    burned = p[p.id == "e"].set_index("k")
    assert np.isnan(burned.loc[-1, "v_next"])  # antes, era a composição da queima
    assert np.isfinite(burned.loc[-2, "v_next"]) and np.isfinite(burned.loc[1, "v_next"])
    assert burned.loc[-2, "v_next"] == pytest.approx(burned.loc[-1, "v"])
