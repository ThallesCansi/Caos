"""Garantias científicas dos contrastes: coorte comum, agrupamento e sensibilidade."""
import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr
from shapely.geometry import box

from amazon_chaos import context_followup as F


def test_pair_uses_only_episodes_observed_in_both_chosen_windows():
    rows = []
    for ep in ("both", "early_only"):
        for k in [1, 2, 3, *range(24, 36)]:
            if ep == "early_only" and k >= 24:
                continue
            rows.append({"variavel": "lai", "episodio": ep, "cell_id": "g",
                         "k": k, "delta": -2. if k < 24 else -.5, "valor": 4.,
                         "ano": 2010, "contexto_agro": "Até 10%", "vpd_pre_60d": .1})
    curves = pd.DataFrame(rows)
    pre = curves.iloc[:1].assign(k=-1, valor=6.)
    pairs = F.paired_episodes(pd.concat([curves, pre], ignore_index=True))
    assert pairs.episodio.tolist() == ["both"]
    assert pairs.mudanca.item() == 1.5
    assert pairs.vegetacao_pre.item() == 6.


def test_joint_cell_bootstrap_preserves_covariance_between_groups():
    rows = []
    for cell in range(8):
        for group, offset in zip(F.GROUPS, [0., 1., 2.], strict=True):
            rows.append({"cell_id": str(cell), "contexto_agro": group,
                         "inicial": float(cell), "posterior": cell + offset,
                         "mudanca": offset})
    point, boot, _ = F._bootstrap(pd.DataFrame(rows), adjusted=False, draws=99)
    # Mesmas células nos contextos: a diferença posterior é exatamente 2 em TODAS as réplicas.
    np.testing.assert_allclose(boot[:, 2, 1] - boot[:, 0, 1], 2.)
    assert np.isclose(point[2, 1] - point[0, 1], 2.)
    few = pd.DataFrame(rows).query("cell_id != '7' and cell_id != '6' and cell_id != '5'"
                                   " and cell_id != '4'")
    point, boot, _ = F._bootstrap(few, adjusted=False, draws=9)
    assert np.isnan(point).all() and np.isnan(boot).all()


def test_adjustment_recovers_known_group_contrast_and_keeps_same_complete_cases():
    rng = np.random.default_rng(17)
    rows = []
    for cell in range(30):
        for group, number in zip(F.GROUPS, range(3), strict=True):
            year = int(rng.integers(2003, 2022))
            drought, pre = rng.normal() + 2 * number, rng.normal() + 5
            change = 2 * number + 3 * drought + .1 * year - .5 * pre
            rows.append({"cell_id": str(cell), "contexto_agro": group, "variavel": "lai",
                         "ano": year, "vpd_pre_60d": drought, "vegetacao_pre": pre,
                         "inicial": -2., "posterior": -2 + change, "mudanca": change})
    data = pd.DataFrame(rows)
    data.loc[0, "vegetacao_pre"] = np.nan
    _, contrasts = F.context_comparison(data, draws=99)
    chosen = contrasts[(contrasts.Contraste == "Mais de 30% menos Até 10%")
                       & (contrasts.Medida == "mudanca")].set_index("Modelo")
    assert chosen.loc["Bruto", "Episódios"] == 90
    assert chosen.loc["Bruto: casos completos", "Episódios"] == 89
    assert chosen.loc["Ajuste linear", "Episódios"] == 89
    assert np.isclose(chosen.loc["Ajuste linear", "Estimativa"], 4.)
    assert chosen.loc["Bruto: casos completos", "Estimativa"] > 8.


def test_historical_sensitivity_excludes_decree_and_omits_same_year_in_both_zones():
    rows = [{"ano": year, "zona": zone, "focos_100km2": value + offset}
            for zone, offset in zip(F.ZONE_COLORS, [0., 10.], strict=True)
            for year, value in zip(range(2003, 2008), [1., 3., 999., 4., 6.], strict=True)]
    # O offset constante não muda a diferença antes/depois, mas permite duas zonas.
    data = pd.DataFrame(rows)
    s = F.history_sensitivity("xingu", data)
    assert set(s.Largura) == {1, 2}
    assert not s["Anos antes"].str.contains("2005").any()
    assert not s["Anos depois"].str.contains("2005").any()
    baseline = s[(s.Largura == 2) & s["Ano retirado"].isna()]
    assert baseline[baseline.Zona == "Área da UC atual"]["Mudança"].item() == 3.
    assert baseline[baseline.Zona == "Mudança UC menos entorno"]["Mudança"].item() == 0.
    for (_, omitted), frame in s[s["Ano retirado"].notna()].groupby(["Largura", "Ano retirado"]):
        assert frame["Anos antes"].nunique() == frame["Anos depois"].nunique() == 1
        assert not frame["Anos antes"].str.contains(str(int(omitted))).any()
        assert not frame["Anos depois"].str.contains(str(int(omitted))).any()


def test_climate_uses_intersection_area_and_rejects_incomplete_cell_year(tmp_path, monkeypatch):
    monkeypatch.setattr(F.T, "processed", lambda slug: tmp_path)
    (tmp_path / "chirps").mkdir()
    grid = gpd.GeoDataFrame({"latitude": [.5, .5], "longitude": [.5, 1.5]},
                            geometry=[box(0, 0, 1, 1), box(1, 0, 2, 1)],
                            index=["a", "b"], crs=4326)
    zones = gpd.GeoDataFrame({"zona": ["whole", "second"]},
                             geometry=[box(0, 0, 2, 1), box(1, 0, 2, 1)], crs=4326)
    dates = pd.date_range("2003-01-01", "2004-12-31")
    rain = pd.DataFrame({"a": 1., "b": 3.}, index=dates)
    rain.loc["2004-01-01":"2004-03-01", "b"] = np.nan
    rain.to_parquet(tmp_path / "chirps/diario.parquet")
    for year in (2003, 2004):
        days = dates[dates.year == year]
        values = np.broadcast_to([1., 3.], (len(days), 1, 2)).copy()
        xr.Dataset({"vpd_kpa_mean": (("time", "latitude", "longitude"), values)},
                   coords={"time": days, "latitude": [.5], "longitude": [.5, 1.5]}).to_netcdf(
                       tmp_path / f"daily_{year}-01-01_{year}-12-31.nc")
    result = F.history_climate("fake", {"grid": grid}, zones, years=(2003, 2004))
    vpd = result[result.Variável == "VPD (kPa)"].set_index(["ano", "zona"])
    assert np.isclose(vpd.loc[(2003, "whole"), "Valor"], 2.)
    assert np.isclose(vpd.loc[(2003, "second"), "Valor"], 3.)
    rain_result = result[result.Variável == "Chuva (mm/ano)"].set_index(["ano", "zona"])
    assert np.isclose(rain_result.loc[(2003, "whole"), "Valor"], 730.)
    assert np.isnan(rain_result.loc[(2004, "whole"), "Valor"])
    assert np.isnan(rain_result.loc[(2004, "second"), "Valor"])
