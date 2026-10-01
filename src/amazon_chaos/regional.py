"""Resumos regionais das séries diárias, calculados ano a ano para caber na memória.

`summarize` lê um arquivo anual por vez e guarda:

- série diária regional, ponderada pela área de cada célula dentro da região;
- médias (ou totais, para chuva) mensais por célula;
- extremos anuais por célula: dia mais quente e maior sequência de dias secos.

O resultado vai para `summary_<início>_<fim>.nc`, reaproveitado enquanto os arquivos
diários não mudarem (tamanho e data de modificação).
"""

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr

from amazon_chaos.preprocess.grid import build_grid

# nome curto → (variável diária, agregação mensal)
VARIABLES = {
    "t2m": ("t2m_c_mean", "mean"),
    "tmin": ("t2m_c_min", "mean"),
    "tmax": ("t2m_c_max", "mean"),
    "dtr": ("t2m_c_range", "mean"),
    "rh": ("rh_pct_mean", "mean"),
    "vpd": ("vpd_kpa_mean", "mean"),
    "q": ("q_gkg_mean", "mean"),
    "wind": ("wind_speed_10m_mean", "mean"),
    "u10": ("u10_mean", "mean"),
    "v10": ("v10_mean", "mean"),
    "sp": ("surface_pressure_hpa_mean", "mean"),
    "precip": ("precip_mm_sum", "sum"),
}
DRY_DAY_MM = 1.0
SUMMARY_VERSION = 2  # incrementar ao mudar o conteúdo do resumo


def region_cells(config):
    """Células da região com o peso (km²) de cada uma e o polígono recortado para mapas."""
    grid = build_grid(config["spatial"]["area"])
    if "basin_source" not in config["spatial"]:
        grid["weight_km2"] = grid.area_km2
        return grid
    basin = gpd.read_file(config["spatial"]["basin_source"]).to_crs("EPSG:4326")
    cells = gpd.read_file(Path("data/processed") / config["experiment_id"] / "basin_grid.geojson")
    grid = grid.merge(cells[["latitude", "longitude", "basin_km2"]], on=["latitude", "longitude"])
    grid["weight_km2"] = grid.basin_km2
    grid["geometry"] = grid.geometry.intersection(basin.union_all())
    return grid


def weights(cells, latitudes, longitudes):
    table = cells.pivot(index="latitude", columns="longitude", values="weight_km2")
    table = table.reindex(index=latitudes, columns=longitudes).fillna(0)
    return xr.DataArray(table.to_numpy(), dims=("latitude", "longitude"),
                        coords={"latitude": latitudes, "longitude": longitudes})


def longest_run(mask):
    """Maior sequência de valores verdadeiros ao longo do primeiro eixo."""
    run = np.zeros(mask.shape[1:], dtype="int16")
    best = run.copy()
    for step in mask:
        run = np.where(step, run + 1, 0)
        best = np.maximum(best, run)
    return best


def _fingerprint(files):
    return json.dumps([SUMMARY_VERSION] + [[f.name, f.stat().st_size, int(f.stat().st_mtime)]
                                           for f in files])


def daily_files(config, first, last, root="data/processed"):
    base = Path(root) / config["experiment_id"]
    files = [base / f"daily_{y}-01-01_{y}-12-31.nc" for y in range(first, last + 1)]
    missing = [f.name for f in files if not f.exists()]
    if missing:
        raise FileNotFoundError(f"Séries diárias ausentes: {missing[:3]}…")
    return files


def summarize(config, first=1990, last=2024, root="data/processed", progress=None):
    files = daily_files(config, first, last, root)
    target = Path(root) / config["experiment_id"] / f"summary_{first}_{last}.nc"
    fingerprint = _fingerprint(files)
    if target.exists():
        with xr.open_dataset(target) as cached:
            if cached.attrs.get("sources") == fingerprint:
                return cached.load()
    cells = region_cells(config)
    names = [source for source, _ in VARIABLES.values()]
    regional, monthly, annual = [], [], []
    for path in files:
        with xr.open_dataset(path) as source:
            ds = source[names].load()
        w = weights(cells, ds.latitude.values, ds.longitude.values)
        inside = w > 0
        ds = ds.where(inside)
        regional.append(ds.weighted(w).mean(("latitude", "longitude")))
        months = ds.resample(time="MS")
        means, sums = months.mean(), months.sum(min_count=1)
        monthly.append(xr.Dataset({
            short: (means if how == "mean" else sums)[var]
            for short, (var, how) in VARIABLES.items()
        }))
        year = int(pd.Timestamp(ds.time.values[0]).year)
        dry = longest_run((ds.precip_mm_sum < DRY_DAY_MM).values)
        annual.append(xr.Dataset({
            "hottest_day": ds.t2m_c_max.max("time"),
            "longest_dry_spell": (("latitude", "longitude"),
                                  np.where(inside.values, dry, np.nan).astype("float32")),
            "rain_days": (ds.precip_mm_sum >= DRY_DAY_MM).sum("time").where(inside),
            "days_in_year": ds.sizes["time"],
            **{f"complete_days_{short}": ds[VARIABLES[short][0]].count("time").where(inside)
               for short in ["t2m", "tmax", "rh", "vpd", "wind", "precip"]},
        }).expand_dims(year=[year]))
        if progress:
            progress(year)
    region = xr.concat(regional, "time").rename({v: k for k, (v, _) in VARIABLES.items()})
    cell_month = xr.concat(monthly, "time").rename(time="month")
    out = xr.merge([
        region.rename({k: f"region_{k}" for k in VARIABLES}),
        cell_month.rename({k: f"cell_{k}" for k in VARIABLES}),
        xr.concat(annual, "year"),
        w.rename("weight_km2"),
    ])
    out.attrs = {"sources": fingerprint, "dry_day_mm": DRY_DAY_MM,
                 "era5_source": xr.open_dataset(files[0]).attrs.get("era5_source", "")}
    out.to_netcdf(target)
    return out


def regional_frame(summary):
    """Série diária regional como DataFrame com nomes curtos."""
    names = [v for v in summary.data_vars if v.startswith("region_")]
    frame = summary[names].to_dataframe()
    frame.columns = [c.removeprefix("region_") for c in frame.columns]
    return frame


def anomalies(series, base=("1991-01-01", "2020-12-31"), window=31):
    """Anomalia diária em relação ao ciclo anual médio (suavizado) do período de referência."""
    reference = series.loc[base[0]:base[1]]
    doy = reference.groupby(reference.index.dayofyear).mean().reindex(range(1, 367))
    doy = doy.interpolate(limit_direction="both")
    padded = pd.concat([doy.iloc[-window:], doy, doy.iloc[:window]])
    smooth = padded.rolling(window, center=True).mean().iloc[window:-window]
    smooth.index = doy.index
    return series - smooth.reindex(series.index.dayofyear).to_numpy(), smooth


def theil_sen(values, years):
    """Inclinação de Theil–Sen por década e p-valor de Mann–Kendall (sem correção serial)."""
    from scipy.stats import kendalltau, theilslopes

    ok = np.isfinite(values)
    if ok.sum() < 8:
        return np.nan, np.nan
    slope = theilslopes(values[ok], years[ok])[0]
    return 10 * slope, kendalltau(years[ok], values[ok]).pvalue
