"""Chuva diária do CHIRPS por célula ERA5 (D-021).

A média é tomada sobre o quadrado inteiro da célula de 0,25°, e não sobre a parte dentro da
bacia, porque é esse quadrado que a série do ERA5 representa: as duas chuvas ficam
comparáveis célula a célula. As bordas das células (x,125° e x,375°) caem sobre os
centros dos pixels de 0,05°, então cada pixel entra com a fração exata da sua área que fica
dentro da célula (metade, nas bordas), e não pela regra do centro.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
import xarray as xr
from scipy import sparse

from amazon_chaos import regions
from amazon_chaos.io.chirps import ROOT, year_file


def out_path(cfg):
    return regions.processed_dir(cfg) / "chirps" / "diario.parquet"


def full_cells(cfg) -> gpd.GeoDataFrame:
    """Quadrados inteiros das células da região (sem recorte), na ordem de `regions.cells`."""
    cells = regions.cells(cfg)[["cell_id", "latitude", "longitude"]].reset_index(drop=True)
    half = cfg["spatial"].get("grid_degrees", 0.25) / 2
    squares = shapely.box(cells.longitude - half, cells.latitude - half,
                          cells.longitude + half, cells.latitude + half)
    return gpd.GeoDataFrame(cells, geometry=squares, crs="EPSG:4326")


def _overlap(centers, step, lo, hi):
    """Fração de cada pixel (centros, largura `step`) dentro de [lo, hi], por célula."""
    left, right = centers - step / 2, centers + step / 2
    inter = np.minimum(right[None, :], hi[:, None]) - np.maximum(left[None, :], lo[:, None])
    return np.clip(inter, 0, None) / step


def overlap_weights(cells, lat, lon) -> sparse.csr_matrix:
    """Pesos (célula × pixel): fração do pixel dentro do quadrado × cos(latitude)."""
    res_x, res_y = float(abs(lon[1] - lon[0])), float(abs(lat[1] - lat[0]))
    b = cells.bounds
    fx = _overlap(lon, res_x, b.minx.to_numpy(), b.maxx.to_numpy())
    fy = _overlap(lat, res_y, b.miny.to_numpy(), b.maxy.to_numpy())
    fy = fy * np.cos(np.radians(lat))[None, :]  # área do pixel ∝ cos(φ) numa grade lat/lon
    rows, cols, vals = [], [], []
    for k in range(len(cells)):
        iy, ix = np.flatnonzero(fy[k]), np.flatnonzero(fx[k])
        if not len(iy) or not len(ix):
            raise RuntimeError("A caixa do CHIRPS não cobre todas as células da região")
        rows.append(np.full(len(iy) * len(ix), k))
        cols.append((iy[:, None] * len(lon) + ix[None, :]).ravel())
        vals.append(np.outer(fy[k, iy], fx[k, ix]).ravel())
    return sparse.csr_matrix((np.concatenate(vals), (np.concatenate(rows),
                                                     np.concatenate(cols))),
                             shape=(len(cells), len(lat) * len(lon)))


def cell_precip(cfg, first: int = 2001, last: int = 2024, root=ROOT) -> pd.DataFrame:
    """Chuva diária (mm) por célula: índice = dia, colunas = cell_id."""
    cells = full_cells(cfg)
    files = [year_file(y, root) for y in range(first, last + 1)]
    missing = [f.name for f in files if not f.exists()]
    if missing:
        raise FileNotFoundError(f"CHIRPS ausente ({', '.join(missing)}): rode "
                                "`amazon-chaos chirps fetch`")
    parts = []
    weights = None
    for path in files:
        with xr.open_dataset(path) as ds:
            field = ds.precip_mm.load()
        if weights is None:
            weights = overlap_weights(cells, field.latitude.values, field.longitude.values)
        values = field.values.reshape(field.sizes["time"], -1)
        valid = np.isfinite(values)
        total = weights @ np.where(valid, values, 0.0).T
        norm = weights @ valid.T.astype(float)
        with np.errstate(invalid="ignore", divide="ignore"):
            parts.append(pd.DataFrame((total / norm).T, index=field.time.values,
                                      columns=cells.cell_id))
    table = pd.concat(parts)
    table.index.name = "time"
    return table
