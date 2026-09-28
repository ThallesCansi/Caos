"""Requisições mensais, cache por conteúdo e validação antes da reutilização."""

import hashlib
import json
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import cdsapi
import numpy as np
import pandas as pd
import xarray as xr

from amazon_chaos.io.era5 import build_request
from amazon_chaos.preprocess.climate import infer_time_name
from amazon_chaos.preprocess.daily import check_units, daily_statistics, derive_hourly
from amazon_chaos.preprocess.grid import grid_coordinates
from amazon_chaos.provenance import sha256_file

NAMES = {
    "2m_temperature": "t2m",
    "2m_dewpoint_temperature": "d2m",
    "surface_pressure": "sp",
    "10m_u_component_of_wind": "u10",
    "10m_v_component_of_wind": "v10",
    "total_precipitation": "tp",
}


def plan_requests(config, start, end):
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if start != start.normalize() or end != end.normalize() or start > end:
        raise ValueError("Usar datas sem horário e início <= fim")
    if config["era5"]["dataset"] != "reanalysis-era5-single-levels":
        raise ValueError("Este processamento é específico ao ERA5 single levels horário")
    grid_coordinates(config["spatial"]["area"])
    offset = config.get("time", {}).get("utc_offset_hours", -3)
    if offset != -3:
        raise ValueError("O piloto usa UTC−03 fixo")
    first = start - pd.Timedelta(hours=offset)
    last = end + pd.Timedelta(days=1) - pd.Timedelta(hours=offset)
    jobs = []
    for month in pd.period_range(first, last, freq="M"):
        lo = max(first.normalize(), month.start_time)
        hi = min(last.normalize(), month.end_time.normalize())
        for group, variables in config["era5"]["variables"].items():
            if not variables or set(variables) - set(NAMES):
                raise ValueError("Lista de variáveis vazia ou não suportada")
            request = build_request(config, variables, str(lo.date()), str(hi.date()))
            payload = {"dataset": config["era5"]["dataset"], "request": request}
            key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:20]
            jobs.append({**payload, "key": key, "month": str(month), "group": group})
    return jobs


def validate_files(files, job):
    opened = []
    try:
        for path in files:
            opened.append(xr.open_dataset(path))
        if not opened:
            raise ValueError("No NetCDF files")
        ds = xr.merge(opened, compat="no_conflicts", join="exact")
        req = job["request"]
        names = [NAMES[v] for v in req["variable"]]
        if set(names) - set(ds.data_vars):
            raise ValueError("Missing requested variables")
        time_name = infer_time_name(ds)
        expected = pd.DatetimeIndex(
            [
                f"{req['year'][0]}-{req['month'][0]}-{day} {hour}"
                for day in req["day"]
                for hour in req["time"]
            ]
        )
        actual = pd.DatetimeIndex(ds[time_name].values)
        if not actual.equals(expected):
            raise ValueError("Time coverage differs from request")
        lats, lons = grid_coordinates(req["area"])
        for coord, values in [("latitude", lats), ("longitude", lons)]:
            if ds[coord].shape != values.shape or not np.allclose(ds[coord], values):
                raise ValueError(f"Grid differs from request: {coord}")
        check_units(ds)
        for name in names:
            if set(ds[name].dims) != {time_name, "latitude", "longitude"}:
                raise ValueError(f"Unexpected dimensions: {name}")
            values = ds[name].values
            if not np.isfinite(values).any():
                raise ValueError(f"Entire variable missing: {name}")
        return {
            "n_hours": len(actual),
            "n_cells": len(lats) * len(lons),
            "variables": names,
            "missing_values": {n: int((~np.isfinite(ds[n].values)).sum()) for n in names},
        }
    finally:
        for ds in opened:
            ds.close()


def job_directory(config, job, root="data/raw"):
    return (
        Path(root)
        / config["experiment_id"]
        / "era5"
        / f"{job['month']}_{job['group']}_{job['key']}"
    )


def cached_files(directory, job):
    manifest_path = directory / "manifest.json"
    if not manifest_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text())
    if manifest["job"] != job:
        raise ValueError(f"Request mismatch: {directory}")
    files = [directory / row["name"] for row in manifest["files"]]
    for path, row in zip(files, manifest["files"], strict=True):
        if not path.is_file() or sha256_file(path) != row["sha256"]:
            raise ValueError(f"Cache corrupto; preservar e inspecionar: {path}")
    validate_files(files, job)
    return files


def download_plan(config, start, end, root="data/raw", client=None):
    result = []
    for job in plan_requests(config, start, end):
        directory = job_directory(config, job, root)
        directory.mkdir(parents=True, exist_ok=True)
        files = cached_files(directory, job)
        if files is not None:
            print(f"CACHE validado: {job['month']} / {job['group']}", flush=True)
            result.extend(files)
            continue
        # Arquivos finais sem manifesto podem resultar de interrupção após transferência.
        orphaned = sorted(directory.glob("*.nc"))
        if orphaned:
            files = orphaned
        else:
            part = directory / "payload.part"
            if part.exists():
                stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
                part.rename(directory / f"interrupted_{stamp}.part")
            client = client if client is not None else cdsapi.Client()
            print(
                f"CDS: {job['month']} / {job['group']} / {len(job['request']['day'])} dias",
                flush=True,
            )
            client.retrieve(job["dataset"], job["request"]).download(str(part))
            if zipfile.is_zipfile(part):
                files = []
                with zipfile.ZipFile(part) as archive:
                    for i, member in enumerate(archive.infolist()):
                        if member.filename.endswith(".nc"):
                            target = directory / f"field_{i}.nc"
                            with archive.open(member) as src, target.open("xb") as dst:
                                shutil.copyfileobj(src, dst)
                            files.append(target)
                part.rename(directory / "payload.zip")
            else:
                target = directory / "fields.nc"
                part.rename(target)
                files = [target]
        quality = validate_files(files, job)
        manifest = {
            "job": job,
            "retrieved_utc": datetime.now(UTC).isoformat(),
            "quality": quality,
            "files": [
                {"name": f.name, "size_bytes": f.stat().st_size, "sha256": sha256_file(f)}
                for f in files
            ],
        }
        temporary = directory / "manifest.json.part"
        temporary.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        temporary.replace(directory / "manifest.json")
        result.extend(files)
    return result


def open_downloaded(config, start, end, root="data/raw"):
    groups = {}
    for job in plan_requests(config, start, end):
        directory = job_directory(config, job, root)
        files = cached_files(directory, job)
        if files is None:
            raise FileNotFoundError(f"Aquisição pendente: {directory}")
        arrays = []
        for path in files:
            with xr.open_dataset(path) as source:
                ds = source.load()
            for name in ["number", "expver", "surface"]:
                if name in ds.coords and name not in ds.dims:
                    ds = ds.drop_vars(name)
            name = infer_time_name(ds)
            arrays.append(ds.rename({name: "time"}) if name != "time" else ds)
        groups.setdefault(job["group"], []).append(xr.merge(arrays, join="exact"))
    combined = [
        xr.concat(items, dim="time", data_vars="all", coords="minimal", compat="equals").sortby(
            "time"
        )
        for items in groups.values()
    ]
    return xr.merge(combined, join="exact", compat="no_conflicts")


def process_period(config, start, end):
    raw = open_downloaded(config, start, end)
    hourly = derive_hourly(raw)
    daily = daily_statistics(hourly, start, end, config["time"]["utc_offset_hours"])
    out = Path("data/processed") / config["experiment_id"]
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"daily_{start}_{end}.nc"
    daily.attrs["request_keys"] = ",".join(j["key"] for j in plan_requests(config, start, end))
    daily.to_netcdf(target)
    return target
