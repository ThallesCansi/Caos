from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from typing import Any

import cdsapi
import xarray as xr


def retrieve_cds_netcdf(
    client: cdsapi.Client,
    dataset: str,
    request: dict[str, Any],
    output_dir: str | Path,
    stem: str,
) -> list[Path]:
    """Retrieve CDS data defensively, handling either NetCDF or ZIP payloads."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    existing = sorted(output_dir.glob(f"{stem}*.nc"))
    extracted_existing = sorted((output_dir / f"{stem}_extracted").glob("**/*.nc"))
    if existing or extracted_existing:
        return existing + extracted_existing

    payload = output_dir / f"{stem}.download"
    if not payload.exists():
        client.retrieve(dataset, request).download(str(payload))

    if zipfile.is_zipfile(payload):
        extract_dir = output_dir / f"{stem}_extracted"
        extract_dir.mkdir(exist_ok=True)
        with zipfile.ZipFile(payload) as zf:
            zf.extractall(extract_dir)
        files = sorted(extract_dir.rglob("*.nc"))
        if not files:
            raise RuntimeError(f"ZIP returned by CDS contains no .nc files: {payload}")
        return files

    target = output_dir / f"{stem}.nc"
    shutil.move(str(payload), str(target))
    return [target]


def _drop_aux_forecast_coords(ds: xr.Dataset) -> xr.Dataset:
    drop = [
        name
        for name in ["step", "forecast_reference_time"]
        if name in ds.coords and name not in ds.dims
    ]
    return ds.drop_vars(drop) if drop else ds


def open_netcdf_group(paths: list[str | Path]) -> xr.Dataset:
    datasets = [_drop_aux_forecast_coords(xr.open_dataset(path)) for path in paths]
    if len(datasets) == 1:
        return datasets[0]
    return xr.merge(datasets, compat="no_conflicts", join="exact")


def merge_step_types(instant_files: list[Path], accum_files: list[Path]) -> xr.Dataset:
    instant = open_netcdf_group(instant_files)
    accum = open_netcdf_group(accum_files)
    instant, accum = xr.align(instant, accum, join="exact")
    return xr.merge([instant, accum], compat="no_conflicts", join="exact")


def build_request(
    config: dict[str, Any], variables: list[str], start: str, end: str
) -> dict[str, Any]:
    """Build a CDS request for a single calendar month.

    Pilot configs currently stay within one month. The scale-up pipeline should chunk
    multi-month/multi-year requests explicitly rather than issuing a huge single request.
    """
    import pandas as pd

    dates = pd.date_range(start=start, end=end, freq="D")
    years = sorted({d.strftime("%Y") for d in dates})
    months = sorted({d.strftime("%m") for d in dates})
    if len(years) != 1 or len(months) != 1:
        raise ValueError("build_request currently expects a single calendar month")

    era = config["era5"]
    return {
        "product_type": [era.get("product_type", "reanalysis")],
        "variable": variables,
        "year": years,
        "month": months,
        "day": [d.strftime("%d") for d in dates],
        "time": [f"{h:02d}:00" for h in range(24)],
        "data_format": era.get("data_format", "netcdf"),
        "download_format": era.get("download_format", "unarchived"),
        "area": config["spatial"]["area"],
    }


def download_pilot(config: dict[str, Any], output_dir: str | Path) -> tuple[list[Path], list[Path]]:
    client = cdsapi.Client()
    era = config["era5"]
    start = str(config["time"]["science_start"])
    end = str(config["time"]["download_end"])
    dataset = era["dataset"]

    instant_request = build_request(config, era["variables"]["instant"], start, end)
    accum_request = build_request(config, era["variables"]["accum"], start, end)

    output_dir = Path(output_dir)
    instant = retrieve_cds_netcdf(client, dataset, instant_request, output_dir, "era5_instant")
    accum = retrieve_cds_netcdf(client, dataset, accum_request, output_dir, "era5_accum")
    return instant, accum
