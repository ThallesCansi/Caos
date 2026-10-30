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

from amazon_chaos import regions
from amazon_chaos.preprocess.zonal import grid_cell_index, grid_cell_mean

DRY_MONTHS = (6, 7, 8, 9)


def good_quality(qc: np.ndarray) -> np.ndarray:
    # o AppEEARS declara 0 como "sem dado" do QC, e o xarray o decodifica como NaN; mas
    # QC = 0 é justamente a melhor qualidade. O LST ausente é filtrado pelo próprio LST.
    qc = np.nan_to_num(np.asarray(qc, dtype=float), nan=0.0).astype("uint8")
    return ((qc & 0b11) <= 1) & (((qc >> 6) & 0b11) <= 1)


def month_year(value) -> tuple[int, int]:
    """Mês e ano de um instante, venha ele como datetime64 ou como cftime (AppEEARS)."""
    value = np.asarray(value)
    if value.dtype.kind == "M":
        stamp = pd.Timestamp(value.astype("datetime64[ns]").reshape(-1)[0])
        return stamp.month, stamp.year
    when = value.reshape(-1)[0]
    return when.month, when.year


def cell_lst(cfg, files: list[Path] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(climatologia por célula, LST diurno da estação seca por célula e ano), em °C."""
    files = files or sorted((Path("data/raw") / cfg["experiment_id"] / "modis").glob("*.nc"))
    if not files:
        raise FileNotFoundError("MODIS ausente: rode `amazon-chaos modis fetch <região>`")
    cells = regions.cells(cfg).reset_index(drop=True)
    with xr.open_mfdataset(files, combine="by_coords") as ds:
        lat, lon = ds["lat"].values, ds["lon"].values
        ids, area = grid_cell_index(cells, lat, lon)
        sums = {k: np.zeros((len(lat), len(lon))) for k in
                ("day", "night", "dry", "n_day", "n_night", "n_dry")}
        yearly: dict[int, np.ndarray] = {}
        for t in range(ds.sizes["time"]):
            step = ds.isel(time=t).load()
            month, year = month_year(step.time.values)
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
            "lst_dia_c": grid_cell_mean(sums["day"] / sums["n_day"] - 273.15, ids, area, n),
            "lst_noite_c": grid_cell_mean(sums["night"] / sums["n_night"] - 273.15, ids, area, n),
            "lst_dia_seca_c": grid_cell_mean(sums["dry"] / sums["n_dry"] - 273.15, ids, area, n),
            "lst_composicoes_validas": grid_cell_mean(sums["n_day"], ids, area, n),
            "lst_composicoes_validas_seca": grid_cell_mean(sums["n_dry"], ids, area, n),
        }, index=pd.Index(cells.cell_id, name="cell_id"))
        dry = pd.DataFrame({year: grid_cell_mean(acc[0] / acc[1] - 273.15, ids, area, n)
                            for year, acc in sorted(yearly.items())},
                           index=pd.Index(cells.cell_id, name="cell_id"))
    return clim, dry


# ── ERA5 na passagem do Terra (F2e, D-027) ───────────────────────────────────

SOLAR_HOUR = 10.5
CLEAR_SKY = 0.3
HALVES = {"2001_2012": (2001, 2012), "2013_2024": (2013, 2024)}


def overpass_utc(longitude) -> np.ndarray:
    """Hora UTC das 10h30 solares locais: 10,5 − longitude/15 (de 13,8 a 14,5 nas bacias)."""
    return SOLAR_HOUR - np.asarray(longitude, dtype=float) / 15


def at_overpass(ds: xr.Dataset) -> xr.Dataset:
    """Interpola os campos horários (13–15 UTC) para as 10h30 solares de cada longitude."""
    day = ds.valid_time.dt.floor("D").values
    hour = ds.valid_time.dt.hour.values
    hourly = (ds.assign_coords(day=("valid_time", day), hour=("valid_time", hour))
              .set_index(valid_time=["day", "hour"]).unstack("valid_time"))
    target = xr.DataArray(overpass_utc(ds.longitude), coords={"longitude": ds.longitude})
    if float(target.min()) < hourly.hour.min() or float(target.max()) > hourly.hour.max():
        raise ValueError("as horas baixadas não cobrem a passagem em todas as longitudes")
    lower = np.floor(target).clip(max=float(hourly.hour.max()) - 1)
    frac = target - lower
    return hourly.sel(hour=lower) * (1 - frac) + hourly.sel(hour=lower + 1) * frac


def era5_overpass(cfg, folder: Path) -> pd.DataFrame:
    """Médias da estação seca, por célula, de skt e t2m às 10h30 solares, em °C.

    Uma coluna por janela (2001–2024 e metades), as mudanças entre as metades e a média de
    skt só nos dias com cobertura de nuvens < 0,3 às 10h30 (perto da amostragem do MODIS).
    """
    files = sorted(folder.glob("[0-9][0-9][0-9][0-9].nc"))
    if not files:
        raise FileNotFoundError("Passagem ausente: rode `amazon-chaos era5 passage <região>`")
    sums: dict[str, xr.DataArray] = {}

    def add(key, field):
        sums[key] = field if key not in sums else sums[key] + field

    for path in files:
        year = int(path.stem)
        with xr.open_dataset(path) as ds:
            day = at_overpass(ds.load())
        day = day.sel(day=day.day.dt.month.isin(DRY_MONTHS))
        skt, t2m = day.skt - 273.15, day.t2m - 273.15
        clear = day.tcc < CLEAR_SKY
        labels = ["2001_2024"] + [h for h, (a, b) in HALVES.items() if a <= year <= b]
        for label in labels:
            add(f"skt_{label}", skt.sum("day"))
            add(f"t2m_{label}", t2m.sum("day"))
            add(f"n_{label}", skt.notnull().sum("day"))
        add("skt_limpo", skt.where(clear).sum("day"))
        add("n_limpo", clear.sum("day"))
    grid = {}
    for label in ("2001_2024", *HALVES):
        suffix = "" if label == "2001_2024" else f"_{label}"
        grid[f"era5_skt_1030_seca{suffix}"] = sums[f"skt_{label}"] / sums[f"n_{label}"]
        grid[f"era5_t2m_1030_seca{suffix}"] = sums[f"t2m_{label}"] / sums[f"n_{label}"]
    grid["era5_skt_1030_seca_limpo"] = sums["skt_limpo"] / sums["n_limpo"]
    grid["era5_fracao_limpo"] = sums["n_limpo"] / sums["n_2001_2024"]
    frame = xr.Dataset(grid).to_dataframe().reset_index()
    cells = regions.cells(cfg)[["cell_id", "latitude", "longitude"]]
    out = cells.merge(frame, on=["latitude", "longitude"], how="left").set_index("cell_id")
    for name in ("skt", "t2m"):
        out[f"delta_era5_{name}_1030_seca"] = (out[f"era5_{name}_1030_seca_2013_2024"]
                                               - out[f"era5_{name}_1030_seca_2001_2012"])
    return out.drop(columns=["latitude", "longitude"])
