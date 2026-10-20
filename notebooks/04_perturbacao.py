import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium", app_title="04 · Perturbação por célula")

with app.setup:
    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    from scipy.stats import spearmanr

    from amazon_chaos import nb, regions
    from amazon_chaos.config import load_region
    from amazon_chaos.features.disturbance import out_dir
    from amazon_chaos.viz import COLORS, map_cells

    book = nb.notebook("04_perturbacao")
    MAPS = [
        ("floresta_frac_2000", "Floresta em 2000 (MapBiomas)", "Greens", (0, 1)),
        ("floresta_frac_2024", "Floresta em 2024 (MapBiomas)", "Greens", (0, 1)),
        ("prodes_acumulado_2024_frac", "Desmatamento acumulado até 2024 (PRODES)", "OrRd", (0, 1)),
        ("prodes_2013_2024_frac", "Desmatamento 2013–2024 (PRODES)", "OrRd", None),
        ("deter_degradacao_frac_2016_2024", "Degradação 2016–2024 (DETER)", "PuRd", None),
        ("focos_100km2_ano_2013_2024", "Focos por 100 km² por ano, 2013–2024", "YlOrRd", None),
        ("mb_frequencia_fogo_media_2024", "Anos com fogo 1985–2024 (MapBiomas)", "YlOrRd", None),
        ("agro_frac_2024", "Agropecuária em 2024 (MapBiomas)", "YlOrBr", (0, 1)),
    ]
    PAIRS = [
        ("prodes_acumulado_2024_frac", "floresta_frac_2024", "PRODES acumulado × floresta MapBiomas"),
        ("prodes_2013_2024_frac", "mb_perda_floresta_2013_2024", "PRODES × perda MapBiomas, 2013–2024"),
        ("focos_100km2_ano_2013_2024", "mb_frequencia_fogo_media_2024", "Focos × frequência de fogo"),
        ("deter_corte_frac_2016_2024", "prodes_2013_2024_frac", "DETER corte raso × PRODES"),
    ]


@app.cell(hide_code=True)
def _():
    nb.header(
        "04 · Perturbação por célula",
        "Quanto cada célula ERA5 foi desmatada, degradada e queimada, segundo fontes "
        "independentes, e quanto essas fontes concordam?",
        stage="F3 · perturbação (definida sem olhar a resposta climática)",
        inputs=["`data/processed/<exp>/perturbacao/` (gerado por `amazon-chaos disturbance "
                "fetch` e `build`)"],
        outputs=["`reports/figures/04_perturbacao/<slug>/`",
                 "`reports/tables/04_perturbacao/<slug>/`"],
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## As fontes e o que cada uma mede

    | Fonte | Mede | Período usado | Cuidados |
    |---|---|---|---|
    | **PRODES** (INPE) | corte raso da floresta primária | até 2007 (bloco), 2008–2024 anual | só floresta: a conversão de Cerrado não entra; ano agosto–julho |
    | **DETER** (INPE) | alertas de corte raso e de degradação | 2016–2024 | data de detecção ≠ data do evento; não é taxa oficial |
    | **BDQueimadas** (INPE) | focos de fogo ativo, satélite de referência | 2003–2024 | foco ≠ incêndio ≠ área queimada |
    | **MapBiomas** Cobertura col. 11 | fração de floresta, agropecuária e água | 1990, 2000, 2012, 2024 | mudança de classe ≠ desmatamento PRODES |
    | **MapBiomas** Fogo col. 5 | frequência e recência do fogo (30 m) | 1985–2024 | recorrência anual, não eventos dentro do ano |

    Frações usam a **área terrestre observada** de cada célula (MapBiomas, sem água) como
    denominador. Tudo foi agregado nos polígonos das células recortados pelo limite da bacia,
    com área geodésica exata (`preprocess.zonal`).
    """)
    return


@app.cell
def _():
    picker = nb.region_picker()
    picker
    return (picker,)


@app.cell
def _(picker):
    cfg = load_region(picker.value)
    slug = cfg["slug"]
    _path = out_dir(cfg) / "celulas.parquet"
    mo.stop(not _path.exists(), nb.missing(
        [_path], f"no HPC: sbatch --export=ALL,REGION={slug} scripts/hpc/disturbance.sbatch\n"
                 f"localmente: make pull REGION={slug}"))
    table = pd.read_parquet(_path)
    cells = regions.cells(cfg)
    limit = regions.boundary(cfg)
    rivers = regions.load_context(cfg).get("rios")
    land_share = table.terra_km2_2000 / table.celula_km2
    _w = table.terra_km2_2000
    nb.stats({
        "Células": len(table),
        "Floresta 2000 → 2024": f"{np.average(table.floresta_frac_2000, weights=_w):.0%} → "
                                f"{np.average(table.floresta_frac_2024, weights=_w):.0%}",
        "PRODES acumulado 2024": f"{np.average(table.prodes_acumulado_2024_frac, weights=_w):.0%}",
        "Focos por 100 km²·ano": f"{np.average(table.focos_100km2_ano_2013_2024, weights=_w):.1f}",
    }, caption=f"{cfg['name']} · médias ponderadas pela área terrestre")
    return cells, cfg, land_share, limit, rivers, slug, table


@app.function
def plot_maps(cells, table, limit, rivers, region):
    tall = (cells.total_bounds[3] - cells.total_bounds[1]) > 1.3 * (
        cells.total_bounds[2] - cells.total_bounds[0])
    fig, axes = plt.subplots(2, 4, figsize=(17, 12 if tall else 7.5), layout="constrained")
    indexed = cells.set_index("cell_id")
    for ax, (column, title, cmap, limits) in zip(axes.flat, MAPS, strict=True):
        if column not in table:
            ax.set_axis_off()
            ax.set_title(f"{title}\n(fonte ausente)")
            continue
        field = (table[column].to_frame("v").join(indexed[["latitude", "longitude"]])
                 .set_index(["latitude", "longitude"]).v.to_xarray())
        kw = {"vmin": limits[0], "vmax": limits[1]} if limits else {}
        map_cells(ax, cells, field, cmap, "", outline=limit, lines=rivers, **kw)
        ax.set_title(title, fontsize=10)
    fig.suptitle(f"Perturbação por célula ERA5 · {region}", fontsize=14, x=0.02, ha="left")
    return fig


@app.cell(hide_code=True)
def _(cells, cfg, limit, rivers, slug, table):
    mo.vstack([
        mo.md("## Onde está a perturbação"),
        book.figure(plot_maps(cells, table, limit, rivers, cfg["name"]), "mapas",
                    f"{cfg['name']}: floresta (MapBiomas, 2000 e 2024), desmatamento PRODES "
                    "acumulado e de 2013–2024, degradação DETER, densidade de focos "
                    "(BDQueimadas), frequência de fogo (MapBiomas) e agropecuária, por célula "
                    "ERA5. Frações sobre a área terrestre observada.", region=slug),
    ])
    return


@app.function
def plot_agreement(table):
    fig, axes = plt.subplots(1, 4, figsize=(17, 4.4), layout="constrained")
    rows = []
    for ax, (x, y, title) in zip(axes, PAIRS, strict=True):
        if x not in table or y not in table:
            ax.set_axis_off()
            continue
        ok = table[[x, y]].dropna()
        rho, p = spearmanr(ok[x], ok[y])
        ax.scatter(ok[x], ok[y], s=10, alpha=0.5, color=COLORS["ink"], lw=0)
        ax.set(xlabel=x, ylabel=y, title=nb.pt(f"{title}\nρ de Spearman = {rho:.2f}"))
        ax.xaxis.label.set_size(8)
        ax.yaxis.label.set_size(8)
        rows.append({"Par": title, "ρ de Spearman": round(rho, 3), "p (células não "
                     "independentes: indicativo)": p, "Células": len(ok)})
    return fig, pd.DataFrame(rows)


@app.cell(hide_code=True)
def _(cfg, slug, table):
    _fig, _rows = plot_agreement(table)
    mo.vstack([
        mo.md("## As fontes concordam?\n\nSe PRODES, DETER, BDQueimadas e MapBiomas medem a "
              "mesma paisagem, as métricas devem andar juntas entre as células, mesmo com "
              "métodos e definições diferentes. Concordância alta autoriza resumir a "
              "perturbação num índice; baixa pede que cada fonte seja analisada à parte."),
        book.figure(_fig, "concordancia",
                    f"{cfg['name']}: concordância entre fontes independentes de perturbação, "
                    "célula a célula (ρ de Spearman).", region=slug),
        book.table(_rows, "concordancia",
                   f"{cfg['name']}: correlação de postos entre métricas de fontes diferentes. "
                   "Células vizinhas não são independentes: o p é só indicativo.",
                   region=slug, selection=None),
    ])
    return


@app.function
def regional_series(cfg, table):
    folder = out_dir(cfg)
    foci = pd.read_parquet(folder / "focos_mensais.parquet")
    by_year = foci.sum().groupby(foci.columns.str[:4].astype(int)).sum()
    prodes = pd.read_parquet(folder / "prodes_anual.parquet").sum()
    prodes.index = prodes.index.astype(int)
    prodes = prodes[(prodes.index >= 2008) & (prodes.index <= 2024)]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 4.2), layout="constrained")
    ax1.bar(by_year.index, by_year.values, color=COLORS["t2m"], alpha=0.85)
    ax1.set(title="Focos de fogo ativo por ano (BDQueimadas, satélite de referência)",
            ylabel="focos na região")
    ax2.bar(prodes.index, prodes.values, color="#8f2d2a", alpha=0.85)
    ax2.set(title="Desmatamento anual PRODES (ano agosto–julho)", ylabel="km²")
    return fig


@app.cell(hide_code=True)
def _(cfg, slug, table):
    mo.vstack([
        mo.md("## No tempo"),
        book.figure(regional_series(cfg, table), "series_anuais",
                    f"{cfg['name']}: focos de fogo por ano (2003–2024) e desmatamento anual "
                    "PRODES (2008–2024) dentro da região.", region=slug),
        nb.caveat("Picos de focos acompanham secas (2005, 2010, 2015–16, 2023–24) e o "
                  "desmatamento recente: fogo e clima não são independentes. Por isso a "
                  "perturbação **antecedente** (estado em 2000, PRODES até 2007) é separada da "
                  "perturbação **durante** a janela de análise (docs/metodologia.md §7).",
                  "info"),
    ])
    return


@app.cell(hide_code=True)
def _(land_share, slug, table):
    _rule = 0.5
    _eligible = land_share >= _rule
    mo.vstack([
        mo.md(f"## Células elegíveis\n\nCélulas em que a terra observada ocupa menos de "
              f"**{_rule:.0%}** da área (rios largos, várzeas) têm frações instáveis: poucos km² "
              "de terra tornam qualquer mudança enorme. Proposta para o pré-registro: excluí-las "
              "da comparação (caderno 08), mantendo-as nos mapas."),
        nb.stats({"Elegíveis": int(_eligible.sum()), "Excluídas": int((~_eligible).sum()),
                  "Terra mediana": f"{land_share.median():.0%}"}),
        book.table(table.round(4).reset_index(), "celulas",
                   "Métricas de perturbação por célula (todas as fontes).", region=slug,
                   overleaf=False, selection=None),
    ])
    return


@app.cell(hide_code=True)
def _():
    nb.caveat("**MODIS LST (D-011): pendente.** A checagem do ERA5 com a temperatura de "
              "superfície observada por satélite precisa de uma conta gratuita no NASA "
              "Earthdata (`~/.netrc` no HPC). Ela entra neste caderno e no 08.", "warn")
    return


@app.cell(hide_code=True)
def _(cfg):
    nb.provenance(cfg, sorted(out_dir(cfg).glob("*.parquet")))
    return


if __name__ == "__main__":
    app.run()
