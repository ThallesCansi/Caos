"""Métricas por célula: perturbação, território, climatologia da chuva e metades do lote."""

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

from amazon_chaos import gradient as G
from amazon_chaos.features import disturbance, territory
from amazon_chaos.nonlinear import precip


def test_cover_metrics_use_land_without_water_or_gaps(monkeypatch):
    # célula a: 100 km², 10 de água, 10 sem dado, 60 de floresta, 20 de pasto (classe 15)
    tables = {}
    for year, forest in zip(disturbance.COVER_YEARS, [70, 60, 45, 30], strict=True):
        tables[f"mapbiomas_cobertura_{year}"] = pd.DataFrame(
            {"3": [forest], "15": [80 - forest], "33": [10], "0": [10]}, index=["a"])
    monkeypatch.setattr(disturbance, "_read", lambda cfg, name: tables[name])
    out = disturbance.cover_metrics({})
    assert out.terra_km2_2000.iloc[0] == 80
    assert out.agua_frac_2000.iloc[0] == 0.1
    assert out.floresta_frac_2000.iloc[0] == 60 / 80
    assert out.mb_perda_floresta_2001_2012.iloc[0] == (60 - 45) / 80
    assert out.mb_perda_floresta_2013_2024.iloc[0] == (45 - 30) / 80


def test_foci_metrics_density_and_censoring(monkeypatch):
    months = [f"{y}-{m:02d}" for y in range(2003, 2025) for m in range(1, 13)]
    counts = pd.DataFrame(0, index=["a", "b"], columns=months)
    counts.loc["a", "2005-08"] = 10
    counts.loc["a", "2020-09"] = 12
    monkeypatch.setattr(disturbance, "_read", lambda cfg, name: counts)
    out = disturbance.foci_metrics({}, pd.Series({"a": 200.0, "b": 200.0}))
    assert np.isclose(out.focos_100km2_ano_2003_2012["a"], 100 * 10 / 200 / 10)
    assert np.isclose(out.focos_100km2_ano_2013_2024["a"], 100 * 12 / 200 / 12)
    assert out.ultimo_foco_ano["a"] == 2020 and not out.ultimo_foco_censurado["a"]
    assert out.ultimo_foco_censurado["b"] and out.anos_com_foco_2003_2024["b"] == 0


def test_protection_counts_ti_and_uc_overlap_once(monkeypatch):
    cells = gpd.GeoDataFrame({"cell_id": ["a", "b"]},
                             geometry=[box(-55, -10, -54.75, -9.75),
                                       box(-54.75, -10, -54.5, -9.75)], crs="EPSG:4326")
    areas = cells.to_crs("EPSG:6933").area / 1e6
    cells["weight_km2"] = areas.to_numpy()
    ti = gpd.GeoDataFrame(geometry=[box(-55, -10, -54.75, -9.75)], crs="EPSG:4326")
    uc = gpd.GeoDataFrame(geometry=[box(-54.875, -10, -54.5, -9.75)], crs="EPSG:4326")
    monkeypatch.setattr(territory.regions, "cells", lambda cfg: cells)
    monkeypatch.setattr(territory.regions, "load_context",
                        lambda cfg: {"tis": ti, "ucs": uc})
    out = territory.protection({})
    assert np.isclose(out.frac_ti["a"], 1, atol=0.01) and np.isclose(out.frac_uc["a"], 0.5,
                                                                      atol=0.01)
    assert np.isclose(out.frac_protegida["a"], 1, atol=0.01)  # sem contar a sobreposição
    assert out.classe.to_dict() == {"a": "ti", "b": "uc"}


def test_rain_climatology(monkeypatch):
    days = pd.date_range("2001-01-01", "2002-12-31", freq="D")
    rain = pd.DataFrame({"a": np.where(days.month <= 6, 10.0, 0.5)}, index=days)
    monkeypatch.setattr(precip, "load_series", lambda cfg, source: rain)
    out = precip.climatology({}, "2001", "2002")
    assert np.isclose(out.chuva_anual_era5["a"], rain.a.sum() / 2)
    assert out.dias_secos_era5["a"] == 0  # 0,5 mm não é seco no limiar de 0,1 mm
    assert np.isclose(out.dias_secos_1mm_era5["a"], (days.month > 6).mean())
    assert out.meses_secos_era5["a"] == 6


def test_dither_breaks_ties_without_reordering():
    x = np.array([0.0, 0.0, 0.0, 1.0, 0.5, 0.5])
    y = precip.dither(x, seed=1)
    assert len(np.unique(y)) == len(y)
    assert (np.argsort(y)[-3:] == [4, 5, 3]).all() or (np.argsort(y)[-3:] == [5, 4, 3]).all()
    assert np.allclose(y, x, atol=1e-6)


def test_half_changes_pair_windows_whatever_the_row_order():
    rows = []
    for cell in ("a", "b"):
        for var in ("t2m", "vpd"):
            for desc in ("rqa_det", "pe_entropy"):
                for window, value in (("2001_2012", 1.0), ("2013_2024", 3.0), ("2001_2024", 9)):
                    bump = 0.5 if (cell, var) == ("b", "vpd") else 0
                    rows.append({"cell_id": cell, "variable": var, "descriptor": desc,
                                 "window": window, "observed": value + bump * (window > "2012")})
    tests = pd.DataFrame(rows).sample(frac=1, random_state=3)
    out = G.half_changes(tests)
    assert set(out.columns) == {"delta_t2m_rqa_det", "delta_t2m_pe_entropy",
                                "delta_vpd_rqa_det", "delta_vpd_pe_entropy"}
    assert out.loc["a", "delta_vpd_rqa_det"] == 2 and out.loc["b", "delta_vpd_rqa_det"] == 2.5
