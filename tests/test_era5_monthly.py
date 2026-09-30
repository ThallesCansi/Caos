import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from amazon_chaos.config import load_config
from amazon_chaos.io.era5_monthly import (
    NAMES,
    cached_files,
    download_plan,
    job_directory,
    mask_to_basin,
    open_downloaded,
    plan_requests,
    validate_files,
)


def small_config():
    cfg = load_config("configs/tapajos_2024.yaml")
    cfg["spatial"]["area"] = [-2.25, -56, -2.5, -55.75]
    return cfg


class FakeCDS:
    """Somente a transferência externa é substituída; validação/NetCDF/cache são reais."""

    def retrieve(self, dataset, request):
        self.request = request
        return self

    def download(self, target):
        req = self.request
        times = pd.DatetimeIndex(
            [f"{req['year'][0]}-{req['month'][0]}-{d} {h}" for d in req["day"] for h in req["time"]]
        )
        coords = {"valid_time": times, "latitude": [-2.25, -2.5], "longitude": [-56, -55.75]}
        units = {"t2m": "K", "d2m": "K", "sp": "Pa", "u10": "m s**-1", "v10": "m s**-1", "tp": "m"}
        ds = xr.Dataset(
            {
                NAMES[v]: xr.DataArray(
                    np.ones((len(times), 2, 2)),
                    coords=coords,
                    dims=list(coords),
                    attrs={"units": units[NAMES[v]]},
                )
                for v in req["variable"]
            }
        )
        ds.to_netcdf(target)


class NoNetwork:
    def retrieve(self, *args):
        raise AssertionError("Cache completo não deve acessar rede")


def test_download_resume_and_corruption_detection(tmp_path):
    cfg = small_config()
    paths = download_plan(cfg, "2024-01-01", "2024-01-01", tmp_path, FakeCDS())
    assert len(paths) == 2
    resumed = download_plan(cfg, "2024-01-01", "2024-01-01", tmp_path, NoNetwork())
    assert paths == resumed
    ds = open_downloaded(cfg, "2024-01-01", "2024-01-01", tmp_path)
    assert dict(ds.sizes) == {"time": 48, "latitude": 2, "longitude": 2}
    assert float(ds.tp.sum()) == 192
    paths[0].write_bytes(b"broken")
    with pytest.raises(ValueError, match="Cache corrupto"):
        download_plan(cfg, "2024-01-01", "2024-01-01", tmp_path, NoNetwork())


def test_validation_rejects_truncated_period_and_grid(tmp_path):
    cfg = small_config()
    paths = download_plan(cfg, "2024-01-01", "2024-01-01", tmp_path, FakeCDS())
    job = plan_requests(cfg, "2024-01-01", "2024-01-01")[0]
    with xr.open_dataset(paths[0]) as source:
        ds = source.load()
    shortened = tmp_path / "short.nc"
    ds.isel(valid_time=slice(1, None)).to_netcdf(shortened)
    with pytest.raises(ValueError, match="Time coverage"):
        validate_files([shortened], job)
    moved = tmp_path / "moved.nc"
    ds.assign_coords(longitude=[-55.75, -55.5]).to_netcdf(moved)
    with pytest.raises(ValueError, match="Grid differs"):
        validate_files([moved], job)
    directory = job_directory(cfg, job, tmp_path)
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["quality"]["n_hours"] == 48
    assert cached_files(directory, job) == [paths[0]]


def test_mask_to_basin_preserves_partial_cells_and_excludes_outside(tmp_path, monkeypatch):
    cfg = small_config()
    source = tmp_path / "basin.geojson"
    source.touch()
    cfg["spatial"]["basin_source"] = str(source)
    cells = pd.DataFrame({
        "latitude": [-2.25, -2.5], "longitude": [-56.0, -55.75],
        "basin_fraction": [1.0, 0.25],
    })
    monkeypatch.setattr("amazon_chaos.io.era5_monthly.gpd.read_file", lambda _: cells)
    daily = xr.Dataset({"temp": (("time", "latitude", "longitude"), np.ones((1, 2, 2)))},
                       coords={"time": [pd.Timestamp("2024-01-01")],
                               "latitude": [-2.25, -2.5], "longitude": [-56.0, -55.75]})
    masked = mask_to_basin(daily, cfg)
    assert float(masked.temp.sel(latitude=-2.5, longitude=-55.75).item()) == 1
    assert np.isnan(masked.temp.sel(latitude=-2.25, longitude=-55.75).item())
    assert float(masked.basin_fraction.sel(latitude=-2.5, longitude=-55.75)) == 0.25


def test_combined_instant_and_accum_request(tmp_path):
    cfg = small_config()
    groups = cfg["era5"]["variables"]
    cfg["era5"]["variables"] = {"all": groups["instant"] + groups["accum"]}
    paths = download_plan(cfg, "2024-01-01", "2024-01-01", tmp_path, FakeCDS())
    assert len(paths) == 1
    raw = open_downloaded(cfg, "2024-01-01", "2024-01-01", tmp_path)
    assert set(NAMES.values()) <= set(raw.data_vars)
    assert raw.sizes["time"] == 48


class FakeCDSZip(FakeCDS):
    def download(self, target):
        super().download(target)
        target = Path(target)
        with xr.open_dataset(target) as source:
            ds = source.load()
        parts = []
        for name, fields in [("instant", list(ds.data_vars)[:-1]),
                             ("accum", list(ds.data_vars)[-1:])]:
            path = target.with_name(f"{name}.nc")
            ds[fields].to_netcdf(path)
            parts.append(path)
        archive = target.with_suffix(".zip")
        with zipfile.ZipFile(archive, "w") as zf:
            for path in parts:
                zf.write(path, path.name)
                path.unlink()
        archive.replace(target)


def test_combined_zip_step_types(tmp_path):
    cfg = small_config()
    groups = cfg["era5"]["variables"]
    cfg["era5"]["variables"] = {"all": groups["instant"] + groups["accum"]}
    paths = download_plan(cfg, "2024-01-01", "2024-01-01", tmp_path, FakeCDSZip())
    assert len(paths) == 2
    assert (paths[0].parent / "payload.zip").exists()
    raw = open_downloaded(cfg, "2024-01-01", "2024-01-01", tmp_path)
    assert set(NAMES.values()) <= set(raw.data_vars)


def test_combined_request_rejects_missing_field(tmp_path):
    cfg = small_config()
    groups = cfg["era5"]["variables"]
    cfg["era5"]["variables"] = {"all": groups["instant"] + groups["accum"]}
    job = plan_requests(cfg, "2024-01-01", "2024-01-01")[0]
    path = download_plan(cfg, "2024-01-01", "2024-01-01", tmp_path, FakeCDS())[0]
    with xr.open_dataset(path) as source:
        ds = source.load()
    ds["tp"].values[0, 0, 0] = np.nan
    broken = tmp_path / "missing.nc"
    ds.to_netcdf(broken)
    with pytest.raises(ValueError, match="valores ausentes"):
        validate_files([broken], job)
