import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium", app_title="02 · Regiões de estudo")

with app.setup:
    import json
    from pathlib import Path

    import marimo as mo
    import pandas as pd

    from amazon_chaos import nb, regions
    from amazon_chaos.config import load_region
    from amazon_chaos.preprocess.grid import build_grid

    book = nb.notebook("02_regioes")
    SLUGS = ["xingu", "tapajos"]


@app.cell(hide_code=True)
def _():
    nb.header(
        "02 · Regiões de estudo",
        "Onde estão as duas bacias, quantas células ERA5 cada uma tem e o que já foi baixado?",
        stage="F1 · recortes (gate: mapa e grade aprovados antes de qualquer download)",
        inputs=["`configs/regions/<slug>.yaml`", "`data/external/<slug>/` (limite e contexto)",
                "`data/processed/<experimento>/basin_grid.geojson`"],
        outputs=["`reports/figures/02_regioes/<slug>/mapa.{png,pdf}`",
                 "`reports/tables/02_regioes/comparacao.{csv,tex}`"],
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Por que bacias hidrográficas

    A unidade de análise é a **célula ERA5 de 0,25°** (D-005). As regiões só delimitam
    quais células entram e quanto pesa cada uma: a área efetiva dentro do limite. Usamos
    bacias inteiras da BHB250 (IBGE/ANA, nível 3) porque são unidades físicas do ciclo da
    água e porque Xingu e Tapajós, vizinhas e de tamanho parecido, cobrem o mesmo gradiente:
    cabeceiras desmatadas no Cerrado de Mato Grosso, florestas protegidas no médio curso e
    a foz no Pará (D-006, D-009).

    Nenhum dado climático é baixado aqui. Se algo faltar, o caderno mostra o comando que o
    produz.
    """)
    return


@app.function
def load(slug):
    """Limite, células, contexto e situação dos dados de uma região (só arquivos locais)."""
    cfg = load_region(slug)
    grid_path = regions.processed_dir(cfg) / "basin_grid.geojson"
    needed = [Path(cfg["spatial"]["basin_source"]), grid_path]
    if any(not p.exists() for p in needed):
        return {"cfg": cfg, "missing": [p for p in needed if not p.exists()]}
    limit = regions.boundary(cfg)
    cells = regions.cells(cfg)
    context = regions.load_context(cfg)
    exp = cfg["experiment_id"]
    years = range(1990, 2025)
    daily = [regions.processed_dir(cfg) / f"daily_{y}-01-01_{y}-12-31.nc" for y in years]
    edh = list(Path("data/raw", exp, "edh").glob("*/manifest.json"))
    biomes = regions.biome_shares(limit, context)
    protected = regions.protected_share(limit, context)
    return {
        "cfg": cfg, "limit": limit, "cells": cells, "context": context, "missing": [],
        "daily": sum(p.exists() for p in daily), "months": len(edh),
        "summary": (regions.processed_dir(cfg) / "summary_1990_2024.nc").exists(),
        "biomes": biomes / biomes.sum() if len(biomes) else biomes,
        "protected": protected,
        "record": json.loads(Path(cfg["spatial"]["basin_source"]).parent
                             .joinpath("source.json").read_text()),
    }


@app.function
def summary_row(d):
    cfg, cells = d["cfg"], d["cells"]
    return {
        "Região": cfg["name"],
        "cod_otto": cfg["boundary"].get("cod_otto", "—"),
        "Área (mil km²)": round(d["record"]["source_area_km2"] / 1e3, 1),
        "Células ERA5": len(cells),
        "Pontos pedidos ao ERA5": len(build_grid(cfg["spatial"]["area"])),
        "Latitudes": f"{cells.latitude.min():.2f}° a {cells.latitude.max():.2f}°",
        "Amazônia (%)": round(100 * d["biomes"].get("Amazônia", 0)),
        "Cerrado (%)": round(100 * d["biomes"].get("Cerrado", 0)),
        "TIs ou UCs (%)": round(100 * d["protected"].get("tis_ou_ucs", float("nan"))),
        "Meses EDH baixados": f"{d['months']}/421",
        "Anos diários": f"{d['daily']}/35",
    }


@app.cell
def _():
    data = {slug: load(slug) for slug in SLUGS}
    return (data,)


@app.cell(hide_code=True)
def _(data):
    mo.stop(any(d["missing"] for d in data.values()), mo.vstack([
        nb.missing(d["missing"], f"uv run amazon-chaos region prepare {slug}")
        for slug, d in data.items() if d["missing"]
    ]))
    comparison = pd.DataFrame([summary_row(_d) for _d in data.values()])
    nb.stats({"Células nas duas bacias": int(comparison["Células ERA5"].sum()),
              "Área total (mil km²)": f"{comparison['Área (mil km²)'].sum():.0f}",
              "Anos diários prontos": " · ".join(comparison["Anos diários"])})
    return (comparison,)


@app.cell(hide_code=True)
def _(comparison):
    book.table(
        comparison, "comparacao",
        "Xingu e Tapajós: limite BHB250, grade ERA5, biomas (IBGE), TIs (FUNAI) e UCs federais "
        "(ICMBio), sem dupla contagem, e situação dos dados climáticos locais.",
        selection=None,
    )
    return


@app.function
def region_panel(slug, d):
    cfg = d["cfg"]
    fig = regions.plot_region(cfg, d["limit"], d["cells"], d["context"])
    shown = book.figure(
        fig, "mapa",
        f"{cfg['name']}: limite BHB250 (IBGE/ANA, 2021), {len(d['cells'])} células ERA5 de "
        "0,25° com interseção, biomas, Terras Indígenas, UCs federais, rios e cidades. "
        "Limites atuais, para contexto: não medem cobertura florestal nem sua história.",
        region=slug,
    )
    status = []
    if d["months"] < 421:
        status.append(nb.caveat(
            f"**ERA5 ainda não baixado** ({d['months']} de 421 meses). No HPC:\n\n"
            f"```bash\nsbatch --export=ALL,REGION={slug} scripts/hpc/era5.sbatch\n```", "warn"))
    elif d["daily"] < 35:
        status.append(nb.caveat(f"Brutos completos; faltam séries diárias ({d['daily']}/35).",
                                "warn"))
    else:
        status.append(nb.caveat("ERA5 1990–2024 completo: brutos e séries diárias.", "success"))
    cells = (d["cells"].drop(columns="geometry")
             .assign(area_km2=lambda t: t.area_km2.round(1),
                     weight_km2=lambda t: t.weight_km2.round(1)))
    return mo.vstack([*status, shown,
                      mo.accordion({f"As {len(cells)} células": mo.ui.table(
                          cells, selection=None, page_size=10)})])


@app.cell(hide_code=True)
def _(data):
    mo.vstack([
        mo.md("## As bacias no mapa"),
        mo.ui.tabs({data[s]["cfg"]["name"]: region_panel(s, data[s]) for s in SLUGS}),
    ])
    return


@app.cell(hide_code=True)
def _():
    nb.caveat(
        "**A caixa antiga do Baixo Tapajós** (56 pontos, `configs/regions/tapajos_caixa.yaml`) "
        "fica como plano B e como registro da execução `full_e57802a1f7` das substitutas. "
        "Ela tinha muita água (rios Tapajós e Amazonas) e pouco contraste de perturbação, por "
        "isso foi substituída pela bacia inteira (D-009).", "neutral")
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Como acrescentar uma região

    1. Copie `configs/regions/_modelo.yaml` para `configs/regions/<slug>.yaml` e preencha o
       limite (BHB250 ou caixa) e a célula de demonstração.
    2. `uv run amazon-chaos region prepare <slug>`: baixa o limite e a cartografia, confere a
       caixa ERA5 e grava a grade. Este caderno passa a mostrar a região.
    3. No HPC: `sbatch --export=ALL,REGION=<slug> scripts/hpc/era5.sbatch`.
    4. Localmente: `make pull REGION=<slug>`.

    Detalhes em `docs/hpc.md`.
    """)
    return


@app.cell(hide_code=True)
def _(data):
    nb.provenance(files=[p for d in data.values() if not d["missing"]
                         for p in (d["cfg"]["spatial"]["basin_source"],
                                   regions.processed_dir(d["cfg"]) / "basin_grid.geojson")])
    return


if __name__ == "__main__":
    app.run()
