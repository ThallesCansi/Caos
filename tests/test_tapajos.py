import copy

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from shapely.geometry import box

from amazon_chaos.config import load_config


def hourly_fixture():
    times = pd.date_range("2024-01-01", "2024-01-03", freq="h")
    shape = (len(times), 2, 2)
    coords = {"valid_time": times, "latitude": [-2.25, -2.5], "longitude": [-56, -55.75]}
    units = {"t2m": "K", "d2m": "K", "sp": "Pa", "u10": "m s**-1", "v10": "m s**-1", "tp": "m"}
    values = {"t2m": 293.15, "d2m": 293.15, "sp": 100000, "u10": 3, "v10": 4, "tp": 0.001}
    return xr.Dataset(
        {
            k: xr.DataArray(
                np.full(shape, v), coords=coords, dims=list(coords), attrs={"units": units[k]}
            )
            for k, v in values.items()
        }
    )


def test_grid_covers_bbox_without_overlap_and_clips_edge_cells():
    from amazon_chaos.preprocess.grid import build_grid

    grid = build_grid([-2.25, -56, -3.75, -54.25])
    assert len(grid) == 56
    assert grid.cell_id.is_unique
    assert grid.geometry.union_all().equals(box(-56, -3.75, -54.25, -2.25))
    assert grid.geometry.apply(lambda g: g.area).sum() == pytest.approx(2.625)
    assert grid.iloc[0].geometry.area == pytest.approx(0.015625)
    assert (grid.area_km2 > 0).all()


def test_month_plan_handles_leap_year_and_utc_support_day():
    from amazon_chaos.io.era5_monthly import plan_requests

    config = load_config("configs/pilot.yaml")
    jobs = plan_requests(config, "2024-02-01", "2024-02-29")
    assert len(jobs) == 4
    assert jobs[0]["request"]["day"][-1] == "29"
    assert jobs[-1]["request"]["month"] == ["03"]
    assert jobs[-1]["request"]["day"] == ["01"]
    other = copy.deepcopy(config)
    other["spatial"]["area"][0] = -1.25
    assert jobs[0]["key"] != plan_requests(other, "2024-02-01", "2024-02-29")[0]["key"]
    new_year = plan_requests(config, "2024-12-31", "2024-12-31")
    assert new_year[-1]["request"]["year"] == ["2025"]
    with pytest.raises(ValueError):
        plan_requests(config, "2024-03-01", "2024-02-29")


def test_daily_local_precipitation_and_saturated_humidity():
    from amazon_chaos.preprocess.daily import daily_statistics, derive_hourly

    raw = hourly_fixture()
    # 03 UTC terminates an interval in the PREVIOUS local day.
    raw["tp"][3] = 0.1
    hourly = derive_hourly(raw)
    daily = daily_statistics(hourly, "2024-01-01", "2024-01-01")
    assert np.allclose(daily.precip_mm_sum, 24)
    assert np.allclose(daily.rh_pct_mean, 100)
    assert np.allclose(daily.vpd_kpa_mean, 0)
    assert np.allclose(daily.wind_speed_10m_mean, 5)
    assert np.allclose(daily.t2m_c_max, 20)
    assert np.allclose(daily.t2m_c_n_hours, 24)
    assert np.allclose(daily.q_gkg_mean, 14.67, atol=0.03)


def test_dewpoint_tolerance_absorbs_edh_rounding_only():
    from amazon_chaos.preprocess.daily import derive_hourly

    raw = hourly_fixture()
    raw["d2m"] = raw.t2m + 0.28  # margem CDS + arredondamento do EDH (0,05 + 2 × 0,125 K)
    assert derive_hourly(raw).humidity_flag.all()
    edh = derive_hourly(raw, dewpoint_tolerance_k=0.3)
    assert not edh.humidity_flag.any() and np.allclose(edh.rh_pct, 100)
    raw["d2m"] = raw.t2m + 0.35
    assert derive_hourly(raw, dewpoint_tolerance_k=0.3).humidity_flag.all()


def test_daily_missing_hours_never_become_zero_rain_or_complete_means():
    from amazon_chaos.preprocess.daily import daily_statistics, derive_hourly

    raw = hourly_fixture().drop_sel(valid_time=pd.Timestamp("2024-01-01 10:00"))
    daily = daily_statistics(derive_hourly(raw), "2024-01-01", "2024-01-03")
    assert daily.precip_mm_sum.isnull().all()
    assert daily.t2m_c_mean.isnull().all()
    assert (daily.precip_mm_n_hours.sel(time="2024-01-01") == 23).all()
    assert (daily.precip_mm_n_hours.sel(time="2024-01-03") == 0).all()


def test_daily_rejects_duplicate_timestamps():
    from amazon_chaos.preprocess.daily import daily_statistics, derive_hourly

    raw = hourly_fixture()
    duplicate = xr.concat([raw, raw.isel(valid_time=[-1])], dim="valid_time")
    with pytest.raises(ValueError, match="duplic"):
        daily_statistics(derive_hourly(duplicate), "2024-01-01", "2024-01-01")


def test_derivation_rejects_unexpected_units():
    from amazon_chaos.preprocess.daily import derive_hourly

    raw = hourly_fixture()
    raw.t2m.attrs["units"] = "degC"
    with pytest.raises(ValueError, match="units"):
        derive_hourly(raw)
