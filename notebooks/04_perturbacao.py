import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium", app_title="04 · Desmatamento e fogo, célula por célula")

with app.setup(hide_code=True):
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
         "Desmatamento 2013–2024: PRODES × MapBiomas"),
        ("deter_corte_frac_2016_2024", "prodes_2013_2024_frac",
         "Corte raso: DETER 2016–2024 × PRODES 2013–2024"),
        ("focos_100km2_ano_2013_2024", "mb_frequencia_fogo_media_2024",
         "Fogo: focos BDQueimadas × frequência MapBiomas"),
        ("prodes_acumulado_2024_frac", "agro_frac_2024",
         "Acumulado: PRODES × agropecuária MapBiomas, 2024"),
    ]


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
    que ela mede que vai reaparecer no último capítulo. O menu abaixo escolhe a bacia.
    """)
    return


@app.cell(hide_code=True)
def _():
    picker = nb.region_picker()
    picker
    return (picker,)


@app.cell(hide_code=True)
def _(picker):
    cfg = load_region(picker.value)
    slug = cfg["slug"]
    _path = out_dir(cfg) / "celulas.parquet"
    mo.stop(not _path.exists(), nb.missing([_path], f"make pull REGION={slug}"))
    table = pd.read_parquet(_path)
    cells = regions.cells(cfg)
    limit = regions.boundary(cfg)
    rivers = regions.load_context(cfg).get("rios")
    weights = table.terra_km2_2000
    return cells, cfg, limit, rivers, slug, table, weights


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
        mo.ui.table(_sources, selection=None, show_download=False),
        mo.md(r"""
        <small>Tabela 1. As fontes de perturbação, o que cada uma mede, o período e a
        resolução usados e o principal cuidado de interpretação.</small>

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
def field(cells, table, column):
    indexed = cells.set_index("cell_id")
    return (table[column].clip(upper=1 if "frac" in column else None).to_frame("v")
            .join(indexed[["latitude", "longitude"]])
            .set_index(["latitude", "longitude"]).v.to_xarray())


@app.function(hide_code=True)
def plot_cover(cells, table, limit, rivers, region, year):
    fig, axes = plt.subplots(1, 3, figsize=(15, 7.4), layout="constrained")
    loss = (table.floresta_frac_1990 - table[f"floresta_frac_{year}"]).rename("perda")
    panels = [(table[f"floresta_frac_{year}"], f"Floresta em {year}", "Greens", (0, 1)),
              (table[f"agro_frac_{year}"], f"Agropecuária em {year}", "YlOrBr", (0, 1)),
              (loss, f"Perda de floresta de 1990 a {year}", "OrRd", (0, 0.6))]
    indexed = cells.set_index("cell_id")
    for ax, (values, title, cmap, (lo, hi)) in zip(axes, panels, strict=True):
        f = (values.to_frame("v").join(indexed[["latitude", "longitude"]])
             .set_index(["latitude", "longitude"]).v.to_xarray())
        map_cells(ax, cells, f, cmap, "fração da área terrestre", outline=limit,
                  lines=rivers, vmin=lo, vmax=hi)
        ax.set_title(title)
    fig.suptitle(f"{region} · MapBiomas Cobertura", x=0.02, ha="left", fontsize=13)
    return fig


@app.cell(hide_code=True)
def _(cells, cfg, limit, rivers, slug, table, weights, year_radio):
    _year = int(year_radio.value)
    _share = {y: np.average(table[f"floresta_frac_{y}"], weights=weights) for y in YEARS}
    _agro = np.average(table[f"agro_frac_{_year}"], weights=weights)
    mo.vstack([
        mo.md(r"""
        ## 🌳 A floresta em quatro datas

        Começamos pelo que existe, e não pelo que se perdeu. A Figura 1 mostra, para um ano
        escolhido entre os quatro que lemos do MapBiomas, a fração de floresta e a de
        agropecuária em cada célula e quanto de floresta a célula perdeu desde 1990. A versão
        impressa é a de 2000, o ano que define a medida principal do trabalho.
        """),
        year_radio,
        book.figure(plot_cover(cells, table, limit, rivers, cfg["name"], _year), "cobertura",
                    "Figura 1. Fração da área terrestre de cada célula coberta por floresta e "
                    "por agropecuária no ano escolhido e perda de floresta desde 1990 "
                    "(MapBiomas Cobertura, coleção 11). Na versão impressa, 2000.",
                    region=slug, save=_year == 2000),
        mo.callout(mo.md(nb.pt(
            f"Floresta na bacia, em fração da área terrestre: {_share[1990]:.0%} em 1990, "
            f"{_share[2000]:.0%} em 2000, {_share[2012]:.0%} em 2012 e {_share[2024]:.0%} em "
            f"2024. Agropecuária em {_year}: {_agro:.0%}.")), kind="info"),
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
def plot_maps(cells, table, limit, rivers, region):
    tall = (cells.total_bounds[3] - cells.total_bounds[1]) > 1.3 * (
        cells.total_bounds[2] - cells.total_bounds[0])
    fig, axes = plt.subplots(2, 4, figsize=(17, 13 if tall else 8), layout="constrained")
    for ax, (column, title, cmap, (lo, hi)) in zip(axes.flat, MAPS, strict=True):
        map_cells(ax, cells, field(cells, table, column), cmap, "", outline=limit,
                  lines=rivers, vmin=lo, vmax=hi)
        ax.set_title(title, fontsize=10)
    fig.suptitle(region, fontsize=13, x=0.02, ha="left")
    return fig


@app.cell(hide_code=True)
def _(cells, cfg, limit, rivers, slug, table, weights):
    _focos = [np.average(table[f"focos_100km2_ano_{p}"], weights=weights)
              for p in ["2003_2012", "2013_2024"]]
    mo.vstack([
        mo.md(r"""
        ## 🗺️ Onde está a perturbação

        A Figura 2 reúne oito medidas de perturbação, quatro de desmatamento e degradação e
        quatro de fogo. As frações de desmatamento e degradação estão em relação à área
        terrestre; em algumas poucas células da borda, uma medida do INPE passa um pouco de
        1, porque os polígonos do INPE e o mapa de água do MapBiomas não coincidem
        exatamente, e por isso limitamos as frações a 1 nos mapas.
        """),
        book.figure(plot_maps(cells, table, limit, rivers, cfg["name"]), "mapas",
                    "Figura 2. Perturbação por célula: desmatamento acumulado até 2024 e de "
                    "2013 a 2024 (PRODES), alertas de corte raso e de degradação de 2016 a 2024 "
                    "(DETER), densidade de focos de fogo nas duas décadas (BDQueimadas), número "
                    "de anos com fogo e fração da área queimada ao menos uma vez, de 1985 a "
                    "2024 (MapBiomas Fogo). Frações sobre a área terrestre, limitadas a 1.", region=slug),
        mo.callout(mo.md(nb.pt(
            f"Densidade média de focos na bacia: {_focos[0]:.1f} por 100 km² por ano em "
            f"2003–2012 e {_focos[1]:.1f} em 2013–2024.")), kind="info"),
        mo.md(r"""
        As medidas de desmatamento repetem o desenho da Figura 1, com uma diferença: o
        desmatamento recente, de 2013 a 2024, não está mais concentrado no extremo sul, que
        já estava aberto, mas na frente que avança para o norte e para dentro da floresta.
        Os alertas de degradação ocupam uma área maior que os de corte raso e se espalham
        pelas bordas das áreas abertas, onde a floresta em pé é explorada e queimada antes
        de ser derrubada. O fogo acompanha o desmatamento, porque é a ferramenta usada para
        limpar a área derrubada e para renovar o pasto, e foi menos frequente na segunda
        década que na primeira. Os grandes blocos de floresta do centro e do norte quase não
        queimaram em quarenta anos, o que mostra que a floresta úmida intacta raramente
        queima; as áreas de Cerrado do extremo sul, ao contrário, queimam com frequência,
        como é próprio dessa vegetação.
        """),
    ])
    return


@app.function(hide_code=True)
def regional_series(cfg):
    folder = out_dir(cfg)
    foci = pd.read_parquet(folder / "focos_mensais.parquet")
    by_year = foci.sum().groupby(foci.columns.str[:4].astype(int)).sum()
    prodes = pd.read_parquet(folder / "prodes_anual.parquet").sum()
    prodes.index = prodes.index.astype(int)
    prodes = prodes[(prodes.index >= 2008) & (prodes.index <= 2024)]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 4.2), layout="constrained")
    ax1.bar(by_year.index, by_year.values, color=COLORS["t2m"], alpha=0.85)
    ax1.set(title="Focos de fogo ativo por ano (BDQueimadas)", ylabel="focos na bacia")
    ax2.bar(prodes.index, prodes.values, color="#8f2d2a", alpha=0.85)
    ax2.set(title="Desmatamento anual (PRODES, ano de agosto a julho)", ylabel="km²")
    return fig, by_year, prodes


@app.cell(hide_code=True)
def _(cfg, slug):
    _fig, _foci, _prodes = regional_series(cfg)
    mo.vstack([
        mo.md(r"""
        ## ⏳ No tempo

        A Figura 3 soma, a cada ano, os focos de fogo e o desmatamento do PRODES na bacia
        inteira.
        """),
        book.figure(_fig, "series_anuais",
                    "Figura 3. Focos de fogo ativo por ano, de 2003 a 2024 (BDQueimadas, "
                    "satélite de referência), e desmatamento anual de 2008 a 2024 (PRODES), "
                    "somados sobre a bacia.", region=slug),
        mo.callout(mo.md(nb.pt(
            f"Anos com mais focos: {', '.join(map(str, sorted(_foci.sort_values().index[-4:])))}. "
            f"Desmatamento PRODES: {_prodes.loc[2008]:,.0f} km² em 2008, mínimo de "
            f"{_prodes.min():,.0f} km² em {_prodes.idxmin()} e máximo recente de "
            f"{_prodes.loc[2019:].max():,.0f} km² em {_prodes.loc[2019:].idxmax()}.")),
            kind="info"),
        mo.md(r"""
        As duas séries contam a história conhecida da Amazônia brasileira. O desmatamento
        caiu depressa no fim da década de 2000, com o plano federal de controle, o
        monitoramento por satélite e as restrições de crédito, chegou ao mínimo no início da
        década de 2010 e voltou a subir a partir de 2019, recuando de novo em 2023 e 2024
        [6]. Os focos de fogo foram mais numerosos no começo da série, quando o desmatamento
        era maior, e voltam a crescer nos anos de seca, como 2005, 2010 e 2024: fogo e clima
        não são independentes. Por isso a medida principal do trabalho é a perturbação
        anterior à janela de análise, e não a que ocorreu durante ela, que pode ser em parte
        consequência do próprio clima que queremos explicar.
        """),
    ])
    return


@app.function(hide_code=True)
def plot_agreement(table):
    fig, axes = plt.subplots(1, 4, figsize=(17, 4.6), layout="constrained")
    rows = []
    for ax, (x, y, title) in zip(axes, PAIRS, strict=True):
        ok = table[[x, y]].dropna()
        rho = spearmanr(ok[x], ok[y]).statistic
        ax.scatter(ok[x], ok[y], s=10, alpha=0.5, color=COLORS["ink"], lw=0)
        ax.set_title(nb.pt(f"{title}\nρ = {rho:.2f}"), fontsize=9.5)
        ax.set(xlabel=x.split("_")[0].upper() if "frac" in x else "focos por 100 km² por ano",
               ylabel="MapBiomas" if "mb_" in y or "agro" in y else y.split("_")[0].upper())
        rows.append({"Par": title, "ρ de Spearman": round(rho, 2), "Células": len(ok)})
    return fig, pd.DataFrame(rows)


@app.cell(hide_code=True)
def _(cfg, slug, table):
    _fig, _rows = plot_agreement(table)
    _forest = spearmanr(table.prodes_acumulado_2024_frac, table.floresta_frac_2024).statistic
    mo.vstack([
        mo.md(r"""
        ## 🔁 As fontes concordam?

        Se as fontes medem a mesma paisagem, as suas medidas devem andar juntas de uma célula
        para outra, mesmo com métodos, resoluções e definições diferentes. A Figura 4 compara
        quatro pares, cada um com a correlação de postos de Spearman, que só pergunta se as
        células se ordenam da mesma maneira.
        """),
        book.figure(_fig, "concordancia",
                    "Figura 4. Concordância entre fontes independentes, célula a célula, com a "
                    "correlação de postos de Spearman.", region=slug),
        mo.callout(mo.md(nb.pt(
            f"Para comparação: o desmatamento acumulado do PRODES e a floresta do MapBiomas em "
            f"2024 têm ρ = {_forest:.2f}, uma concordância bem menor que a dos pares da "
            f"figura.")), kind="info"),
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
        muita agropecuária. Por isso o PRODES acompanha bem a agropecuária, que é o que a
        derrubada produz, e acompanha menos a floresta remanescente. Nenhuma das fontes está
        errada; elas respondem a perguntas diferentes.
        """),
        book.table(_rows, "concordancia",
                   "Tabela 2. Correlação de postos de Spearman entre medidas de fontes "
                   "diferentes, sobre as células da bacia.", region=slug, selection=None),
    ])
    return


@app.function(hide_code=True)
def plot_antecedent(cells, table, limit, rivers, region):
    natural = (1 - table.floresta_frac_2000 - table.agro_frac_2000).clip(lower=0)
    panels = [((1 - table.floresta_frac_2000), "Perda antecedente\n(1 − floresta em 2000)", "OrRd"),
              (table.agro_frac_2000, "Agropecuária em 2000\n(conversão)", "YlOrBr"),
              (natural, "Vegetação natural não florestal\nem 2000", "PuBuGn")]
    indexed = cells.set_index("cell_id")
    fig, axes = plt.subplots(1, 3, figsize=(15, 7.4), layout="constrained")
    for ax, (values, title, cmap) in zip(axes, panels, strict=True):
        f = (values.to_frame("v").join(indexed[["latitude", "longitude"]])
             .set_index(["latitude", "longitude"]).v.to_xarray())
        map_cells(ax, cells, f, cmap, "fração da área terrestre", outline=limit,
                  lines=rivers, vmin=0, vmax=1)
        ax.set_title(title)
    fig.suptitle(region, x=0.02, ha="left", fontsize=13)
    return fig, natural


@app.cell(hide_code=True)
def _(cells, cfg, limit, rivers, slug, table, weights):
    _fig, _natural = plot_antecedent(cells, table, limit, rivers, cfg["name"])
    _loss = 1 - table.floresta_frac_2000
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
        book.figure(_fig, "perda_antecedente",
                    "Figura 5. A perda antecedente de floresta (1 − fração de floresta em 2000) "
                    "e as suas duas componentes principais: a agropecuária e a vegetação "
                    "natural não florestal em 2000 (MapBiomas).", region=slug),
        mo.callout(mo.md(nb.pt(
            f"Na média da bacia, a perda antecedente é de {np.average(_loss, weights=weights):.0%}"
            f" da área terrestre, dos quais {np.average(table.agro_frac_2000, weights=weights):.0%}"
            f" são agropecuária e {np.average(_natural, weights=weights):.0%} vegetação natural "
            f"não florestal. A correlação de postos da perda antecedente com a vegetação "
            f"natural não florestal é de {spearmanr(_loss, _natural).statistic:.2f}.")),
            kind="info"),
        mo.md(r"""
        As duas componentes se concentram no sul, e por isso andam juntas. Isso não invalida
        a medida, porque, do ponto de vista da superfície, uma savana e um pasto se parecem
        mais entre si do que com uma floresta: ambos são mais baixos, mais claros, mais
        quentes e transpiram menos. Mas significa que uma associação entre a perda
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


@app.cell(hide_code=True)
def _():
    mo.callout(mo.md(
        "Uma terceira fonte de informação sobre a superfície, a temperatura medida pelo "
        "sensor MODIS dos satélites Terra e Aqua, está sendo processada. Ela permitirá "
        "verificar se o contraste de temperatura entre áreas desmatadas e preservadas, que o "
        "satélite observa diretamente, aparece também no ERA5."), kind="warn")
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 🧭 Em resumo

    De 1990 a 2024, a floresta das duas bacias encolheu em perto de um sexto da área
    terrestre, e a agropecuária passou a ocupar de um quinto a mais de um quarto dela. A
    perturbação é muito desigual no espaço: concentrada no sul, onde a fronteira agrícola
    chegou primeiro, intensa ao longo das estradas e da frente que avança para o norte, quase
    nula nos grandes blocos protegidos do centro. As fontes do INPE e do MapBiomas concordam muito bem onde medem a mesma coisa e
    divergem de um modo explicável onde as definições diferem, sobretudo no Cerrado. A
    medida principal do trabalho, a perda antecedente de floresta, é anterior ao clima que
    vamos analisar e contínua, mas mistura conversão e vegetação natural, uma ambiguidade que
    o último capítulo trata explicitamente. A tabela completa, com as quarenta medidas de
    cada célula, está disponível abaixo.
    """)
    return


@app.cell(hide_code=True)
def _(slug, table):
    mo.accordion({"📋 Todas as medidas por célula": book.table(
        table.round(4).reset_index(), "celulas",
        "Medidas de perturbação por célula, de todas as fontes.", region=slug,
        overleaf=False, selection=None)})
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
    """)
    return


if __name__ == "__main__":
    app.run()
