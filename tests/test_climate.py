import numpy as np
import pandas as pd
import xarray as xr

from amazon_chaos.preprocess.climate import aggregate_daily, saturation_vapor_pressure_kpa


def test_saturation_vapor_pressure_increases_with_temperature():
    temps = np.array([10.0, 20.0, 30.0])
    values = saturation_vapor_pressure_kpa(temps)
    assert np.all(np.diff(values) > 0)


def test_precipitation_midnight_belongs_to_previous_day():
    times = pd.date_range("2024-08-01 01:00", "2024-08-03 00:00", freq="h")
    precip = xr.DataArray(np.ones(len(times)), coords={"valid_time": times}, dims=["valid_time"])
    ds = xr.Dataset({"precip_mm_hour_ending": precip})
    daily = aggregate_daily(ds, "2024-08-01", "2024-08-02")
    assert float(daily["precip_mm_day"].sel(valid_time="2024-08-01")) == 24.0
    assert float(daily["precip_mm_day"].sel(valid_time="2024-08-02")) == 24.0
