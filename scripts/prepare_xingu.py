"""Extrai a bacia do Xingu da BHB250/IBGE e recorta a grade ERA5."""

import hashlib
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import requests

from amazon_chaos.config import load_config
from amazon_chaos.preprocess.grid import build_grid

SOURCE = (
    "https://geoftp.ibge.gov.br/informacoes_ambientais/estudos_ambientais/"
    "bacias_e_divisoes_hidrograficas_do_brasil/2021/"
    "Bacias_Hidrograficas_do_Brasil_BHB250/vetores/bacias_nivel_3.zip"
)
CONFIG = Path("configs/xingu_1990_2024.yaml")


def main():
    config = load_config(CONFIG)
    archive = Path("data/external/bacias_nivel_3_ibge_2021.zip")
    archive.parent.mkdir(parents=True, exist_ok=True)
    meta_path = Path("data/external/xingu/source.json")
    if archive.exists():
        recorded = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        retrieved_utc = recorded.get("retrieved_utc", "unknown: archive predates metadata")
    else:
        response = requests.get(SOURCE, timeout=120)
        response.raise_for_status()
        archive.write_bytes(response.content)
        retrieved_utc = datetime.now(UTC).isoformat()
    archive_sha256 = hashlib.sha256(archive.read_bytes()).hexdigest()
    if recorded := (json.loads(meta_path.read_text()) if meta_path.exists() else {}):
        if recorded["archive_sha256"] != archive_sha256:
            raise ValueError("Arquivo BHB250 difere do hash registrado")
    with zipfile.ZipFile(archive) as zf:
        shp = next(name for name in zf.namelist() if name.lower().endswith(".shp"))
    basins = gpd.read_file(f"zip://{archive}!{shp}")
    basin = basins[basins.cod_otto.astype(str) == "642"].to_crs("EPSG:4326")
    assert len(basin) == 1 and basin.iloc[0].nome_bacia == "Bacia do Rio Xingu"
    out = Path(config["spatial"]["basin_source"])
    out.parent.mkdir(parents=True, exist_ok=True)
    basin.to_file(out, driver="GeoJSON")
    grid = build_grid(config["spatial"]["area"])
    basin_equal = basin.to_crs("EPSG:6933").geometry.iloc[0]
    cells = grid.to_crs("EPSG:6933")
    cells["basin_km2"] = cells.geometry.intersection(basin_equal).area / 1e6
    cells["basin_fraction"] = cells.basin_km2 / cells.area_km2
    cells = cells[cells.basin_km2 > 0].to_crs("EPSG:4326")
    assert len(cells) > 0 and abs(cells.basin_km2.sum() - basin_equal.area / 1e6) < 5
    dest = Path("data/processed") / config["experiment_id"]
    dest.mkdir(parents=True, exist_ok=True)
    cells.to_file(dest / "basin_grid.geojson", driver="GeoJSON")
    fig, ax = plt.subplots(figsize=(8, 12), layout="constrained")
    basin.boundary.plot(ax=ax, color="#163f47", linewidth=1.4)
    cells.boundary.plot(ax=ax, color="#889e9e", linewidth=0.13)
    ax.set(title=f"Bacia do Rio Xingu · {len(cells)} células ERA5 com interseção",
           xlabel="Longitude (°)", ylabel="Latitude (°)", aspect="equal")
    images = Path("reports/figures/xingu_1990_2024")
    images.mkdir(parents=True, exist_ok=True)
    fig.savefig(images / "01_bacia_grade.png", dpi=170)
    fig.savefig(images / "01_bacia_grade.pdf")
    plt.close(fig)
    meta_path.write_text(json.dumps({
        "source": SOURCE, "retrieved_utc": retrieved_utc,
        "archive_sha256": archive_sha256,
        "cod_otto": "642", "name": "Bacia do Rio Xingu",
        "source_area_km2": float(basin.iloc[0].area_total),
        "selected_cells": len(cells), "grid_intersection_km2": float(cells.basin_km2.sum()),
    }, indent=2, ensure_ascii=False))
    print(f"{len(cells)} células; {cells.basin_km2.sum():.0f} km² na bacia")


if __name__ == "__main__":
    main()
