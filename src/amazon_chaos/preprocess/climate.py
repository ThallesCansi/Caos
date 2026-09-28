from __future__ import annotations

import numpy as np
import xarray as xr


def infer_time_name(ds: xr.Dataset) -> str:
    if "valid_time" in ds.coords:
        return "valid_time"
    if "time" in ds.coords:
        return "time"
    raise KeyError("Dataset has neither valid_time nor time coordinate")


def infer_coord_names(ds: xr.Dataset) -> tuple[str, str, str]:
    time_name = infer_time_name(ds)
    lat_name = "latitude" if "latitude" in ds.coords else "lat"
    lon_name = "longitude" if "longitude" in ds.coords else "lon"
    missing = [name for name in [lat_name, lon_name] if name not in ds.coords]
    if missing:
        raise KeyError(f"Missing expected spatial coordinates: {missing}")
    return time_name, lat_name, lon_name


def saturation_vapor_pressure_kpa(temp_c: xr.DataArray | np.ndarray) -> xr.DataArray | np.ndarray:
    return 0.6108 * np.exp((17.27 * temp_c) / (temp_c + 237.3))


def derive_climate_variables(ds: xr.Dataset) -> xr.Dataset:
    out = xr.Dataset(coords=ds.coords)
    if "t2m" in ds:
        out["t2m_c"] = ds["t2m"] - 273.15
        out["t2m_c"].attrs["units"] = "degC"
    if "d2m" in ds:
        out["d2m_c"] = ds["d2m"] - 273.15
        out["d2m_c"].attrs["units"] = "degC"
    if "t2m_c" in out and "d2m_c" in out:
        es = saturation_vapor_pressure_kpa(out["t2m_c"])
        ea = saturation_vapor_pressure_kpa(out["d2m_c"])
        out["vpd_kpa"] = xr.where(es - ea < 0, 0, es - ea)
        out["vpd_kpa"].attrs["units"] = "kPa"
    if "sp" in ds:
        out["surface_pressure_hpa"] = ds["sp"] / 100.0
        out["surface_pressure_hpa"].attrs["units"] = "hPa"
    if "tp" in ds:
        out["precip_mm_hour_ending"] = ds["tp"] * 1000.0
        out["precip_mm_hour_ending"].attrs.update(
            units="mm",
            time_semantics="accumulation for hour ending at valid_time",
        )
    if "u10" in ds and "v10" in ds:
        out["wind_speed_10m"] = np.hypot(ds["u10"], ds["v10"])
        out["wind_speed_10m"].attrs["units"] = "m s-1"
    return out


def extract_nearest_point(ds: xr.Dataset, lat: float, lon: float) -> xr.Dataset:
    _, lat_name, lon_name = infer_coord_names(ds)
    return ds.sel({lat_name: lat, lon_name: lon}, method="nearest")


def aggregate_daily(point: xr.Dataset, science_start: str, science_end: str) -> xr.Dataset:
    time_name = infer_time_name(point)
    daily = xr.Dataset()
    means = ["t2m_c", "d2m_c", "vpd_kpa", "surface_pressure_hpa", "wind_speed_10m"]
    for var in means:
        if var in point:
            daily[var] = point[var].resample({time_name: "1D"}).mean()

    if "precip_mm_hour_ending" in point:
        precip = point["precip_mm_hour_ending"].copy()
        precip = precip.assign_coords({time_name: precip[time_name] - np.timedelta64(1, "h")})
        daily["precip_mm_day"] = precip.resample({time_name: "1D"}).sum()
        daily["precip_mm_day"].attrs["units"] = "mm/day"

    return daily.sel({time_name: slice(science_start, science_end)})
