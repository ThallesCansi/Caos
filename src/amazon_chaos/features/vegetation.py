"""A floresta como variável dinâmica (D-031): LAI, NDMI e área queimada do MODIS.

Aquisição pelo AppEEARS (`io/appeears.py`), em duas tarefas por bacia:
- `vegetacao`: MOD15A2H (LAI) e MOD09A1 (refletâncias para o NDMI), recortados nas células
  da subamostra de D-024 (etapas 1 e 2);
- `fogo`: MCD64A1 (dia da queima) na bacia inteira (etapa 3); a vegetação dos episódios
  e dos controles sorteados vem depois, por pedido de pontos.

Os filtros de qualidade e a máscara de floresta seguem a D-031.
"""

from __future__ import annotations

import numpy as np

from amazon_chaos import regions

SUBSAMPLE = {"n": 60, "seed": 20261023}  # a mesma de D-024
VEGETATION_LAYERS = [
    ("MOD15A2H.061", "Lai_500m"), ("MOD15A2H.061", "FparLai_QC"),
    ("MOD09A1.061", "sur_refl_b02"), ("MOD09A1.061", "sur_refl_b06"),
    ("MOD09A1.061", "sur_refl_state_500m"), ("MOD09A1.061", "sur_refl_qc_500m"),
    ("MOD09A1.061", "sur_refl_vzen"), ("MOD09A1.061", "sur_refl_day_of_year"),
]
FIRE_LAYERS = [("MCD64A1.061", "Burn_Date"), ("MCD64A1.061", "QA")]
# máscara reserva, na mesma grade de 500 m, caso os COGs do MapBiomas fiquem inacessíveis
COVER_LAYERS = [("MCD12Q1.061", "LC_Type1")]
EVERGREEN_FOREST = 2  # IGBP
MAX_VIEW_ZENITH = 35.0  # graus


def subsample_cells(cfg, spec):
    """Polígonos das células da subamostra de D-024."""
    from amazon_chaos import gradient as G
    from amazon_chaos.nonlinear.sensitivity import subsample

    chosen = subsample(G.cell_table(cfg, spec), SUBSAMPLE["n"], SUBSAMPLE["seed"])
    cells = regions.cells(cfg)
    return cells[cells.cell_id.isin(chosen)][["cell_id", "geometry"]]


# o AppEEARS limita o número de arquivos por pedido (um por camada × data × feição): as
# células vão juntas numa só feição, e o pedido é dividido por produto e metade do período
VEGETATION_PARTS = {f"{product[:5].lower()}_{first}_{last}": (product, first, last)
                    for product in ("MOD15A2H.061", "MOD09A1.061")
                    for first, last in ((2001, 2012), (2013, 2024))}


def vegetation_payload(cfg, spec, part: str) -> dict:
    from amazon_chaos.io.appeears import area_payload

    product, first, last = VEGETATION_PARTS[part]
    cells = subsample_cells(cfg, spec)
    union = cells.dissolve()[["geometry"]]
    return area_payload(f"tcc-caos-{cfg['slug']}-{part}",
                        [layer for layer in VEGETATION_LAYERS if layer[0] == product], union,
                        start=f"01-01-{first}", end=f"12-31-{last}")


def fire_payload(cfg, tolerance=0.01) -> dict:
    from amazon_chaos.io.appeears import area_payload

    limit = regions.boundary(cfg)
    limit = limit.assign(geometry=limit.geometry.simplify(tolerance))
    return area_payload(f"tcc-caos-{cfg['slug']}-mcd64a1", FIRE_LAYERS, limit,
                        start="11-01-2000")


def cover_payload(cfg, tolerance=0.01) -> dict:
    from amazon_chaos.io.appeears import area_payload

    limit = regions.boundary(cfg)
    limit = limit.assign(geometry=limit.geometry.simplify(tolerance))
    return area_payload(f"tcc-caos-{cfg['slug']}-mcd12q1", COVER_LAYERS, limit)


# ── filtros de qualidade (D-031) ────────────────────────────────────────────


def _bits(value, first: int, count: int) -> np.ndarray:
    v = np.nan_to_num(np.asarray(value, dtype=float), nan=0.0).astype(np.int64)
    return (v >> first) & ((1 << count) - 1)


def lai_ok(qc) -> np.ndarray:
    """Sem nuvem (bits 3–4 = 00) e algoritmo principal (bits 5–7 ∈ {0, 1})."""
    return (_bits(qc, 3, 2) == 0) & (_bits(qc, 5, 3) <= 1)


def reflectance_ok(state, qc, view_zenith) -> np.ndarray:
    """Céu limpo, sem sombra, aerossol não alto, sem nuvem interna, bandas 2 e 6 ideais e
    ângulo de visada ≤ 35°."""
    clear = ((_bits(state, 0, 2) == 0) & (_bits(state, 2, 1) == 0)
             & (_bits(state, 6, 2) != 3) & (_bits(state, 10, 1) == 0))
    bands = (_bits(qc, 6, 4) == 0) & (_bits(qc, 22, 4) == 0)
    return clear & bands & (np.asarray(view_zenith, dtype=float) <= MAX_VIEW_ZENITH)


def ndmi(nir, swir) -> np.ndarray:
    nir, swir = np.asarray(nir, dtype=float), np.asarray(swir, dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        return (nir - swir) / (nir + swir)


def burned(burn_date, qa) -> np.ndarray:
    """Queima válida: dia do ano entre 1 e 366 e QA com bit 0 = 1."""
    d = np.asarray(burn_date, dtype=float)
    return (d >= 1) & (d <= 366) & (_bits(qa, 0, 1) == 1)


# ── máscara de floresta (MapBiomas 30 m → grade de 500 m) ───────────────────


def forest_fraction(year: int, lat: np.ndarray, lon: np.ndarray, *, block: int = 4096,
                    source: str | None = None) -> np.ndarray:
    """Fração de floresta (classes 3 e 6 do MapBiomas) em cada pixel da grade regular
    (`lat` decrescente ou crescente, `lon` crescente, centros dos pixels), média dos pixels
    de 30 m cujo centro cai no pixel; NaN onde não há pixel observado."""
    import rasterio
    from rasterio.windows import Window, from_bounds

    from amazon_chaos.io import mapbiomas
    from amazon_chaos.preprocess.zonal import GDAL_ENV

    source = source or mapbiomas.url("cobertura", year)
    path = f"/vsicurl/{source}" if source.startswith("http") else source
    lat, lon = np.asarray(lat, float), np.asarray(lon, float)
    dlat, dlon = abs(lat[1] - lat[0]), abs(lon[1] - lon[0])
    top, left = lat.max() + dlat / 2, lon.min() - dlon / 2
    bounds = (left, lat.min() - dlat / 2, lon.max() + dlon / 2, top)
    forest = np.zeros((len(lat), len(lon)))
    land = np.zeros((len(lat), len(lon)))
    with rasterio.Env(**GDAL_ENV), rasterio.open(path) as src:
        window = from_bounds(*bounds, src.transform).round_offsets().round_lengths()
        window = window.intersection(Window(0, 0, src.width, src.height))
        for r0 in range(int(window.row_off), int(window.row_off + window.height), block):
            for c0 in range(int(window.col_off), int(window.col_off + window.width), block):
                sub = Window(c0, r0, min(block, window.col_off + window.width - c0),
                             min(block, window.row_off + window.height - r0))
                values = src.read(1, window=sub)
                t = src.window_transform(sub)
                ys = t.f + (np.arange(values.shape[0]) + 0.5) * t.e
                xs = t.c + (np.arange(values.shape[1]) + 0.5) * t.a
                rows = np.floor((top - ys) / dlat).astype(int)
                cols = np.floor((xs - left) / dlon).astype(int)
                okr, okc = (rows >= 0) & (rows < len(lat)), (cols >= 0) & (cols < len(lon))
                values = values[np.ix_(okr, okc)]
                rr, cc = np.meshgrid(rows[okr], cols[okc], indexing="ij")
                seen = ~np.isin(values, mapbiomas.NOT_OBSERVED)
                np.add.at(land, (rr[seen], cc[seen]), 1)
                np.add.at(forest, (rr[seen], cc[seen]), np.isin(values[seen], mapbiomas.FOREST))
    with np.errstate(invalid="ignore", divide="ignore"):
        frac = forest / land
    frac[land == 0] = np.nan
    return frac if lat[0] > lat[-1] else frac[::-1]


# ── séries por célula (etapas 1 e 2) ────────────────────────────────────────

# fração mínima dos pixels da máscara válidos numa composição; era 0,2, e a emenda da
# D-031 (31/10, só pela disponibilidade: nuvens da estação chuvosa) a baixou para 0,05
MIN_VALID = 0.05
FOREST_MIN = 0.9         # fração de floresta para um pixel contar como floresta


def _open(cfg, pattern: str):
    import xarray as xr

    from amazon_chaos.io.appeears import task_dir

    files = sorted(task_dir(cfg, "vegetacao").glob(f"*/{pattern}"))
    if not files:
        raise FileNotFoundError(f"{pattern}: rode `amazon-chaos vegetation fetch`")
    return unique_time(xr.open_mfdataset(files, combine="by_coords"))


def unique_time(ds):
    """Sem as composições repetidas: a de 26/12/2012 vem no fim de 2001–2012 e no começo de
    2013–2024 (mesmos valores)."""
    import pandas as pd

    return ds.isel(time=~pd.Index(ds.time.values).duplicated())


def _nearest(values: np.ndarray, grid: np.ndarray) -> np.ndarray:
    """Índice do ponto de `grid` mais próximo de cada valor."""
    order = np.argsort(grid)
    pos = np.clip(np.searchsorted(grid[order], values), 1, len(grid) - 1)
    left, right = order[pos - 1], order[pos]
    return np.where(np.abs(values - grid[left]) <= np.abs(values - grid[right]), left, right)


def ever_burned(cfg, lat, lon) -> np.ndarray:
    """Pixel com alguma queima válida no MCD64A1 (nov/2000–2024), na grade `lat` × `lon`."""
    import xarray as xr

    from amazon_chaos.io.appeears import task_dir

    files = sorted(task_dir(cfg, "fogo").glob("*.nc"))
    with xr.open_mfdataset(files, combine="by_coords") as ds:
        burnt = np.zeros((ds.sizes["lat"], ds.sizes["lon"]), bool)
        for t in range(ds.sizes["time"]):
            step = ds.isel(time=t).load()
            burnt |= burned(step.Burn_Date.values, step.QA.values)
        rows, cols = _nearest(lat, ds.lat.values), _nearest(lon, ds.lon.values)
    return burnt[np.ix_(rows, cols)]


def forest_mask(cfg, lat, lon, source: str = "mapbiomas") -> np.ndarray:
    """Floresta persistente (D-031): fração ≥ 0,9 no início e no fim do período."""
    if source == "mapbiomas":
        return ((forest_fraction(2000, lat, lon) >= FOREST_MIN)
                & (forest_fraction(2024, lat, lon) >= FOREST_MIN))
    import xarray as xr

    from amazon_chaos.io.appeears import task_dir

    files = sorted(task_dir(cfg, "cobertura").glob("*.nc"))
    with xr.open_mfdataset(files, combine="by_coords") as ds:
        first = ds.LC_Type1.isel(time=0).values == EVERGREEN_FOREST
        last = ds.LC_Type1.isel(time=-1).values == EVERGREEN_FOREST
        rows, cols = _nearest(lat, ds.lat.values), _nearest(lon, ds.lon.values)
    return (first & last)[np.ix_(rows, cols)]


def _when(value):
    import pandas as pd

    v = np.asarray(value).reshape(-1)[0]
    if hasattr(v, "year"):
        return pd.Timestamp(v.year, v.month, v.day)
    return pd.Timestamp(v)


def cell_series(cfg, spec, mask_source: str = "mapbiomas"):
    """LAI e NDMI médios dos pixels de floresta persistente nunca queimados de cada célula
    da subamostra, por composição, com o número de pixels válidos e o dia de observação.
    A cobertura mínima (`with_coverage`) é aplicada depois, na análise."""
    import pandas as pd

    from amazon_chaos.preprocess.zonal import grid_cell_index

    cells = subsample_cells(cfg, spec).reset_index(drop=True)
    lai, refl = _open(cfg, "MOD15A2H*.nc"), _open(cfg, "MOD09A1*.nc")
    lat, lon = refl.lat.values, refl.lon.values
    ids, _ = grid_cell_index(cells, lat, lon)
    keep = forest_mask(cfg, lat, lon, mask_source) & ~ever_burned(cfg, lat, lon) & (ids > 0)
    rr, cc = np.nonzero(keep)          # só os pixels da máscara entram no laço
    pix = ids[rr, cc]
    n = len(cells)
    in_mask = np.bincount(pix, minlength=n + 1)[1:]
    li, lj = _nearest(lat[rr], lai.lat.values), _nearest(lon[cc], lai.lon.values)
    lai_times = {_when(t): k for k, t in enumerate(lai.time.values)}
    names = cells.cell_id.to_numpy()
    rows = []
    for k in range(refl.sizes["time"]):
        step = refl.isel(time=k).load()
        when = _when(step.time.values)

        def at(name, s=step):
            return s[name].values[rr, cc]

        ok = reflectance_ok(at("sur_refl_state_500m"), at("sur_refl_qc_500m"),
                            at("sur_refl_vzen"))
        fields = {"ndmi": np.where(ok, ndmi(at("sur_refl_b02"), at("sur_refl_b06")), np.nan)}
        doy = np.where(ok, at("sur_refl_day_of_year"), np.nan)
        if when in lai_times:
            s = lai.isel(time=lai_times[when]).load()
            value = s.Lai_500m.values[li, lj]
            fields["lai"] = np.where(lai_ok(s.FparLai_QC.values[li, lj]) & (value <= 10),
                                     value, np.nan)
        day = pd.Series(doy).groupby(pix).median().reindex(range(1, n + 1)).to_numpy()
        for name, field in fields.items():
            good = np.isfinite(field)
            count = np.bincount(pix[good], minlength=n + 1)[1:]
            total = np.bincount(pix[good], weights=field[good], minlength=n + 1)[1:]
            with np.errstate(invalid="ignore", divide="ignore"):
                mean = np.where(count > 0, total / count, np.nan)
            rows += [{"cell_id": names[c], "composicao": when, "variavel": name,
                      "valor": mean[c], "validos": int(count[c]), "mascara": int(in_mask[c]),
                      "dia_obs": day[c]} for c in range(n)]
    return pd.DataFrame(rows)


def with_coverage(table, min_valid: float = MIN_VALID):
    """Apaga o valor das composições com menos de `min_valid` dos pixels da máscara válidos."""
    return table.assign(valor=table.valor.where(table.validos >= min_valid * table.mascara))


def prepare(values, dates, *, interpolate_max: int = 2, max_missing: float = 0.2):
    """Anomalia padronizada por composição do ano e lacunas tratadas (D-031).

    Devolve (série preenchida, máscara das composições originalmente vazias, se a célula
    passa no limite de lacunas)."""
    import pandas as pd

    from amazon_chaos.nonlinear.coupling import refill

    x = pd.Series(np.asarray(values, float), index=pd.DatetimeIndex(dates))
    slot = (x.index.dayofyear - 1) // 8
    mean = x.groupby(slot).transform("mean")
    sd = x.groupby(slot).transform("std")
    z = ((x - mean) / sd).to_numpy()
    missing = ~np.isfinite(z)
    return refill(z, missing, interpolate_max), missing, missing.mean() <= max_missing
