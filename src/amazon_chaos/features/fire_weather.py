"""Condições meteorológicas antes do fogo (pergunta secundária; D-025).

O evento é o início de um episódio de fogo: um dia com foco de fogo ativo (BDQueimadas,
satélite de referência) numa célula que não teve foco nos 30 dias anteriores, de 2003 a
2024, no dia local (UTC−03:00, o mesmo do ERA5). Ficar só com o início evita contar como
independentes os focos de um mesmo incêndio, e não depende do calendário: o primeiro foco
do ano civil cairia muitas vezes em janeiro, numa queima que vem da temporada anterior.

Para cada evento medimos as condições até a véspera: anomalia do VPD e da temperatura do
ERA5 (em relação à normal 1991–2020) nos 7 e nos 30 dias anteriores, chuva acumulada nos
30 dias anteriores no CHIRPS e no ERA5 e dias seguidos sem chuva (< 1 mm) no CHIRPS. O
controle são os mesmos dias do calendário (±15 dias) na mesma célula, nos anos em que ela
não teve foco nessa janela; o percentil do evento entre os controles tira a sazonalidade e
a geografia.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from amazon_chaos import regions
from amazon_chaos.features.chirps import out_path as chirps_path
from amazon_chaos.io import queimadas
from amazon_chaos.nonlinear.batch import load_cubes
from amazon_chaos.preprocess.zonal import point_counts
from amazon_chaos.regional import anomalies

YEARS = (2003, 2024)
WINDOW = 15  # dias do calendário de cada lado, para os controles
GAP = 30  # dias sem foco antes do início de um episódio
DRY_MM = 1.0
MEASURES = {
    "vpd_7d": "anomalia do VPD, 7 dias antes (kPa)",
    "vpd_30d": "anomalia do VPD, 30 dias antes (kPa)",
    "t2m_7d": "anomalia da temperatura, 7 dias antes (°C)",
    "chuva_30d_chirps": "chuva dos 30 dias antes, CHIRPS (mm)",
    "chuva_30d_era5": "chuva dos 30 dias antes, ERA5 (mm)",
    "dias_secos_chirps": "dias seguidos sem chuva até a véspera, CHIRPS",
}


def fire_days(cfg) -> pd.DataFrame:
    """Número de focos por dia local (linhas) e célula (colunas), 2003–2024."""
    cells = regions.cells(cfg)
    bounds = cells.total_bounds
    parts = []
    for year in range(YEARS[0], YEARS[1] + 1):
        points = queimadas.read_year(queimadas.fetch_year(year), bounds)
        points["dia"] = (points.data_pas - pd.Timedelta(hours=3)).dt.normalize()
        parts.append(point_counts(points, cells, by="dia"))
    table = pd.concat(parts, axis=1).fillna(0).T.sort_index()
    days = pd.date_range(f"{YEARS[0]}-01-01", f"{YEARS[1]}-12-31", freq="D")
    return table.groupby(level=0).sum().reindex(days, fill_value=0)


def dry_run(rain: pd.DataFrame, threshold: float = DRY_MM) -> pd.DataFrame:
    """Dias seguidos com chuva abaixo do limiar terminando em cada dia (0 se choveu)."""
    dry = (rain < threshold).to_numpy()
    out = np.zeros(dry.shape, dtype=float)
    for k in range(len(dry)):
        out[k] = np.where(dry[k], (out[k - 1] if k else 0) + 1, 0)
    return pd.DataFrame(out, index=rain.index, columns=rain.columns)


def conditions(cfg) -> dict[str, pd.DataFrame]:
    """Cada medida (dias × células), referida à véspera de cada dia."""
    names = {"vpd": "vpd_kpa_mean", "t2m": "t2m_c_mean", "precip": "precip_mm_sum"}
    cubes = load_cubes(cfg, names)
    ids = regions.cells(cfg).cell_id

    def frame(cube):
        f = cube.stack(point=("latitude", "longitude")).to_pandas()
        f.columns = [f"ERA5_{lat:+07.2f}_{lon:+08.2f}" for lat, lon in f.columns]
        return f[ids]

    vpd, t2m, era5 = (frame(cubes[k]) for k in ("vpd", "t2m", "precip"))
    vpd_a, t2m_a = anomalies(vpd)[0], anomalies(t2m)[0]
    chirps = pd.read_parquet(chirps_path(cfg))[ids]
    chirps.index = pd.DatetimeIndex(chirps.index)
    era5 = era5.reindex(chirps.index)
    before = {  # tudo deslocado um dia: só o que aconteceu antes do dia do evento
        "vpd_7d": vpd_a.rolling(7).mean().shift(1),
        "vpd_30d": vpd_a.rolling(30).mean().shift(1),
        "t2m_7d": t2m_a.rolling(7).mean().shift(1),
        "chuva_30d_chirps": chirps.rolling(30).sum().shift(1),
        "chuva_30d_era5": era5.rolling(30).sum().shift(1),
        "dias_secos_chirps": dry_run(chirps).shift(1),
    }
    days = pd.date_range(f"{YEARS[0]}-01-01", f"{YEARS[1]}-12-31", freq="D")
    return {k: v.reindex(days) for k, v in before.items()}


def events(fires: pd.DataFrame, gap: int = GAP) -> pd.DataFrame:
    """Dias com foco precedidos de pelo menos `gap` dias sem foco na mesma célula."""
    burned = fires > 0
    quiet = burned.astype(int).rolling(gap, min_periods=gap).sum().shift(1) == 0
    start = burned & quiet
    long = fires.where(start).stack().dropna().reset_index()
    long.columns = ["dia", "cell_id", "focos"]
    long["ano"] = long.dia.dt.year
    return long.sort_values(["cell_id", "dia"]).reset_index(drop=True)


def _window_sum(cube: np.ndarray, half: int) -> np.ndarray:
    """Soma circular, no dia do ano, de ±`half` dias (anos × 366 × células)."""
    padded = np.concatenate([cube[:, -half:], cube, cube[:, :half]], axis=1)
    acc = np.cumsum(np.nan_to_num(padded), axis=1)
    acc = np.concatenate([np.zeros_like(acc[:, :1]), acc], axis=1)
    return acc[:, 2 * half + 1:] - acc[:, :-2 * half - 1]


def _by_year(table: pd.DataFrame, years) -> np.ndarray:
    """Tabela diária (dias × células) como cubo anos × dia do ano (1–366) × células."""
    cube = np.full((len(years), 366, table.shape[1]), np.nan)
    rows = np.searchsorted(years, table.index.year)
    cube[rows, table.index.day_of_year - 1] = table.to_numpy(dtype=float)
    return cube


def composite(cfg, fires=None, cond=None) -> pd.DataFrame:
    """Uma linha por evento: cada medida no evento, a mediana dos controles e o percentil.

    Controles: os dias a até ±WINDOW dias do calendário do evento, na mesma célula, nos anos
    sem nenhum foco nessa janela. O percentil (0 a 1; empates contam metade) é a posição do
    evento na distribuição dos seus controles: 0,5 é um dia típico daquela época e lugar.
    Ele não depende da forma da distribuição, ao contrário da diferença para a média, que
    seria negativa sem efeito nenhum em medidas assimétricas como a chuva acumulada.
    """
    fires = fire_days(cfg) if fires is None else fires
    cond = conditions(cfg) if cond is None else cond
    ev = events(fires)
    years = np.arange(YEARS[0], YEARS[1] + 1)
    burned = np.nan_to_num(_by_year((fires > 0).astype(float), years))
    clean = ~(_window_sum(burned, WINDOW) > 0)  # ano × dia × célula sem foco na janela
    cubes = {name: _by_year(table, years) for name, table in cond.items()}
    yi = ev.ano.to_numpy() - YEARS[0]
    di = ev.dia.dt.day_of_year.to_numpy() - 1
    ci = fires.columns.get_indexer(ev.cell_id)
    offsets = np.arange(-WINDOW, WINDOW + 1)
    values = {name: np.full(len(ev), np.nan) for name in cubes}
    medians = {name: np.full(len(ev), np.nan) for name in cubes}
    ranks = {name: np.full(len(ev), np.nan) for name in cubes}
    controls = np.zeros(len(ev), dtype=int)
    for k, (y, d, c) in enumerate(zip(yi, di, ci, strict=True)):
        ok = clean[:, d, c]
        days = (d + offsets) % 366
        for name, cube in cubes.items():
            sample = cube[:, days, c][ok].ravel()
            sample = sample[np.isfinite(sample)]
            x = cube[y, d, c]
            values[name][k] = x
            if len(sample) and np.isfinite(x):
                medians[name][k] = np.median(sample)
                ranks[name][k] = np.mean(sample < x) + 0.5 * np.mean(sample == x)
            if name == "vpd_7d":
                controls[k] = len(sample)
    out = ev.copy()
    out["controles"] = controls
    for name in cubes:
        out[name] = values[name]
        out[f"{name}_controle"] = medians[name]
        out[f"{name}_percentil"] = ranks[name]
    return out


def summary(events: pd.DataFrame, by: list[str] | None = None, n: int = 999,
            seed: int = 20261023) -> pd.DataFrame:
    """Percentil médio de cada medida, com IC 95% reamostrando anos inteiros.

    Os eventos de um mesmo ano dividem o mesmo tempo (uma seca atinge muitas células de
    uma vez), então o ano é a unidade de reamostragem, e não o evento.
    """
    rng = np.random.default_rng(seed)
    groups = events.groupby(by) if by else [((), events)]
    rows = []
    for key, part in groups:
        years = np.unique(part.ano)
        by_year = {y: part[part.ano == y] for y in years}
        for name in MEASURES:
            column = f"{name}_percentil"
            sums = np.array([by_year[y][column].sum() for y in years])
            counts = np.array([by_year[y][column].notna().sum() for y in years])
            pick = rng.integers(0, len(years), size=(n, len(years)))
            boot = sums[pick].sum(axis=1) / counts[pick].sum(axis=1)
            key = key if isinstance(key, tuple) else (key,)
            rows.append({**dict(zip(by or [], key, strict=True)), "medida": name,
                         "eventos": int(counts.sum()), "percentil": sums.sum() / counts.sum(),
                         "ic_inf": float(np.quantile(boot, 0.025)),
                         "ic_sup": float(np.quantile(boot, 0.975))})
    return pd.DataFrame(rows)
