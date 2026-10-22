# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "amazon-chaos @ git+https://github.com/ThallesCansi/Caos.git",
#     "marimo>=0.23",
# ]
# [tool.marimo.opengraph]
# title = "04 · Desmatamento e fogo, célula por célula"
# description = "Quatro fontes e o que elas medem"
# ///
import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium", app_title="04 · Desmatamento e fogo, célula por célula")

with app.setup(hide_code=True):
    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    from scipy.stats import spearmanr

    from amazon_chaos import gradient as G
    from amazon_chaos import nb, regions
    from amazon_chaos.config import load_region
    from amazon_chaos.features.disturbance import out_dir
    from amazon_chaos.viz import COLORS, map_basins

    book = nb.notebook("04_perturbacao")
    SLUGS = ["xingu", "tapajos"]
    SHORT = {"xingu": "Xingu", "tapajos": "Tapajós"}
    BASIN_COLORS = {"xingu": COLORS["ink"], "tapajos": COLORS["t2m"]}
    YEARS = [1990, 2000, 2012, 2024]
    MAPS = [
        ("prodes_acumulado_2024_frac", "Desmatamento acumulado até 2024\n(PRODES)", "OrRd", (0, 1)),
        ("prodes_2013_2024_frac", "Desmatamento 2013–2024\n(PRODES)", "OrRd", (0, 0.4)),
        ("deter_corte_frac_2016_2024", "Alertas de corte raso 2016–2024\n(DETER)", "OrRd",
         (0, 0.4)),
        ("deter_degradacao_frac_2016_2024", "Alertas de degradação 2016–2024\n(DETER)", "PuRd",
         (0, 1)),
        ("focos_100km2_ano_2003_2012", "Focos por 100 km² por ano, 2003–2012\n(BDQueimadas)",
         "YlOrRd", (0, 20)),
        ("focos_100km2_ano_2013_2024", "Focos por 100 km² por ano, 2013–2024\n(BDQueimadas)",
         "YlOrRd", (0, 20)),
        ("mb_frequencia_fogo_media_2024", "Anos com fogo, 1985–2024\n(MapBiomas Fogo)",
         "YlOrRd", (0, 6)),
        ("mb_queimada_alguma_vez_frac_2024", "Área queimada ao menos uma vez,\n1985–2024 "
         "(MapBiomas Fogo)", "YlOrRd", (0, 1)),
    ]
    PAIRS = [
        ("prodes_2013_2024_frac", "mb_perda_floresta_2013_2024",
         "Desmatamento 2013–2024: PRODES × MapBiomas", "PRODES", "MapBiomas"),
        ("deter_corte_frac_2016_2024", "prodes_2013_2024_frac",
         "Corte raso: DETER 2016–2024 × PRODES 2013–2024", "DETER", "PRODES"),
        ("focos_100km2_ano_2013_2024", "mb_frequencia_fogo_media_2024",
         "Fogo: focos BDQueimadas × frequência MapBiomas", "focos por 100 km² por ano",
         "anos com fogo"),
        ("prodes_acumulado_2024_frac", "agro_frac_2024",
         "Acumulado: PRODES × agropecuária MapBiomas, 2024", "PRODES", "MapBiomas"),
    ]


@app.function(hide_code=True)
@mo.cache
def basin(slug):
    cfg = load_region(slug)
    table = pd.read_parquet(out_dir(cfg) / "celulas.parquet")
    table["natural_nao_florestal_2000"] = (
        1 - table.floresta_frac_2000 - table.agro_frac_2000).clip(lower=0)
    return {"cfg": cfg, "table": table, "cells": regions.cells(cfg),
            "limit": regions.boundary(cfg), "weights": table.terra_km2_2000,
            "surface": G.surface_table(cfg)}


@app.function(hide_code=True)
def field(slug, values):
    """Uma série por célula (índice cell_id) como campo latitude × longitude."""
    indexed = basin(slug)["cells"].set_index("cell_id")
    return (values.to_frame("v").join(indexed[["latitude", "longitude"]])
            .set_index(["latitude", "longitude"]).v.to_xarray())


@app.function(hide_code=True)
def column(slug, name):
    values = basin(slug)["table"][name]
    return values.clip(upper=1) if "frac" in name else values


@app.function(hide_code=True)
def both(values_of):
    return [(basin(s)["cells"], field(s, values_of(s)), basin(s)["limit"]) for s in SLUGS]


@app.function(hide_code=True)
def mean_of(slug, name):
    d = basin(slug)
    return float(np.average(column(slug, name), weights=d["weights"]))


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # 🔥 Desmatamento e fogo, célula por célula

    A pergunta central do trabalho compara lugares mais e menos perturbados. Para isso,
    precisamos de uma medida de perturbação para cada célula, construída sem olhar para o
    clima, que é a resposta que queremos explicar. Este capítulo constrói essa medida. Ele
    reúne quatro fontes independentes, três do Instituto Nacional de Pesquisas Espaciais e
    uma do projeto MapBiomas, agrega cada uma às células da grade e verifica se elas contam
    a mesma história.

    O percurso começa pelas fontes, pelo que cada uma mede e pelo modo como as levamos às
    células. Em seguida vemos a floresta em quatro datas e a perturbação em oito medidas,
    nos mapas e no tempo. Depois comparamos as fontes entre si e, por fim, apresentamos a
    medida principal do trabalho, a perda antecedente de floresta, com uma ressalva sobre o
    que ela mede que vai reaparecer no último capítulo. Os mapas mostram as duas bacias
    juntas, como estão no território: o Tapajós a oeste e o Xingu a leste.
    """)
    return


@app.cell(hide_code=True)
def _():
    _sources = pd.DataFrame([
        {"Fonte": "PRODES (INPE)", "O que mede": "corte raso da floresta primária",
         "Período": "até 2007 em bloco; anual de 2008 a 2024", "Resolução": "polígonos, 6,25 ha",
         "Cuidado": "não registra a conversão de vegetação não florestal; ano de agosto a julho"},
        {"Fonte": "DETER (INPE)", "O que mede": "alertas de corte raso e de degradação",
         "Período": "2016 a 2024", "Resolução": "polígonos, 3 ha",
         "Cuidado": "a data é a da detecção; é um sistema de alerta, não a taxa oficial"},
        {"Fonte": "BDQueimadas (INPE)", "O que mede": "focos de fogo ativo",
         "Período": "2003 a 2024", "Resolução": "pontos, pixel de ~1 km",
         "Cuidado": "um foco não é um incêndio nem uma área queimada"},
        {"Fonte": "MapBiomas Cobertura", "O que mede": "floresta, agropecuária e água",
         "Período": "1990, 2000, 2012 e 2024", "Resolução": "raster, 30 m",
         "Cuidado": "mudança de classe não é o mesmo que desmatamento do PRODES"},
        {"Fonte": "MapBiomas Fogo", "O que mede": "frequência e recência do fogo",
         "Período": "1985 a 2024", "Resolução": "raster, 30 m",
         "Cuidado": "conta anos com fogo, não eventos dentro do ano"},
    ])
    mo.vstack([
        mo.md(r"""
        ## 🛰️ Quatro olhares sobre a mesma paisagem

        Cada fonte olha para a paisagem de um jeito. O PRODES [1] é o levantamento oficial
        do desmatamento na Amazônia: analistas do INPE mapeiam, ano a ano, em imagens de
        satélite de 30 m, os polígonos de floresta primária que foram derrubados por inteiro.
        O DETER [2] usa imagens mais frequentes e menos detalhadas para emitir alertas de
        corte raso e de degradação, como a extração seletiva de madeira e as cicatrizes de
        fogo na floresta em pé. O BDQueimadas [3] registra os focos de fogo ativo detectados
        por um satélite de referência, sempre o mesmo, para que os anos sejam comparáveis. O
        MapBiomas [4, 5] classifica cada pixel de 30 m do país, a cada ano desde 1985, em
        classes de cobertura, e mapeia as áreas queimadas. A Tabela 1 resume as cinco
        bases.
        """),
        book.table(_sources, "fontes",
                   "Tabela 1. As fontes de perturbação, o que cada uma mede, o período e a "
                   "resolução usados e o principal cuidado de interpretação.", selection=None),
        mo.md(r"""
        As fontes do INPE são a base principal, como previa o projeto do trabalho, e o
        MapBiomas é o complemento: ele cobre um período mais longo, inclui o Cerrado e
        permite medir a floresta, e não só a sua perda. Todas foram baixadas uma única vez e
        agregadas às células sem nenhum serviço de processamento remoto. Para cada célula
        $c$ e cada classe $k$, a fração é a área da classe dividida pela área terrestre da
        célula dentro da bacia,

        $$
        f_{c,k} = \frac{\sum_{p \in c} a_p\, \mathbb 1[k_p = k]}{\sum_{p \in c} a_p\,
        \mathbb 1[k_p \ne \text{água}]},
        $$

        em que $a_p$ é a área do pixel ou do pedaço de polígono $p$, calculada sobre o
        elipsoide terrestre, e não como se cada grau tivesse o mesmo tamanho. Os focos de
        fogo viram uma densidade, focos por 100 km² por ano. Usar a área terrestre como
        denominador evita que uma célula com metade da área coberta por um rio pareça meio
        preservada só porque o rio não pode ser desmatado.
        """),
    ])
    return


@app.cell(hide_code=True)
def _():
    year_radio = mo.ui.radio(options=[str(y) for y in YEARS], value="2000", label="Ano",
                             inline=True)
    return (year_radio,)


@app.function(hide_code=True)
def plot_cover(year):
    fig, axes = plt.subplots(1, 3, figsize=(16, 7.4), layout="constrained")
    panels = [(lambda s: basin(s)["table"][f"floresta_frac_{year}"], f"Floresta em {year}",
               "Greens", 1),
              (lambda s: basin(s)["table"][f"agro_frac_{year}"], f"Agropecuária em {year}",
               "YlOrBr", 1),
              (lambda s: basin(s)["table"].floresta_frac_1990
               - basin(s)["table"][f"floresta_frac_{year}"],
               f"Perda de floresta de 1990 a {year}", "OrRd", 0.6)]
    for ax, (values_of, title, cmap, top) in zip(axes, panels, strict=True):
        map_basins(ax, both(values_of), cmap, "fração da área terrestre", vmin=0, vmax=top)
        ax.set_title(title)
    fig.suptitle("MapBiomas Cobertura", x=0.02, ha="left", fontsize=13)
    return fig


@app.cell(hide_code=True)
def _(year_radio):
    _year = int(year_radio.value)
    _txt = " ".join(
        f"{SHORT[s]}: " + ", ".join(f"{mean_of(s, f'floresta_frac_{y}'):.0%} em {y}"
                                    for y in YEARS)
        + f"; agropecuária em {_year}, {mean_of(s, f'agro_frac_{_year}'):.0%}." for s in SLUGS)
    mo.vstack([
        mo.md(r"""
        ## 🌳 A floresta em quatro datas

        Começamos pelo que existe, e não pelo que se perdeu. A Figura 1 mostra, para um ano
        escolhido entre os quatro que lemos do MapBiomas, a fração de floresta e a de
        agropecuária em cada célula e quanto de floresta a célula perdeu desde 1990. A versão
        impressa é a de 2000, o ano que define a medida principal do trabalho.
        """),
        year_radio,
        book.figure(plot_cover(_year), "cobertura",
                    "Figura 1. Fração da área terrestre de cada célula coberta por floresta e "
                    "por agropecuária no ano escolhido e perda de floresta desde 1990, nas duas "
                    "bacias (MapBiomas Cobertura, coleção 11). Na versão impressa, 2000.",
                    save=_year == 2000),
        mo.callout(mo.md(nb.pt(f"Floresta em fração da área terrestre. {_txt}")),
                   kind="info"),
        mo.md(r"""
        Em 1990 a floresta já tinha sido aberta no extremo sul e ao longo de alguns eixos de
        ocupação, mas a maior parte das duas bacias ainda era floresta contínua. Passando aos
        anos seguintes, a frente avança de sul para norte e ao longo das estradas, e a
        agropecuária ocupa o lugar da floresta quase célula por célula. No centro das duas
        bacias, os grandes blocos de Terras Indígenas e Unidades de Conservação permanecem
        verdes em todas as datas; a borda deles é, muitas vezes, a borda do desmatamento.
        Note também que algumas células do sul nunca foram floresta: são as savanas e os
        campos do Cerrado, que aparecem com pouca floresta já em 1990 sem que nada tenha sido
        derrubado. Essa distinção vai importar.
        """),
    ])
    return


@app.function(hide_code=True)
def plot_maps():
    fig, axes = plt.subplots(2, 4, figsize=(18, 12.5), layout="constrained")
    for ax, (name, title, cmap, (lo, hi)) in zip(axes.flat, MAPS, strict=True):
        map_basins(ax, both(lambda s, n=name: column(s, n)), cmap, "", vmin=lo, vmax=hi)
        ax.set_title(title, fontsize=10)
    return fig


@app.cell(hide_code=True)
def _():
    _txt = "; ".join(
        f"{SHORT[s]}, {mean_of(s, 'focos_100km2_ano_2003_2012'):.1f} em 2003–2012 e "
        f"{mean_of(s, 'focos_100km2_ano_2013_2024'):.1f} em 2013–2024" for s in SLUGS)
    mo.vstack([
        mo.md(r"""
        ## 🗺️ Onde está a perturbação

        A Figura 2 reúne oito medidas de perturbação, quatro de desmatamento e degradação e
        quatro de fogo. As frações de desmatamento e degradação estão em relação à área
        terrestre; em algumas poucas células da borda, uma medida do INPE passa um pouco de
        1, porque os polígonos do INPE e o mapa de água do MapBiomas não coincidem
        exatamente, e por isso limitamos as frações a 1 nos mapas.
        """),
        book.figure(plot_maps(), "mapas",
                    "Figura 2. Perturbação por célula nas duas bacias: desmatamento acumulado "
                    "até 2024 e de 2013 a 2024 (PRODES), alertas de corte raso e de degradação "
                    "de 2016 a 2024 (DETER), densidade de focos de fogo nas duas décadas "
                    "(BDQueimadas), número de anos com fogo e fração da área queimada ao menos "
                    "uma vez, de 1985 a 2024 (MapBiomas Fogo). Frações sobre a área terrestre, "
                    "limitadas a 1."),
        mo.callout(mo.md(nb.pt(f"Densidade média de focos por 100 km² por ano: {_txt}.")),
                   kind="info"),
        mo.md(r"""
        As medidas de desmatamento repetem o desenho da Figura 1, com uma diferença: o
        desmatamento recente, de 2013 a 2024, não está mais concentrado no sul, que já
        estava aberto, mas na frente que avança para o norte e para dentro da floresta, com
        destaque para o leste do Tapajós, ao longo da BR-163. Os alertas de degradação ocupam
        uma área maior que os de corte raso e se espalham pelas bordas das áreas abertas, onde
        a floresta em pé é explorada e queimada antes de ser derrubada. O fogo acompanha o
        desmatamento, porque é a ferramenta usada para limpar a área derrubada e para renovar
        o pasto, e foi menos frequente na segunda década que na primeira. Os grandes blocos de
        floresta do centro e do norte quase não queimaram em quarenta anos, o que mostra que
        a floresta úmida intacta raramente queima; as áreas de Cerrado do extremo sul, ao
        contrário, queimam com frequência, como é próprio dessa vegetação, sem aparecer no
        PRODES.
        """),
    ])
    return


@app.function(hide_code=True)
def annual_series(slug):
    folder = out_dir(basin(slug)["cfg"])
    foci = pd.read_parquet(folder / "focos_mensais.parquet")
    by_year = foci.sum().groupby(foci.columns.str[:4].astype(int)).sum()
    prodes = pd.read_parquet(folder / "prodes_anual.parquet").sum()
    prodes.index = prodes.index.astype(int)
    return by_year, prodes[(prodes.index >= 2008) & (prodes.index <= 2024)]


@app.function(hide_code=True)
def plot_series():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 4.4), layout="constrained")
    for k, slug in enumerate(SLUGS):
        foci, prodes = annual_series(slug)
        ax1.bar(foci.index + (k - 0.5) * 0.4, foci.values, width=0.4,
                color=BASIN_COLORS[slug], label=SHORT[slug])
        ax2.bar(prodes.index + (k - 0.5) * 0.4, prodes.values, width=0.4,
                color=BASIN_COLORS[slug], label=SHORT[slug])
    ax1.set(title="Focos de fogo ativo por ano (BDQueimadas)", ylabel="focos na bacia")
    ax2.set(title="Desmatamento anual (PRODES, ano de agosto a julho)", ylabel="km²")
    ax1.legend(fontsize=9)
    return fig


@app.cell(hide_code=True)
def _():
    _parts = []
    for _slug in SLUGS:
        _foci, _prodes = annual_series(_slug)
        _parts.append(
            f"{SHORT[_slug]}: mais focos em "
            f"{', '.join(map(str, sorted(_foci.sort_values().index[-3:])))}; desmatamento de "
            f"{_prodes.loc[2008]:,.0f} km² em 2008, mínimo de {_prodes.min():,.0f} km² em "
            f"{_prodes.idxmin()} e máximo recente de {_prodes.loc[2019:].max():,.0f} km² em "
            f"{_prodes.loc[2019:].idxmax()}.")
    mo.vstack([
        mo.md(r"""
        ## ⏳ No tempo

        A Figura 3 soma, a cada ano, os focos de fogo e o desmatamento do PRODES em cada
        bacia.
        """),
        book.figure(plot_series(), "series_anuais",
                    "Figura 3. Focos de fogo ativo por ano, de 2003 a 2024 (BDQueimadas, "
                    "satélite de referência), e desmatamento anual de 2008 a 2024 (PRODES), "
                    "somados sobre cada bacia."),
        mo.callout(mo.md(nb.pt(" ".join(_parts))), kind="info"),
        mo.md(r"""
        As duas séries contam a história conhecida da Amazônia brasileira, e as duas bacias a
        contam juntas. O desmatamento caiu depressa no fim da década de 2000, com o plano
        federal de controle, o monitoramento por satélite e as restrições de crédito, chegou
        ao mínimo no início da década de 2010 e voltou a subir a partir de 2019, recuando de
        novo em 2023 e 2024 [6]. Os focos de fogo foram mais numerosos no começo da série,
        quando o desmatamento era maior, e voltam a crescer nos anos de seca, como 2005, 2010
        e 2024: fogo e clima não são independentes. Por isso a medida principal do trabalho é
        a perturbação anterior à janela de análise, e não a que ocorreu durante ela, que pode
        ser em parte consequência do próprio clima que queremos explicar.
        """),
    ])
    return


@app.function(hide_code=True)
def plot_agreement():
    fig, axes = plt.subplots(1, 4, figsize=(17, 4.6), layout="constrained")
    rows = []
    for ax, (x, y, title, xlabel, ylabel) in zip(axes, PAIRS, strict=True):
        rhos = []
        for slug in SLUGS:
            ok = basin(slug)["table"][[x, y]].dropna()
            rho = spearmanr(ok[x], ok[y]).statistic
            rhos.append(nb.pt(f"{SHORT[slug]} {rho:.2f}"))
            ax.scatter(ok[x], ok[y], s=8, alpha=0.45, color=BASIN_COLORS[slug], lw=0,
                       label=SHORT[slug])
            rows.append({"Par": title, "Bacia": SHORT[slug], "ρ de Spearman": round(rho, 2),
                         "Células": len(ok)})
        ax.set_title(f"{title}\nρ: {', '.join(rhos)}", fontsize=9.5)
        ax.set(xlabel=xlabel, ylabel=ylabel)
    axes[0].legend(fontsize=8.5, markerscale=2)
    return fig, pd.DataFrame(rows)


@app.cell(hide_code=True)
def _():
    _fig, _rows = plot_agreement()
    _forest = {s: spearmanr(basin(s)["table"].prodes_acumulado_2024_frac,
                            basin(s)["table"].floresta_frac_2024).statistic for s in SLUGS}
    mo.vstack([
        mo.md(r"""
        ## 🔁 As fontes concordam?

        Se as fontes medem a mesma paisagem, as suas medidas devem andar juntas de uma célula
        para outra, mesmo com métodos, resoluções e definições diferentes. A Figura 4 compara
        quatro pares, com as células das duas bacias em cores diferentes e a correlação de
        postos de Spearman de cada uma, que só pergunta se as células se ordenam da mesma
        maneira.
        """),
        book.figure(_fig, "concordancia",
                    "Figura 4. Concordância entre fontes independentes, célula a célula, nas "
                    "duas bacias, com a correlação de postos de Spearman de cada uma."),
        mo.callout(mo.md(nb.pt(
            "Para comparação: o desmatamento acumulado do PRODES e a floresta do MapBiomas em "
            f"2024 têm ρ = {_forest['xingu']:.2f} no Xingu e {_forest['tapajos']:.2f} no "
            "Tapajós, uma concordância bem menor que a dos pares da figura.")), kind="info"),
        mo.md(r"""
        A concordância é muito alta onde as fontes medem a mesma coisa. Os alertas de corte
        raso do DETER e o desmatamento do PRODES têm correlação acima de 0,9, o que é
        esperado, porque um sistema é feito para antecipar o outro; o desmatamento recente
        pelo PRODES e pelo MapBiomas, construídos de modo totalmente independente,
        concordam quase tanto. Os focos de fogo do BDQueimadas e a frequência de área
        queimada do MapBiomas concordam bem, embora meçam coisas diferentes, um a chama vista
        do espaço num instante e o outro a cicatriz que ela deixa.

        A concordância cai quando as definições divergem, e o caso mais instrutivo está na
        caixa acima. O PRODES só registra a derrubada de floresta primária e deixa de fora,
        por construção, a vegetação que nunca foi floresta. Uma célula de Cerrado convertida
        em lavoura não aparece no PRODES, mas aparece no MapBiomas como pouca floresta e
        muita agropecuária; a coluna de pontos no eixo vertical do último painel são essas
        células. Por isso o PRODES acompanha bem a agropecuária, que é o que a derrubada
        produz, e acompanha menos a floresta remanescente, sobretudo no Tapajós, que tem mais
        Cerrado. Nenhuma das fontes está errada; elas respondem a perguntas diferentes.
        """),
        book.table(_rows, "concordancia",
                   "Tabela 2. Correlação de postos de Spearman entre medidas de fontes "
                   "diferentes, sobre as células de cada bacia.", selection=None),
    ])
    return


@app.function(hide_code=True)
def plot_antecedent():
    panels = [(lambda s: 1 - basin(s)["table"].floresta_frac_2000,
               "Perda antecedente\n(1 − floresta em 2000)", "OrRd"),
              (lambda s: basin(s)["table"].agro_frac_2000, "Agropecuária em 2000\n(conversão)",
               "YlOrBr"),
              (lambda s: basin(s)["table"].natural_nao_florestal_2000,
               "Vegetação natural não florestal\nem 2000", "PuBuGn")]
    fig, axes = plt.subplots(1, 3, figsize=(16, 7.4), layout="constrained")
    for ax, (values_of, title, cmap) in zip(axes, panels, strict=True):
        map_basins(ax, both(values_of), cmap, "fração da área terrestre", vmin=0, vmax=1)
        ax.set_title(title)
    return fig


@app.cell(hide_code=True)
def _():
    _txt = " ".join(
        f"{SHORT[s]}: perda antecedente de "
        f"{np.average(1 - basin(s)['table'].floresta_frac_2000, weights=basin(s)['weights']):.0%}"
        f" da área terrestre, dos quais {mean_of(s, 'agro_frac_2000'):.0%} são agropecuária e "
        f"{mean_of(s, 'natural_nao_florestal_2000'):.0%} vegetação natural não florestal; "
        f"correlação de postos entre a perda e a vegetação natural de "
        f"{spearmanr(1 - basin(s)['table'].floresta_frac_2000, basin(s)['table'].natural_nao_florestal_2000).statistic:.2f}."  # noqa: E501
        for s in SLUGS)
    mo.vstack([
        mo.md(r"""
        ## 🧮 A medida principal: a perda antecedente

        Entre tantas medidas, o pré-registro fixou uma como principal antes de qualquer
        comparação com o clima: a perda antecedente de floresta, um menos a fração de
        floresta em 2000. Ela tem três virtudes. É anterior à janela de análise do clima,
        que começa em 2001, e por isso não pode ser consequência dele. É contínua, de zero a
        um, sem exigir que escolhamos um limiar para separar células perturbadas de
        preservadas. E vem de uma única fonte, consistente em todo o território, inclusive
        no Cerrado. As demais medidas entram como secundárias, como o desmatamento durante a
        janela e o fogo, ou como análise de sensibilidade, como o PRODES.

        A medida tem, porém, uma ambiguidade que a Figura 5 torna visível. Tudo o que não é
        floresta conta como perda, e isso inclui duas coisas muito diferentes: a floresta
        convertida em agropecuária e a vegetação natural que nunca foi floresta, como as
        savanas e os campos do Cerrado no sul das bacias.
        """),
        book.figure(plot_antecedent(), "perda_antecedente",
                    "Figura 5. A perda antecedente de floresta (1 − fração de floresta em 2000) "
                    "e as suas duas componentes principais, a agropecuária e a vegetação "
                    "natural não florestal em 2000, nas duas bacias (MapBiomas)."),
        mo.callout(mo.md(nb.pt(_txt)), kind="info"),
        mo.md(r"""
        As duas componentes se concentram no sul, e por isso andam juntas; a vegetação natural
        não florestal pesa mais no Tapajós, cujo extremo sudoeste é de Cerrado. Isso não
        invalida a medida, porque, do ponto de vista da superfície, uma savana e um pasto se
        parecem mais entre si do que com uma floresta: ambos são mais baixos, mais claros,
        mais quentes e transpiram menos. Mas significa que uma associação entre a perda
        antecedente e o clima pode refletir, em parte, a vegetação natural, e não a ação
        humana. O último capítulo enfrenta essa objeção diretamente, substituindo a medida
        principal pela fração de agropecuária e controlando a vegetação natural.
        """),
        mo.callout(mo.md(
            "A substituição da perda antecedente pela agropecuária, com controle da "
            "vegetação natural não florestal, não estava no pré-registro: é uma análise "
            "complementar, motivada por esta figura e registrada como tal."), kind="warn"),
    ])
    return


@app.function(hide_code=True)
def plot_surface():
    panels = [("lst_dia_seca_c", "Superfície de dia, estação seca\n(MODIS, ~10h30)", "inferno"),
              ("lst_noite_c", "Superfície à noite, ano todo\n(MODIS, ~22h30)", "cividis"),
              ("era5_tmax_seca", "Máxima do ar a 2 m, estação seca\n(ERA5)", "inferno")]
    fig, axes = plt.subplots(1, 3, figsize=(16, 7.4), layout="constrained")
    for ax, (name, title, cmap) in zip(axes, panels, strict=True):
        map_basins(ax, both(lambda s, n=name: basin(s)["surface"][n]), cmap, "°C")
        ax.set_title(title)
    return fig


@app.cell(hide_code=True)
def _():
    _n = {s: int(basin(s)["surface"].lst_dia_c.notna().sum()) for s in SLUGS}
    mo.vstack([
        mo.md(r"""
        ## 🌡️ A temperatura vista do espaço

        Uma última fonte não mede a perturbação, mas um dos seus efeitos: a temperatura da
        superfície registrada pelo sensor MODIS, a bordo do satélite Terra, a cada oito
        dias, de 2001 a 2024, num pixel de 1 km [7]. Ela é medida por volta das 10h30 e das
        22h30, só nos dias sem nuvem, e usamos apenas as medidas marcadas como de boa
        qualidade, agregadas às células como as demais fontes. A Figura 6 mostra a média
        diurna da estação seca, a média noturna e, para comparação, a temperatura máxima do
        ar a 2 m no ERA5, também na estação seca.
        """),
        book.figure(plot_surface(), "temperatura_superficie",
                    "Figura 6. Temperatura média da superfície de dia na estação seca (junho a "
                    "setembro) e à noite no ano todo, medidas pelo MODIS (MOD11A2, coleção 6.1) "
                    "de 2001 a 2024, e temperatura máxima do ar a 2 m no ERA5 na estação seca, "
                    "nas duas bacias."),
        mo.callout(mo.md(nb.pt(
            f"Células com temperatura da superfície válida: {_n['xingu']} de "
            f"{len(basin('xingu')['table'])} no Xingu e {_n['tapajos']} de "
            f"{len(basin('tapajos')['table'])} no Tapajós.")), kind="info"),
        mo.md(r"""
        O mapa diurno do satélite é quase um negativo do mapa da floresta da Figura 1: a
        superfície é mais quente exatamente onde a floresta foi convertida, ao longo das
        estradas e no sul, e a borda das áreas protegidas aparece como um degrau de vários
        graus. À noite o desenho é outro: as diferenças entre floresta e áreas abertas quase
        somem, e o que aparece é o planalto do sul, o mais frio, pela altitude e pelo ar
        seco, que perde calor depressa. O ERA5, à direita, tem um desenho próprio, com as
        máximas mais altas no centro-oeste do Tapajós, em plena floresta, e as mais baixas no
        planalto do sudoeste, e nenhum traço do desenho do desmatamento. O último
        capítulo transforma essa impressão em números e mostra o que ela significa para a
        análise.
        """),
    ])
    return


@app.cell(hide_code=True)
def _():
    _tables = {SHORT[s]: book.table(basin(s)["table"].round(4).reset_index(), "celulas",
                                    "Medidas de perturbação por célula, de todas as fontes.",
                                    region=s, overleaf=False, selection=None) for s in SLUGS}
    mo.vstack([
        mo.md(r"""
        ## 🧭 Em resumo

        De 1990 a 2024, a floresta das duas bacias encolheu em perto de um sexto da área
        terrestre, e a agropecuária passou a ocupar de um quinto a mais de um quarto dela. A
        perturbação é muito desigual no espaço: concentrada no sul, onde a fronteira agrícola
        chegou primeiro, intensa ao longo das estradas e da frente que avança para o norte,
        quase nula nos grandes blocos protegidos do centro. As fontes do INPE e do MapBiomas
        concordam muito bem onde medem a mesma coisa e divergem de um modo explicável onde
        as definições diferem, sobretudo no Cerrado. A medida principal do trabalho, a perda
        antecedente de floresta, é anterior ao clima que vamos analisar e contínua, mas
        mistura conversão e vegetação natural, uma ambiguidade que o último capítulo trata
        explicitamente. O satélite mostra que a conversão aquece a superfície em vários
        graus, e que o ERA5 não registra esse aquecimento. As tabelas completas, com as quarenta medidas de cada célula, estão
        abaixo.
        """),
        mo.accordion({f"📋 Todas as medidas por célula, {k}": v for k, v in _tables.items()}),
    ])
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 📚 Referências

    [1] INPE. *Metodologia utilizada nos projetos PRODES e DETER*. 2. ed. São José dos
    Campos: Instituto Nacional de Pesquisas Espaciais, 2022.

    [2] Diniz, C. G. et al. DETER-B: the new Amazon near real-time deforestation detection
    system. *IEEE Journal of Selected Topics in Applied Earth Observations and Remote
    Sensing*, v. 8, p. 3619–3628, 2015.

    [3] INPE. *Programa Queimadas: banco de dados de queimadas*. São José dos Campos:
    Instituto Nacional de Pesquisas Espaciais, 2024.

    [4] Souza, C. M. et al. Reconstructing three decades of land use and land cover changes
    in Brazilian biomes with Landsat archive and Earth Engine. *Remote Sensing*, v. 12,
    2735, 2020.

    [5] Alencar, A. A. C. et al. Long-term Landsat-based monthly burned area dataset for the
    Brazilian biomes using deep learning. *Remote Sensing*, v. 14, 2510, 2022.

    [6] Assunção, J.; Gandour, C.; Rocha, R. Deforestation slowdown in the Brazilian Amazon:
    prices or policies? *Environment and Development Economics*, v. 20, p. 697–722, 2015.

    [7] Wan, Z. New refinements and validation of the collection-6 MODIS land-surface
    temperature/emissivity product. *Remote Sensing of Environment*, v. 140, p. 36–45, 2014.
    """)
    return


if __name__ == "__main__":
    app.run()
