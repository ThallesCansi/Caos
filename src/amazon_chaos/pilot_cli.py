"""CLI do piloto: plano offline, mapa explícito, aquisição e processamento separados."""

import json
from pathlib import Path

import typer

from amazon_chaos.config import load_config
from amazon_chaos.io.era5_monthly import download_plan, plan_requests, process_period
from amazon_chaos.pilot_maps import prepare_map

app = typer.Typer(no_args_is_help=True)
DEFAULT = Path("configs/tapajos_2024.yaml")


@app.command("plan")
def plan(start: str, end: str, config: Path = DEFAULT):
    """Lista requisições, incluindo apoio UTC, sem rede ou credencial."""
    jobs = plan_requests(load_config(config), start, end)
    print(json.dumps(jobs, indent=2))


@app.command("map")
def region_map(config: Path = DEFAULT, download_context: bool = False):
    """Gera mapa; --download-context busca explicitamente bases cartográficas."""
    print(prepare_map(load_config(config), download_context=download_context))


@app.command("download")
def download(start: str, end: str, config: Path = DEFAULT):
    """Baixa somente o período explícito e suas horas de apoio."""
    files = download_plan(load_config(config), start, end)
    print(f"{len(files)} NetCDF validados; {sum(p.stat().st_size for p in files) / 2**20:.3f} MiB")


@app.command("process")
def process(start: str, end: str, config: Path = DEFAULT):
    """Valida dados locais e grava derivados diários; não acessa rede."""
    print(process_period(load_config(config), start, end))


if __name__ == "__main__":
    app()
