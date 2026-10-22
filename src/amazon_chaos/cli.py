"""CLI `amazon-chaos`: toda aquisição e todo processamento pesado passam por aqui.

    amazon-chaos region list | prepare <região>
    amazon-chaos era5 plan | download | edh | process | summarize <região> ...
    amazon-chaos disturbance fetch | build <região>
    amazon-chaos descriptors run | basin | precip <região>
    amazon-chaos modis fetch | build <região>
    amazon-chaos chirps fetch | build <região>
    amazon-chaos gate run [--quick]
    amazon-chaos manifest <pasta>
    amazon-chaos notify "mensagem"

`<região>` é o slug de `configs/regions/<slug>.yaml` (ou o caminho de um YAML).
Os cadernos Marimo só leem o que estes comandos gravam.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from amazon_chaos.config import list_regions, load_region
from amazon_chaos.notify import reporter, telegram

app = typer.Typer(no_args_is_help=True, help="TCC Caos — floresta–atmosfera amazônica")
region_app = typer.Typer(no_args_is_help=True, help="Limites, grade ERA5 e contexto")
era5_app = typer.Typer(no_args_is_help=True, help="ERA5 horário → séries diárias")
app.add_typer(region_app, name="region")
disturbance_app = typer.Typer(no_args_is_help=True,
                              help="Perturbação por célula: PRODES, DETER, BDQueimadas, MapBiomas")
descriptors_app = typer.Typer(no_args_is_help=True,
                              help="Descritores pré-registrados por célula, com substitutas")
modis_app = typer.Typer(no_args_is_help=True, help="MODIS LST pelo AppEEARS (checagem D-011)")
chirps_app = typer.Typer(no_args_is_help=True, help="Chuva diária CHIRPS v3 sat (D-021)")
gate_app = typer.Typer(no_args_is_help=True, help="Gate F4: descritores em controles sintéticos")
app.add_typer(era5_app, name="era5")
app.add_typer(disturbance_app, name="disturbance")
app.add_typer(descriptors_app, name="descriptors")
app.add_typer(modis_app, name="modis")
app.add_typer(chirps_app, name="chirps")
app.add_typer(gate_app, name="gate")

Region = Annotated[str, typer.Argument(help="slug em configs/regions/ (ex.: xingu)")]
Start = Annotated[str, typer.Argument(help="primeiro dia, AAAA-MM-DD")]
End = Annotated[str, typer.Argument(help="último dia, AAAA-MM-DD")]


# ── região ──────────────────────────────────────────────────────────────────


@region_app.command("list")
def region_list() -> None:
    """Regiões configuradas."""
    for slug in list_regions():
        cfg = load_region(slug)
        typer.echo(f"{slug:16} {cfg['name']}  ({cfg['experiment_id']})")


@region_app.command("prepare")
def region_prepare(
    region: Region,
    context: Annotated[bool, typer.Option(help="baixar também a cartografia")] = True,
) -> None:
    """Baixa o limite, confere a caixa ERA5, grava a grade e a cartografia de contexto."""
    from amazon_chaos.regions import prepare

    summary = prepare(load_region(region), context=context)
    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))


# ── ERA5 ────────────────────────────────────────────────────────────────────


@era5_app.command("plan")
def era5_plan(region: Region, start: Start, end: End) -> None:
    """Lista as requisições mensais (com as horas UTC de apoio), sem rede."""
    from amazon_chaos.io.era5_monthly import plan_requests

    jobs = plan_requests(load_region(region), start, end)
    typer.echo(json.dumps(jobs, indent=2))


@era5_app.command("download")
def era5_download(region: Region, start: Start, end: End) -> None:
    """Baixa pelo CDS (fila lenta; prefira `edh`). Retoma do último mês validado."""
    from amazon_chaos.io.era5_monthly import download_plan

    files = download_plan(load_region(region), start, end)
    size = sum(p.stat().st_size for p in files) / 2**20
    typer.echo(f"{len(files)} NetCDF validados; {size:.3f} MiB")


@era5_app.command("edh")
def era5_edh(
    region: Region,
    start: Start,
    end: End,
    workers: int = 16,
    verify: Annotated[bool, typer.Option(help="conferir contra meses CDS já baixados")] = True,
    notify: Annotated[bool, typer.Option(help="avisos no Telegram")] = True,
) -> None:
    """Baixa do Earth Data Hub; antes, confere contra os meses CDS já validados (D-007)."""
    from amazon_chaos.io.era5_edh import EDH_RTOL, compare_with_cds, download_edh, open_edh
    from amazon_chaos.io.era5_monthly import cached_files, job_directory, plan_edh_requests

    cfg = load_region(region)
    report = reporter(notify)
    name = cfg["region_name"]
    jobs = plan_edh_requests(cfg, start, end)
    saved = sum(cached_files(job_directory(cfg, j), j) is not None for j in jobs)
    report(
        f"🛰️ ERA5 · {name}\n"
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
                f"❌ {name}: nenhum mês CDS em {cds} para conferir o Earth Data Hub.\n"
                "Copie os meses já baixados ou rode com --no-verify."
            )
            raise typer.Exit(1)
        download_edh(cfg, start, end, open_dataset=opener, years={m[:4] for m in months},
                     report=report)
        stats = compare_with_cds(cfg)
        lines = [
            f"{'✅' if r['ok'] else '❌'} {var}: dif. máx. {r['max_abs_diff']:.3g} "
            f"(relativa {r['max_rel_diff']:.1e}; limite {EDH_RTOL:.1e}) · viés {r['bias']:+.1e}"
            for var, r in stats.items()
        ]
        compared = sorted(set().union(*(r["months"] for r in stats.values())))
        if not stats or not all(r["ok"] for r in stats.values()):
            report(f"❌ {name}: Earth Data Hub difere do CDS; download interrompido.\n"
                   + "\n".join(lines))
            raise typer.Exit(1)
        report(f"🔬 Conferência com o CDS ({len(compared)} meses): tudo certo!\n"
               + "\n".join(lines)
               + "\nDiferenças dentro da compressão conhecida do EDH (~10 bits)."
               + "\nSeguindo para o período completo. 🚀")
    download_edh(cfg, start, end, open_dataset=opener, report=report)
    files = [cached_files(job_directory(cfg, j), j) for j in jobs]
    if any(f is None for f in files):
        raise RuntimeError("Há meses sem manifesto validado após o download")
    size = sum(f.stat().st_size for group in files for f in group) / 2**30
    report(
        f"🎉 Download concluído · {name}\n"
        f"✅ {len(jobs)} meses, todas as horas e células conferidas, sem valores ausentes\n"
        f"💾 {size:.2f} GiB em data/raw/{cfg['experiment_id']}/edh"
    )


@era5_app.command("process")
def era5_process(
    region: Region,
    start: Start,
    end: End,
    source: Annotated[str, typer.Option(help="cds ou edh")] = "edh",
) -> None:
    """Valida os brutos locais e grava a série diária do período; não acessa a rede."""
    from amazon_chaos.io.era5_monthly import process_period

    typer.echo(process_period(load_region(region), start, end, source=source))


@era5_app.command("static")
def era5_static(region: Region) -> None:
    """Relevo do modelo e vegetação fixa do ERA5 na grade da região (Earth Data Hub)."""
    from amazon_chaos.io.era5_edh import static_fields
    from amazon_chaos.regions import processed_dir

    cfg = load_region(region)
    target = processed_dir(cfg) / "era5_estatico.nc"
    static_fields(cfg).to_netcdf(target)
    typer.echo(target)


@era5_app.command("summarize")
def era5_summarize(region: Region, first: int = 1990, last: int = 2024) -> None:
    """Resumo regional (série ponderada, mensais e extremos por célula) lido pelos cadernos."""
    from amazon_chaos.regional import summarize

    cfg = load_region(region)
    summarize(cfg, first, last, progress=lambda year: typer.echo(f"{year} ✓"))
    typer.echo(f"data/processed/{cfg['experiment_id']}/summary_{first}_{last}.nc")


# ── perturbação ─────────────────────────────────────────────────────────────


@disturbance_app.command("fetch")
def disturbance_fetch(
    region: Region,
    sources: Annotated[str, typer.Option(help="lista separada por vírgulas")] = (
        "mapbiomas,terrabrasilis,queimadas"),
) -> None:
    """Baixa as fontes e agrega por célula (retomável; tabelas já feitas são puladas)."""
    from amazon_chaos.features.disturbance import fetch_all

    fetch_all(load_region(region), tuple(sources.split(",")), report=typer.echo)


@disturbance_app.command("build")
def disturbance_build(region: Region) -> None:
    """Monta a tabela final por célula a partir das tabelas locais; não acessa a rede."""
    from amazon_chaos.features.disturbance import build, out_dir

    cfg = load_region(region)
    table = build(cfg)
    target = out_dir(cfg) / "celulas.parquet"
    table.to_parquet(target)
    typer.echo(f"{len(table)} células × {table.shape[1]} colunas em {target}")


# ── descritores por célula ──────────────────────────────────────────────────


@descriptors_app.command("run")
def descriptors_run(
    region: Region,
    workers: Annotated[int | None, typer.Option(help="processos; padrão: todos")] = None,
    block: Annotated[int, typer.Option(help="células por bloco gravado")] = 25,
    limit: Annotated[int | None, typer.Option(help="só as primeiras N células (teste)")] = None,
    notify: Annotated[bool, typer.Option(help="avisos no Telegram")] = True,
) -> None:
    """Lote retomável; exige o pré-registro congelado."""
    from amazon_chaos.nonlinear.batch import run
    from amazon_chaos.nonlinear.suite import load_spec

    target = run(load_region(region), load_spec(), workers=workers, block=block,
                 report=reporter(notify), limit=limit)
    typer.echo(target)


@descriptors_app.command("basin")
def descriptors_basin(
    region: Region,
    workers: Annotated[int | None, typer.Option(help="processos; padrão: um por teste")] = None,
    notify: Annotated[bool, typer.Option(help="avisos no Telegram")] = False,
) -> None:
    """Teste FT e IAAFT (199 substitutas) na série média da bacia (caderno 06, D-016)."""
    from amazon_chaos.nonlinear.basin_test import run
    from amazon_chaos.nonlinear.suite import load_spec

    typer.echo(run(load_region(region), load_spec(), workers=workers, report=reporter(notify)))


@descriptors_app.command("precip")
def descriptors_precip(
    region: Region,
    sources: Annotated[str, typer.Option(help="precip_era5,precip_chirps")] = (
        "precip_era5,precip_chirps"),
    workers: Annotated[int | None, typer.Option(help="processos; padrão: todos")] = None,
    limit: Annotated[int | None, typer.Option(help="só as primeiras N células (teste)")] = None,
    notify: Annotated[bool, typer.Option(help="avisos no Telegram")] = True,
) -> None:
    """Descritores ordinais da chuva no ERA5 e no CHIRPS, contra substitutas (D-021)."""
    from amazon_chaos.nonlinear.precip import run
    from amazon_chaos.nonlinear.suite import load_spec

    typer.echo(run(load_region(region), load_spec(), sources=tuple(sources.split(",")),
                   workers=workers, report=reporter(notify), limit=limit))


# ── MODIS ───────────────────────────────────────────────────────────────────


@modis_app.command("fetch")
def modis_fetch(
    region: Region,
    notify: Annotated[bool, typer.Option(help="avisos no Telegram")] = True,
) -> None:
    """Envia o pedido ao AppEEARS (ou retoma), espera o processamento e baixa os arquivos."""
    from amazon_chaos.io import appeears

    cfg, report = load_region(region), reporter(notify)
    token = appeears.login()
    task = appeears.submit(cfg, token)
    report(f"🛰️ MODIS LST · {cfg['name']}: pedido {task[:8]} no AppEEARS; aviso quando ficar "
           "pronto (o servidor pode levar horas)")
    appeears.wait(task, token, report=report)
    files = appeears.download(cfg, task, appeears.login(), report=typer.echo)
    report(f"✅ MODIS LST · {cfg['name']}: {len(files)} arquivos baixados")


@modis_app.command("build")
def modis_build(region: Region) -> None:
    """Climatologia do LST por célula e LST diurno da estação seca por ano."""
    from amazon_chaos.features.disturbance import out_dir
    from amazon_chaos.features.lst import cell_lst

    cfg = load_region(region)
    clim, dry = cell_lst(cfg)
    clim.to_parquet(out_dir(cfg) / "modis_lst.parquet")
    dry = dry.set_axis(dry.columns.map(str), axis=1)
    dry.to_parquet(out_dir(cfg) / "modis_lst_seca_anual.parquet")
    typer.echo(f"{len(clim)} células · {clim.lst_dia_c.notna().sum()} com LST")


# ── CHIRPS ──────────────────────────────────────────────────────────────────


@chirps_app.command("fetch")
def chirps_fetch(
    first: Annotated[int, typer.Option(help="primeiro ano")] = 2001,
    last: Annotated[int, typer.Option(help="último ano")] = 2024,
    notify: Annotated[bool, typer.Option(help="avisos no Telegram")] = True,
) -> None:
    """Baixa um ano por vez e recorta a caixa que cobre todas as regiões (retomável)."""
    import numpy as np

    from amazon_chaos.features.chirps import full_cells
    from amazon_chaos.io import chirps

    boxes = np.array([full_cells(load_region(s)).total_bounds for s in list_regions()])
    union = (*boxes[:, :2].min(axis=0), *boxes[:, 2:].max(axis=0))
    files = chirps.fetch(union, first, last, report=reporter(notify))
    typer.echo(f"{len(files)} anos em {chirps.ROOT}")


@chirps_app.command("build")
def chirps_build(region: Region) -> None:
    """Chuva diária do CHIRPS por célula (quadrado inteiro da célula ERA5)."""
    from amazon_chaos.features.chirps import cell_precip, out_path

    cfg = load_region(region)
    table = cell_precip(cfg)
    target = out_path(cfg)
    target.parent.mkdir(parents=True, exist_ok=True)
    table.to_parquet(target)
    typer.echo(f"{table.shape[0]} dias × {table.shape[1]} células em {target}")


# ── gate F4 ─────────────────────────────────────────────────────────────────


@gate_app.command("run")
def gate_run(
    workers: Annotated[int | None, typer.Option(help="processos; padrão: todos os núcleos")] = None,
    quick: Annotated[bool, typer.Option(help="versão mínima, só para testar o código")] = False,
    notify: Annotated[bool, typer.Option(help="avisos no Telegram")] = True,
) -> None:
    """Descritores pré-registrados × controles sintéticos, contra substitutas IAAFT."""
    from amazon_chaos.nonlinear.gate import run_gate
    from amazon_chaos.nonlinear.suite import load_spec

    report = reporter(notify)
    spec = load_spec()
    report(f"🧪 Gate F4 iniciado (pré-registro v{spec['version']}, {spec['status']})")
    out = run_gate(spec, workers=workers, quick=quick, progress=typer.echo)
    report(f"✅ Gate F4 concluído: {out}\nNa máquina local: make pull-gate")


# ── utilidades ──────────────────────────────────────────────────────────────


@app.command("manifest")
def manifest(
    directory: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
    output: Annotated[Path | None, typer.Option(help="padrão: <pasta>/manifest.csv")] = None,
) -> None:
    """Inventário com tamanho e SHA-256 de todos os arquivos de uma pasta."""
    from amazon_chaos.provenance import build_manifest

    output = output or directory / "manifest.csv"
    frame = build_manifest(directory)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)
    typer.echo(f"{len(frame)} arquivos em {output}")


@app.command("notify")
def notify(message: str) -> None:
    """Envia uma mensagem ao Telegram (TG_TOKEN e TG_CHAT_ID); nunca falha o job."""
    typer.echo("enviado" if telegram(message) else "Telegram não configurado ou indisponível")


if __name__ == "__main__":
    app()
