"""Cartografia explícita e mapas offline para revisão do recorte."""

import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
import requests
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

from amazon_chaos.preprocess.grid import build_grid
from amazon_chaos.provenance import sha256_file


def fetch_context(config, directory="data/external/tapajos"):
    """Chamado somente pela aquisição explícita; registra origem e hash dos recortes."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    n, w, s, e = config["spatial"]["area"]
    bounds = (w - 0.5, s - 0.5, e + 0.5, n + 0.5)
    sources = [
        (
            "municipio_1506807",
            "Santarém",
            "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/1506807",
            {"formato": "application/vnd.geo+json", "qualidade": "maxima", "periodo": 2022},
        ),
        (
            "municipio_1501451",
            "Belterra",
            "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/1501451",
            {"formato": "application/vnd.geo+json", "qualidade": "maxima", "periodo": 2022},
        ),
        (
            "municipio_1504752",
            "Mojuí dos Campos",
            "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/1504752",
            {"formato": "application/vnd.geo+json", "qualidade": "maxima", "periodo": 2022},
        ),
        (
            "rios",
            "Natural Earth 1:50m — contexto, não máscara de água",
            "https://naciscdn.org/naturalearth/50m/physical/ne_50m_rivers_lake_centerlines.zip",
            {},
        ),
        (
            "ucs",
            "ICMBio/INDE — limites consultados em 2026; contexto atual",
            "https://geoservicos.inde.gov.br/geoserver/ICMBio/ows",
            {
                "service": "WFS",
                "version": "1.0.0",
                "request": "GetFeature",
                "typeName": "ICMBio:limiteucsfederais_a",
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "bbox": ",".join(map(str, bounds)) + ",EPSG:4326",
                "maxFeatures": 100,
            },
        ),
    ]
    records = []
    for name, label, url, params in sources:
        target = directory / f"{name}.geojson"
        sidecar = directory / f"{name}.json"
        if target.exists() and sidecar.exists():
            record = json.loads(sidecar.read_text())
            if record.get("bounds") != list(bounds) or record["sha256"] != sha256_file(target):
                raise ValueError(f"Contexto incompatível/corrompido: {target}")
            records.append(record)
            continue
        print(f"Cartografia: {label}", flush=True)
        try:
            response = requests.get(url, params=params, timeout=60)
            response.raise_for_status()
            geo = gpd.read_file(io.BytesIO(response.content)).to_crs("EPSG:4326")
            if name == "ucs" and len(geo) >= 100:
                raise ValueError("Resposta UC pode estar truncada")
            if geo.empty:
                raise ValueError("Fonte retornou camada vazia")
            geo.geometry = geo.geometry.make_valid()
            geo = geo.cx[bounds[0] : bounds[2], bounds[1] : bounds[3]].copy()
            if name.startswith("municipio"):
                geo["nome"] = label
            if geo.empty:
                raise ValueError("Camada sem interseção com região")
            geo.to_file(target, driver="GeoJSON")
            record = {
                "name": name,
                "label": label,
                "url": response.url,
                "retrieved_utc": datetime.now(UTC).isoformat(),
                "bounds": list(bounds),
                "response_sha256": hashlib.sha256(response.content).hexdigest(),
                "sha256": sha256_file(target),
                "features": len(geo),
                "status": "ok",
            }
            sidecar.write_text(json.dumps(record, ensure_ascii=False, indent=2))
        except (requests.RequestException, ValueError) as error:
            record = {
                "name": name,
                "label": label,
                "status": "unavailable",
                "error": str(error),
                "url": url,
            }
            print(f"Camada indisponível: {label}: {error}", flush=True)
        records.append(record)
    (directory / "sources.json").write_text(json.dumps(records, ensure_ascii=False, indent=2))
    return records


def load_context(directory="data/external/tapajos"):
    directory = Path(directory)
    layers = {}
    for name in ["rios", "ucs"]:
        path = directory / f"{name}.geojson"
        if path.exists():
            layers[name] = gpd.read_file(path)
    municipal = [gpd.read_file(p) for p in directory.glob("municipio_*.geojson")]
    if municipal:
        layers["municipios"] = gpd.GeoDataFrame(pd.concat(municipal), crs=municipal[0].crs)
    return layers


def plot_region(config, context=None):
    context = load_context() if context is None else context
    grid = build_grid(config["spatial"]["area"])
    n, w, s, e = config["spatial"]["area"]
    states = gpd.read_file("data/external/ibge_estados_minima.geojson").to_crs("EPSG:4326")
    para = states[states.codarea.astype(str) == "15"]
    fig = plt.figure(figsize=(14, 8), layout="constrained")
    layout = fig.add_gridspec(2, 2, width_ratios=[1, 2.15])
    brazil = fig.add_subplot(layout[0, 0])
    state = fig.add_subplot(layout[1, 0])
    ax = fig.add_subplot(layout[:, 1])
    states.plot(ax=brazil, color="#ecece4", edgecolor="white", linewidth=0.5)
    para.plot(ax=brazil, color="#91b69a")
    brazil.plot((w + e) / 2, (n + s) / 2, "o", color="#b63034", ms=5)
    brazil.set_title("Brasil · localização no Pará", loc="left", fontsize=11)
    brazil.set_axis_off()
    para.plot(ax=state, color="#e6eee3", edgecolor="#687866")
    state.add_patch(Rectangle((w, s), e - w, n - s, fill=False, ec="#b63034", lw=2))
    state.set_title("Pará · recorte do Baixo Tapajós", loc="left", fontsize=11)
    state.set_axis_off()
    ax.set_facecolor("#f4f3eb")
    if "municipios" in context:
        context["municipios"].plot(ax=ax, facecolor="#e9eee1", edgecolor="#8e9284", lw=0.8)
        for _, row in context["municipios"].iterrows():
            point = row.geometry.representative_point()
            if w - 0.2 < point.x < e + 0.2 and s - 0.2 < point.y < n + 0.2:
                ax.text(
                    point.x,
                    point.y,
                    row["nome"],
                    fontsize=9,
                    color="#555d51",
                    ha="center",
                    bbox={"facecolor": "white", "alpha": 0.65, "edgecolor": "none"},
                )
    if "ucs" in context:
        context["ucs"].plot(ax=ax, facecolor="#a3caaa", edgecolor="#37744d", lw=0.9, alpha=0.65)
    if "rios" in context:
        context["rios"].plot(ax=ax, color="#3c90b5", linewidth=1.8)
    grid.boundary.plot(ax=ax, color="#5a6371", linewidth=0.65, alpha=0.65)
    ax.scatter(grid.longitude, grid.latitude, s=9, color="#425573", zorder=5)
    ax.add_patch(Rectangle((w, s), e - w, n - s, fill=False, ec="#b63034", lw=2.2, zorder=6))
    lat, lon = config["spatial"]["pilot_point"]
    ax.scatter(lon, lat, marker="*", s=190, color="#f2bd40", edgecolor="#292e35", zorder=7)
    ax.set(
        xlim=(w - 0.15, e + 0.15),
        ylim=(s - 0.15, n + 0.15),
        xlabel="Longitude (°)",
        ylabel="Latitude (°)",
    )
    ax.grid(False)
    ax.set_title(f"Baixo Tapajós · {len(grid)} pontos ERA5 · grade de 0,25°", loc="left", pad=14)
    handles = [
        Line2D([], [], color="#b63034", lw=2, label="Recorte do estudo"),
        Line2D([], [], marker=".", color="#425573", lw=0, label="Centros ERA5"),
        Line2D(
            [],
            [],
            marker="*",
            color="#f2bd40",
            markeredgecolor="#292e35",
            lw=0,
            ms=12,
            label="Célula de demonstração",
        ),
    ]
    if "rios" in context:
        handles.append(Line2D([], [], color="#3c90b5", label="Rios · contexto generalizado"))
    if "ucs" in context:
        handles.append(Patch(fc="#a3caaa", ec="#37744d", label="UCs federais · limites atuais"))
    ax.legend(handles=handles, loc="lower left", fontsize=8, framealpha=0.95)
    ax.annotate(
        "N",
        xy=(0.95, 0.95),
        xytext=(0.95, 0.87),
        xycoords="axes fraction",
        ha="center",
        arrowprops={"arrowstyle": "->", "color": "#333333"},
    )
    fig.suptitle("Região de estudo | Floresta–atmosfera", fontsize=17, x=0.04, ha="left")
    fig.supxlabel(
        "IBGE · ICMBio/INDE · Natural Earth | Limites de contexto não medem cobertura florestal",
        fontsize=9,
    )
    return fig, grid


def prepare_map(config, download_context=False):
    if download_context:
        fetch_context(config)
    fig, grid = plot_region(config)
    out = Path("reports/figures/tapajos_2024")
    out.mkdir(parents=True, exist_ok=True)
    for suffix in ["png", "pdf"]:
        fig.savefig(out / f"01_regiao_grade.{suffix}", dpi=180, bbox_inches="tight")
    spatial = Path("data/processed") / config["experiment_id"]
    spatial.mkdir(parents=True, exist_ok=True)
    grid.to_file(spatial / "grid.geojson", driver="GeoJSON")
    plt.close(fig)
    return out / "01_regiao_grade.png"
