"""Camadas cartográficas de contexto e o mapa "Onde estamos?" de uma bacia.

A aquisição é explícita (`fetch_basin_context`) e registra URL, data e SHA-256 de cada
camada, como em `pilot_maps.fetch_context`. Os mapas leem apenas arquivos locais.
"""

import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
import requests
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from shapely.geometry import box

from amazon_chaos.provenance import sha256_file

STATES_PATH = Path("data/external/ibge_estados_minima.geojson")
STATES_URL = "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
BROWSER = {"User-Agent": "Mozilla/5.0 (amazon-chaos; TCC ILUM)"}  # a FUNAI recusa o padrão


def _layers(bounds):
    bbox = ",".join(map(str, bounds)) + ",EPSG:4326"
    wfs = {"service": "WFS", "version": "1.0.0", "request": "GetFeature",
           "outputFormat": "application/json", "srsName": "EPSG:4326", "bbox": bbox,
           "maxFeatures": 500}
    natural_earth = "https://naciscdn.org/naturalearth/10m/"  # CDN oficial; o GitHub é lento
    return [
        ("rios", "Natural Earth 1:10m — rios generalizados, contexto",
         natural_earth + "physical/ne_10m_rivers_lake_centerlines.zip", {}),
        ("cidades", "Natural Earth 1:10m — localidades",
         natural_earth + "cultural/ne_10m_populated_places_simple.zip", {}),
        ("ucs", "ICMBio/INDE — UCs federais, limites atuais",
         "https://geoservicos.inde.gov.br/geoserver/ICMBio/ows",
         {**wfs, "typeName": "ICMBio:limiteucsfederais_a"}),
        ("tis", "FUNAI — Terras Indígenas, limites atuais",
         "https://geoserver.funai.gov.br/geoserver/Funai/ows",
         {**wfs, "typeName": "Funai:tis_poligonais"}),
        ("biomas", "IBGE — Biomas 1:250.000 (2019)",
         "https://geoftp.ibge.gov.br/informacoes_ambientais/estudos_ambientais/biomas/"
         "vetores/Biomas_250mil.zip", {}),
    ]


def _read(content):
    if content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            shp = next(n for n in zf.namelist() if n.lower().endswith(".shp"))
        return gpd.read_file(io.BytesIO(content), layer=Path(shp).stem)
    return gpd.read_file(io.BytesIO(content))


def _record(name, label, response, target, bounds, features):
    return {
        "name": name, "label": label, "url": response.url,
        "retrieved_utc": datetime.now(UTC).isoformat(),
        "bounds": None if bounds is None else list(bounds),
        "sha256": sha256_file(target), "features": features, "status": "ok",
    }


def fetch_states(path=STATES_PATH):
    """Malha estadual mínima do IBGE (edição vigente da API), usada nos mapas de situação."""
    path = Path(path)
    if path.exists():
        return path
    params = {"intrarregiao": "UF", "formato": "application/vnd.geo+json", "qualidade": "minima"}
    response = requests.get(STATES_URL, params=params, timeout=120)
    response.raise_for_status()
    states = gpd.read_file(io.BytesIO(response.content))
    path.parent.mkdir(parents=True, exist_ok=True)
    states.to_file(path, driver="GeoJSON")
    record = _record("estados", "IBGE — UFs, qualidade mínima", response, path, None, len(states))
    path.with_suffix(".json").write_text(json.dumps(record, ensure_ascii=False, indent=2))
    return path


def fetch_basin_context(basin, directory, margin=0.75):
    """Baixa e recorta as camadas ao envelope da bacia; reutiliza arquivos já verificados."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    w, s, e, n = basin.total_bounds
    bounds = tuple(round(v, 3) for v in (w - margin, s - margin, e + margin, n + margin))
    frame = box(*bounds)
    records = []
    for name, label, url, params in _layers(bounds):
        target, sidecar = directory / f"{name}.geojson", directory / f"{name}.json"
        if target.exists() and sidecar.exists():
            record = json.loads(sidecar.read_text())
            if record["bounds"] != list(bounds) or record["sha256"] != sha256_file(target):
                raise ValueError(f"Contexto incompatível ou alterado: {target}")
            records.append(record)
            continue
        print(f"Cartografia: {label}", flush=True)
        try:
            response = requests.get(url, params=params, headers=BROWSER, timeout=300)
            response.raise_for_status()
            layer = _read(response.content).to_crs("EPSG:4326")
            if params.get("maxFeatures") and len(layer) >= params["maxFeatures"]:
                raise ValueError("Resposta WFS pode estar truncada")
            layer.geometry = layer.geometry.make_valid()
            layer = layer[layer.intersects(frame)]
            if name == "biomas":
                layer = gpd.clip(layer, frame)
                layer.geometry = layer.geometry.simplify(0.005)
            if layer.empty:
                raise ValueError("Camada sem interseção com a região")
            layer.to_file(target, driver="GeoJSON")
            record = _record(name, label, response, target, bounds, len(layer))
            sidecar.write_text(json.dumps(record, ensure_ascii=False, indent=2))
        except (requests.RequestException, ValueError) as error:
            record = {"name": name, "label": label, "status": "unavailable",
                      "error": str(error), "url": url}
            print(f"Camada indisponível: {label}: {error}", flush=True)
        records.append(record)
    (directory / "sources.json").write_text(json.dumps(records, ensure_ascii=False, indent=2))
    return records


def load_basin_context(directory):
    directory = Path(directory)
    return {
        path.stem: gpd.read_file(path)
        for path in sorted(directory.glob("*.geojson"))
        if path.stem in {"rios", "cidades", "ucs", "tis", "biomas"}
    }


BIOME_COLORS = {"Amazônia": "#dfeadb", "Cerrado": "#f1ead2"}
UF = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
      "21": "MA", "51": "MT", "52": "GO"}


def plot_basin_region(config, basin, cells, context, title, states_path=STATES_PATH):
    """Brasil → estados → bacia, com biomas, áreas protegidas, rios, cidades e grade ERA5."""
    states = gpd.read_file(states_path).to_crs("EPSG:4326")
    touched = states[states.intersects(basin.union_all())]
    w, s, e, n = basin.total_bounds
    pad = 0.35
    fig = plt.figure(figsize=(13, 11), layout="constrained")
    layout = fig.add_gridspec(2, 2, width_ratios=[1, 1.5], height_ratios=[1, 1.1])
    brazil, local, ax = (fig.add_subplot(layout[0, 0]), fig.add_subplot(layout[1, 0]),
                         fig.add_subplot(layout[:, 1]))

    states.plot(ax=brazil, color="#ecece4", edgecolor="white", linewidth=0.5)
    touched.plot(ax=brazil, color="#c9d8c5", edgecolor="white", linewidth=0.5)
    basin.plot(ax=brazil, color="#b63034")
    brazil.set_title("Brasil · a bacia no território", loc="left", fontsize=11)
    brazil.set_axis_off()

    touched.plot(ax=local, color="#e6eee3", edgecolor="#687866", linewidth=0.9)
    basin.plot(ax=local, color="#b63034", alpha=0.18, edgecolor="#b63034", linewidth=1.6)
    for _, row in touched.iterrows():
        point = row.geometry.representative_point()
        local.text(point.x, point.y, UF.get(str(row.codarea), ""), fontsize=12,
                   color="#555d51", ha="center", weight="bold")
    local.set(aspect="equal")
    names = " e ".join(UF.get(str(c), str(c)) for c in touched.codarea)
    local.set_title(f"{names} · a bacia nos estados", loc="left", fontsize=11)
    local.set_axis_off()

    ax.set_facecolor("#f7f6f0")
    if "biomas" in context:
        for name, color in BIOME_COLORS.items():
            part = context["biomas"][context["biomas"].iloc[:, 0].astype(str).str.contains(name)]
            part.plot(ax=ax, color=color, edgecolor="none")
    if "tis" in context:
        context["tis"].plot(ax=ax, facecolor="#e7c9a6", edgecolor="#a0673a", lw=0.5, alpha=0.7)
    if "ucs" in context:
        context["ucs"].plot(ax=ax, facecolor="#9fc7a6", edgecolor="#37744d", lw=0.6, alpha=0.7)
    cells.boundary.plot(ax=ax, color="#5a6371", linewidth=0.25, alpha=0.5)
    if "rios" in context:
        context["rios"].plot(ax=ax, color="#3c90b5", linewidth=1.3)
    basin.boundary.plot(ax=ax, color="#b63034", linewidth=2.2, zorder=6)
    if "cidades" in context:
        towns = context["cidades"]
        towns = towns[towns.within(basin.buffer(0.3).union_all())]
        ax.scatter(towns.geometry.x, towns.geometry.y, s=14, color="#2b2f36", zorder=7)
        for _, row in towns.iterrows():
            ax.annotate(row["name"], (row.geometry.x, row.geometry.y), xytext=(4, 3),
                        textcoords="offset points", fontsize=8.5, color="#2b2f36", zorder=8,
                        bbox={"facecolor": "white", "alpha": 0.6, "edgecolor": "none", "pad": 1})
    lat, lon = config["spatial"]["pilot_point"]
    ax.scatter(lon, lat, marker="*", s=230, color="#f2bd40", edgecolor="#292e35", zorder=9)
    ax.set(xlim=(w - pad, e + pad), ylim=(s - pad, n + pad), aspect="equal",
           xlabel="Longitude (°)", ylabel="Latitude (°)")
    ax.grid(False)
    ax.set_title(f"{title} · {len(cells)} células ERA5 de 0,25°", loc="left", pad=12)
    handles = [
        Line2D([], [], color="#b63034", lw=2.2, label="Limite da bacia (IBGE/ANA)"),
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


def biome_shares(basin, context):
    """Área da bacia em cada bioma (km², projeção de área igual)."""
    if "biomas" not in context:
        return pd.Series(dtype=float)
    biomes = context["biomas"].to_crs("EPSG:6933")
    name = biomes.columns[0]
    parts = gpd.overlay(biomes[[name, "geometry"]], basin[["geometry"]].to_crs("EPSG:6933"),
                        how="intersection")
    return (parts.area / 1e6).groupby(parts[name]).sum().sort_values(ascending=False)
