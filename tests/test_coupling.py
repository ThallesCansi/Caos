"""Floresta e atmosfera acopladas (D-031): lacunas, previsão, CCM e fogo."""

import numpy as np
import pandas as pd

from amazon_chaos.features import vegetation as V
from amazon_chaos.nonlinear import coupling as C


def test_refill_interpolates_short_gaps_and_zeroes_long_ones():
    x = np.arange(12, dtype=float)
    missing = np.zeros(12, bool)
    missing[[2, 3]] = True          # curta: interpola
    missing[6:9] = True             # longa: climatologia (0)
    y = C.refill(x, missing)
    assert np.allclose(y[[2, 3]], [2, 3]) and (y[6:9] == 0).all()
    assert np.allclose(y[~missing], x[~missing])


def _coupled_logistic(n=1000, beta=0.32, seed=0):
    # x força y (Sugihara et al., 2012): y mapeia x, x não mapeia y
    rng = np.random.default_rng(seed)
    x, y = np.empty(n), np.empty(n)
    x[0], y[0] = rng.uniform(0.2, 0.8, 2)
    for t in range(n - 1):
        x[t + 1] = x[t] * (3.8 - 3.8 * x[t])
        y[t + 1] = y[t] * (3.5 - 3.5 * y[t] - beta * x[t])
    return x, y


def test_ccm_finds_the_driver():
    x, y = _coupled_logistic()
    sizes = np.array([50, 900])
    y_maps_x = C.ccm(y, x, E=2, tau=1, theiler=0, sizes=sizes, samples=10)
    x_maps_y = C.ccm(x, y, E=2, tau=1, theiler=0, sizes=sizes, samples=10)
    assert y_maps_x.rho.iloc[-1] > 0.8 and y_maps_x.rho.iloc[-1] > y_maps_x.rho.iloc[0]
    assert x_maps_y.rho.iloc[-1] < y_maps_x.rho.iloc[-1] - 0.3


def test_seasonal_surrogate_permutes_whole_years():
    x = np.repeat(np.arange(10), 46).astype(float)
    s = C.seasonal_surrogate(x, np.random.default_rng(1))
    assert sorted(s) == sorted(x)
    assert all(len(set(s[i:i + 46])) == 1 for i in range(0, 460, 46))


def test_ccm_test_rejects_with_coupling_and_not_without():
    rng = np.random.default_rng(2)
    n = 46 * 20
    d = rng.normal(size=n)
    v = np.zeros(n)
    for t in range(1, n):
        v[t] = 0.6 * v[t - 1] + 0.8 * np.tanh(2 * d[t - 1]) + 0.2 * rng.normal()
    coupled = C.ccm_test(v, d, E=3, tau=1, theiler=1, n_surrogates=19, samples=3)
    assert coupled["pvalue"] <= 0.05 and coupled["rho"] > coupled["rho_nulo"]
    alone = C.ccm_test(rng.normal(size=n), d, E=3, tau=1, theiler=1, n_surrogates=19,
                       samples=3)
    assert alone["pvalue"] > 0.05


def test_compare_forecasts_sees_atmospheric_forcing():
    rng = np.random.default_rng(3)
    n = 1100
    d = rng.normal(size=n)
    h = np.convolve(rng.normal(size=n), np.ones(4) / 2, "same")
    v = np.zeros(n)
    for t in range(1, n):
        v[t] = 0.5 * v[t - 1] - 0.6 * d[t - 1] + 0.3 * h[t - 1] + 0.3 * rng.normal()
    out = C.compare_forecasts({"v": v, "d": d, "h": h}, "v", ["d", "h"], m=2, tau=1,
                              theiler=1).set_index(["preditores", "modelo"])
    assert out.loc[("conjunto", "linear"), "ganho"] > 0.2
    assert out.loc[("conjunto", "linear"), "p_dm"] < 0.01
    assert np.isnan(out.loc[("vegetacao", "linear"), "dm"])


def test_state_dependence_detects_a_state_dependent_response():
    rng = np.random.default_rng(4)
    n = 600
    d = rng.normal(size=n)
    v = np.zeros(n)
    for t in range(1, n):  # a resposta a d cresce com v
        v[t] = 0.5 * v[t - 1] - (0.2 + 0.5 * (v[t - 1] > 0)) * d[t - 1] + 0.1 * rng.normal()
    r = C.state_dependence({"v": v, "d": d}, "v", "d", m=1, tau=1, theta=4)
    assert r < -0.3


def test_baci_recovers_the_effect_and_recovery():
    rows_b, rows_c, clusters = [], [], {}
    rng = np.random.default_rng(5)
    for e in range(40):
        clusters[e] = e % 8
        common = rng.normal(size=200)
        for k in range(-46, 138):
            effect = -1.0 * np.exp(-k / 20) if k > 0 else 0.0
            rows_b.append({"episodio": e, "k": k, "v": common[k + 46] + effect
                           + 0.05 * rng.normal()})
            for _ in range(3):
                rows_c.append({"episodio": e, "k": k, "v": common[k + 46] + 0.05 * rng.normal()})
    delta = C.baci(pd.DataFrame(rows_b), pd.DataFrame(rows_c))
    assert 0 not in set(delta.k)
    summary, recovery = C.baci_summary(delta, pd.Series(clusters), n=199)
    assert summary.set_index("k").delta.loc[1] < -0.8
    assert 40 < recovery < 138


def test_response_change_finds_the_interaction():
    rng = np.random.default_rng(6)
    rows = []
    for pixel in range(60):
        burned = pixel < 30
        for t in range(80):
            after = t >= 40
            h, d, v = rng.normal(), rng.normal(), rng.normal()
            slope = -0.3 - (0.4 if burned and after else 0.0)
            rows.append({"pixel": pixel, "celula": pixel % 6, "queimado": int(burned),
                         "depois": int(after), "v": v, "h": h, "d": d,
                         "v_next": 0.5 * v + slope * d + 0.2 * h + 0.1 * rng.normal()})
    out = C.response_change(pd.DataFrame(rows)).set_index("termo")
    assert -0.5 < out.loc["d_qd", "coeficiente"] < -0.3 and out.loc["d_qd", "p"] < 0.01
    assert abs(out.loc["h_qd", "coeficiente"]) < 0.05
    broken = pd.DataFrame(rows)
    broken.loc[:9, "v"] = np.inf                # anomalia com desvio nulo
    broken.loc[10:19, "d"] = np.nan
    again = C.response_change(broken).set_index("termo")
    assert np.isfinite(again.coeficiente).all()


def test_anomaly_with_constant_slot_is_missing_not_infinite():
    from amazon_chaos.nonlinear import fire_response as R

    dates = pd.to_datetime(["2010-01-01", "2011-01-01", "2010-01-09", "2011-01-09"])
    frame = pd.DataFrame({"id": "p", "data": dates, "valor": [5.0, 5.0, 4.0, 6.0]})
    z = R._anomaly(frame, "valor")
    assert z.iloc[:2].isna().all() and np.allclose(z.iloc[2:], [-0.7071, 0.7071], atol=1e-4)


def test_quality_filters():
    assert V.lai_ok(np.array([0b00000000, 0b00100000, 0b01000000, 0b00001000])).tolist() == [
        True, True, False, False]
    state = np.array([0, 1, 0b100, 0b11000000, 0b10000000000])
    qc = np.zeros(5)
    assert V.reflectance_ok(state, qc, np.full(5, 20.0)).tolist() == [True, False, False,
                                                                       False, False]
    assert not V.reflectance_ok(np.array([0]), np.array([1 << 6]), np.array([20.0]))[0]
    assert not V.reflectance_ok(np.array([0]), np.array([0]), np.array([40.0]))[0]
    assert np.isclose(V.ndmi(np.array([3000]), np.array([1000]))[0], 0.5)
    assert V.burned(np.array([0, 150, -1, 200]), np.array([1, 1, 1, 0])).tolist() == [
        False, True, False, False]


def test_prepare_standardizes_by_composite_and_flags_gaps():
    dates = pd.DatetimeIndex([d for y in range(2001, 2011)
                              for d in pd.date_range(f"{y}-01-01", periods=46, freq="8D")])
    rng = np.random.default_rng(7)
    x = np.asarray(5 + np.sin(2 * np.pi * dates.dayofyear / 365) + rng.normal(0, 0.1, len(dates)))
    x[10:13] = np.nan
    z, missing, ok = V.prepare(x, dates)
    assert ok and missing.sum() == 3 and np.isfinite(z).all()
    assert abs(np.nanmean(z[~missing])) < 0.05 and 0.8 < np.std(z[~missing]) < 1.2
    x[:200] = np.nan
    assert not V.prepare(x, dates)[2]


def test_episodes_follow_the_rules(monkeypatch):
    import geopandas as gpd
    from shapely.geometry import box

    from amazon_chaos.features import fire_episodes as F

    lat = np.array([-1.0, -1.01, -1.02])
    lon = np.array([-50.0, -49.99, -49.98, -49.97])
    months = list(pd.date_range("2001-01-01", "2024-12-01", freq="MS"))
    stack = np.zeros((len(months), 3, 4), bool)
    k = months.index(pd.Timestamp("2010-08-01"))
    stack[k, 0, 0] = True                       # válido
    stack[k, 0, 1] = True
    stack[k + 5, 0, 1] = True                   # requeima
    stack[k, 1, 0] = True
    stack[k - 6, 1, 0] = True                   # queimou há menos de 2 anos
    stack[k, 1, 1] = True                       # perde floresta depois
    forest = {y: np.ones((3, 4), bool) for y in range(2001, 2024)}
    for y in (2011, 2012):
        forest[y] = forest[y].copy()
        forest[y][1, 1] = False
    monkeypatch.setattr(F, "burn_history", lambda cfg: (stack, months, lat, lon))
    monkeypatch.setattr(F, "_annual_forest", lambda cfg, a, b: forest)
    cells = gpd.GeoDataFrame({"cell_id": ["c"]}, geometry=[box(-50.1, -1.1, -49.9, -0.9)],
                             crs="EPSG:4326")
    monkeypatch.setattr(F.regions, "cells", lambda cfg: cells)
    chosen, pool = F.episodes({"slug": "t"})
    assert len(chosen) == 1 and (chosen.i.iloc[0], chosen.j.iloc[0]) == (0, 0)
    assert {"ano", "mes", "cell_id"} <= set(chosen.columns)
    # o pixel que queimou 6 meses antes é um episódio naquela data, com requeima
    assert chosen.attrs["resumo"] == {"encontrados": 4, "validos": 1, "requeima": 2,
                                      "perdem_floresta": 1}
    burnt = stack.any(axis=0)
    assert len(pool) == min(10, int((~burnt).sum()))
    assert not any((r.lat, r.lon) in {(lat[a], lon[b]) for a, b in zip(*np.nonzero(burnt),
                                                                       strict=True)}
                   for r in pool.itertuples())


def test_episodes_only_in_the_given_cells(monkeypatch):
    import geopandas as gpd
    from shapely.geometry import box

    from amazon_chaos.features import fire_episodes as F

    lat = np.array([-1.0, -1.01])
    lon = np.array([-50.0, -49.99, -49.98, -49.97])
    months = list(pd.date_range("2001-01-01", "2024-12-01", freq="MS"))
    stack = np.zeros((len(months), 2, 4), bool)
    k = months.index(pd.Timestamp("2010-08-01"))
    stack[k, 0, 0] = stack[k, 0, 2] = True      # um episódio em cada célula
    forest = {y: np.ones((2, 4), bool) for y in range(2001, 2024)}
    monkeypatch.setattr(F, "burn_history", lambda cfg: (stack, months, lat, lon))
    monkeypatch.setattr(F, "_annual_forest", lambda cfg, a, b: forest)
    cells = gpd.GeoDataFrame({"cell_id": ["a", "b"]},
                             geometry=[box(-50.1, -1.1, -49.985, -0.9),
                                       box(-49.985, -1.1, -49.9, -0.9)], crs="EPSG:4326")
    monkeypatch.setattr(F.regions, "cells", lambda cfg: cells)
    chosen, pool = F.episodes({"slug": "t"})
    assert set(chosen.cell_id) == {"a", "b"}
    chosen, pool = F.episodes({"slug": "t"}, F.LOCAL_RULES, only=["b"])
    assert list(chosen.cell_id) == ["b"] and set(pool.cell_id) == {"b"}
    assert (pool.lon > -49.985).all()


def test_cube_series_reads_points_like_the_point_request(monkeypatch):
    import xarray as xr

    from amazon_chaos.features import fire_episodes as F

    times = pd.date_range("2010-01-01", periods=3, freq="8D")
    lat, lon = np.array([-1.0, -1.01]), np.array([-50.0, -49.99])
    shape = (3, 2, 2)
    refl = xr.Dataset({
        "sur_refl_b02": (("time", "lat", "lon"), np.full(shape, 4800)),
        "sur_refl_b06": (("time", "lat", "lon"), np.full(shape, 1200)),
        "sur_refl_state_500m": (("time", "lat", "lon"), np.zeros(shape, int)),
        "sur_refl_qc_500m": (("time", "lat", "lon"), np.zeros(shape, int)),
        "sur_refl_vzen": (("time", "lat", "lon"), np.full(shape, 10.0)),
        "sur_refl_day_of_year": (("time", "lat", "lon"), np.full(shape, 5))},
        coords={"time": times, "lat": lat, "lon": lon})
    lai_values = np.full((2, 2, 2), 5.0)
    lai_values[1, 0, 1] = 25.0                  # fora do intervalo físico
    lai = xr.Dataset({"Lai_500m": (("time", "lat", "lon"), lai_values),
                      "FparLai_QC": (("time", "lat", "lon"), np.zeros((2, 2, 2), int))},
                     coords={"time": times[:2], "lat": lat, "lon": lon})
    monkeypatch.setattr(F.V, "_open", lambda cfg, pattern: refl if "MOD09" in pattern else lai)
    points = pd.DataFrame({"id": ["e", "c"], "lat": [-1.0, -1.0], "lon": [-50.0, -49.99]})
    out = F.cube_series({}, points)
    ndmi = out[out.variavel == "ndmi"]
    assert len(ndmi) == 6 and np.allclose(ndmi.valor, 0.6) and (ndmi.dia_obs == 5).all()
    lai_out = out[out.variavel == "lai"].set_index(["id", "data"]).valor
    assert len(lai_out) == 4 and np.isnan(lai_out.loc[("c", times[1])])
    assert lai_out.loc[("e", times[1])] == 5.0


def test_point_series_and_matching():
    from amazon_chaos.features import fire_episodes as F

    dates = pd.date_range("2008-01-01", "2012-12-31", freq="8D")
    rows = []
    for pid, level in [("e", 0.6), ("c1", 0.6), ("c2", 0.3), ("c3", 0.61), ("c4", 0.9)]:
        for d in dates:
            rows.append({"ID": pid, "Date": d.strftime("%Y-%m-%d"),
                         "MOD09A1_061_sur_refl_b02": 3000 * (1 + level),
                         "MOD09A1_061_sur_refl_b06": 3000 * (1 - level),
                         "MOD09A1_061_sur_refl_state_500m": 0,
                         "MOD09A1_061_sur_refl_qc_500m": 0,
                         "MOD09A1_061_sur_refl_vzen": 10.0,
                         "MOD09A1_061_sur_refl_day_of_year": d.dayofyear + 3})
    series = F.point_series([pd.DataFrame(rows)])
    assert np.allclose(series[series.id == "e"].valor, 0.6)
    chosen = pd.DataFrame({"episodio": ["e"], "mes": [pd.Timestamp("2011-08-01")]})
    pool = pd.DataFrame({"episodio": "e", "candidato": ["c1", "c2", "c3", "c4"]})
    matched = F.match(chosen, pool, series, controls=2)
    assert set(matched.controle) == {"c1", "c3"}
    burned, controls = F.delta_tables(chosen, matched, series, "ndmi")
    assert burned.k.min() >= -46 and (burned.k == 0).any()
    assert set(controls.episodio) == {"e"} and len(controls) == 2 * len(burned)


def test_composite_index_is_unique_across_the_year_boundary():
    from amazon_chaos.features import fire_episodes as F

    dates = pd.DatetimeIndex([pd.Timestamp(y, 1, 1) + pd.Timedelta(days=8 * j)
                              for y in (2010, 2011, 2012) for j in range(46)])
    k = F.composite_index(dates, pd.Timestamp("2011-08-15"))
    assert len(set(k)) == len(dates) and (np.diff(k) == 1).all()
    assert dates[k == 0][0] == pd.Timestamp("2011-08-05")   # primeira que começa em agosto
    rows = F.composite_index(dates[:2], pd.Series([pd.Timestamp("2010-01-01")] * 2))
    assert list(rows) == [0, 1]


def test_unique_time_drops_the_composite_shared_by_two_files():
    import xarray as xr

    from amazon_chaos.features import vegetation as V

    times = pd.to_datetime(["2012-12-18", "2012-12-26", "2012-12-26", "2013-01-01"])
    ds = xr.Dataset({"v": ("time", [1.0, 2.0, 2.0, 3.0])}, coords={"time": times})
    out = V.unique_time(ds)
    assert list(out.v.values) == [1.0, 2.0, 3.0] and out.indexes["time"].is_unique


def test_point_payloads_fit_and_cover_each_episode():
    from amazon_chaos.features import fire_episodes as F

    rng = np.random.default_rng(0)
    years = rng.integers(2003, 2022, 300)
    chosen = pd.DataFrame({"episodio": [f"e{k}" for k in range(300)], "ano": years,
                           "lat": -5.0, "lon": -55.0})
    pool = pd.DataFrame({"episodio": np.repeat(chosen.episodio, 10), "lat": -5.0, "lon": -55.0})
    pool["candidato"] = pool.episodio + "_c" + (pool.groupby("episodio").cumcount()).astype(str)
    payloads = F.point_payloads({"slug": "x"}, chosen, pool, max_values=1_500_000)
    assert len(payloads) > 1
    seen = []
    for p in payloads.values():
        coords = p["params"]["coordinates"]
        start = int(p["params"]["dates"][0]["startDate"][-4:])
        end = int(p["params"]["dates"][0]["endDate"][-4:])
        assert len(coords) * len(p["params"]["layers"]) * 46 * (end - start + 1) <= 1_500_000
        eps = [c["id"] for c in coords if c["category"] == "queimado"]
        y = chosen.set_index("episodio").ano.loc[eps]
        assert (y - 2 >= start).all() and (y + 3 <= end).all()
        assert sum(c["category"] == "controle" for c in coords) == 10 * len(eps)
        seen += eps
    assert sorted(seen) == sorted(chosen.episodio)


def test_full_grid_keeps_empty_composites_and_coverage_masks():
    from amazon_chaos.features import vegetation as V
    from amazon_chaos.nonlinear.vegetation_dynamics import full_grid

    dates = pd.date_range("2001-01-01", periods=6, freq="8D")
    rows = [{"cell_id": c, "composicao": d, "variavel": v, "valor": 1.0 + k,
             "validos": 0 if k in (2, 3) else 50, "mascara": 100}
            for c in ("a", "b") for k, d in enumerate(dates) for v in ("lai", "ndmi")]
    table = V.with_coverage(pd.DataFrame(rows), 0.05)
    table.loc[table.validos == 0, "valor"] = np.nan
    wide = full_grid(table)
    assert len(wide.loc["a"]) == 6
    assert wide.loc["a"].lai.isna().tolist() == [False, False, True, True, False, False]
    assert V.with_coverage(pd.DataFrame(rows), 0.6).valor.isna().all()
