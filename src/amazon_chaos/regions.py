"""Regiões de estudo: limite, grade ERA5, cartografia de contexto e mapa de situação.

Tudo é lido de `configs/regions/<slug>.yaml` (via `config.load_region`); nada de região
fica fixo no código. A aquisição é explícita (`prepare`, chamado pelo CLI
`amazon-chaos region prepare`) e registra URL, data e SHA-256 de cada arquivo. As
funções de leitura e os mapas só usam arquivos locais.
"""

from __future__ import annotations

import io
import json
import ssl
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import certifi
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from shapely.geometry import box

from amazon_chaos.preprocess.grid import build_grid
from amazon_chaos.provenance import sha256_file

EQUAL_AREA = "EPSG:6933"
STATES_PATH = Path("data/external/ibge_estados_minima.geojson")
STATES_URL = "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
BHB250_URL = (
    "https://geoftp.ibge.gov.br/informacoes_ambientais/estudos_ambientais/"
    "bacias_e_divisoes_hidrograficas_do_brasil/2021/"
    "Bacias_Hidrograficas_do_Brasil_BHB250/vetores/bacias_nivel_{level}.zip"
)
BHB250_DIR = Path("data/external/bhb250")
MUNICIPIO_URL = "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/{code}"
NATURAL_EARTH = "https://naciscdn.org/naturalearth/10m/"  # CDN oficial; o GitHub é lento
BROWSER = {"User-Agent": "Mozilla/5.0 (amazon-chaos; TCC ILUM)"}  # a FUNAI recusa o padrão
WFS_LIMIT = 500
# Servidores que omitem o certificado intermediário. O intermediário vem do endereço AIA
# do próprio certificado e é somado às raízes do certifi: a cadeia ainda precisa fechar
# numa raiz confiável, então a verificação TLS continua completa.
MISSING_INTERMEDIATE = {
    "geoserver.funai.gov.br":
        "http://crt.sectigo.com/SectigoPublicServerAuthenticationCAOVR36.crt",
}


# ── caminhos ────────────────────────────────────────────────────────────────


def processed_dir(cfg) -> Path:
    return Path("data/processed") / cfg["experiment_id"]


def context_dir(cfg) -> Path:
    return Path(cfg["spatial"]["context_dir"])


def is_basin(cfg) -> bool:
    return cfg["boundary"]["source"] == "bhb250"


def _boundary_record_path(cfg) -> Path:
    return Path(cfg["spatial"]["basin_source"]).parent / "source.json"


# ── limite e grade ──────────────────────────────────────────────────────────


def boundary(cfg) -> gpd.GeoDataFrame:
    """Polígono da região (EPSG:4326), lido do disco; a caixa vem direto do YAML."""
    if is_basin(cfg):
        path = Path(cfg["spatial"]["basin_source"])
        if not path.exists():
            raise FileNotFoundError(
                f"Limite ausente: {path}. Rode `amazon-chaos region prepare {cfg['slug']}`."
            )
        return gpd.read_file(path).to_crs("EPSG:4326")
    north, west, south, east = cfg["spatial"]["area"]
    return gpd.GeoDataFrame({"nome": [cfg["name"]]}, geometry=[box(west, south, east, north)],
                            crs="EPSG:4326")


def envelope(geometry, step=0.25):
    """Caixa [N, W, S, E] alinhada à grade que contém todas as células tocadas pelo limite."""
    west, south, east, north = geometry.bounds
    snap = 1 / step
    return [float(np.ceil(north * snap) / snap), float(np.floor(west * snap) / snap),
            float(np.floor(south * snap) / snap), float(np.ceil(east * snap) / snap)]


def intersect_grid(cfg, limit) -> gpd.GeoDataFrame:
    """Células ERA5 com interseção positiva, com área efetiva (`basin_km2`) e fração."""
    grid = build_grid(cfg["spatial"]["area"], cfg["spatial"].get("grid_degrees", 0.25))
    shape = limit.to_crs(EQUAL_AREA).union_all()
    cells = grid.to_crs(EQUAL_AREA)
    cells["basin_km2"] = cells.geometry.intersection(shape).area / 1e6
    cells["basin_fraction"] = cells.basin_km2 / cells.area_km2
    cells = cells[cells.basin_km2 > 0].to_crs("EPSG:4326")
    if abs(cells.basin_km2.sum() - shape.area / 1e6) > 5:
        raise ValueError("A grade não cobre o limite inteiro; confira spatial.area")
    return cells


def cells(cfg) -> gpd.GeoDataFrame:
    """Células da região com peso em km² (`weight_km2`) e polígono recortado, para mapas."""
    grid = build_grid(cfg["spatial"]["area"], cfg["spatial"].get("grid_degrees", 0.25))
    if not is_basin(cfg):
        grid["weight_km2"] = grid.area_km2
        return grid
    saved = gpd.read_file(processed_dir(cfg) / "basin_grid.geojson")
    grid = grid.merge(saved[["latitude", "longitude", "basin_km2"]], on=["latitude", "longitude"])
    grid["weight_km2"] = grid.basin_km2
    grid["geometry"] = grid.geometry.intersection(boundary(cfg).union_all())
    return grid


# ── aquisição (explícita) ───────────────────────────────────────────────────


def _record(name, label, url, target, bounds=None, **extra):
    return {"name": name, "label": label, "url": url,
            "retrieved_utc": datetime.now(UTC).isoformat(),
            "bounds": None if bounds is None else list(bounds),
            "sha256": sha256_file(target), **extra, "status": "ok"}


def _download(url, target, **kwargs):
    response = requests.get(url, timeout=300, **kwargs)
    response.raise_for_status()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(response.content)
    return response


def fetch_states(path=STATES_PATH):
    """Malha estadual mínima do IBGE, usada nos mapas de situação."""
    path = Path(path)
    if path.exists():
        return path
    params = {"intrarregiao": "UF", "formato": "application/vnd.geo+json", "qualidade": "minima"}
    response = requests.get(STATES_URL, params=params, timeout=120)
    response.raise_for_status()
    states = gpd.read_file(io.BytesIO(response.content))
    path.parent.mkdir(parents=True, exist_ok=True)
    states.to_file(path, driver="GeoJSON")
    record = _record("estados", "IBGE — UFs, qualidade mínima", response.url, path,
                     features=len(states))
    path.with_suffix(".json").write_text(json.dumps(record, ensure_ascii=False, indent=2))
    return path


def fetch_boundary(cfg) -> gpd.GeoDataFrame:
    """Extrai a bacia da BHB250, confere nome e hash, e grava o limite com proveniência."""
    spec = cfg["boundary"]
    level, code = int(spec["level"]), str(spec["cod_otto"])
    url = BHB250_URL.format(level=level)
    archive = BHB250_DIR / f"bacias_nivel_{level}_ibge_2021.zip"
    record_path = _boundary_record_path(cfg)
    recorded = json.loads(record_path.read_text()) if record_path.exists() else {}
    if archive.exists():
        retrieved = recorded.get("retrieved_utc", "anterior ao registro")
    else:
        print(f"BHB250 nível {level}: {url}", flush=True)
        _download(url, archive)
        retrieved = datetime.now(UTC).isoformat()
    digest = sha256_file(archive)
    if recorded.get("archive_sha256") not in (None, digest):
        raise ValueError(f"{archive} difere do hash registrado em {record_path}")
    with zipfile.ZipFile(archive) as zf:
        shp = next(n for n in zf.namelist() if n.lower().endswith(".shp"))
    basins = gpd.read_file(f"zip://{archive}!{shp}")
    basin = basins[basins.cod_otto.astype(str) == code].to_crs("EPSG:4326")
    if len(basin) != 1:
        raise ValueError(f"BHB250 nível {level}: cod_otto {code} não encontrado (ou repetido)")
    name = basin.iloc[0].nome_bacia
    if spec.get("expected_name") and name != spec["expected_name"]:
        raise ValueError(f"cod_otto {code} é '{name}', não '{spec['expected_name']}'")
    target = Path(cfg["spatial"]["basin_source"])
    target.parent.mkdir(parents=True, exist_ok=True)
    basin.to_file(target, driver="GeoJSON")
    record_path.write_text(json.dumps({
        "source": url, "retrieved_utc": retrieved, "archive_sha256": digest,
        "level": level, "cod_otto": code, "name": name,
        "source_area_km2": float(basin.iloc[0].area_total),
    }, ensure_ascii=False, indent=2))
    return basin


def _verify(url):
    """Pacote de CAs para `requests`: o do certifi, com o intermediário ausente se preciso."""
    host = url.split("/")[2]
    if host not in MISSING_INTERMEDIATE:
        return True
    bundle = Path("data/cache/ca") / f"{host}.pem"
    if not bundle.exists():
        response = requests.get(MISSING_INTERMEDIATE[host], timeout=60)
        response.raise_for_status()
        intermediate = ssl.DER_cert_to_PEM_cert(response.content)
        bundle.parent.mkdir(parents=True, exist_ok=True)
        bundle.write_text(Path(certifi.where()).read_text() + "\n" + intermediate)
    return str(bundle)


def _layers(cfg, bounds):
    bbox = ",".join(map(str, bounds)) + ",EPSG:4326"
    wfs = {"service": "WFS", "version": "1.0.0", "request": "GetFeature",
           "outputFormat": "application/json", "srsName": "EPSG:4326", "bbox": bbox,
           "maxFeatures": WFS_LIMIT}
    catalog = {
        "rios": ("Natural Earth 1:10m — rios generalizados, contexto",
                 NATURAL_EARTH + "physical/ne_10m_rivers_lake_centerlines.zip", {}),
        "cidades": ("Natural Earth 1:10m — localidades",
                    NATURAL_EARTH + "cultural/ne_10m_populated_places_simple.zip", {}),
        "ucs": ("ICMBio/INDE — UCs federais, limites atuais",
                "https://geoservicos.inde.gov.br/geoserver/ICMBio/ows",
                {**wfs, "typeName": "ICMBio:limiteucsfederais_a"}),
        "tis": ("FUNAI — Terras Indígenas, limites atuais",
                "https://geoserver.funai.gov.br/geoserver/Funai/ows",
                {**wfs, "typeName": "Funai:tis_poligonais"}),
        "biomas": ("IBGE — Biomas 1:250.000 (2019)",
                   "https://geoftp.ibge.gov.br/informacoes_ambientais/estudos_ambientais/biomas/"
                   "vetores/Biomas_250mil.zip", {}),
    }
    layers = [(name, *catalog[name]) for name in cfg["context"]["layers"]]
    for code, label in cfg["context"].get("municipios", {}).items():
        layers.append((f"municipio_{code}", label, MUNICIPIO_URL.format(code=code),
                       {"formato": "application/vnd.geo+json", "qualidade": "maxima",
                        "periodo": 2022}))
    return layers


def _read_layer(content):
    if content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            shp = next(n for n in zf.namelist() if n.lower().endswith(".shp"))
        return gpd.read_file(io.BytesIO(content), layer=Path(shp).stem)
    return gpd.read_file(io.BytesIO(content))


def fetch_context(cfg, limit) -> list[dict]:
    """Baixa e recorta as camadas ao envelope do limite; reutiliza as já verificadas."""
    directory = context_dir(cfg)
    directory.mkdir(parents=True, exist_ok=True)
    margin = cfg["context"].get("margin_degrees", 0.75)
    w, s, e, n = limit.total_bounds
    bounds = tuple(round(v, 3) for v in (w - margin, s - margin, e + margin, n + margin))
    frame = box(*bounds)
    records = []
    for name, label, url, params in _layers(cfg, bounds):
        target, sidecar = directory / f"{name}.geojson", directory / f"{name}.json"
        if target.exists() and sidecar.exists():
            record = json.loads(sidecar.read_text())
            if record["bounds"] != list(bounds) or record["sha256"] != sha256_file(target):
                raise ValueError(f"Contexto incompatível ou alterado: {target}")
            records.append(record)
            continue
        print(f"Cartografia: {label}", flush=True)
        try:
            response = requests.get(url, params=params, headers=BROWSER, timeout=300,
                                    verify=_verify(url))
            response.raise_for_status()
            layer = _read_layer(response.content).to_crs("EPSG:4326")
            if params.get("maxFeatures") and len(layer) >= params["maxFeatures"]:
                raise ValueError("Resposta WFS pode estar truncada")
            layer.geometry = layer.geometry.make_valid()
            layer = layer[layer.intersects(frame)]
            if name == "biomas":
                layer = gpd.clip(layer, frame)
                layer.geometry = layer.geometry.simplify(0.005)
            if name.startswith("municipio_"):
                layer["nome"] = label
            if layer.empty:
                raise ValueError("Camada sem interseção com a região")
            layer.to_file(target, driver="GeoJSON")
            record = _record(name, label, response.url, target, bounds, features=len(layer))
            sidecar.write_text(json.dumps(record, ensure_ascii=False, indent=2))
        except (requests.RequestException, ValueError) as error:
            record = {"name": name, "label": label, "status": "unavailable",
                      "error": str(error), "url": url}
            print(f"Camada indisponível: {label}: {error}", flush=True)
        records.append(record)
    (directory / "sources.json").write_text(json.dumps(records, ensure_ascii=False, indent=2))
    return records


def prepare(cfg, context=True) -> dict:
    """Prepara uma região: limite, conferência da caixa ERA5, grade e contexto."""
    fetch_states()
    limit = fetch_boundary(cfg) if is_basin(cfg) else boundary(cfg)
    step = cfg["spatial"].get("grid_degrees", 0.25)
    expected = envelope(limit.union_all(), step)
    if is_basin(cfg) and [float(v) for v in cfg["spatial"]["area"]] != expected:
        raise ValueError(
            f"spatial.area de {cfg['slug']} deveria ser {expected} (envelope do limite "
            "alinhado à grade). Corrija o YAML antes de baixar o ERA5."
        )
    grid = intersect_grid(cfg, limit)
    lat, lon = cfg["spatial"]["pilot_point"]
    if not ((grid.latitude == lat) & (grid.longitude == lon)).any():
        raise ValueError(f"pilot_point {cfg['spatial']['pilot_point']} fora da região")
    out = processed_dir(cfg)
    out.mkdir(parents=True, exist_ok=True)
    if is_basin(cfg):
        grid.to_file(out / "basin_grid.geojson", driver="GeoJSON")
        record_path = _boundary_record_path(cfg)
        record = json.loads(record_path.read_text())
        record.update(selected_cells=len(grid),
                      grid_intersection_km2=float(grid.basin_km2.sum()))
        record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2))
    records = fetch_context(cfg, limit) if context else []
    return {
        "region": cfg["name"], "cells": len(grid), "area_km2": round(grid.basin_km2.sum()),
        "era5_points": len(build_grid(cfg["spatial"]["area"], step)),
        "context": {r["name"]: r["status"] for r in records},
    }


# ── leitura e mapas (só arquivos locais) ────────────────────────────────────


def load_context(cfg) -> dict[str, gpd.GeoDataFrame]:
    directory = context_dir(cfg)
    layers = {path.stem: gpd.read_file(path) for path in sorted(directory.glob("*.geojson"))
              if not path.stem.startswith("municipio_")}
    municipal = [gpd.read_file(p) for p in sorted(directory.glob("municipio_*.geojson"))]
    if municipal:
        layers["municipios"] = gpd.GeoDataFrame(pd.concat(municipal), crs=municipal[0].crs)
    return layers


def biome_shares(limit, context) -> pd.Series:
    """Área da região em cada bioma, em km²."""
    if "biomas" not in context:
        return pd.Series(dtype=float)
    biomes = context["biomas"].to_crs(EQUAL_AREA)
    name = biomes.columns[0]
    parts = gpd.overlay(biomes[[name, "geometry"]], limit[["geometry"]].to_crs(EQUAL_AREA),
                        how="intersection")
    return (parts.area / 1e6).groupby(parts[name]).sum().sort_values(ascending=False)


def protected_share(limit, context) -> dict[str, float]:
    """Fração da região em TIs, UCs federais e na união das duas (sem dupla contagem)."""
    shape = limit.to_crs(EQUAL_AREA).union_all()
    parts = {k: context[k].to_crs(EQUAL_AREA).union_all().intersection(shape)
             for k in ("tis", "ucs") if k in context}
    out = {k: v.area / shape.area for k, v in parts.items()}
    if len(parts) == 2:
        out["tis_ou_ucs"] = parts["tis"].union(parts["ucs"]).area / shape.area
    return out


BIOME_COLORS = {"Amazônia": "#dfeadb", "Cerrado": "#f1ead2"}
UF = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
      "21": "MA", "51": "MT", "52": "GO"}


def plot_region(cfg, limit=None, grid=None, context=None, states_path=STATES_PATH):
    """Brasil → estados → região, com biomas, áreas protegidas, rios, cidades e grade ERA5."""
    limit = boundary(cfg) if limit is None else limit
    grid = cells(cfg) if grid is None else grid
    context = load_context(cfg) if context is None else context
    basin = is_basin(cfg)
    states = gpd.read_file(states_path).to_crs("EPSG:4326")
    touched = states[states.intersects(limit.union_all())]
    w, s, e, n = limit.total_bounds
    pad = 0.35
    tall = (n - s) > 1.3 * (e - w)
    fig = plt.figure(figsize=(13, 11) if tall else (14, 8.5), layout="constrained")
    layout = fig.add_gridspec(2, 2, width_ratios=[1, 1.5 if tall else 2.1],
                              height_ratios=[1, 1.1])
    brazil, local, ax = (fig.add_subplot(layout[0, 0]), fig.add_subplot(layout[1, 0]),
                         fig.add_subplot(layout[:, 1]))

    states.plot(ax=brazil, color="#ecece4", edgecolor="white", linewidth=0.5, rasterized=True)
    touched.plot(ax=brazil, color="#c9d8c5", edgecolor="white", linewidth=0.5)
    limit.plot(ax=brazil, color="#b63034")
    brazil.set_title("Brasil · a região no território", loc="left", fontsize=11)
    brazil.set_axis_off()

    touched.plot(ax=local, color="#e6eee3", edgecolor="#687866", linewidth=0.9)
    limit.plot(ax=local, color="#b63034", alpha=0.18, edgecolor="#b63034", linewidth=1.6)
    for _, row in touched.iterrows():
        point = row.geometry.representative_point()
        local.text(point.x, point.y, UF.get(str(row.codarea), ""), fontsize=12,
                   color="#555d51", ha="center", weight="bold")
    local.set(aspect="equal")
    names = " e ".join(UF.get(str(c), str(c)) for c in touched.codarea)
    local.set_title(f"{names} · a região nos estados", loc="left", fontsize=11)
    local.set_axis_off()

    ax.set_facecolor("#f7f6f0")
    if "biomas" in context:
        for name, color in BIOME_COLORS.items():
            part = context["biomas"][context["biomas"].iloc[:, 0].astype(str).str.contains(name)]
            part.plot(ax=ax, color=color, edgecolor="none", rasterized=True)
    if "municipios" in context:
        context["municipios"].plot(ax=ax, facecolor="#e9eee1", edgecolor="#8e9284", lw=0.8,
                                      rasterized=True)
        for _, row in context["municipios"].iterrows():
            point = row.geometry.representative_point()
            if w - 0.2 < point.x < e + 0.2 and s - 0.2 < point.y < n + 0.2:
                ax.text(point.x, point.y, row["nome"], fontsize=9, color="#555d51",
                        ha="center", bbox={"facecolor": "white", "alpha": 0.65,
                                           "edgecolor": "none"})
    if "tis" in context:
        context["tis"].plot(ax=ax, facecolor="#e7c9a6", edgecolor="#a0673a", lw=0.5, alpha=0.7,
                            rasterized=True)
    if "ucs" in context:
        context["ucs"].plot(ax=ax, facecolor="#9fc7a6", edgecolor="#37744d", lw=0.6, alpha=0.7,
                            rasterized=True)
    grid.boundary.plot(ax=ax, color="#5a6371", linewidth=0.25 if basin else 0.6, alpha=0.5,
                       rasterized=True)
    if "rios" in context:
        context["rios"].plot(ax=ax, color="#3c90b5", linewidth=1.3)
    limit.boundary.plot(ax=ax, color="#b63034", linewidth=2.2, zorder=6)
    if "cidades" in context:
        towns = context["cidades"]
        near = limit.to_crs(EQUAL_AREA).buffer(30_000).to_crs("EPSG:4326").union_all()
        towns = towns[towns.within(near)]
        ax.scatter(towns.geometry.x, towns.geometry.y, s=14, color="#2b2f36", zorder=7)
        for _, row in towns.iterrows():
            ax.annotate(row["name"], (row.geometry.x, row.geometry.y), xytext=(4, 3),
                        textcoords="offset points", fontsize=8.5, color="#2b2f36", zorder=8,
                        bbox={"facecolor": "white", "alpha": 0.6, "edgecolor": "none", "pad": 1})
    lat, lon = cfg["spatial"]["pilot_point"]
    ax.scatter(lon, lat, marker="*", s=230, color="#f2bd40", edgecolor="#292e35", zorder=9)
    ax.set(xlim=(w - pad, e + pad), ylim=(s - pad, n + pad), aspect="equal",
           xlabel="Longitude (°)", ylabel="Latitude (°)")
    ax.grid(False)
    ax.set_title(f"{cfg['name']} · {len(grid)} células ERA5 de 0,25°", loc="left", pad=12)
    handles = [
        Line2D([], [], color="#b63034", lw=2.2,
               label="Limite da bacia (IBGE/ANA)" if basin else "Recorte do estudo"),
        Line2D([], [], color="#5a6371", lw=0.8, label="Células ERA5"),
        Line2D([], [], marker="*", color="#f2bd40", markeredgecolor="#292e35", lw=0, ms=13,
               label="Célula de demonstração"),
    ]
    if "rios" in context:
        handles.append(Line2D([], [], color="#3c90b5", lw=1.3, label="Rios · generalizados"))
    if "tis" in context:
        handles.append(Patch(fc="#e7c9a6", ec="#a0673a", label="Terras Indígenas · FUNAI"))
    if "ucs" in context:
        handles.append(Patch(fc="#9fc7a6", ec="#37744d", label="UCs federais · ICMBio"))
    if "biomas" in context:
        handles += [Patch(fc=c, ec="#bbbbbb", label=f"Bioma {b}") for b, c in BIOME_COLORS.items()]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8.5,
              framealpha=0.95, borderaxespad=0)
    ax.annotate("N", xy=(0.95, 0.97), xytext=(0.95, 0.91), xycoords="axes fraction",
                ha="center", arrowprops={"arrowstyle": "->", "color": "#333333"})
    fig.suptitle("Região de estudo | Floresta–atmosfera", fontsize=17, x=0.02, ha="left")
    fig.supxlabel("IBGE · ANA · FUNAI · ICMBio/INDE · Natural Earth | Limites atuais, "
                  "para contexto: não medem cobertura florestal nem sua história", fontsize=9)
    return fig
