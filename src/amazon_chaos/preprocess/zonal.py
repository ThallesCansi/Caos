"""Agregação de rasters, polígonos e pontos nas células ERA5 da região.

Os rasters de 30 m (MapBiomas) são lidos em janelas, direto dos COGs públicos ou de um
arquivo local, sem carregar o Brasil inteiro. Cada pixel entra na célula cujo polígono
recortado (pelo limite da bacia) contém seu centro, com peso igual à sua área geodésica
(km², exata no elipsoide WGS84). O resultado são áreas por classe e por célula: as frações saem
sempre de um denominador declarado (área válida dentro da célula).
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.windows import Window, from_bounds

WGS84_A_KM = 6378.137
WGS84_F = 1 / 298.257223563
GDAL_ENV = {"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
            "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif", "GDAL_HTTP_MAX_RETRY": "5",
            "GDAL_HTTP_RETRY_DELAY": "2", "VSI_CACHE": "TRUE"}


def _zone(lat):
    """Área do elipsoide WGS84 entre o equador e a latitude `lat` (rad), por radiano de λ."""
    e2 = WGS84_F * (2 - WGS84_F)
    e = np.sqrt(e2)
    b2 = (WGS84_A_KM * (1 - WGS84_F)) ** 2
    s = np.sin(lat)
    return b2 / 2 * (s / (1 - e2 * s**2) + np.log((1 + e * s) / (1 - e * s)) / (2 * e))


def pixel_area_km2(transform, rows: np.ndarray) -> np.ndarray:
    """Área de cada linha de pixels de uma grade lat/lon, exata no elipsoide WGS84."""
    top = np.radians(transform.f + transform.e * rows)
    bottom = np.radians(transform.f + transform.e * (rows + 1))
    return np.radians(abs(transform.a)) * np.abs(_zone(top) - _zone(bottom))


def _blocks(window: Window, size: int):
    for row in range(0, int(window.height), size):
        for col in range(0, int(window.width), size):
            yield Window(window.col_off + col, window.row_off + row,
                         min(size, window.width - col), min(size, window.height - row))


def class_areas(source: str, cells: gpd.GeoDataFrame, *, block: int = 4096,
                band: int = 1, progress=None) -> pd.DataFrame:
    """Área (km²) de cada valor do raster em cada célula: colunas = valores, índice = cell_id.

    `cells` precisa ter `cell_id` e a geometria já recortada pelo limite da região.
    `source` pode ser um caminho local ou uma URL (lida por /vsicurl/).
    """
    path = f"/vsicurl/{source}" if source.startswith("http") else source
    cells = cells.to_crs("EPSG:4326").reset_index(drop=True)
    shapes = list(zip(cells.geometry, range(1, len(cells) + 1), strict=True))
    n = len(cells) + 1
    totals: dict[int, np.ndarray] = {}
    with rasterio.Env(**GDAL_ENV), rasterio.open(path) as src:
        if src.crs.to_epsg() != 4326:
            raise ValueError("class_areas espera um raster em EPSG:4326")
        window = from_bounds(*cells.total_bounds, src.transform).round_offsets().round_lengths()
        window = window.intersection(Window(0, 0, src.width, src.height))
        blocks = list(_blocks(window, block))
        for k, sub in enumerate(blocks, 1):
            transform = src.window_transform(sub)
            ids = rasterize(shapes, out_shape=(int(sub.height), int(sub.width)),
                            transform=transform, fill=0, dtype="int32")
            inside = ids > 0
            if inside.any():
                values = src.read(band, window=sub)[inside]
                area = np.broadcast_to(
                    pixel_area_km2(transform, np.arange(int(sub.height)))[:, None], ids.shape
                )[inside]
                unique, inverse = np.unique(values, return_inverse=True)
                sums = np.bincount(ids[inside].astype(np.int64) * len(unique) + inverse,
                                   weights=area, minlength=n * len(unique))
                for j, value in enumerate(unique.tolist()):
                    totals.setdefault(value, np.zeros(n))
                    totals[value] += sums[j::len(unique)][:n]
            if progress:
                progress(k, len(blocks))
    frame = pd.DataFrame({v: a[1:] for v, a in sorted(totals.items())},
                         index=pd.Index(cells.cell_id.to_numpy(), name="cell_id"))
    return frame


def polygonal(frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Geometrias válidas e só polígonos: `make_valid` pode gerar linhas e coleções a partir
    de polígonos degenerados; linhas e pontos têm área nula e são descartados."""
    frame = frame.copy()
    frame.geometry = frame.geometry.make_valid()
    frame = frame.explode(index_parts=False)
    return frame[frame.geom_type.isin(["Polygon", "MultiPolygon"])]


def polygon_areas(polygons: gpd.GeoDataFrame, cells: gpd.GeoDataFrame,
                  by: str | None = None, crs: str = "EPSG:6933") -> pd.DataFrame:
    """Área (km²) de polígonos (PRODES, DETER) dentro de cada célula, opcionalmente por `by`."""
    cols = ["geometry"] + ([by] if by else [])
    parts = gpd.overlay(polygonal(polygons[cols]).to_crs(crs), cells[["cell_id", "geometry"]].to_crs(crs),
                        how="intersection", keep_geom_type=True)
    parts["km2"] = parts.area / 1e6
    keys = ["cell_id"] + ([by] if by else [])
    table = parts.groupby(keys).km2.sum()
    table = table.unstack(fill_value=0.0) if by else table.to_frame("km2")
    return table.reindex(cells.cell_id, fill_value=0.0)


def point_counts(points: gpd.GeoDataFrame, cells: gpd.GeoDataFrame,
                 by: str | None = None) -> pd.DataFrame:
    """Número de pontos (focos de fogo) em cada célula, opcionalmente por `by`."""
    joined = gpd.sjoin(points.to_crs(cells.crs), cells[["cell_id", "geometry"]],
                       predicate="within", how="inner")
    keys = ["cell_id"] + ([by] if by else [])
    table = joined.groupby(keys).size()
    table = table.unstack(fill_value=0) if by else table.to_frame("count")
    return table.reindex(cells.cell_id, fill_value=0)
