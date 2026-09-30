"""Derivados ERA5 e dias locais completos, com contagens explícitas."""

import numpy as np
import pandas as pd
import xarray as xr

from amazon_chaos.preprocess.climate import infer_time_name, saturation_vapor_pressure_kpa

UNITS = {
    "t2m": {"K"},
    "d2m": {"K"},
    "sp": {"Pa"},
    "u10": {"m s**-1", "m s-1", "m/s"},
    "v10": {"m s**-1", "m s-1", "m/s"},
    "tp": {"m"},
}


def check_units(ds):
    for var in ds.data_vars:
        if var in UNITS and ds[var].attrs.get("units") not in UNITS[var]:
            raise ValueError(f"Unexpected units for {var}: {ds[var].attrs.get('units')}")


def derive_hourly(ds, dewpoint_tolerance_k=0.05):
    check_units(ds)
    missing = set(UNITS) - set(ds.data_vars)
    if missing:
        raise ValueError(f"Missing ERA5 variables: {sorted(missing)}")
    time_name = infer_time_name(ds)
    raw = ds.rename({time_name: "time"}) if time_name != "time" else ds
    t = raw.t2m - 273.15
    td = raw.d2m - 273.15
    es = saturation_vapor_pressure_kpa(t)
    ea = saturation_vapor_pressure_kpa(td)
    bad = (td > t + dewpoint_tolerance_k) | (raw.sp <= ea * 1000)
    out = xr.Dataset(
        {
            "t2m_c": t,
            "d2m_c": td,
            "vpd_kpa": (es - ea).clip(min=0).where(~bad),
            "rh_pct": (100 * ea / es).clip(0, 100).where(~bad),
            "q_gkg": (1000 * 0.622 * ea / (raw.sp / 1000 - 0.378 * ea)).where(~bad),
            "wind_speed_10m": np.hypot(raw.u10, raw.v10),
            "u10": raw.u10,
            "v10": raw.v10,
            "surface_pressure_hpa": raw.sp / 100,
            "precip_mm": (raw.tp * 1000).where(raw.tp >= 0),
            "humidity_flag": bad.astype("int8"),
        }
    )
    units = {
        "t2m_c": "degC",
        "d2m_c": "degC",
        "vpd_kpa": "kPa",
        "rh_pct": "%",
        "q_gkg": "g kg-1",
        "wind_speed_10m": "m s-1",
        "u10": "m s-1",
        "v10": "m s-1",
        "surface_pressure_hpa": "hPa",
        "precip_mm": "mm",
        "humidity_flag": "1",
    }
    for var, unit in units.items():
        out[var].attrs = {"units": unit}
    out.precip_mm.attrs["time_semantics"] = "hour ending at time (UTC)"
    out.attrs["time_zone"] = "UTC"
    out.attrs["dewpoint_tolerance_k"] = dewpoint_tolerance_k
    return out


def daily_statistics(hourly, start, end, utc_offset_hours=-3):
    idx = pd.DatetimeIndex(hourly.time.values)
    if idx.has_duplicates or not idx.is_monotonic_increasing:
        raise ValueError("Timestamps duplicados ou fora de ordem")
    if not idx.equals(idx.floor("h")):
        raise ValueError("Expected timestamps on exact hours")
    dates = pd.date_range(start, end, freq="D")
    if not len(dates):
        raise ValueError("Intervalo diário vazio")
    out = xr.Dataset(coords={"time": dates})
    for var in hourly.data_vars:
        if var == "humidity_flag":
            continue
        da = hourly[var].where(np.isfinite(hourly[var]))
        shift = utc_offset_hours - (1 if var == "precip_mm" else 0)
        local = da.assign_coords(time=da.time + np.timedelta64(shift, "h"))
        grouped = local.resample(time="1D")
        count = grouped.count().reindex(time=dates, fill_value=0).fillna(0).astype("int16")
        out[f"{var}_n_hours"] = count
        stats = ["sum"] if var == "precip_mm" else ["mean", "min", "max"]
        for stat in stats:
            value = getattr(grouped, stat)(keep_attrs=True).reindex(time=dates)
            out[f"{var}_{stat}"] = value.where(count == 24)
            out[f"{var}_{stat}"].attrs.update(
                units=da.attrs.get("units", ""),
                cell_methods=f"time: {stat} (24 hourly samples per local day)",
            )
    out["t2m_c_range"] = out.t2m_c_max - out.t2m_c_min
    out.t2m_c_range.attrs["units"] = "degC"
    out.attrs.update(
        utc_offset_hours=utc_offset_hours,
        day_definition="fixed UTC offset; timestamps are local calendar labels",
        completeness="only 24 finite hourly samples produce daily statistics",
    )
    return out
