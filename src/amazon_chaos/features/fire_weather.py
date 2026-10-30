"""Condições meteorológicas antes do fogo (pergunta secundária; D-025).

O evento é o início de um episódio de fogo: um dia com foco de fogo ativo (BDQueimadas,
satélite de referência) numa célula que não teve foco nos 30 dias anteriores, de 2003 a
2024, no dia local (UTC−03:00, o mesmo do ERA5). Ficar só com o início evita contar como
independentes os focos de um mesmo incêndio, e não depende do calendário: o primeiro foco
do ano civil cairia muitas vezes em janeiro, numa queima que vem da temporada anterior.

Para cada evento medimos as condições até a véspera: anomalia do VPD e da temperatura do
ERA5 (em relação à normal 1991–2020) nos 7 e nos 30 dias anteriores, chuva acumulada nos
30 dias anteriores no CHIRPS e no ERA5 e dias seguidos sem chuva (< 1 mm) no CHIRPS. O
controle são os mesmos dias do calendário (±15 dias corridos, em datas reais) na mesma
célula, nos anos em que ela não teve foco nessa janela; o percentil do evento entre os
controles tira a sazonalidade e a geografia.
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
    "t2m_30d": "anomalia da temperatura, 30 dias antes (°C)",
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
        "t2m_30d": t2m_a.rolling(30).mean().shift(1),
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


def same_dates(days: pd.Series, year: int) -> np.ndarray:
    """A mesma data do calendário em `year`; 29 de fevereiro vira 28 nos anos comuns."""
    leap = pd.Timestamp(f"{year}-12-31").day_of_year == 366
    day = np.where((days.dt.month == 2) & (days.dt.day == 29) & ~leap, 28, days.dt.day)
    return pd.to_datetime(pd.DataFrame({"year": year, "month": days.dt.month, "day": day}))\
        .to_numpy()


def composite(cfg, fires=None, cond=None) -> pd.DataFrame:
    """Uma linha por evento: cada medida no evento, a mediana dos controles e o percentil.

    Controles: em cada um dos outros anos, a mesma data do calendário e os dias a até
    ±WINDOW dias corridos dela (atravessando a virada do ano), na mesma célula, se a célula
    não teve nenhum foco nesse intervalo. O percentil (0 a 1; empates contam metade) é a
    posição do evento na distribuição dos seus controles: 0,5 é um dia típico daquela época
    e lugar. Ele não depende da forma da distribuição, ao contrário da diferença para a
    média, que seria negativa sem efeito nenhum em medidas assimétricas como a chuva
    acumulada.
    """
    fires = fire_days(cfg) if fires is None else fires
    cond = conditions(cfg) if cond is None else cond
    ev = events(fires)
    start, n_days = fires.index[0], len(fires)
    burned = (fires > 0).astype(float)
    nearby = burned.rolling(2 * WINDOW + 1, center=True, min_periods=1).sum().to_numpy()
    clean = nearby == 0  # dia × célula sem foco a ±WINDOW dias
    tables = {name: table.reindex(fires.index)[fires.columns].to_numpy(dtype=float)
              for name, table in cond.items()}
    years = np.arange(YEARS[0], YEARS[1] + 1)
    anchors = np.column_stack([(same_dates(ev.dia, y) - start.to_datetime64())
                               // np.timedelta64(1, "D") for y in years])
    ci = fires.columns.get_indexer(ev.cell_id)
    ei = ((ev.dia - start).dt.days).to_numpy()
    offsets = np.arange(-WINDOW, WINDOW + 1)
    values = {name: np.full(len(ev), np.nan) for name in tables}
    medians = {name: np.full(len(ev), np.nan) for name in tables}
    ranks = {name: np.full(len(ev), np.nan) for name in tables}
    controls = np.zeros(len(ev), dtype=int)
    for k, (e, c) in enumerate(zip(ei, ci, strict=True)):
        a = anchors[k]
        a = a[clean[a, c]]  # o ano do próprio evento nunca é limpo
        days = (a[:, None] + offsets).ravel()
        days = days[(days >= 0) & (days < n_days)]
        for name, table in tables.items():
            sample = table[days, c]
            sample = sample[np.isfinite(sample)]
            x = table[e, c]
            values[name][k] = x
            if len(sample) and np.isfinite(x):
                medians[name][k] = np.median(sample)
                ranks[name][k] = np.mean(sample < x) + 0.5 * np.mean(sample == x)
            if name == "vpd_7d":
                controls[k] = len(sample)
    out = ev.copy()
    out["controles"] = controls
    for name in tables:
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


THIRDS = ("preservada", "intermediária", "perturbada")


def cell_thirds(cells: pd.DataFrame, column: str = "perda_antecedente") -> pd.Series:
    """Terço de perturbação de cada célula elegível, com os cortes calculados nas células.

    Os eventos herdam o terço da sua célula. Cortar sobre a tabela de eventos daria peso a
    cada episódio, e uma célula com muitos episódios deslocaria os cortes.
    """
    eligible = cells.loc[cells.elegivel, column]
    return pd.qcut(eligible.rank(method="first"), 3, labels=list(THIRDS)).rename("terco")


def contrast(events: pd.DataFrame, by: list[str] | None = None, column: str = "terco",
             first: str = "preservada", second: str = "perturbada", n: int = 999,
             seed: int = 20261023) -> pd.DataFrame:
    """Diferença do percentil médio entre dois grupos de células, com IC 95% por anos.

    Os mesmos anos sorteados valem para os dois grupos, que dividem as mesmas secas.
    """
    rng = np.random.default_rng(seed)
    groups = events.groupby(by) if by else [((), events)]
    rows = []
    for key, part in groups:
        years = np.unique(part.ano)
        pick = rng.integers(0, len(years), size=(n, len(years)))
        for name in MEASURES:
            col = f"{name}_percentil"
            stats = {}
            for label in (first, second):
                sub = part[part[column] == label]
                per_year = sub.groupby("ano")[col].agg(["sum", "count"]).reindex(
                    years, fill_value=0)
                sums, counts = per_year["sum"].to_numpy(), per_year["count"].to_numpy()
                stats[label] = (sums.sum() / counts.sum(),
                                sums[pick].sum(axis=1) / counts[pick].sum(axis=1))
            diff = stats[first][1] - stats[second][1]
            key = key if isinstance(key, tuple) else (key,)
            lo, hi = np.nanquantile(diff, [0.025, 0.975])
            rows.append({**dict(zip(by or [], key, strict=True)), "medida": name,
                         first: stats[first][0], second: stats[second][0],
                         "diferenca": stats[first][0] - stats[second][0],
                         "ic_inf": float(lo), "ic_sup": float(hi),
                         "exclui_zero": bool(lo > 0 or hi < 0)})
    return pd.DataFrame(rows)
