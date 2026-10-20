"""Focos de fogo ativo do BDQueimadas (INPE), satélite de referência, 2003 em diante.

Os CSVs anuais do Brasil (dados abertos do Programa Queimadas) são baixados uma vez para
`data/raw/queimadas/` com manifesto e compartilhados entre as regiões. Um foco é um pixel
detectado quente numa passagem do satélite: não é um incêndio nem mede área queimada, e o
mesmo evento pode gerar vários focos (docs/dados.md).
"""

from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

from amazon_chaos.provenance import sha256_file

URL = ("https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/anual/Brasil_sat_ref/"
       "focos_br_ref_{year}.zip")
RAW = Path("data/raw/queimadas")
FIRST_YEAR = 2003
HEADERS = {"User-Agent": "Mozilla/5.0 (amazon-chaos; TCC ILUM)"}


def fetch_year(year: int) -> Path:
    """Baixa (ou reutiliza, conferindo o hash) o arquivo anual de focos."""
    if year < FIRST_YEAR:
        raise ValueError(f"O satélite de referência só tem arquivos anuais desde {FIRST_YEAR}")
    target = RAW / f"focos_br_ref_{year}.zip"
    record = target.with_suffix(".json")
    if target.exists() and record.exists():
        if json.loads(record.read_text())["sha256"] == sha256_file(target):
            return target
    RAW.mkdir(parents=True, exist_ok=True)
    response = requests.get(URL.format(year=year), headers=HEADERS, timeout=600)
    response.raise_for_status()
    target.write_bytes(response.content)
    with zipfile.ZipFile(target) as zf:
        zf.testzip()
    record.write_text(json.dumps({"url": response.url, "year": year,
                                  "retrieved_utc": datetime.now(UTC).isoformat(),
                                  "bytes": target.stat().st_size,
                                  "sha256": sha256_file(target)}, indent=2))
    return target


def read_year(path: Path, bounds) -> gpd.GeoDataFrame:
    """Focos do arquivo anual dentro da caixa (W, S, E, N), com data e hora UTC."""
    west, south, east, north = bounds
    with zipfile.ZipFile(path) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".csv"))
        frame = pd.read_csv(zf.open(name), usecols=["lat", "lon", "data_pas"])
    frame = frame[frame.lon.between(west, east) & frame.lat.between(south, north)]
    frame["data_pas"] = pd.to_datetime(frame.data_pas)
    return gpd.GeoDataFrame(frame, geometry=gpd.points_from_xy(frame.lon, frame.lat),
                            crs="EPSG:4674")
