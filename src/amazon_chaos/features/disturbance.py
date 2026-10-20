"""Métricas de perturbação por célula ERA5, definidas sem olhar a resposta climática (F3).

Fontes (D-012): PRODES, DETER e BDQueimadas (INPE) como principais; MapBiomas Cobertura e
Fogo como complemento. Regras em docs/metodologia.md §7:

- frações usam a **área terrestre observada** (MapBiomas, sem água e sem "não observado")
  como denominador declarado;
- o PRODES de 1988–2007 é um bloco agregado: nunca é repartido por ano;
- o PRODES só monitora vegetação florestal; a conversão no Cerrado só aparece no MapBiomas;
- sem foco observado, o ano do último foco é **censurado** (NaN + indicador), não zero;
- fontes diferentes não são emendadas numa mesma variável.

`fetch_all` grava as tabelas intermediárias em `data/processed/<exp>/perturbacao/`;
`build` lê só essas tabelas e devolve uma linha por célula.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from amazon_chaos import regions
from amazon_chaos.io import mapbiomas, queimadas, terrabrasilis
from amazon_chaos.preprocess.zonal import class_areas, point_counts, polygon_areas
from amazon_chaos.provenance import sha256_file

COVER_YEARS = (1990, 2000, 2012, 2024)
FIRE_YEARS = (2000, 2012, 2024)
FOCI_YEARS = range(2003, 2025)
WINDOWS = {"2001_2012": (2001, 2012), "2013_2024": (2013, 2024)}
DETER_CLEARING = {"DESMATAMENTO_CR", "DESMATAMENTO_VEG", "MINERACAO"}
DETER_DEGRADATION = {"DEGRADACAO", "CICATRIZ_DE_QUEIMADA", "CS_DESORDENADO", "CS_GEOMETRICO"}


def out_dir(cfg) -> Path:
    path = regions.processed_dir(cfg) / "perturbacao"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _save(frame: pd.DataFrame, path: Path, **meta) -> Path:
    frame.columns = frame.columns.map(str)
    frame.to_parquet(path)
    path.with_suffix(".json").write_text(json.dumps({
        **meta, "rows": len(frame), "saved_utc": datetime.now(UTC).isoformat(),
        "sha256": sha256_file(path)}, ensure_ascii=False, indent=2, default=str))
    return path


def _done(path: Path) -> bool:
    record = path.with_suffix(".json")
    return path.exists() and record.exists() and (
        json.loads(record.read_text())["sha256"] == sha256_file(path))


# ── aquisição e agregação (explícitas; chamadas pelo CLI) ───────────────────


def fetch_mapbiomas(cfg, cells, report=print):
    jobs = [("cobertura", y) for y in COVER_YEARS] + [
        (p, y) for p in ("frequencia_fogo", "ultimo_fogo") for y in FIRE_YEARS]
    for product, year in jobs:
        target = out_dir(cfg) / f"mapbiomas_{product}_{year}.parquet"
        if _done(target):
            continue
        source = mapbiomas.url(product, year)
        report(f"MapBiomas {product} {year}")
        table = class_areas(source, cells)
        _save(table, target, source=source, collection=mapbiomas.COLLECTIONS[product],
              unit="km² por valor do raster")


def fetch_terrabrasilis(cfg, cells, report=print):
    bounds = tuple(cells.total_bounds)
    raw = Path("data/raw") / cfg["experiment_id"] / "terrabrasilis"
    for name, by in [("prodes_anual", "year"), ("prodes_acumulado_2007", None),
                     ("prodes_nao_floresta", None), ("deter", "classe_ano")]:
        target = out_dir(cfg) / f"{name}.parquet"
        if _done(target):
            continue
        path = terrabrasilis.download_layer(name, bounds, raw, report=report)
        polygons = gpd.read_parquet(path)
        if name == "deter":
            polygons["classe_ano"] = (polygons.classname.astype(str) + "|"
                                      + pd.to_datetime(polygons.view_date).dt.year.astype(str))
        report(f"{name}: interseção de {len(polygons)} polígonos com as células")
        _save(polygon_areas(polygons, cells, by=by), target, source=str(path), unit="km²")


def fetch_foci(cfg, cells, report=print):
    target = out_dir(cfg) / "focos_mensais.parquet"
    if _done(target):
        return
    bounds = tuple(cells.total_bounds)
    frames = []
    for year in FOCI_YEARS:
        points = queimadas.read_year(queimadas.fetch_year(year), bounds)
        points["mes"] = points.data_pas.dt.to_period("M").astype(str)
        frames.append(point_counts(points, cells, by="mes"))
        report(f"BDQueimadas {year}: {len(points)} focos na caixa")
    table = pd.concat(frames, axis=1).fillna(0).astype(int)
    _save(table, target, source=queimadas.URL, unit="focos por célula e mês")


def fetch_all(cfg, sources=("mapbiomas", "terrabrasilis", "queimadas"), report=print):
    cells = regions.cells(cfg)[["cell_id", "latitude", "longitude", "weight_km2", "geometry"]]
    if "mapbiomas" in sources:
        fetch_mapbiomas(cfg, cells, report)
    if "terrabrasilis" in sources:
        fetch_terrabrasilis(cfg, cells, report)
    if "queimadas" in sources:
        fetch_foci(cfg, cells, report)


# ── métricas (só arquivos locais) ───────────────────────────────────────────


def _read(cfg, name) -> pd.DataFrame:
    path = out_dir(cfg) / f"{name}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path}: rode `amazon-chaos disturbance fetch {cfg['slug']}`")
    return pd.read_parquet(path)


def _columns(frame, values):
    return frame[[c for c in map(str, values) if c in frame.columns]].sum(axis=1)


def cover_metrics(cfg) -> pd.DataFrame:
    out = {}
    for year in COVER_YEARS:
        t = _read(cfg, f"mapbiomas_cobertura_{year}")
        total = t.sum(axis=1)
        land = total - _columns(t, mapbiomas.WATER) - _columns(t, mapbiomas.NOT_OBSERVED)
        out[f"terra_km2_{year}"] = land
        out[f"agua_frac_{year}"] = _columns(t, mapbiomas.WATER) / total
        out[f"floresta_frac_{year}"] = _columns(t, mapbiomas.FOREST) / land
        out[f"agro_frac_{year}"] = _columns(t, mapbiomas.AGRO) / land
    frame = pd.DataFrame(out)
    frame["mb_perda_floresta_2001_2012"] = frame.floresta_frac_2000 - frame.floresta_frac_2012
    frame["mb_perda_floresta_2013_2024"] = frame.floresta_frac_2012 - frame.floresta_frac_2024
    return frame


def prodes_metrics(cfg, land: pd.Series) -> pd.DataFrame:
    yearly = _read(cfg, "prodes_anual")
    yearly.columns = yearly.columns.astype(int)
    acc = _read(cfg, "prodes_acumulado_2007")["km2"]
    no_forest = _read(cfg, "prodes_nao_floresta")["km2"]

    def span(first, last):
        return yearly[[y for y in yearly.columns if first <= y <= last]].sum(axis=1) / land

    return pd.DataFrame({
        "prodes_ate_2007_frac": acc / land,  # bloco agregado 1988–2007, não repartido
        "prodes_2008_2012_frac": span(2008, 2012),
        "prodes_2013_2024_frac": span(2013, 2024),
        "prodes_acumulado_2024_frac": (acc + span(2008, 2024) * land) / land,
        "prodes_nao_floresta_frac": no_forest / land,
    })


def deter_metrics(cfg, land: pd.Series) -> pd.DataFrame:
    t = _read(cfg, "deter")
    keys = pd.Series(t.columns).str.split("|", expand=True)
    classes, years = keys[0].to_numpy(), keys[1].astype(int).to_numpy()
    keep = years <= 2024

    def area(group):
        cols = t.columns[keep & np.isin(classes, list(group))]
        return t[cols].sum(axis=1) / land

    return pd.DataFrame({"deter_corte_frac_2016_2024": area(DETER_CLEARING),
                         "deter_degradacao_frac_2016_2024": area(DETER_DEGRADATION)})


def foci_metrics(cfg, land: pd.Series) -> pd.DataFrame:
    t = _read(cfg, "focos_mensais")
    years = t.T.groupby(t.columns.str[:4].astype(int)).sum().T
    out = {}
    for name, (first, last) in {"2003_2012": (2003, 2012), "2013_2024": (2013, 2024)}.items():
        span = years[[y for y in years.columns if first <= y <= last]]
        out[f"focos_100km2_ano_{name}"] = 100 * span.sum(axis=1) / land / span.shape[1]
    out["anos_com_foco_2003_2024"] = (years > 0).sum(axis=1)
    last = years.apply(lambda row: row[row > 0].index.max() if (row > 0).any() else np.nan,
                       axis=1)
    out["ultimo_foco_ano"] = last
    out["ultimo_foco_censurado"] = last.isna()  # sem foco observado desde 2003
    return pd.DataFrame(out)


def fire_metrics(cfg, land: pd.Series) -> pd.DataFrame:
    out = {}
    for year in FIRE_YEARS:
        freq = _read(cfg, f"mapbiomas_frequencia_fogo_{year}")
        values = freq.columns.astype(int)
        burned = freq[freq.columns[values > 0]].sum(axis=1)
        out[f"mb_queimada_alguma_vez_frac_{year}"] = burned / land
        out[f"mb_frequencia_fogo_media_{year}"] = (freq * values).sum(axis=1) / land
    last = _read(cfg, "mapbiomas_ultimo_fogo_2024")
    years = last.columns.astype(int)
    burned = last[last.columns[years > 0]]
    since = (2024 - years[years > 0]).to_numpy()
    out["mb_anos_desde_ultimo_fogo_2024"] = (burned * since).sum(axis=1) / burned.sum(axis=1)
    return pd.DataFrame(out)


def build(cfg) -> pd.DataFrame:
    """Tabela final: uma linha por célula, com as métricas e a fonte de cada uma no nome."""
    cells = regions.cells(cfg).set_index("cell_id")
    cover = cover_metrics(cfg)
    land = cover["terra_km2_2000"]
    parts = [cells[["latitude", "longitude", "weight_km2"]].rename(
        columns={"weight_km2": "celula_km2"}), cover]
    for func in (prodes_metrics, deter_metrics, foci_metrics, fire_metrics):
        try:
            parts.append(func(cfg, land))
        except FileNotFoundError:
            continue
    table = pd.concat(parts, axis=1)
    table.index.name = "cell_id"
    return table
