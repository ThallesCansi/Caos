"""MODIS LST por célula ERA5 (checagem D-011): o gradiente observado aparece no ERA5?

Filtro de qualidade do MOD11A2 (bits do QC): qualidade obrigatória "boa" ou "outra"
(bits 0–1 ∈ {0, 1}) e erro médio de LST ≤ 2 K (bits 6–7 ∈ {0, 1}). Cada pixel de 1 km entra
na célula cujo polígono (recortado pela bacia) contém seu centro, com peso pela área. O LST
só é usado como média (climatologia e estação seca); as lacunas de nuvem impedem séries
diárias, então ele não entra na análise não linear.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from rasterio.features import rasterize
from rasterio.transform import from_origin

from amazon_chaos import regions
from amazon_chaos.preprocess.zonal import pixel_area_km2

DRY_MONTHS = (6, 7, 8, 9)


def good_quality(qc: np.ndarray) -> np.ndarray:
    # o AppEEARS declara 0 como "sem dado" do QC, e o xarray o decodifica como NaN; mas
    # QC = 0 é justamente a melhor qualidade. O LST ausente é filtrado pelo próprio LST.
    qc = np.nan_to_num(np.asarray(qc, dtype=float), nan=0.0).astype("uint8")
    return ((qc & 0b11) <= 1) & (((qc >> 6) & 0b11) <= 1)


def _cell_index(cells, lat, lon):
    res_x, res_y = float(abs(lon[1] - lon[0])), float(abs(lat[1] - lat[0]))
    transform = from_origin(float(lon.min()) - res_x / 2, float(lat.max()) + res_y / 2,
                            res_x, res_y)
    shapes = list(zip(cells.geometry, range(1, len(cells) + 1), strict=True))
    ids = rasterize(shapes, out_shape=(len(lat), len(lon)), transform=transform, fill=0,
                    dtype="int32")
    if lat[0] < lat[-1]:  # grade crescente: alinhar linhas com a latitude
        ids = ids[::-1]
    area = pixel_area_km2(transform, np.arange(len(lat)))
    if lat[0] < lat[-1]:
        area = area[::-1]
    return ids, np.broadcast_to(area[:, None], ids.shape)


def _cell_mean(field, ids, area, n):
    ok = np.isfinite(field) & (ids > 0)
    w = np.bincount(ids[ok], weights=area[ok], minlength=n + 1)
    s = np.bincount(ids[ok], weights=(field * area)[ok], minlength=n + 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return (s / w)[1:]


def cell_lst(cfg, files: list[Path] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(climatologia por célula, LST diurno da estação seca por célula e ano), em °C."""
    files = files or sorted((Path("data/raw") / cfg["experiment_id"] / "modis").glob("*.nc"))
    if not files:
        raise FileNotFoundError("MODIS ausente: rode `amazon-chaos modis fetch <região>`")
    cells = regions.cells(cfg).reset_index(drop=True)
    with xr.open_mfdataset(files, combine="by_coords") as ds:
        lat, lon = ds["lat"].values, ds["lon"].values
        ids, area = _cell_index(cells, lat, lon)
        sums = {k: np.zeros((len(lat), len(lon))) for k in
                ("day", "night", "dry", "n_day", "n_night", "n_dry")}
        yearly: dict[int, np.ndarray] = {}
        for t in range(ds.sizes["time"]):
            step = ds.isel(time=t).load()
            when = step.time.values.item()  # datetime do cftime (calendário juliano)
            month, year = when.month, when.year
            day = np.where(good_quality(step.QC_Day.values), step.LST_Day_1km.values, np.nan)
            night = np.where(good_quality(step.QC_Night.values), step.LST_Night_1km.values,
                             np.nan)
            for name, field in (("day", day), ("night", night)):
                ok = np.isfinite(field)
                sums[name][ok] += field[ok]
                sums[f"n_{name}"][ok] += 1
            if month in DRY_MONTHS:
                ok = np.isfinite(day)
                sums["dry"][ok] += day[ok]
                sums["n_dry"][ok] += 1
                acc = yearly.setdefault(year, np.zeros((2, len(lat), len(lon))))
                acc[0][ok] += day[ok]
                acc[1][ok] += 1
    n = len(cells)
    with np.errstate(invalid="ignore", divide="ignore"):
        clim = pd.DataFrame({
            "lst_dia_c": _cell_mean(sums["day"] / sums["n_day"] - 273.15, ids, area, n),
            "lst_noite_c": _cell_mean(sums["night"] / sums["n_night"] - 273.15, ids, area, n),
            "lst_dia_seca_c": _cell_mean(sums["dry"] / sums["n_dry"] - 273.15, ids, area, n),
            "lst_composicoes_validas": _cell_mean(sums["n_day"], ids, area, n),
        }, index=pd.Index(cells.cell_id, name="cell_id"))
        dry = pd.DataFrame({year: _cell_mean(acc[0] / acc[1] - 273.15, ids, area, n)
                            for year, acc in sorted(yearly.items())},
                           index=pd.Index(cells.cell_id, name="cell_id"))
    return clim, dry
