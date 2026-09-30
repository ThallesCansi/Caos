"""ERA5 horário pelo Earth Data Hub (DestinE), com o contrato dos arquivos mensais do CDS.

O espelho Zarr é organizado para séries longas: uma leitura anual do recorte busca poucos
blocos em paralelo, sem a fila do CDS. Cada mês é gravado em NetCDF com as seis variáveis,
os mesmos dias/horas UTC e a mesma grade das requisições CDS, validado por `validate_files`
e registrado em manifesto com SHA-256. `compare_with_cds` confere os valores contra os
meses já baixados do CDS antes do download integral.

O espelho não é bit a bit igual ao CDS: guarda o float32 com a mantissa arredondada a ~10
bits (erro relativo ≤ 2⁻¹¹ ≈ 4,9e-4, sem viés), medido em jan/1990 e jan/2024 (D-007).
"""

import json
import os
import time
from base64 import b64encode
from datetime import UTC, datetime
from pathlib import Path

import aiohttp
import numpy as np
import xarray as xr
import zarr

from amazon_chaos.io.era5_monthly import (
    NAMES,
    cached_files,
    job_directory,
    open_job_files,
    plan_edh_requests,
    request_times,
    validate_files,
)
from amazon_chaos.preprocess.grid import grid_coordinates
from amazon_chaos.provenance import sha256_file

EDH_URL = "https://data.earthdatahub.destine.eu/era5/era5-single-levels-atmosphere-v0.zarr"
NETWORK_ERRORS = (OSError, TimeoutError, aiohttp.ClientError)
# Dobro do erro de arredondamento a 10 bits: aceita a compressão do espelho e ainda barra
# hora, grade ou convenção trocadas (1 K em 300 K já é 3,3e-3).
EDH_RTOL = 2**-10
EDH_PRECISION = "mantissa float32 arredondada a ~10 bits no EDH; erro relativo <= 2**-11"


def open_edh(url=EDH_URL, token=None, concurrency=16):
    """Abre o Zarr sem carregar dados; a chave vai no cabeçalho, nunca na URL."""
    zarr.config.set({"async.concurrency": concurrency})
    storage_options = None
    if url.startswith("http"):
        token = token or os.environ.get("EDH_TOKEN")
        if not token:
            raise RuntimeError("Defina EDH_TOKEN com a chave do Earth Data Hub (~/.edh_env)")
        credentials = b64encode(f"edh:{token}".encode()).decode()
        storage_options = {
            "client_kwargs": {
                "headers": {"Authorization": f"Basic {credentials}"},
                "timeout": aiohttp.ClientTimeout(total=900),
            }
        }
    try:
        return xr.open_zarr(url, chunks=None, storage_options=storage_options)
    except aiohttp.ClientResponseError as error:
        if error.status in {401, 403}:
            raise PermissionError(
                f"Earth Data Hub recusou a chave (HTTP {error.status}); confira EDH_TOKEN"
            ) from None
        raise


def fetch_block(ds, jobs):
    """Lê um intervalo contínuo (um ano) e devolve um Dataset por mês, na grade do CDS."""
    req = jobs[0]["request"]
    names = [NAMES[v] for v in req["variable"]]
    lats, lons = grid_coordinates(req["area"])
    east = np.round(lons % 360, 6)
    if np.any(np.diff(east) <= 0):
        raise ValueError("Recorte atravessa o meridiano 0°; não suportado")
    times = [request_times(job["request"]) for job in jobs]
    block = (
        ds[names]
        .sel(latitude=lats, longitude=east, method="nearest", tolerance=1e-6)
        .sel(valid_time=slice(times[0][0], times[-1][-1]))
        .load()
    )
    if block.indexes["valid_time"].has_duplicates:
        raise ValueError("Horários duplicados no Earth Data Hub")
    months = {}
    for job, expected in zip(jobs, times, strict=True):
        missing = expected.difference(block.indexes["valid_time"])
        if len(missing):
            raise ValueError(f"EDH sem {len(missing)} horas em {job['month']}: {missing[0]} …")
        month = block.sel(valid_time=expected).reset_coords(drop=True)
        months[job["month"]] = month.assign_coords(latitude=lats, longitude=lons)
    return months


def write_month(month, directory, job, url=EDH_URL):
    directory.mkdir(parents=True, exist_ok=True)
    for variable in month.variables.values():
        variable.encoding = {}
    month.attrs["edh_source_url"] = url
    month.attrs["edh_precision"] = EDH_PRECISION
    temporary = directory / "fields.tmp.nc"
    month.to_netcdf(
        temporary, encoding={n: {"zlib": True, "complevel": 4} for n in month.data_vars}
    )
    quality = validate_files([temporary], job)
    target = directory / "fields.nc"
    temporary.replace(target)
    manifest = {
        "job": job,
        "retrieved_utc": datetime.now(UTC).isoformat(),
        "source_url": url,
        "quality": quality,
        "files": [
            {
                "name": target.name,
                "size_bytes": target.stat().st_size,
                "sha256": sha256_file(target),
            }
        ],
    }
    partial = directory / "manifest.json.part"
    partial.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    partial.replace(directory / "manifest.json")
    return target


def _duration(seconds):
    minutes = round(seconds / 60)
    return f"{minutes // 60} h {minutes % 60:02d} min" if minutes >= 60 else f"{minutes} min"


def download_edh(
    config,
    start,
    end,
    root="data/raw",
    open_dataset=open_edh,
    years=None,
    report=print,
    retries=5,
    wait_seconds=60,
    url=EDH_URL,
):
    """Baixa ano a ano; retoma pelos manifestos e só busca meses ausentes."""
    by_year = {}
    for job in plan_edh_requests(config, start, end):
        by_year.setdefault(job["month"][:4], []).append(job)
    if years is not None:
        by_year = {y: jobs for y, jobs in by_year.items() if y in set(years)}
    pending = {
        year: [j for j in jobs if cached_files(job_directory(config, j, root), j) is None]
        for year, jobs in by_year.items()
    }
    todo = [year for year in by_year if pending[year]]
    if not todo:
        return by_year
    region = config.get("region_name", config["experiment_id"])
    ds = open_dataset()
    started = time.monotonic()
    for done, year in enumerate(todo, start=1):
        year_started = time.monotonic()
        for attempt in range(1, retries + 1):
            try:
                months = fetch_block(ds, pending[year])
                break
            except NETWORK_ERRORS as error:
                if attempt == retries:
                    raise
                pause = wait_seconds * 2 ** (attempt - 1)
                report(
                    f"⚠️ {region}: instabilidade de rede em {year} "
                    f"({type(error).__name__}, tentativa {attempt}/{retries}).\n"
                    f"Tento de novo em {pause} s, sem perder o que já foi salvo."
                )
                time.sleep(pause)
                ds = open_dataset()
        files = [
            write_month(months[j["month"]], job_directory(config, j, root), j, url)
            for j in pending[year]
        ]
        elapsed = time.monotonic() - started
        remaining = elapsed / done * (len(todo) - done)
        size = sum(f.stat().st_size for f in files) / 2**20
        report(
            f"📦 {region}: {year} pronto! ({done}/{len(todo)} · {100 * done // len(todo)}%)\n"
            f"🗓️ {len(files)} meses validados, sem lacunas · 💾 {size:.0f} MiB\n"
            f"⏱️ {_duration(time.monotonic() - year_started)} neste ano"
            + (f" · ⏳ faltam ~{_duration(remaining)}" if done < len(todo) else "")
        )
    return by_year


def compare_with_cds(config, root="data/raw", rtol=EDH_RTOL, atol=1e-7):
    """Compara cada mês CDS validado com as mesmas horas e células do EDH."""
    base = Path(root) / config["experiment_id"]
    edh = {}
    for path in sorted((base / "edh").glob("*/manifest.json")):
        job = json.loads(path.read_text())["job"]
        edh[job["month"]] = cached_files(path.parent, job)
    stats = {}
    for path in sorted((base / "era5").glob("*/manifest.json")):
        job = json.loads(path.read_text())["job"]
        if job["month"] not in edh:
            continue
        cds = open_job_files(cached_files(path.parent, job))
        mirror = open_job_files(edh[job["month"]]).sel(
            time=cds.time, latitude=cds.latitude, longitude=cds.longitude
        )
        for name in [NAMES[v] for v in job["request"]["variable"]]:
            a, b = cds[name].values, mirror[name].values
            row = stats.setdefault(
                name,
                {"months": set(), "values": 0, "identical": 0, "max_abs_diff": 0.0,
                 "max_rel_diff": 0.0, "bias": 0.0},
            )
            row["months"].add(job["month"])
            row["values"] += a.size
            row["identical"] += int(np.sum((a == b) | (np.isnan(a) & np.isnan(b))))
            signed = b.astype("float64") - a.astype("float64")
            diff = np.abs(signed)
            nonzero = a != 0
            row["max_abs_diff"] = max(row["max_abs_diff"], float(np.nanmax(diff)))
            row["max_rel_diff"] = max(
                row["max_rel_diff"], float(np.nanmax(diff[nonzero] / np.abs(a[nonzero])))
            )
            row["bias"] += float(np.nansum(signed))
            row["ok"] = row.get("ok", True) and bool(
                np.allclose(a, b, rtol=rtol, atol=atol, equal_nan=True)
            )
    for row in stats.values():
        row["months"] = sorted(row["months"])
        row["bias"] /= row["values"]
    return stats
