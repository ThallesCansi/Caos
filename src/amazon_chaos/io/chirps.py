"""CHIRPS v3.0 diário "sat" (CHC/UCSB), recortado na janela das bacias.

O CHIRPS é um produto de pêntadas (infravermelho + estações); o valor diário é a pêntada
repartida em dias. Na versão "sat" a repartição segue o IMERG Late V07 (satélite), de 1998
em diante; na "rnl" segue o próprio ERA5 e na v2.0, o CFSv2. Só a "sat" tem a dinâmica dia a
dia observada, independente da reanálise que queremos verificar (D-021).

O servidor do CHC bloqueia o IP (CrowdSec) diante de muitas leituras parciais em paralelo,
então os COGs diários não servem. Baixamos o NetCDF global de cada ano, um por vez e numa só
conexão, recortamos a janela que cobre todas as regiões e apagamos o arquivo global; o
SHA-256 dele fica no atributo do recorte e no manifesto. Os recortes ficam em
`data/raw/chirps/`, compartilhados pelas regiões, como o BDQueimadas. Reenviar o comando
retoma do primeiro ano que falta. O dia é o dia UTC do produto, sem deslocamento para a hora
local.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import xarray as xr

from amazon_chaos.provenance import build_manifest, sha256_file

PRODUCT = "CHIRPS v3.0 daily final sat (IMERG Late V07 disaggregation)"
URL = ("https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily/final/sat/netcdf/byYear/"
       "chirps-v3.0.sat.{year}.days_p05.nc")
ROOT = Path("data/raw/chirps")
RESOLUTION = 0.05
CITATION = "Funk et al. (2026), Scientific Data 13, 718, doi:10.1038/s41597-026-07096-4"


def url(year: int) -> str:
    return URL.format(year=year)


def snapped_bounds(bounds, pad: float = RESOLUTION) -> tuple[float, float, float, float]:
    """Caixa (oeste, sul, leste, norte) que contém `bounds`, alinhada à grade de 0,05°."""
    west, south, east, north = bounds
    snap = 1 / RESOLUTION
    return (float(np.floor((west - pad) * snap) / snap),
            float(np.floor((south - pad) * snap) / snap),
            float(np.ceil((east + pad) * snap) / snap),
            float(np.ceil((north + pad) * snap) / snap))


def year_file(year: int, root: Path = ROOT) -> Path:
    return root / f"chirps-v3.0.sat.{year}.nc"


def download(source: str, target: Path, *, chunk: int = 8 << 20) -> Path:
    """Baixa um arquivo numa só conexão, sem pedidos parciais; aborta numa página de erro."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(source, stream=True, timeout=600) as response:
        if response.status_code == 403:
            raise RuntimeError("O servidor do CHC recusou o pedido (403): o IP pode estar "
                               "bloqueado pelo CrowdSec; espere algumas horas")
        response.raise_for_status()
        kind = response.headers.get("content-type", "")
        if kind.startswith("text/"):
            raise RuntimeError(f"Resposta inesperada ({kind}) para {source}")
        with target.open("wb") as f:
            for part in response.iter_content(chunk):
                f.write(part)
    return target


def clip(global_file: Path, bounds) -> xr.Dataset:
    """Janela (oeste, sul, leste, norte) do NetCDF global, como `precip_mm` em mm/dia."""
    west, south, east, north = bounds
    with xr.open_dataset(global_file) as ds:
        name = next(iter(ds.data_vars))
        field = ds[name]
        field = field.rename({d: n for d, n in (("lat", "latitude"), ("lon", "longitude"),
                                                ("x", "longitude"), ("y", "latitude"))
                              if d in field.dims})
        lat = field.latitude.values
        lat_slice = slice(south, north) if lat[0] < lat[-1] else slice(north, south)
        field = field.sel(latitude=lat_slice, longitude=slice(west, east)).load()
    field = field.sortby("latitude", ascending=False).astype("float32")
    field = field.where(field >= 0)  # valores negativos marcam o oceano e a falta de dado
    field = field.assign_coords(latitude=np.round(field.latitude.values, 4),
                                longitude=np.round(field.longitude.values, 4))
    return field.rename("precip_mm").to_dataset()


def fetch_year(year: int, bounds, *, root: Path = ROOT, source: str | None = None) -> Path:
    """Baixa o ano, grava o recorte e apaga o arquivo global."""
    source = source or url(year)
    root.mkdir(parents=True, exist_ok=True)
    temporary = root / f".global.{year}.nc"
    if source.startswith("http"):
        download(source, temporary)
        local = temporary
    else:  # caminho local (testes ou arquivo já baixado)
        local = Path(source)
    try:
        digest = sha256_file(local)
        ds = clip(local, bounds)
        days = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
        if ds.sizes["time"] != len(days) or not (pd.DatetimeIndex(ds.time.values) == days).all():
            raise RuntimeError(f"CHIRPS {year}: {ds.sizes['time']} dias, esperados {len(days)}")
        ds.attrs = {"product": PRODUCT, "source_url": source, "source_sha256": digest,
                    "bounds_wsen": list(bounds), "day_definition": "dia UTC do produto",
                    "retrieved_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                    "citation": CITATION}
        target = year_file(year, root)
        partial = target.with_suffix(".nc.part")
        ds.to_netcdf(partial, encoding={"precip_mm": {"zlib": True, "complevel": 4}})
        partial.rename(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def fetch(bounds, first: int, last: int, *, root: Path = ROOT, pause: float = 5.0,
          report=print) -> list[Path]:
    """Anos `first`–`last` (retomável, um por vez) e o manifesto SHA-256 da pasta."""
    bounds = snapped_bounds(bounds)
    done = []
    for year in range(first, last + 1):
        target = year_file(year, root)
        if target.exists():
            with xr.open_dataset(target) as ds:
                if [float(b) for b in ds.attrs["bounds_wsen"]] != list(bounds):
                    raise RuntimeError(f"{target} cobre outra caixa; apague-o para refazer")
            done.append(target)
            continue
        started = time.monotonic()
        done.append(fetch_year(year, bounds, root=root))
        report(f"🌧️ CHIRPS {year}: pronto em {(time.monotonic() - started) / 60:.1f} min")
        time.sleep(pause)
    manifest = build_manifest(root)
    manifest = manifest[manifest.relative_path.str.endswith(".nc")
                        & ~manifest.relative_path.str.startswith(".")]
    manifest.to_csv(root / "manifest.csv", index=False)
    return done
