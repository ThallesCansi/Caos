"""Checagens dos novos contrastes, sem acesso à rede ou aos dados do TCC."""

import json

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

from amazon_chaos import territorial_comparison as T


def test_covered_area_counts_overlapping_protection_only_once():
    grid = gpd.GeoDataFrame(geometry=[box(0, 0, 2, 2)], crs=6933)
    polygons = gpd.GeoDataFrame(geometry=[box(0, 0, 1.5, 2), box(1, 0, 2, 2)], crs=6933)
    assert T.covered_area(grid, polygons).tolist() == [4.]


def test_modis_clock_handles_short_last_composite_and_exact_fire_date():
    dates = pd.to_datetime(["2004-12-26", "2005-01-01", "2005-01-09"])
    assert np.diff(T.ordinal(dates)).tolist() == [1, 1]
    # Queima no dia 7 pertence à composição de 1º de janeiro, não à de 9 de janeiro.
    assert (T.ordinal(dates) - T.ordinal(["2005-01-07"])).tolist() == [-1, 0, 1]


def test_bootstrap_keeps_cells_and_weights_episodes_equally():
    frame = pd.DataFrame({"cell_id": ["a", "a", "b", "c", "d", "e"],
                          "episodio": ["a1", "a2", "b1", "c1", "d1", "e1"],
                          "delta": [0., 0., 1., 2., 3., 6.]})
    result = T.cluster_mean(frame, "delta", draws=99)
    assert result["celulas"] == 5
    assert result["episodios"] == 6
    assert result["media"] == 2
    assert result["ic_inf"] <= 2 <= result["ic_sup"]
    # Repetir todos os registros de uma mesma composição não cria novos episódios.
    assert T.cluster_mean(pd.concat([frame, frame]), "delta", draws=99) == result
    assert np.isnan(T.cluster_mean(frame[frame.cell_id != "e"], "delta")["ic_inf"])


def test_recovery_uses_exact_date_and_at_least_two_valid_controls(tmp_path, monkeypatch):
    monkeypatch.setattr(T, "processed", lambda slug: tmp_path)
    base = tmp_path / "vegetacao/fogo_subamostra"
    base.mkdir(parents=True)
    dates = pd.date_range("2003-01-01", "2005-01-01", freq="8D")
    # Adiciona observações pós-fogo. O pré possui registros suficientes.
    dates = dates.union(pd.to_datetime(["2005-01-09", "2005-01-17", "2005-01-25"]))
    rows = []
    for date in dates:
        after = date > pd.Timestamp("2005-01-07")
        for pixel, value in [("e", 4. if after else 6.), ("c1", 5.), ("c2", 5.)]:
            if pixel == "c2" and date == pd.Timestamp("2005-01-17"):
                value = np.nan
            rows.append({"id": pixel, "data": date, "variavel": "lai", "valor": value})
    pd.DataFrame(rows).to_parquet(base / "pontos.parquet", index=False)
    pd.DataFrame({"episodio": ["e", "e"], "controle": ["c1", "c2"]}).to_parquet(
        base / "pareamento.parquet", index=False)
    episodes = pd.DataFrame({"episodio": ["e"], "cell_id": ["g"],
                             "data_queima": pd.to_datetime(["2005-01-07"])})
    out = T.recovery("fake", episodes)
    assert not out.k.eq(0).any()
    assert out.loc[out.data.eq("2005-01-09"), "k"].item() == 1
    assert out.loc[out.data.eq("2005-01-09"), "delta"].item() == -2.
    assert np.isnan(out.loc[out.data.eq("2005-01-17"), "delta"].item())


def test_summary_does_not_fill_empty_windows_or_accept_sparse_episode():
    data = pd.DataFrame({"episodio": ["e"] * 3, "cell_id": ["g"] * 3,
                         "variavel": ["lai"] * 3, "grupo": ["um"] * 3,
                         "k": [1, 2, 3], "delta": [-1., -1., -1.]})
    summary = T.recovery_summary(data, "grupo")
    first = summary[summary.janela == "Até 1,5 mês"].iloc[0]
    assert first.episodios == 1
    assert first.media == -1.
    assert np.isnan(summary[summary.janela == "2–3 anos"].iloc[0].media)
    sparse = T.recovery_summary(data.iloc[:2], "grupo")
    assert sparse[sparse.janela == "Até 1,5 mês"].iloc[0].episodios == 0


def test_missing_seasonal_reference_does_not_remove_mean_baseline_observation(
        tmp_path, monkeypatch):
    monkeypatch.setattr(T, "processed", lambda slug: tmp_path)
    base = tmp_path / "vegetacao/fogo_subamostra"
    base.mkdir(parents=True)
    # 24 composições prévias, mas nenhuma no slot de 9 de janeiro.
    dates = pd.date_range("2004-03-05", periods=24, freq="8D").union(
        pd.to_datetime(["2005-01-09"]))
    rows = [{"id": pixel, "data": date, "variavel": "lai", "valor": value}
            for date in dates for pixel, value in [("e", 4.), ("c1", 5.), ("c2", 5.)]]
    pd.DataFrame(rows).to_parquet(base / "pontos.parquet", index=False)
    pd.DataFrame({"episodio": ["e", "e"], "controle": ["c1", "c2"]}).to_parquet(
        base / "pareamento.parquet", index=False)
    episodes = pd.DataFrame({"episodio": ["e"], "cell_id": ["g"],
                             "data_queima": pd.to_datetime(["2005-01-07"])})
    post = T.recovery("fake", episodes).query("k == 1")
    assert len(post) == 1
    assert post.delta.item() == 0.
    assert np.isnan(post.delta_sazonal.item())


def test_monthly_fire_excludes_incomplete_previous_month_not_current_month(tmp_path, monkeypatch):
    monkeypatch.setattr(T, "processed", lambda slug: tmp_path)
    (tmp_path / "chirps").mkdir()
    (tmp_path / "perturbacao").mkdir()
    days = pd.date_range("2002-01-01", "2006-12-31")
    rain = pd.DataFrame({"a": days.year.to_numpy() - 2000.}, index=days)
    rain.loc["2004-05-15", "a"] = np.nan
    rain.to_parquet(tmp_path / "chirps/diario.parquet")
    months = pd.date_range("2003-01-01", "2006-12-01", freq="MS")
    fire = pd.DataFrame([np.zeros(len(months))], index=pd.Index(["a"], name="cell_id"),
                        columns=months.strftime("%Y-%m"))
    fire.to_parquet(tmp_path / "perturbacao/focos_mensais.parquet")
    result = T.monthly_fire("fake", pd.DataFrame({"agro_frac_2000": [0.]}, index=["a"]))
    # 4 anos × 5 meses da estação, menos junho/2004 (maio incompleto).
    assert result["Meses-célula"].sum() == 19
    assert result["Meses com foco (%)"].eq(0).all()


def test_history_windows_excludes_event_year_and_uses_equal_lengths():
    years = list(range(2003, 2010))
    data = pd.DataFrame({"ano": years, "zona": ["uc"] * len(years),
                         "focos_100km2": [1., 3., 999., 4., 6., 100., 100.]})
    result = T.history_windows("xingu", data).iloc[0]
    assert result["Anos completos por janela"] == 2
    assert result["Focos/100 km²/ano antes"] == 2.
    assert result["Focos/100 km²/ano depois"] == 5.
    assert result["Mudança descritiva"] == 3.


def test_fixed_cohort_uses_intersection_of_all_windows_separately_by_variable():
    rows = []
    for variable in ("lai", "ndmi"):
        for episode in ("complete", "partial"):
            for j, (lo, hi) in enumerate(T.RECOVERY_WINDOWS.values()):
                if variable == "lai" and episode == "partial" and j == 3:
                    continue
                for k in range(lo, hi + 1):
                    rows.append({"episodio": episode, "cell_id": episode,
                                 "variavel": variable, "bacia": "xingu",
                                 "grupo": "all", "k": k, "delta": -1.})
    curves = pd.DataFrame(rows)
    fixed = T.window_means(curves, cohort="fixed")
    assert set(fixed[fixed.variavel == "lai"].episodio) == {"complete"}
    assert set(fixed[fixed.variavel == "ndmi"].episodio) == {"complete", "partial"}
    assert T.recovery_summary(curves, "grupo", cohort="fixed").query(
        "variavel == 'lai'").episodios.eq(1).all()
    available = T.recovery_summary(curves, "grupo")
    assert available.query("variavel == 'lai'").episodios.max() == 2


def test_basin_contrast_has_defined_direction_and_requires_five_cells_per_basin():
    rows = []
    for basin, value in [("xingu", -2.), ("tapajos", -1.)]:
        for i in range(5):
            for k in range(1, 7):
                rows.append({"bacia": basin, "episodio": f"{basin}_{i}",
                             "cell_id": f"{basin}_{i}", "variavel": "lai",
                             "k": k, "delta": value})
    curves = pd.DataFrame(rows)
    result = T.basin_contrast(curves, draws=99).iloc[2]
    assert result["Xingu − Tapajós"] == -1.
    assert result["IC inferior"] == result["IC superior"] == -1.
    without = curves[curves.cell_id != "tapajos_0"]
    assert np.isnan(T.basin_contrast(without).iloc[2]["Xingu − Tapajós"])


def test_selection_reports_paired_cells_not_cells_of_the_draw(tmp_path, monkeypatch):
    monkeypatch.setattr(T, "processed", lambda slug: tmp_path)
    base = tmp_path / "vegetacao/fogo_subamostra"
    base.mkdir(parents=True)
    (base / "episodios.json").write_text(json.dumps({"encontrados": 10,
        "requeima": 5, "perdem_floresta": 4, "validos": 3}), encoding="utf-8")
    pd.DataFrame({"episodio": ["a", "b"], "cell_id": ["x", "y"]}).to_parquet(
        base / "episodios.parquet")
    pd.DataFrame({"episodio": ["a"], "controle": ["c"]}).to_parquet(
        base / "pareamento.parquet")
    result = T.selection_table("fake")
    assert result.iloc[-2]["Células ERA5"] == 2
    assert result.iloc[-1]["Células ERA5"] == 1
    assert pd.isna(result.iloc[0]["Células ERA5"])
