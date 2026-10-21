import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium", app_title="02 · As bacias do Xingu e do Tapajós")

with app.setup(hide_code=True):
    import json
    from pathlib import Path

    import marimo as mo
    import matplotlib.pyplot as plt
    import pandas as pd

    from amazon_chaos import gradient as G
    from amazon_chaos import nb, regions
    from amazon_chaos.config import load_region
    from amazon_chaos.nonlinear.suite import load_spec
    from amazon_chaos.viz import COLORS, map_cells

    book = nb.notebook("02_regioes")
    SPEC = load_spec()
    SLUGS = ["xingu", "tapajos"]


@app.function(hide_code=True)
@mo.cache
def region(slug):
    cfg = load_region(slug)
    limit = regions.boundary(cfg)
    context = regions.load_context(cfg)
    record = json.loads(Path(cfg["spatial"]["basin_source"]).parent
                        .joinpath("source.json").read_text())
    biomes = regions.biome_shares(limit, context)
    return {"cfg": cfg, "limit": limit, "cells": regions.cells(cfg), "context": context,
            "record": record, "biomes": biomes / biomes.sum(),
            "protected": regions.protected_share(limit, context),
            "table": G.cell_table(cfg, SPEC)}


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # 🗺️ As bacias do Xingu e do Tapajós

    Para perguntar se a perturbação da floresta se associa à dinâmica do clima, precisamos
    de lugares em que a perturbação varie muito, de quase nada a quase tudo, e em que o
    resto varie o menos possível. Este capítulo apresenta os dois recortes escolhidos, as
    bacias hidrográficas do Xingu e do Tapajós, e a grade de células em que cada uma foi
    dividida. É a unidade de tudo o que vem depois: cada número dos capítulos seguintes
    pertence a uma célula desta grade.

    Começamos pelas razões da escolha e pelos mapas das duas bacias. Depois descrevemos a
    grade, como cada célula é pesada pela área que tem dentro da bacia e quais células
    entram na comparação final. Terminamos com a fronteira que as duas bacias compartilham
    e com o que isso significa para a análise.
    """)
    return


@app.cell(hide_code=True)
def _():
    map_region = mo.ui.dropdown(options={load_region(s)["name"]: s for s in SLUGS},
                                value="Bacia do Rio Xingu", label="Bacia")
    return (map_region,)


@app.cell(hide_code=True)
def _(map_region):
    _d = region(map_region.value)
    _fig = regions.plot_region(_d["cfg"], _d["limit"], _d["cells"], _d["context"])
    _cerrado = 100 * _d["biomes"].get("Cerrado", 0)
    _protected = 100 * _d["protected"]["tis_ou_ucs"]
    mo.vstack([
        mo.md(r"""
        ## 💧 Por que bacias hidrográficas

        Uma bacia hidrográfica é toda a área cuja chuva escoa para um mesmo rio. Ela é uma
        unidade física do ciclo da água, o que importa num trabalho sobre o acoplamento entre
        floresta e atmosfera, e tem um limite objetivo, definido pelo relevo, que não depende
        de nenhuma escolha nossa. Usamos os limites da base hidrográfica oficial do IBGE e da
        ANA, na escala 1:250.000 [1], que codifica as bacias pelo método de Otto
        Pfafstetter [2]; no nível 3 dessa codificação, o Xingu e o Tapajós aparecem como
        duas bacias inteiras, de tamanho parecido, perto de meio milhão de quilômetros
        quadrados cada.

        As duas foram escolhidas por atravessarem o mesmo gradiente. As cabeceiras ficam no
        norte de Mato Grosso, na transição com o Cerrado, onde a fronteira agrícola avançou
        primeiro e mais intensamente. O médio curso tem grandes blocos de floresta contínua,
        boa parte protegida em Terras Indígenas e Unidades de Conservação. A foz fica no
        Pará, no rio Amazonas. Ao longo de cada bacia, a perturbação vai de quase total a
        quase nula, e as duas, vizinhas, permitem verificar se um resultado em uma se repete
        na outra. A Figura 1 mostra cada bacia no território, com os biomas, as áreas
        protegidas, os rios principais, as cidades e a grade de células.
        """),
        map_region,
        book.figure(_fig, "mapa",
                    "Figura 1. A bacia no território brasileiro e no detalhe: limite da base "
                    "hidrográfica BHB250 (IBGE/ANA, 2021), células ERA5 de 0,25° que a "
                    "intersectam, biomas (IBGE), Terras Indígenas (FUNAI), Unidades de "
                    "Conservação federais (ICMBio), rios e cidades. Os limites são atuais e "
                    "servem de contexto; não medem a cobertura florestal nem a sua história.",
                    region=map_region.value, save=False),
        mo.callout(mo.md(nb.pt(
            f"{_d['cfg']['name']}: {_d['record']['source_area_km2'] / 1e3:.0f} mil km², "
            f"{len(_d['cells'])} células, {_cerrado:.0f}% no Cerrado e {_protected:.0f}% em "
            f"Terras Indígenas ou Unidades de Conservação federais.")), kind="info"),
        mo.md(r"""
        As duas bacias se parecem no desenho geral e diferem nos detalhes que vão importar
        mais adiante. O Xingu é quase todo amazônico, e mais da metade da sua área está em
        Terras Indígenas ou Unidades de Conservação, que formam um grande corredor
        protegido no médio curso, cercado de desmatamento nas bordas. O Tapajós tem uma
        fatia maior de Cerrado, perto de um quinto, e menos área protegida; a BR-163, que o
        corta de sul a norte, organiza boa parte da sua ocupação. Em ambas, o sul é ao mesmo
        tempo mais seco, mais alto, mais sazonal e mais desmatado, e essa coincidência é o
        principal obstáculo que a análise terá de contornar.
        """),
    ])
    return


@app.cell(hide_code=True)
def _():
    grid_region = mo.ui.dropdown(options={load_region(s)["name"]: s for s in SLUGS},
                                 value="Bacia do Rio Xingu", label="Bacia")
    return (grid_region,)


@app.function(hide_code=True)
def plot_grid(slug):
    d = region(slug)
    t = d["table"].reset_index()
    grid = d["cells"]
    fig, axes = plt.subplots(1, 3, figsize=(15, 7.2), layout="constrained")
    fields = [("basin_fraction", "Fração da célula dentro da bacia", "Blues"),
              ("fracao_terra", "Fração em terra (sem rios e lagos)", "YlGn")]
    for ax, (column, title, cmap) in zip(axes, fields, strict=False):
        field = t.set_index(["latitude", "longitude"])[column].astype(float).to_xarray()
        map_cells(ax, grid, field, cmap, "fração", outline=d["limit"], vmin=0, vmax=1)
        ax.set_title(title)
    ax = axes[2]
    flags = grid.merge(t[["latitude", "longitude", "elegivel"]], on=["latitude", "longitude"])
    for value, color, label in [(True, COLORS["q"], "na comparação"),
                                (False, COLORS["vpd"], "fora da comparação")]:
        part = flags[flags.elegivel == value]
        part.plot(ax=ax, color=color, edgecolor="none")
        ax.scatter([], [], marker="s", s=60, color=color, label=f"{label} ({len(part)})")
    d["limit"].boundary.plot(ax=ax, color=COLORS["ink"], linewidth=0.8)
    ax.legend(loc="lower left", fontsize=9, frameon=False)
    ax.set(aspect="equal")
    ax.grid(False)
    ax.tick_params(labelsize=8)
    ax.set_title("Células na comparação final")
    fig.suptitle(d["cfg"]["name"], x=0.02, ha="left", fontsize=13)
    return fig


@app.cell(hide_code=True)
def _(grid_region):
    _t = region(grid_region.value)["table"]
    _water = int(((_t.basin_fraction >= 0.5) & (_t.fracao_terra < 0.5)).sum())
    mo.vstack([
        mo.md(r"""
        ## 🔲 A grade de células

        O clima vem da reanálise ERA5 [3], que entrega valores numa grade regular de 0,25°
        de latitude por 0,25° de longitude, cerca de 28 km de lado no equador. Cada ponto
        dessa grade representa a célula ao seu redor, e é nessa resolução que trabalhamos:
        não há como afirmar nada sobre escalas menores que a célula com os dados do ERA5. As
        células de uma bacia são todas as que a intersectam, e cada uma recebe como peso a
        área que tem dentro do limite, calculada sobre o elipsoide. Quando um capítulo fala
        da média da bacia, é a média ponderada

        $$
        \bar x_{\text{bacia}}(t) = \frac{\sum_c a_c\, x_c(t)}{\sum_c a_c},
        $$

        em que $a_c$ é a área da célula $c$ dentro da bacia. A soma das áreas das células
        reproduz a área oficial da bacia até a precisão numérica.

        Nem toda célula, porém, serve para a comparação célula a célula. Uma célula da borda
        com 10% da área dentro da bacia, ou uma célula quase toda coberta pelo rio, tem uma
        medida de perturbação feita sobre um pedaço pequeno demais para representar o clima
        que o ERA5 lhe atribui. Por isso, a comparação final usa só as células com pelo menos
        metade da área dentro da bacia e pelo menos metade dessa área em terra, regra fixada
        no pré-registro. A Figura 2 mostra as duas frações e as células que sobram.
        """),
        grid_region,
        book.figure(plot_grid(grid_region.value), "grade",
                    "Figura 2. Fração de cada célula ERA5 dentro da bacia, fração em terra "
                    "(MapBiomas, 2000) e células que entram na comparação entre perturbação e "
                    "dinâmica (ao menos metade dentro da bacia e metade em terra).",
                    region=grid_region.value, save=False),
        mo.callout(mo.md(nb.pt(
            f"{int(_t.elegivel.sum())} das {len(_t)} células entram na comparação final; "
            f"{int((_t.basin_fraction < 0.5).sum())} ficam de fora por terem menos de "
            f"metade da área dentro da bacia e {_water} por terem menos de metade em "
            f"terra.")),
            kind="info"),
        mo.md(r"""
        O primeiro mapa mostra que as células parciais formam uma moldura estreita ao redor
        de cada bacia; o interior é todo de células inteiras. O segundo mostra os rios: o
        Xingu e o Tapajós se alargam muito no baixo curso, mas, na escala de 28 km, quase
        nenhuma célula é dominada por água. Por isso, a regra de
        elegibilidade remove sobretudo a moldura, e o mapa da direita mantém a bacia quase
        inteira. As séries climáticas de todas as células, inclusive as da moldura, são
        calculadas e entram nas médias da bacia, com o peso da área que têm dentro dela.
        """),
    ])
    return


@app.cell(hide_code=True)
def _():
    _rows = []
    for _slug in SLUGS:
        _d = region(_slug)
        _c, _t = _d["cells"], _d["table"]
        _rows.append({
            "Bacia": _d["cfg"]["name"].replace("Bacia do Rio ", ""),
            "Código Otto": _d["cfg"]["boundary"].get("cod_otto", ""),
            "Área (mil km²)": round(_d["record"]["source_area_km2"] / 1e3, 1),
            "Células": len(_c),
            "Células na comparação": int(_t.elegivel.sum()),
            "Latitudes": nb.pt(f"{_c.latitude.min():.2f}° a {_c.latitude.max():.2f}°"),
            "Amazônia (%)": round(100 * _d["biomes"].get("Amazônia", 0)),
            "Cerrado (%)": round(100 * _d["biomes"].get("Cerrado", 0)),
            "TIs ou UCs (%)": round(100 * _d["protected"]["tis_ou_ucs"]),
        })
    _key = {s: set(zip(region(s)["cells"].latitude.round(3),
                       region(s)["cells"].longitude.round(3), strict=True)) for s in SLUGS}
    _shared = len(_key["xingu"] & _key["tapajos"])
    _both = (region("xingu")["table"].elegivel.reset_index()
             .merge(region("tapajos")["table"].elegivel.reset_index(), on="cell_id"))
    mo.vstack([
        mo.md(r"""
        ## 🤝 Duas bacias vizinhas

        A Tabela 1 reúne as duas bacias lado a lado. Elas têm áreas e números de células
        quase iguais e cobrem a mesma faixa de latitudes, do paralelo 15° S à foz; as
        diferenças estão na parte de Cerrado, maior no Tapajós, e na parte protegida, maior
        no Xingu.
        """),
        book.table(pd.DataFrame(_rows), "comparacao",
                   "Tabela 1. As duas bacias: código de Otto Pfafstetter (BHB250, nível 3), "
                   "área, células ERA5 que as intersectam e que entram na comparação final, "
                   "faixa de latitudes dos centros das células, participação dos biomas (IBGE) "
                   "e de Terras Indígenas ou Unidades de Conservação federais, sem contar duas "
                   "vezes as áreas sobrepostas.", selection=None),
        mo.md(nb.pt(rf"""
        Como as bacias são vizinhas, o divisor de águas entre elas atravessa algumas
        células, que aparecem nas duas grades: são {_shared}, cada uma com parte da área em
        cada bacia. Isso não é um problema. Nas médias de bacia, cada célula entra com o peso
        da área que tem dentro daquela bacia, então nenhuma área é contada duas vezes. Na
        comparação célula a célula, a regra de elegibilidade exige mais da metade da área
        dentro da bacia, e uma célula não pode ter mais da metade em cada uma; das células
        compartilhadas, {len(_both[_both.elegivel_x & _both.elegivel_y])} entram nas duas
        comparações. Os resultados das duas bacias são, portanto, independentes no que diz
        respeito às células, embora não no que diz respeito ao clima, que é regional: as
        duas bacias estão sob a mesma atmosfera, e essa é mais uma razão para tratar a
        repetição de um resultado nas duas como confirmação, e não como prova.
        """)),
    ])
    return


@app.cell(hide_code=True)
def _():
    # Versões impressas das Figuras 1 e 2 para as duas bacias (sem exibição).
    for _slug in SLUGS:
        _d = region(_slug)
        book.figure(regions.plot_region(_d["cfg"], _d["limit"], _d["cells"], _d["context"]),
                    "mapa", "Figura 1. A bacia no território brasileiro e no detalhe: limite da "
                    "base hidrográfica BHB250 (IBGE/ANA, 2021), células ERA5 de 0,25° que a "
                    "intersectam, biomas (IBGE), Terras Indígenas (FUNAI), Unidades de "
                    "Conservação federais (ICMBio), rios e cidades. Os limites são atuais e "
                    "servem de contexto; não medem a cobertura florestal nem a sua história.",
                    region=_slug)
        book.figure(plot_grid(_slug), "grade",
                    "Figura 2. Fração de cada célula ERA5 dentro da bacia, fração em terra "
                    "(MapBiomas, 2000) e células que entram na comparação entre perturbação e "
                    "dinâmica (ao menos metade dentro da bacia e metade em terra).",
                    region=_slug)
    return


@app.cell(hide_code=True)
def _():
    mo.accordion({
        "🛠️ Para acrescentar uma região": mo.md(r"""
        A análise é dirigida por um arquivo de configuração por região, com o limite (um
        código da base hidrográfica ou uma caixa de coordenadas), o período e uma célula de
        exemplo. A partir dele, um comando prepara o limite, a cartografia de contexto e a
        grade (`amazon-chaos region prepare <região>`), e os mesmos comandos de download e
        de cálculo usados para o Xingu e o Tapajós produzem o clima, a perturbação e os
        descritores da nova região, que passa a aparecer nos menus destes cadernos. O passo
        a passo está no guia do cluster do projeto.
        """),
    })
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 📚 Referências

    [1] IBGE. *Bacias e divisões hidrográficas do Brasil: BHB250*. Rio de Janeiro: Instituto
    Brasileiro de Geografia e Estatística, 2021.

    [2] Pfafstetter, O. *Classificação de bacias hidrográficas: metodologia de codificação*.
    Rio de Janeiro: Departamento Nacional de Obras de Saneamento, 1989.

    [3] Hersbach, H. et al. The ERA5 global reanalysis. *Quarterly Journal of the Royal
    Meteorological Society*, v. 146, p. 1999–2049, 2020.
    """)
    return


if __name__ == "__main__":
    app.run()
