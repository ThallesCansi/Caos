"""CLI do piloto: plano offline, mapa explícito, aquisição e processamento separados."""

import json
from pathlib import Path

import typer

from amazon_chaos.config import load_config
from amazon_chaos.io.era5_edh import compare_with_cds, download_edh, open_edh
from amazon_chaos.io.era5_monthly import (
    cached_files,
    download_plan,
    job_directory,
    plan_edh_requests,
    plan_requests,
    process_period,
)
from amazon_chaos.notify import reporter
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


@app.command("edh-download")
def edh_download(
    start: str,
    end: str,
    config: Path = DEFAULT,
    workers: int = 16,
    verify: bool = True,
    telegram: bool = True,
):
    """Baixa do Earth Data Hub; antes, confere contra os meses CDS já validados."""
    cfg = load_config(config)
    report = reporter(telegram)
    region = cfg.get("region_name", cfg["experiment_id"])
    jobs = plan_edh_requests(cfg, start, end)
    saved = sum(cached_files(job_directory(cfg, j), j) is not None for j in jobs)
    report(
        f"🛰️ ERA5 · {region}\n"
        f"🗓️ {start} → {end} · {len(jobs)} meses ({saved} já salvos)\n"
        "Fonte: Earth Data Hub. Aviso a cada ano concluído. ☕"
    )

    def opener():
        return open_edh(concurrency=workers)

    if verify:
        planned = {j["month"] for j in jobs}
        cds = Path("data/raw") / cfg["experiment_id"] / "era5"
        months = {
            json.loads(m.read_text())["job"]["month"] for m in cds.glob("*/manifest.json")
        } & planned
        if not months:
            report(
                f"❌ {region}: nenhum mês CDS em {cds} para conferir o Earth Data Hub.\n"
                "Copie os meses já baixados ou rode com --no-verify."
            )
            raise typer.Exit(1)
        download_edh(cfg, start, end, open_dataset=opener, years={m[:4] for m in months},
                     report=report)
        stats = compare_with_cds(cfg)
        lines = [
            f"{'✅' if r['ok'] else '❌'} {name}: {100 * r['identical'] / r['values']:.2f}% "
            f"idênticos · dif. máx. {r['max_abs_diff']:.3g}"
            for name, r in stats.items()
        ]
        compared = sorted(set().union(*(r["months"] for r in stats.values())))
        if not stats or not all(r["ok"] for r in stats.values()):
            report(f"❌ {region}: Earth Data Hub difere do CDS; download interrompido.\n"
                   + "\n".join(lines))
            raise typer.Exit(1)
        report(f"🔬 Conferência com o CDS ({len(compared)} meses): tudo certo!\n"
               + "\n".join(lines) + "\nSeguindo para o período completo. 🚀")
    download_edh(cfg, start, end, open_dataset=opener, report=report)
    files = [cached_files(job_directory(cfg, j), j) for j in jobs]
    if any(f is None for f in files):
        raise RuntimeError("Há meses sem manifesto validado após o download")
    size = sum(f.stat().st_size for group in files for f in group) / 2**30
    report(
        f"🎉 Download concluído · {region}\n"
        f"✅ {len(jobs)} meses, todas as horas e células conferidas, sem valores ausentes\n"
        f"💾 {size:.2f} GiB em data/raw/{cfg['experiment_id']}/edh"
    )


@app.command("process")
def process(start: str, end: str, config: Path = DEFAULT, source: str = "cds"):
    """Valida dados locais e grava derivados diários; não acessa rede."""
    print(process_period(load_config(config), start, end, source=source))


if __name__ == "__main__":
    app()
