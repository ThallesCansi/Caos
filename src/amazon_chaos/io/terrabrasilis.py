"""PRODES e DETER (INPE/TerraBrasilis) pelo WFS, recortados pela caixa da região.

O download é paginado (ordenado por um campo fixo, para que as páginas sejam estáveis),
retomável e conferido: no fim, o total baixado precisa igualar o `numberMatched`
anunciado pelo servidor. Cada página vai para um GeoParquet, com manifesto (consulta,
data, SHA-256). Fontes e limitações: docs/dados.md.
"""

from __future__ import annotations

import io
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

from amazon_chaos.provenance import sha256_file

GEOSERVER = "https://terrabrasilis.dpi.inpe.br/geoserver/{workspace}/ows"
HEADERS = {"User-Agent": "Mozilla/5.0 (amazon-chaos; TCC ILUM)"}

# nome lógico → (workspace, camada, campo de ordenação, campos guardados)
LAYERS = {
    "prodes_anual": ("prodes-legal-amz", "yearly_deforestation", "fid",
                     ["year", "main_class", "class_name", "area_km", "image_date", "state"]),
    "prodes_acumulado_2007": ("prodes-legal-amz", "accumulated_deforestation_2007", "fid",
                              ["main_class", "class_name", "area_km"]),
    "prodes_nao_floresta": ("prodes-legal-amz", "no_forest", "fid", ["main_class"]),
    "prodes_hidrografia": ("prodes-legal-amz", "hydrography", "fid", ["main_class"]),
    "deter": ("deter-amz", "deter_amz", "gid",
              ["classname", "view_date", "areauckm", "areamunkm", "satellite", "sensor"]),
}


def _get(url, params, timeout=300, attempts=5):
    error = None
    for _ in range(attempts):
        try:
            response = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
            response.raise_for_status()
            if b"ExceptionReport" in response.content[:500]:
                raise RuntimeError(f"WFS: {response.text[:400]}")
            return response
        except (requests.RequestException, RuntimeError) as exc:
            error = exc
    raise RuntimeError(f"WFS falhou {attempts} vezes: {error}") from error


def bbox_filter(bounds) -> str:
    """CQL com a caixa em lon/lat explícito (CRS:84).

    Sem o CRS, o GeoServer lê a caixa na ordem de eixos oficial do EPSG:4674 (lat, lon) e
    devolve zero feições sem erro.
    """
    west, south, east, north = bounds
    return f"BBOX(geom,{west},{south},{east},{north},'CRS:84')"


def count_features(name: str, cql: str) -> int:
    workspace, layer, *_ = LAYERS[name]
    response = _get(GEOSERVER.format(workspace=workspace), {
        "service": "WFS", "version": "2.0.0", "request": "GetFeature",
        "typeNames": f"{workspace}:{layer}", "resultType": "hits", "CQL_FILTER": cql})
    found = re.search(rb'numberMatched="(\d+)"', response.content)
    if not found:
        raise RuntimeError("O WFS não informou numberMatched")
    return int(found.group(1))


def download_layer(name: str, bounds, directory: Path, *, page: int = 10_000,
                   report=print) -> Path:
    """Baixa a camada na caixa `bounds` (W, S, E, N); devolve o GeoParquet consolidado."""
    workspace, layer, order, keep = LAYERS[name]
    directory = Path(directory) / name
    directory.mkdir(parents=True, exist_ok=True)
    target = directory.parent / f"{name}.parquet"
    manifest_path = directory.parent / f"{name}.json"
    cql = bbox_filter(bounds)
    expected = count_features(name, cql)
    if target.exists() and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if manifest["features"] == expected and manifest["sha256"] == sha256_file(target):
            return target
    pages = range(0, expected, page)
    report(f"{name}: {expected} feições em {len(pages)} páginas")
    for k, start in enumerate(pages, 1):
        part = directory / f"pagina_{start:08d}.parquet"
        if part.exists():
            continue
        response = _get(GEOSERVER.format(workspace=workspace), {
            "service": "WFS", "version": "2.0.0", "request": "GetFeature",
            "typeNames": f"{workspace}:{layer}", "CQL_FILTER": cql,
            "outputFormat": "application/json", "srsName": "EPSG:4674",
            "sortBy": order, "count": page, "startIndex": start})
        frame = gpd.read_file(io.BytesIO(response.content))
        frame = frame[[c for c in keep if c in frame.columns] + ["geometry"]]
        frame.to_parquet(part)
        if k % 5 == 0 or k == len(pages):
            report(f"{name}: página {k}/{len(pages)}")
    parts = [gpd.read_parquet(p) for p in sorted(directory.glob("pagina_*.parquet"))]
    frame = (gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=parts[0].crs)
             if parts else gpd.GeoDataFrame(geometry=[], crs="EPSG:4674"))
    if len(frame) != expected:
        raise RuntimeError(f"{name}: baixadas {len(frame)} feições, servidor anunciou {expected}")
    frame.to_parquet(target)
    manifest_path.write_text(json.dumps({
        "source": GEOSERVER.format(workspace=workspace), "layer": f"{workspace}:{layer}",
        "cql": cql, "features": expected, "retrieved_utc": datetime.now(UTC).isoformat(),
        "sha256": sha256_file(target),
    }, ensure_ascii=False, indent=2))
    for p in directory.glob("pagina_*.parquet"):
        p.unlink()
    directory.rmdir()
    return target
