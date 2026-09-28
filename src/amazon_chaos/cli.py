from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import typer

from amazon_chaos.config import load_config
from amazon_chaos.io.era5 import download_pilot as download_era5_pilot
from amazon_chaos.io.terrabrasilis import download_deter_pilot
from amazon_chaos.paths import ensure_data_dirs
from amazon_chaos.provenance import build_manifest

app = typer.Typer(no_args_is_help=True, help="TCC Amazônia + dinâmica não linear")


@app.command("init-dirs")
def init_dirs() -> None:
    paths = ensure_data_dirs()
    for name, path in paths.items():
        typer.echo(f"{name}: {path}")


@app.command("pilot")
def pilot(config: Path = typer.Option(Path("configs/pilot.yaml"), exists=True)) -> None:
    cfg = load_config(config)
    paths = ensure_data_dirs()
    experiment_id = cfg["experiment_id"]
    out = paths["raw"] / experiment_id
    out.mkdir(parents=True, exist_ok=True)

    typer.echo("Downloading ERA5 instant/accum groups...")
    instant, accum = download_era5_pilot(cfg, out / "era5")
    typer.echo(f"ERA5 instant: {[str(p) for p in instant]}")
    typer.echo(f"ERA5 accum: {[str(p) for p in accum]}")

    typer.echo("Downloading DETER as GeoJSON...")
    deter = download_deter_pilot(cfg, out / "terrabrasilis" / "deter.geojson")
    gdf = gpd.read_file(deter)
    typer.echo(f"DETER features downloaded: {len(gdf)}")


@app.command("manifest")
def manifest(
    directory: Path = typer.Argument(..., exists=True, file_okay=False),
    output: Path = typer.Option(Path("metadata/manifests/files.csv")),
) -> None:
    df = build_manifest(directory)
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)
    typer.echo(f"Wrote {len(df)} rows to {output}")


if __name__ == "__main__":
    app()
