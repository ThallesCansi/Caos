import cftime
import numpy as np
import pandas as pd
import xarray as xr

from amazon_chaos.features import lst
from amazon_chaos.features.lst import good_quality, month_year


def test_quality_filter_keeps_best_pixels_decoded_as_nan():
    # 0 (melhor qualidade, decodificado como NaN), 1 (outra qualidade), 2 (nuvem),
    # 0b01000001 (erro ≤ 2 K) e 0b11000000 (erro > 3 K)
    qc = np.array([np.nan, 0, 1, 2, 0b01000001, 0b11000000])
    assert good_quality(qc).tolist() == [True, True, True, False, True, False]


def test_cftime_step_gives_month_and_year():
    times = [cftime.DatetimeJulian(2007, 7, 20)]
    ds = xr.Dataset(coords={"time": times})
    assert month_year(ds.isel(time=0).time.values) == (7, 2007)
    plain = xr.Dataset(coords={"time": np.array(["2007-07-20"], dtype="datetime64[ns]")})
    assert month_year(plain.isel(time=0).time.values) == (7, 2007)


def passage_year(year, lon=(-60.0, -52.5), clouds=0.0):
    """Campos sintéticos: skt e t2m crescem 1 K por hora UTC a partir de 300 e 290 K."""
    times = pd.DatetimeIndex([t for d in pd.date_range(f"{year}-06-01", f"{year}-09-30")
                              for t in d + pd.to_timedelta([13, 14, 15], "h")])
    hour = times.hour.to_numpy(float)[:, None, None] * np.ones((1, 1, len(lon)))
    coords = {"valid_time": times, "latitude": [-5.0], "longitude": list(lon)}
    dims = ("valid_time", "latitude", "longitude")
    return xr.Dataset({"skt": (dims, 300 + (hour - 13)), "t2m": (dims, 290 + (hour - 13)),
                       "tcc": (dims, np.full(hour.shape, clouds))}, coords=coords)


def test_overpass_interpolates_to_solar_morning_by_longitude():
    assert np.allclose(lst.overpass_utc([-60.0, -52.5]), [14.5, 14.0])
    day = lst.at_overpass(passage_year(2001))
    assert day.skt.dims == ("latitude", "longitude", "day")
    assert np.allclose(day.skt.isel(day=0, latitude=0), [301.5, 301.0])
    assert day.sizes["day"] == 122


def test_era5_overpass_means_halves_and_clear_sky(tmp_path, monkeypatch):
    for year, clouds in [(2001, 0.1), (2013, 0.9)]:
        ds = passage_year(year, clouds=clouds)
        ds["skt"] = ds.skt + (year == 2013)
        ds.to_netcdf(tmp_path / f"{year}.nc")
    cells = pd.DataFrame({"cell_id": ["a", "b"], "latitude": [-5.0, -5.0],
                          "longitude": [-60.0, -52.5]})
    monkeypatch.setattr(lst.regions, "cells", lambda cfg: cells)
    out = lst.era5_overpass({}, tmp_path)
    assert np.allclose(out.era5_skt_1030_seca, [28.85, 28.35])
    assert np.allclose(out.delta_era5_skt_1030_seca, 1.0)
    assert np.allclose(out.delta_era5_t2m_1030_seca, 0.0)
    # só 2001 tem céu limpo, então a média de céu limpo é a do ano sem o +1 K
    assert np.allclose(out.era5_skt_1030_seca_limpo, [28.35, 27.85])
    assert np.allclose(out.era5_fracao_limpo, 0.5)
