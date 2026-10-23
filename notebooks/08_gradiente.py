# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "amazon-chaos @ git+https://github.com/ThallesCansi/Caos.git",
#     "marimo>=0.23",
# ]
# [tool.marimo.opengraph]
# title = "08 · Perturbação e dinâmica"
# description = "O que o ERA5 vê e o que o satélite vê"
# ///
import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium", app_title="08 · Perturbação e dinâmica")

with app.setup(hide_code=True):
    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    from scipy.stats import rankdata

    from amazon_chaos import gradient as G
    from amazon_chaos import nb, regions
    from amazon_chaos.config import load_region
    from amazon_chaos.nonlinear import results as R
    from amazon_chaos.nonlinear.suite import load_spec
    from amazon_chaos.viz import COLORS, map_cells

    book = nb.notebook("08_gradiente")
    SPEC = load_spec()
    SLUGS = ["xingu", "tapajos"]
    PRIMARY = SPEC["families"]["primary"]
    SHORT = {"pe_entropy": "PE", "pe_complexity": "C", "prediction": "EP", "rqa_det": "DET"}
    MODELS = {
        "pré-registrado": ("perda_antecedente", G.CONTROLS),
        "conversão, sem o Cerrado natural": ("agro_frac_2000",
                                             G.CONTROLS + ("natural_nao_florestal_2000",)),
        "com a vegetação do ERA5": ("perda_antecedente", G.CONTROLS + ("era5_veg_alta",)),
    }


@app.function(hide_code=True)
@mo.cache
def cells(slug):
    table = G.cell_table(load_region(slug), SPEC).join(G.surface_table(load_region(slug)))
    table["natural_nao_florestal_2000"] = (
        1 - table.floresta_frac_2000 - table.agro_frac_2000).clip(lower=0)
    return table


@app.function(hide_code=True)
@mo.cache
def model_results():
    rows = []
    for slug in SLUGS:
        e = cells(slug)[cells(slug).elegivel]
        for var in R.VARIABLES:
            for d in PRIMARY:
                for model, (exposure, controls) in MODELS.items():
                    rows.append({"bacia": slug, "variavel": var, "descritor": d,
                                 "modelo": model,
                                 **G.associate(e, exposure, f"z_{var}_{d}", controls)})
                rows.append({"bacia": slug, "variavel": var, "descritor": d,
                             "modelo": "longitudinal",
                             **G.associate(e, "mb_perda_floresta_2001_2012", f"delta_{var}_{d}")})
                rows.append({"bacia": slug, "variavel": var, "descritor": d,
                             "modelo": "longitudinal, m igual",
                             **G.associate(e[e[f"dm_{var}"] == 0], "mb_perda_floresta_2001_2012",
                                           f"delta_{var}_{d}")})
                for exposure in ["perda_2000_2024", "focos_100km2_ano_2003_2024",
                                 "mb_frequencia_fogo_media_2024", "prodes_acumulado_2024_frac",
                                 "prodes_ate_2007_frac"]:
                    rows.append({"bacia": slug, "variavel": var, "descritor": d,
                                 "modelo": "outras exposições",
                                 **G.associate(e, exposure, f"z_{var}_{d}")})
    return pd.DataFrame(rows)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # 🌳 Perturbação da floresta e dinâmica do clima

    Chegamos à pergunta que motivou o trabalho. Os capítulos anteriores mostraram que as
    séries diárias de temperatura e de déficit de pressão de vapor das bacias do Xingu e do
    Tapajós têm estrutura não linear, que essa estrutura varia de célula para célula e que
    boa parte dessa variação acompanha a latitude. Também medimos, de forma independente e
    com quatro fontes que concordam entre si, quanto cada célula foi desmatada e queimada.
    Agora juntamos as duas coisas: as células mais perturbadas têm uma dinâmica climática
    diferente das preservadas?

    Responder a isso exige cuidado, porque desmatamento e geografia andam juntos. Nas duas
    bacias, a fronteira agrícola avançou pelo sul, onde o clima é naturalmente mais seco e
    mais sazonal, o relevo é mais alto e a vegetação original já incluía o Cerrado. Uma
    associação simples entre perturbação e dinâmica misturaria tudo isso. Por isso seguimos o
    caminho fixado no pré-registro: comparamos células controlando a latitude, a fração de
    água e o relevo, levamos em conta que células vizinhas não são independentes e, além da
    comparação entre lugares, olhamos para a mudança dentro de cada lugar ao longo do tempo.

    O capítulo tem cinco partes. Primeiro vemos a perturbação e a vegetação que o próprio
    ERA5 enxerga, que não são a mesma coisa. Depois fazemos a comparação entre células, o
    resultado principal, e testamos se ele resiste a duas objeções. Em seguida vem a
    comparação dentro de cada célula entre as duas décadas. Depois confrontamos o ERA5 com
    a temperatura da superfície medida por satélite, uma observação independente do
    modelo. Por fim, juntamos tudo numa conclusão proporcional à evidência.
    """)
    return


@app.cell(hide_code=True)
def _():
    map_region = mo.ui.dropdown(options={load_region(s)["name"]: s for s in SLUGS},
                                value="Bacia do Rio Xingu", label="Bacia")
    return (map_region,)


@app.function(hide_code=True)
def plot_landscape(slug):
    cfg = load_region(slug)
    c = cells(slug)
    grid = regions.cells(cfg)
    limit = regions.boundary(cfg)
    fields = [("perda_antecedente", "Perda até 2000 (MapBiomas)", "OrRd"),
              ("perda_2000_2024", "Perda 2000–2024 (MapBiomas)", "OrRd"),
              ("era5_veg_alta", "Vegetação alta no ERA5 (fixa)", "Greens")]
    fig, axes = plt.subplots(1, 3, figsize=(15, 7.4), layout="constrained")
    for ax, (column, title, cmap) in zip(axes, fields, strict=True):
        field = c.reset_index().set_index(["latitude", "longitude"])[column].to_xarray()
        map_cells(ax, grid, field, cmap, "fração", outline=limit, vmin=0,
                  vmax=1 if column != "perda_2000_2024" else 0.5)
        ax.set_title(title)
    fig.suptitle(cfg["name"], x=0.02, ha="left", fontsize=13)
    return fig


@app.cell(hide_code=True)
def _(map_region):
    _c = cells(map_region.value)
    _e = _c[_c.elegivel]
    _rho_hist = _e[["era5_veg_alta", "floresta_frac_2000"]].corr("spearman").iloc[0, 1]
    _rho_new = _e[["era5_veg_alta", "perda_2000_2024"]].corr("spearman").iloc[0, 1]
    mo.vstack([
        mo.md(r"""
        ## 🛰️ A perturbação e o que o ERA5 enxerga

        Duas medidas de perturbação organizam a comparação. A perda antecedente é a fração
        da área terrestre da célula que não era floresta em 2000; ela resume o desmatamento
        acumulado até o início da janela de análise, junto com a vegetação naturalmente não
        florestal, ponto a que voltaremos. A perda de 2000 a 2024 é o que se desmatou durante
        a janela. A Figura 1 mostra as duas ao lado de uma terceira grandeza, que costuma
        ficar escondida: a fração de vegetação alta que o próprio ERA5 usa em cada célula.

        O ERA5 é uma reanálise: um modelo de previsão do tempo, corrigido continuamente por
        observações [1]. Para calcular as trocas de calor, de água e de momento entre a
        superfície e a atmosfera, o modelo precisa saber que vegetação cobre cada ponto, e
        essa informação vem de um mapa de cobertura construído com imagens de satélite do
        início da década de 1990 [2, 3], mantido fixo ao longo de toda a reanálise.
        """),
        map_region,
        book.figure(plot_landscape(map_region.value), "paisagem",
                    "Figura 1. Fração da área terrestre de cada célula sem floresta em 2000 "
                    "(perda antecedente) e desmatada entre 2000 e 2024, segundo o MapBiomas, "
                    "e fração de vegetação alta fixa usada pelo ERA5. Na versão impressa, as "
                    "duas bacias.", region=map_region.value, save=False),
        mo.callout(mo.md(nb.pt(
            f"Nas células elegíveis desta bacia, a vegetação do ERA5 acompanha a floresta de "
            f"2000 (ρ = {_rho_hist:+.2f}), mas não o desmatamento posterior "
            f"(ρ = {_rho_new:+.2f}).")), kind="info"),
        mo.md(r"""
        A comparação dos três mapas é reveladora. A perda antecedente tem um desenho
        nítido, concentrado no sul e ao longo das estradas, e o mapa de vegetação do ERA5
        reproduz parte desse desenho, porque foi feito com imagens de uma época em que boa
        parte daquela conversão já existia. O desmatamento de 2000 a 2024, ao contrário, não
        aparece no ERA5: o modelo continua tratando como floresta áreas que viraram pasto
        depois de 1990. Essa é a limitação central do trabalho, agora medida com os dados do
        próprio modelo, e ela orienta a leitura de tudo o que vem a seguir.
        """),
        mo.callout(mo.md(
            "O ERA5 não incorpora o desmatamento ano a ano. Diferenças entre células podem "
            "refletir o mapa de vegetação fixo do modelo, o clima de fundo e as observações "
            "assimiladas, mas uma mudança de vegetação posterior a 1990 só chega às séries "
            "indiretamente, se chegar."), kind="danger"),
    ])
    return


@app.cell(hide_code=True)
def _():
    sc_region = mo.ui.dropdown(options={load_region(s)["name"]: s for s in SLUGS},
                               value="Bacia do Rio Xingu", label="Bacia")
    sc_descriptor = mo.ui.dropdown(options={R.NAMES[d]: d for d in PRIMARY},
                                   value=R.NAMES["pe_complexity"], label="Descritor")
    sc_variable = mo.ui.radio(options={v: k for k, v in R.VARIABLES.items()},
                              value="déficit de pressão de vapor", label="Variável",
                              inline=True)
    return sc_descriptor, sc_region, sc_variable


@app.function(hide_code=True)
def plot_scatter(slug, descriptor, variable):
    e = cells(slug)
    e = e[e.elegivel]
    y = e[f"z_{variable}_{descriptor}"].to_numpy()
    x = e.perda_antecedente.to_numpy()
    ctrl = e[list(G.CONTROLS)].to_numpy()
    rx, ry = G._residual_ranks(x, ctrl), G._residual_ranks(y, ctrl)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.2), layout="constrained")
    sc = ax1.scatter(x, y, c=e.latitude, cmap="viridis", s=12, alpha=0.8)
    fig.colorbar(sc, ax=ax1, label="latitude (°)")
    ax1.set(xlabel="perda antecedente (fração sem floresta em 2000)",
            ylabel="z contra as substitutas", title="Antes dos controles")
    ax2.scatter(rx, ry, c=e.latitude, cmap="viridis", s=12, alpha=0.8)
    slope = (rx @ ry) / (rx @ rx)
    xs = np.array([rx.min(), rx.max()])
    ax2.plot(xs, slope * xs, color=COLORS["t2m"], lw=2)
    ax2.set(xlabel="perda antecedente (posto, sem os controles)",
            ylabel="z (posto, sem os controles)",
            title="Depois de retirar latitude, água e relevo")
    fig.suptitle(f"{load_region(slug)['name']} · {R.NAMES[descriptor]} · "
                 f"{R.VARIABLES[variable]}", x=0.02, ha="left", fontsize=12)
    raw = float(np.corrcoef(rankdata(x), rankdata(y))[0, 1])
    return fig, raw, float(np.corrcoef(rx, ry)[0, 1])


@app.cell(hide_code=True)
def _(sc_descriptor, sc_region, sc_variable):
    _fig, _raw, _partial = plot_scatter(sc_region.value, sc_descriptor.value, sc_variable.value)
    mo.vstack([
        mo.md(r"""
        ## 🔍 Comparando células

        A comparação entre células usa as células com pelo menos metade da área em terra e
        pelo menos metade dentro da bacia, 668 no Xingu e 652 no Tapajós; as demais, de borda
        ou dominadas por rios, têm uma perturbação medida sobre uma área pequena demais para
        representar o clima da célula inteira. A resposta é o $z$ de cada descritor primário
        contra as substitutas, que vimos no capítulo anterior.

        A medida de associação é a correlação de postos de Spearman, que não supõe relação
        linear nem distribuição gaussiana. Para separar a perturbação da geografia, usamos a
        versão parcial: transformamos todas as variáveis em postos, retiramos da perturbação e
        do descritor a parte explicada linearmente pelos postos da latitude, da fração de
        água e da altitude do relevo, e correlacionamos o que sobra,

        $$
        \rho_{\text{parcial}} = \operatorname{corr}\!\left(r_x - \hat r_x(\mathbf c),\;
        r_y - \hat r_y(\mathbf c)\right),
        $$

        em que $r_x$ e $r_y$ são os postos e $\hat r(\mathbf c)$ a sua previsão pelos
        controles. A Figura 2 mostra as duas versões para um par de cada vez: à esquerda, a
        relação bruta, com as células coloridas pela latitude; à direita, a mesma relação
        depois de retirar os controles.
        """),
        mo.hstack([sc_region, sc_descriptor, sc_variable], justify="start", gap=1),
        book.figure(_fig, "dispersao",
                    "Figura 2. Perturbação antecedente e z do descritor, por célula, antes "
                    "(esquerda) e depois (direita) de retirar dos postos a parte explicada pela "
                    "latitude, pela fração de água e pela altitude. Cor: latitude. Na versão "
                    "impressa, complexidade estatística do VPD, Xingu.",
                    save=(sc_region.value, sc_descriptor.value, sc_variable.value)
                    == ("xingu", "pe_complexity", "vpd")),
        mo.callout(mo.md(nb.pt(
            f"Para este par, a correlação de postos é ρ = {_raw:+.2f} antes dos controles e "
            f"ρ parcial = {_partial:+.2f} depois.")), kind="info"),
        mo.md(r"""
        O painel da esquerda explica por que os controles são indispensáveis: as cores formam
        faixas, e as células do extremo sul (roxas) concentram ao mesmo tempo a perturbação e
        os valores extremos do descritor. Boa parte da correlação bruta é geografia. Depois
        dos controles, à direita, a ordenação por cor quase se desfaz e a inclinação diminui,
        mas, em vários pares, não desaparece. Destoa um grupo de células do extremo norte
        (amarelas), perto da foz do Xingu, com valores bem abaixo do esperado pelos
        controles; a correlação de postos não se deixa dominar por um grupo assim, e a
        reamostragem por blocos espaciais leva em conta que essas células são vizinhas. O que resta é a pergunta que interessa: entre células na
        mesma latitude, com a mesma proporção de água e no mesmo relevo, as que tinham mais
        floresta convertida até 2000 diferem das preservadas?
        """),
    ])
    return


@app.function(hide_code=True)
def plot_forest():
    res = model_results()
    res = res[res.modelo.isin(MODELS)]
    fig, axes = plt.subplots(1, 2, figsize=(14, 6.6), sharex=True, layout="constrained")
    styles = {"pré-registrado": (COLORS["ink"], "o"),
              "conversão, sem o Cerrado natural": (COLORS["t2m"], "s"),
              "com a vegetação do ERA5": (COLORS["q"], "D")}
    labels = [f"{R.NAMES[d]} · {'temperatura' if v == 't2m' else 'VPD'}"
              for v in R.VARIABLES for d in PRIMARY]
    for ax, slug in zip(axes, SLUGS, strict=True):
        part = res[res.bacia == slug]
        for k, (model, (color, marker)) in enumerate(styles.items()):
            rows = part[part.modelo == model].set_index(["variavel", "descritor"])
            rows = rows.reindex([(v, d) for v in R.VARIABLES for d in PRIMARY])
            y = np.arange(len(rows)) + (k - 1) * 0.25
            ax.errorbar(rows.rho_parcial, y, xerr=[rows.rho_parcial - rows.ic_inf,
                                                   rows.ic_sup - rows.rho_parcial],
                        fmt=marker, color=color, ms=6, capsize=2, lw=1.2, label=model)
        ax.axvline(0, color=COLORS["muted"], lw=1)
        ax.set_yticks(np.arange(len(labels)), labels, fontsize=9)
        ax.invert_yaxis()
        ax.set(xlabel="ρ parcial de Spearman (IC 95% por blocos de 1°)",
               title=load_region(slug)["name"])
    handles, names = axes[0].get_legend_handles_labels()
    fig.legend(handles, names, loc="outside lower center", ncol=3, fontsize=9.5,
               frameon=False)
    return fig


@app.cell(hide_code=True)
def _():
    _res = model_results()
    _pre = _res[_res.modelo == "pré-registrado"].copy()
    _pre["Bacia"] = _pre.bacia.map(lambda s: load_region(s)["name"].replace("Bacia do Rio ", ""))
    _pre["Descritor"] = _pre.descritor.map(R.NAMES)
    _pre["Variável"] = _pre.variavel.map(R.VARIABLES)
    _pre["IC 95%"] = [f"[{a:+.2f}; {b:+.2f}]" for a, b in zip(_pre.ic_inf, _pre.ic_sup,
                                                             strict=True)]
    _tab = _pre[["Bacia", "Descritor", "Variável", "celulas", "rho_bruto", "rho_parcial",
                 "IC 95%", "moran_residuos"]].rename(columns={
        "celulas": "Células", "rho_bruto": "ρ bruto", "rho_parcial": "ρ parcial",
        "moran_residuos": "Moran dos resíduos"}).round(2)
    mo.vstack([
        mo.md(r"""
        ## 📊 O resultado principal e duas objeções

        A Tabela 1 traz o resultado pré-registrado para os quatro descritores primários, nas
        duas variáveis e nas duas bacias: a correlação bruta, a parcial, o intervalo de 95%
        obtido por reamostragem de blocos espaciais de 1° e o índice de Moran dos resíduos,
        que mede quanto da variação não explicada ainda se parece entre células vizinhas
        (zero indicaria independência; 1, semelhança total) [4].
        """),
        book.table(_tab, "resultado_preregistrado",
                   "Tabela 1. Resultado pré-registrado: correlação de Spearman entre perda "
                   "antecedente de floresta e z dos descritores primários, bruta e parcial "
                   "(controles: latitude, água e altitude), com IC 95% por bootstrap em blocos "
                   "de 1° e I de Moran dos resíduos.", selection=None),
        mo.md(r"""
        Nas duas bacias, a perturbação antecedente se associa a uma dinâmica menos
        estruturada. Quanto maior a perda até 2000, maior a entropia de permutação e menor a
        complexidade do VPD, e menor o determinismo da temperatura, com intervalos que não
        incluem zero. No Xingu, a associação também aparece no erro de previsão e no
        determinismo do VPD e nos padrões ordinais da temperatura; no Tapajós, nem os padrões
        ordinais nem o erro de previsão da temperatura mostram associação. Os valores
        parciais que se destacam ficam entre 0,2 e 0,46 em módulo: associações moderadas,
        bem menores que as brutas, que passavam de 0,6.

        O índice de Moran dos resíduos, entre 0,4 e 0,75, mostra que a variação não explicada
        continua organizada no espaço. Isso tem duas consequências. A primeira é estatística:
        mesmo com blocos de 1°, os intervalos podem estar um pouco otimistas, e por isso só
        consideramos sólidos os efeitos que se repetem nas duas bacias. A segunda é
        substantiva: existe estrutura espacial que nem a perturbação nem os controles
        capturam, e é nela que podem estar os confundidores restantes.

        Duas objeções precisam ser enfrentadas antes de qualquer leitura causal. A primeira é
        que a perda antecedente conta como "perda" toda área que não era floresta em 2000,
        inclusive as savanas e campos naturais do Cerrado, que nunca foram floresta e se
        concentram justamente no sul. A segunda é que, se o ERA5 só conhece a vegetação pelo
        seu mapa fixo, o contraste entre células pode estar passando por esse mapa, e não por
        algo que as observações tenham registrado. A Figura 3 testa as duas.
        """),
        book.figure(plot_forest(), "modelos",
                    "Figura 3. Correlação parcial entre perturbação e z de cada descritor "
                    "primário, com IC 95% por blocos de 1°, em três modelos: o pré-registrado "
                    "(perda antecedente, controlando latitude, água e altitude); a conversão "
                    "agropecuária em 2000, controlando também a vegetação natural não florestal; "
                    "e a perda antecedente controlando também a vegetação alta fixa do ERA5."),
        mo.md(r"""
        Os pontos escuros repetem a Tabela 1. Os vermelhos trocam a exposição pela fração de
        agropecuária em 2000, que mede só a conversão feita pelas pessoas, e controlam a
        vegetação natural não florestal. Nas associações do VPD, nas duas bacias, e no
        determinismo da temperatura no Tapajós, quase nada muda: essas associações não são
        um artefato do Cerrado natural e acompanham a conversão de fato. No Xingu, as
        associações da temperatura enfraquecem, sinal de que parte delas vinha do contraste
        entre floresta e vegetação natural aberta, e não do desmatamento.

        Os pontos verdes acrescentam aos controles a vegetação alta fixa do ERA5, e aqui a
        figura muda. No Tapajós, a associação da entropia e da complexidade do VPD praticamente
        desaparece, e a do determinismo da temperatura cai à metade; no Xingu, o erro de
        previsão da temperatura vai para perto de zero, o determinismo das duas variáveis
        encolhe, e só as associações dos padrões ordinais resistem, com as do VPD
        menores. Em outras palavras, uma parte
        importante da diferença entre células convertidas e preservadas, tal como o ERA5 a
        registra, passa pelo mapa de vegetação que o próprio modelo usa. O modelo calcula uma
        evaporação, um aquecimento da superfície e uma rugosidade diferentes para um ponto de
        pasto e para um ponto de floresta, e essas diferenças deixam marca na dinâmica diária;
        mas o mapa que define o que é pasto e o que é floresta é o da década de 1990.
        """),
        mo.callout(mo.md(
            "As duas análises desta figura além do modelo pré-registrado são complementares: "
            "foram motivadas pelos resultados e registradas como tal (D-014). O resultado "
            "principal do trabalho continua sendo o da Tabela 1; elas servem para delimitar o "
            "que ele significa."), kind="warn"),
    ])
    return


@app.function(hide_code=True)
def plot_others():
    res = model_results()
    res = res[res.modelo == "outras exposições"]
    exposures = ["perda_2000_2024", "focos_100km2_ano_2003_2024",
                 "mb_frequencia_fogo_media_2024", "prodes_acumulado_2024_frac",
                 "prodes_ate_2007_frac"]
    cols = [(v, d) for v in R.VARIABLES for d in PRIMARY]
    fig, axes = plt.subplots(1, 2, figsize=(15, 4.8), layout="constrained")
    for ax, slug in zip(axes, SLUGS, strict=True):
        part = res[res.bacia == slug]
        mat = np.full((len(exposures), len(cols)), np.nan)
        sig = np.zeros_like(mat, dtype=bool)
        for i, ex in enumerate(exposures):
            for j, (v, d) in enumerate(cols):
                r = part[(part.exposicao == ex) & (part.variavel == v) & (part.descritor == d)]
                if len(r):
                    mat[i, j], sig[i, j] = r.rho_parcial.iloc[0], r.exclui_zero.iloc[0]
        im = ax.imshow(mat, cmap="RdBu_r", vmin=-0.5, vmax=0.5, aspect="auto")
        for i in range(mat.shape[0]):
            for j in range(mat.shape[1]):
                ax.text(j, i, f"{mat[i, j]:+.2f}" + ("*" if sig[i, j] else ""), ha="center",
                        va="center", fontsize=8)
        ax.set_xticks(range(len(cols)), [f"{SHORT[d]}\n{'temp.' if v == 't2m' else 'VPD'}"
                                         for v, d in cols], fontsize=8.5)
        ax.set_yticks(range(len(exposures)), [G.EXPOSURES[e] for e in exposures], fontsize=8.5)
        ax.set_title(load_region(slug)["name"])
        ax.grid(False)
    fig.colorbar(im, ax=axes, shrink=0.8, label="ρ parcial")
    return fig


@app.cell(hide_code=True)
def _():
    mo.vstack([
        mo.md(r"""
        ## 🔥 Outras medidas de perturbação

        A perda antecedente é a exposição principal porque antecede a janela de análise; as
        demais medidas foram fixadas como secundárias ou de sensibilidade. A Figura 4 resume a
        correlação parcial de cada uma com cada descritor, com um asterisco quando o intervalo
        de 95% não inclui zero.
        """),
        book.figure(plot_others(), "outras_exposicoes",
                    "Figura 4. Correlação parcial (controles: latitude, água e altitude) entre "
                    "outras medidas de perturbação e o z dos descritores primários: entropia de "
                    "permutação (PE), complexidade estatística (C), erro de previsão (EP) e "
                    "determinismo (DET), da temperatura e do VPD. Asterisco: IC 95% por blocos "
                    "de 1° sem o zero."),
        mo.md(r"""
        As medidas de perturbação durante a janela, a perda de floresta de 2000 a 2024 e a
        densidade de focos de fogo, mostram associações fracas, quase sempre abaixo de 0,15
        e em geral compatíveis com zero. As medidas acumuladas se comportam de modo diferente
        nas duas bacias. No Xingu, a frequência de fogo desde 1985 e o desmatamento segundo o
        PRODES repetem, menores, as associações da exposição principal com o VPD. No
        Tapajós, ao contrário, o PRODES e a perda recente aparecem com o sinal oposto no
        determinismo e no erro de previsão do VPD, ainda que fracos.

        Essas observações são coerentes com o que a Figura 1 mostrou: o que se desmatou
        depois de 2000 não está no mapa de vegetação do ERA5, e por isso a perturbação recente
        não tem como se expressar nas séries. O PRODES, por sua vez, mede só a perda de
        floresta primária e não registra a vegetação aberta do sul das bacias, o que o torna
        uma medida mais estreita do contraste de superfície que o modelo enxerga. A
        inversão de sinal no Tapajós, sem paralelo no Xingu e sem um mecanismo claro, é o
        tipo de resultado que não sustentamos sem replicação.
        """),
    ])
    return


@app.function(hide_code=True)
@mo.cache
def robustness():
    rows = []
    for slug in SLUGS:
        e = cells(slug)[cells(slug).elegivel].copy()
        for var in R.VARIABLES:
            for d in PRIMARY:
                e[f"excesso_{var}_{d}"] = e[f"obs_{var}_{d}"] - e[f"nulo_{var}_{d}"]
                row = {"bacia": slug, "variavel": var, "descritor": d}
                for block in (1.0, 3.0):
                    a = G.associate(e, "perda_antecedente", f"z_{var}_{d}", block=block)
                    row["rho"], row[f"ic{block:.0f}"] = a["rho_parcial"], (a["ic_inf"],
                                                                           a["ic_sup"])
                for name, column in [("observado", f"obs_{var}_{d}"),
                                     ("nulo", f"nulo_{var}_{d}"),
                                     ("excesso", f"excesso_{var}_{d}")]:
                    row[name] = G.associate(e, "perda_antecedente", column)["rho_parcial"]
                a = G.associate(e, "perda_1990_2000", f"z_{var}_{d}")
                row["perda_9000"], row["ic_9000"] = a["rho_parcial"], (a["ic_inf"], a["ic_sup"])
                forest = e[e.natural_nao_florestal_2000 < 0.05]
                a = G.associate(forest, "perda_antecedente", f"z_{var}_{d}")
                row["floresta"], row["ic_floresta"] = a["rho_parcial"], (a["ic_inf"],
                                                                         a["ic_sup"])
                rows.append(row)
    return pd.DataFrame(rows)


@app.cell(hide_code=True)
def _():
    _r = robustness()

    def _ci(rho, ci):
        return f"{rho:+.2f} [{ci[0]:+.2f}; {ci[1]:+.2f}]"

    _tab = pd.DataFrame({
        "Bacia": _r.bacia.map(lambda s: load_region(s)["name"].replace("Bacia do Rio ", "")),
        "Descritor": _r.descritor.map(R.NAMES), "Variável": _r.variavel.map(R.VARIABLES),
        "z, blocos de 1°": [_ci(a, b) for a, b in zip(_r.rho, _r.ic1, strict=True)],
        "z, blocos de 3°": [_ci(a, b) for a, b in zip(_r.rho, _r.ic3, strict=True)],
        "observado": _r.observado.round(2), "média das substitutas": _r.nulo.round(2),
        "excesso": _r.excesso.round(2),
        "z, perda 1990–2000": [_ci(a, b) for a, b in zip(_r.perda_9000, _r.ic_9000,
                                                         strict=True)],
        "z, só células de floresta": [_ci(a, b) for a, b in zip(_r.floresta, _r.ic_floresta,
                                                                strict=True)]})
    mo.vstack([
        mo.md(r"""
        ## 🧪 Até onde o resultado principal resiste

        Quatro perguntas ainda podem ser feitas à Tabela 1. A primeira é sobre a inferência: os
        resíduos continuam parecidos entre vizinhos, e blocos de 1° podem ser pequenos demais
        para tornar as reamostragens independentes. A segunda é sobre o que exatamente se
        associa à perturbação, já que a resposta é o $z$, uma medida relativa às substitutas,
        e não o descritor em si. A terceira é sobre a exposição: a perda antecedente mistura
        o que foi desmatado com o que nunca foi floresta. A quarta é sobre o Cerrado: a
        vegetação natural aberta do sul das bacias tem um clima próprio, e pode ser ela, e
        não a conversão, que distingue as células. A Tabela 2 responde às quatro, com os
        mesmos controles da Tabela 1.
        """),
        book.table(_tab, "robustez",
                   "Tabela 2. Robustez do resultado pré-registrado: correlação parcial "
                   "(controles: latitude, água e altitude) entre a perda antecedente e o z de "
                   "cada descritor primário, com IC 95% por blocos de 1° e de 3°; a mesma "
                   "correlação com o valor observado do descritor, com a média das "
                   "substitutas e com o excesso (observado menos essa média); o z contra a "
                   "perda de floresta de 1990 a 2000; e o z só nas células com menos de 5% de "
                   "vegetação natural não florestal em 2000, com IC por blocos de 1°.",
                   selection=None),
        mo.md(r"""
        Blocos de 3°, com nove vezes a área dos de 1°, alargam os intervalos só um pouco, e
        as associações que excluíam o zero continuam a excluí-lo, com uma ressalva no Xingu:
        a entropia e o erro de previsão da temperatura passam a tocar o zero, e a
        complexidade da temperatura já o tocava. As associações do VPD nas duas bacias e a do
        determinismo da temperatura não dependem do tamanho do bloco.

        A segunda pergunta traz a novidade da tabela. Quando a resposta é o valor observado
        do descritor, as associações dos padrões ordinais desaparecem e, no Tapajós, chegam a
        trocar de sinal, e a do determinismo encolhe. Para entender por quê, separamos o
        $z$ nas suas duas partes: a média das substitutas, que é o valor que o descritor teria
        se a série fosse só a sua parte linear, com o mesmo espectro e a mesma distribuição,
        e o excesso do observado sobre essa média, que é a parte que só a não linearidade
        explica. As duas andam em sentidos opostos. Nas células mais perturbadas, a parte
        linear sozinha daria uma entropia menor, porque a série é mais persistente e mais
        sazonal, mas a entropia observada é praticamente a mesma das outras células; o
        excesso não linear, negativo em quase todas as células, fica mais perto de zero. A
        associação do $z$ é praticamente a do excesso, e não vem da largura da nuvem de
        substitutas. O erro de previsão é a exceção: no Xingu ele é menor nas células
        perturbadas tanto no valor observado quanto no excesso, e no Tapajós só no valor
        observado do VPD, isto é, essas séries são um pouco mais previsíveis um dia à frente,
        coerente com séries mais persistentes.
        """),
        mo.callout(mo.md(
            "Nas células mais perturbadas, a dinâmica diária não é mais aleatória no valor "
            "bruto dos padrões ordinais e da recorrência: o que muda é a proporção entre as "
            "duas partes. Mais da organização dessas séries é explicada pela sua parte "
            "linear, a persistência e o ciclo anual, e menos pela estrutura não linear além "
            "dela."), kind="success"),
        mo.md(r"""
        A terceira pergunta tem resposta mais curta. A perda de floresta de 1990 a 2000 é
        desmatamento de fato, sem a vegetação aberta natural, mas é uma medida pequena: na
        maioria das células ela é quase nula, e a correlação com a perda antecedente fica em
        0,56 no Xingu e 0,36 no Tapajós. Com ela, as associações do VPD no Xingu se repetem
        no mesmo sentido, com metade do tamanho, e as demais ficam compatíveis com zero; no
        Tapajós, o determinismo do VPD aparece com o sinal oposto ao da Tabela 1, sem
        paralelo na outra bacia.

        A quarta pergunta tem a resposta mais limpa. Ficando só com as células em que quase
        não havia vegetação natural aberta em 2000, 521 no Xingu e 437 no Tapajós, todas as
        associações da Tabela 1 se repetem com o mesmo tamanho e o mesmo sinal, e a da
        complexidade da temperatura no Xingu passa a excluir o zero. O contraste não vem do
        Cerrado: ele está dentro da própria floresta, entre a que foi convertida e a que não
        foi.
        """),
        mo.callout(mo.md(
            "Os quatro testes desta seção são complementares, motivados por perguntas feitas "
            "ao resultado depois de vê-lo, e estão registrados como tal (D-022). Não "
            "substituem a Tabela 1, que continua sendo o resultado pré-registrado."),
            kind="warn"),
    ])
    return


@app.cell(hide_code=True)
def _():
    lon_region = mo.ui.dropdown(options={load_region(s)["name"]: s for s in SLUGS},
                                value="Bacia do Rio Xingu", label="Bacia")
    lon_descriptor = mo.ui.dropdown(options={R.NAMES[d]: d for d in PRIMARY},
                                    value=R.NAMES["rqa_det"], label="Descritor")
    lon_variable = mo.ui.radio(options={v: k for k, v in R.VARIABLES.items()},
                               value="temperatura", label="Variável", inline=True)
    return lon_descriptor, lon_region, lon_variable


@app.function(hide_code=True)
def plot_longitudinal(slug, descriptor, variable):
    e = cells(slug)
    e = e[e.elegivel]
    res = model_results()
    res = res[res.modelo.str.startswith("longitudinal")]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.4), layout="constrained",
                                   width_ratios=[1, 1.15])
    dm_colors = {-1: COLORS["precip"], 0: COLORS["ink"], 1: COLORS["vpd"]}
    for dm, color in dm_colors.items():
        part = e[e[f"dm_{variable}"] == dm]
        ax1.scatter(part.mb_perda_floresta_2001_2012, part[f"delta_{variable}_{descriptor}"],
                    s=10, alpha=0.6, color=color,
                    label={-1: "m diminuiu", 0: "m igual", 1: "m aumentou"}[dm]
                    + f" ({len(part)})")
    ax1.legend(fontsize=8.5, loc="upper right", markerscale=1.6)
    ax1.axhline(0, color=COLORS["muted"], lw=1)
    ax1.set(xlabel="perda de floresta 2001–2012 (fração)",
            ylabel="mudança do descritor (2013–2024 menos 2001–2012)",
            title=f"{load_region(slug)['name']} · {R.NAMES[descriptor]}")
    labels = [f"{R.NAMES[d]} · {'temp.' if v == 't2m' else 'VPD'}" for v in R.VARIABLES
              for d in PRIMARY]
    series = [(s, model) for s in SLUGS for model in ["longitudinal", "longitudinal, m igual"]]
    for k, (s, model) in enumerate(series):
        rows = res[(res.bacia == s) & (res.modelo == model)].set_index(
            ["variavel", "descritor"]).reindex([(v, d) for v in R.VARIABLES for d in PRIMARY])
        y = np.arange(len(rows)) + (k - 1.5) * 0.18
        color = COLORS["ink"] if s == "xingu" else COLORS["t2m"]
        ax2.errorbar(rows.rho_parcial, y, xerr=[rows.rho_parcial - rows.ic_inf,
                                                rows.ic_sup - rows.rho_parcial],
                     fmt="o", ms=5, capsize=1.5, lw=1,
                     color=color, mfc=color if model == "longitudinal" else "white",
                     label=f"{load_region(s)['name']}"
                     + ("" if model == "longitudinal" else ", só m igual"))
    ax2.axvline(0, color=COLORS["muted"], lw=1)
    ax2.set_yticks(np.arange(len(labels)), labels, fontsize=9)
    ax2.invert_yaxis()
    ax2.set(xlim=(-0.5, 0.5), xlabel="ρ parcial (IC 95% por blocos de 1°)",
            title="Todos os descritores primários")
    handles, names = ax2.get_legend_handles_labels()
    fig.legend(handles, names, fontsize=8.5, loc="outside lower right", ncol=4,
               frameon=False)
    return fig


@app.cell(hide_code=True)
def _(lon_descriptor, lon_region, lon_variable):
    mo.vstack([
        mo.md(r"""
        ## ⏳ Dentro de cada célula, ao longo do tempo

        A comparação entre células tem uma fraqueza de origem: por mais controles que
        incluamos, células diferentes diferem em mil coisas não medidas. A comparação dentro
        de cada célula elimina essa fraqueza, porque compara o lugar com ele mesmo. A pergunta
        é se as células que mais perderam floresta entre 2001 e 2012 foram as que mais mudaram
        de dinâmica entre a primeira década, 2001–2012, e a segunda, 2013–2024. Toda
        característica fixa do lugar, como a latitude, o relevo, o tipo de solo ou a
        distância do oceano, se cancela na diferença.

        À esquerda, a Figura 5 mostra cada célula com a perda de floresta da primeira década
        no eixo horizontal e a mudança do descritor no vertical; à direita, a correlação
        parcial para todos os descritores primários, nas duas bacias.

        Antes de ler a figura, um detalhe de método que ela torna visível. A dimensão de
        imersão $m$ é escolhida pelo critério dos falsos vizinhos em cada década, como fixado
        no pré-registro, e em um quinto a um terço das células ela muda de uma década para a
        outra. Descritores que dependem do espaço de fases, como o determinismo, saltam
        quando $m$ muda, e o salto é maior que a mudança climática que queremos medir: são as
        três faixas horizontais do painel da esquerda, coloridas pela mudança de $m$. Por
        isso mostramos, ao lado do resultado pré-registrado (pontos cheios), o mesmo cálculo
        só com as células em que $m$ não mudou (pontos vazios). Os padrões ordinais têm ordem
        fixa e não dependem de $m$, e o erro de previsão quase não reage a ele.
        """),
        mo.hstack([lon_region, lon_descriptor, lon_variable], justify="start", gap=1),
        book.figure(plot_longitudinal(lon_region.value, lon_descriptor.value,
                                      lon_variable.value), "longitudinal",
                    "Figura 5. Esquerda: perda de floresta de 2001 a 2012 e mudança do descritor "
                    "entre 2013–2024 e 2001–2012, por célula, colorida pela mudança da dimensão "
                    "de imersão m entre as décadas. Direita: correlação parcial (controles: "
                    "latitude, água e altitude) com IC 95% por blocos de 1°, para os descritores "
                    "primários, com todas as células (cheios) e só aquelas em que m não mudou "
                    "(vazios). Na versão impressa, determinismo da temperatura, Xingu.", save=(lon_region.value, lon_descriptor.value, lon_variable.value)
                    == ("xingu", "rqa_det", "t2m")),
        mo.md(r"""
        A resposta é clara e quase uniforme: não há associação. Dentro de cada faixa, a
        nuvem de pontos não se inclina, e os intervalos de todos os descritores, nas duas
        bacias e com ou sem as células em que $m$ mudou, incluem zero ou ficam colados a
        ele. As células que mais desmataram na primeira década não mudaram de
        dinâmica mais do que as outras. As mudanças vistas no capítulo anterior, como o
        aumento do determinismo na maior parte das células, são comuns às
        células desmatadas e preservadas e combinam melhor com causas regionais, como a década
        mais quente e os El Niño de 2015–2016 e 2023–2024.

        Esse resultado nulo é exatamente o que se espera se o ERA5 não enxerga o desmatamento
        posterior ao seu mapa de vegetação. Ele não prova que o desmatamento não altere a
        dinâmica climática local, que há bons motivos físicos e observacionais para esperar
        [5, 6]; prova que, nas séries do ERA5, essa alteração não aparece.
        """),
    ])
    return


@app.function(hide_code=True)
@mo.cache
def surface_results():
    rows = []
    pairs = [("perda_antecedente", "lst_dia_seca_c", "entre células", "MODIS"),
             ("perda_antecedente", "era5_tmax_seca", "entre células", "ERA5"),
             ("mb_perda_floresta_2001_2012", "delta_lst_seca", "ao longo do tempo", "MODIS"),
             ("mb_perda_floresta_2001_2012", "delta_era5_tmax_seca", "ao longo do tempo", "ERA5")]
    for slug in SLUGS:
        e = cells(slug)[cells(slug).elegivel]
        for exposure, response, kind, source in pairs:
            rows.append({"bacia": slug, "comparacao": kind, "fonte": source,
                         **G.associate(e, exposure, response)})
    return pd.DataFrame(rows)


@app.function(hide_code=True)
def binned(frame, x, y, bins=10):
    ok = frame[[x, y]].dropna()
    q = pd.qcut(ok[x].rank(method="first"), bins, labels=False)
    return ok.groupby(q).agg(x=(x, "mean"), y=(y, "mean"), s=(y, "sem"))


@app.function(hide_code=True)
def plot_surface():
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.4), layout="constrained")
    panels = [("perda_antecedente", "lst_dia_seca_c", "era5_tmax_seca",
               "perda antecedente (fração sem floresta em 2000)",
               "anomalia em relação à média da bacia (°C)", "Entre células, estação seca"),
              ("mb_perda_floresta_2001_2012", "delta_lst_seca", "delta_era5_tmax_seca",
               "perda de floresta 2001–2012 (fração)",
               "aquecimento de 2001–2012 a 2013–2024 (°C)", "Ao longo do tempo, estação seca")]
    for ax, (x, modis, era5, xlabel, ylabel, title) in zip(axes, panels, strict=True):
        for slug, color in zip(SLUGS, [COLORS["ink"], COLORS["t2m"]], strict=True):
            e = cells(slug)[cells(slug).elegivel]
            for column, style, source in [(modis, "-o", "MODIS, superfície"),
                                          (era5, "--s", "ERA5, ar a 2 m")]:
                b = binned(e, x, column)
                y = b.y - (e[column].mean() if ax is axes[0] else 0)
                ax.errorbar(b.x, y, yerr=1.96 * b.s, fmt=style, color=color, ms=5, capsize=2,
                            lw=1.4, mfc=color if "MODIS" in source else "white",
                            label=f"{load_region(slug)['name'].replace('Bacia do Rio ', '')}"
                            f" · {source}")
        ax.axhline(0, color=COLORS["muted"], lw=1)
        ax.set(xlabel=xlabel, ylabel=ylabel, title=title)
    handles, names = axes[0].get_legend_handles_labels()
    fig.legend(handles, names, loc="outside lower center", ncol=4, frameon=False, fontsize=9)
    return fig


@app.cell(hide_code=True)
def _():
    _res = surface_results()
    _tab = _res.assign(
        Bacia=_res.bacia.map(lambda s: load_region(s)["name"].replace("Bacia do Rio ", "")),
        **{"IC 95%": [f"[{a:+.2f}; {b:+.2f}]" for a, b in zip(_res.ic_inf, _res.ic_sup,
                                                             strict=True)]})
    _tab = _tab[["Bacia", "comparacao", "fonte", "celulas", "rho_bruto", "rho_parcial",
                 "IC 95%"]].rename(columns={
        "comparacao": "Comparação", "fonte": "Fonte", "celulas": "Células",
        "rho_bruto": "ρ bruto", "rho_parcial": "ρ parcial"}).round(2)
    _q = {s: binned(cells(s)[cells(s).elegivel], "perda_antecedente", "lst_dia_seca_c", 4).y
          for s in SLUGS}
    mo.vstack([
        mo.md(r"""
        ## 🛰️ O que o satélite vê e o ERA5 não

        Os resultados anteriores apontam para uma mesma explicação: o ERA5 não enxerga o
        desmatamento que veio depois do seu mapa de vegetação. Até aqui, essa explicação se
        apoiava no próprio mapa do modelo. A temperatura da superfície medida pelo sensor
        MODIS, a bordo do satélite Terra, permite testá-la com uma observação independente
        [7]. O produto que usamos dá, a cada oito dias, a temperatura radiativa da superfície
        perto das 10h30 e das 22h30, num pixel de 1 km, e só aproveitamos as medidas de boa
        qualidade, sem nuvem. Ele mede outra grandeza que o ERA5, a temperatura da própria
        superfície, e não a do ar a 2 m; a comparação mais próxima no ERA5 é a temperatura
        máxima diária do ar. Usamos as duas na estação seca, de junho a setembro, quando a
        diferença entre floresta e pasto é maior.

        A Figura 6 faz as duas comparações deste capítulo com as duas fontes. À esquerda,
        entre células: a temperatura média de 2001 a 2024 em cada décimo das células,
        ordenadas pela perda antecedente, como anomalia em relação à média da bacia. À
        direita, ao longo do tempo: o aquecimento de cada célula entre as duas décadas, em
        cada décimo das células ordenadas pela perda de floresta de 2001 a 2012.
        """),
        book.figure(plot_surface(), "modis",
                    "Figura 6. Temperatura da superfície na estação seca medida pelo MODIS "
                    "(MOD11A2, diurna, círculos cheios) e temperatura máxima do ar a 2 m no ERA5 "
                    "(quadrados vazios), por décimo das células elegíveis. Esquerda: média de "
                    "2001 a 2024 contra a perda antecedente, como anomalia em relação à média de "
                    "cada bacia. Direita: mudança de 2001–2012 para 2013–2024 contra a perda de "
                    "floresta de 2001 a 2012. Hastes: IC 95% da média de cada décimo."),
        mo.callout(mo.md(nb.pt(
            "Temperatura diurna da superfície na estação seca, do quarto com menos ao quarto com "
            "mais perda antecedente das células: " + "; ".join(
                f"{load_region(s)['name'].replace('Bacia do Rio ', '')}, de "
                f"{_q[s].iloc[0]:.1f} a {_q[s].iloc[-1]:.1f} °C" for s in SLUGS) + ".")),
            kind="info"),
        mo.md(r"""
        As duas fontes contam histórias opostas. O satélite vê uma diferença enorme: de dia,
        na estação seca, a superfície das células com mais perda antecedente é de 6 a 7 °C
        mais quente que a das preservadas, e a diferença cresce de modo contínuo com a perda,
        sem limiar. Ela não vem da vegetação aberta natural do Cerrado, que também é quente:
        só nas células em que quase não havia vegetação natural aberta em 2000, a correlação
        parcial continua em 0,77 a 0,81, e o décimo mais convertido fica 5,6 °C mais quente
        que o menos convertido, nas duas bacias. É o efeito conhecido da troca de floresta
        por pasto: menos transpiração, menos energia gasta em evaporar água e mais energia
        aquecendo o chão [5, 8]. O ERA5
        não vê nada disso; a sua temperatura máxima do ar fica praticamente igual em todos os
        décimos e, no Tapajós, chega a ser mais fresca nas células com mais perda
        antecedente, as do
        planalto do sul. À direita, a diferença é ainda mais instrutiva. Nas células que não
        perderam floresta, o MODIS mostra um aquecimento de poucos décimos de grau entre as
        décadas, e o ERA5, um pouco mais, de meio grau a um grau: é o aquecimento regional.
        Nas que mais perderam, o MODIS mostra cerca de 1,5 °C, quatro a cinco vezes o das
        preservadas; o ERA5 mostra o mesmo aquecimento regional de todas as outras. A Tabela
        3 dá as correlações parciais, com os mesmos controles e a mesma inferência por
        blocos das seções anteriores.
        """),
        book.table(_tab, "modis",
                   "Tabela 3. Correlação de Spearman, bruta e parcial (controles: latitude, água "
                   "e altitude), entre a perturbação e a temperatura da estação seca pelo MODIS "
                   "(superfície, diurna) e pelo ERA5 (máxima do ar a 2 m), entre células (perda "
                   "antecedente) e ao longo do tempo (perda 2001–2012 contra a mudança entre as "
                   "décadas), com IC 95% por blocos de 1°.", selection=None),
        mo.callout(mo.md(
            "A observação por satélite evidencia, de forma independente, a limitação central "
            "do trabalho: o desmatamento aquece fortemente a superfície, entre lugares e ao "
            "longo do tempo, e o ERA5 não registra esse aquecimento. O resultado nulo da "
            "seção anterior não indica ausência de efeito do desmatamento; indica que a "
            "ferramenta não o enxerga."), kind="success"),
        mo.md(r"""
        Duas cautelas acompanham essa leitura. A temperatura da superfície e a do ar não são
        a mesma coisa, e a diferença entre floresta e pasto é sempre maior na primeira; ainda
        assim, medidas em torres e estações mostram que o ar também esquenta sobre áreas
        desmatadas, embora menos [8], de modo que um ERA5 que acompanhasse a vegetação
        mostraria ao menos parte desse sinal. E o MODIS só vê a superfície em dias sem nuvem,
        o que torna a sua série falhada demais para a análise não linear diária: ele serve
        aqui para verificar o ERA5, e não para substituí-lo. Ver só os dias limpos poderia
        enviesar a comparação, se as células desmatadas tivessem mais dias limpos que as
        preservadas; na estação seca, porém, quase todas as composições de oito dias são
        aproveitáveis, cerca de 378 das 384 possíveis em 24 anos na mediana das células, e
        acrescentar o número de composições válidas aos controles deixa a associação entre
        a perda antecedente e o LST em 0,80 no Xingu e 0,71 no Tapajós.
        """),
    ])
    return


@app.cell(hide_code=True)
def _():
    # Versão de referência da Figura 1 para as duas bacias (sem exibição).
    for _slug in SLUGS:
        book.figure(plot_landscape(_slug), "paisagem",
                    "Figura 1. Fração da área terrestre de cada célula sem floresta em 2000 "
                    "(perda antecedente) e desmatada entre 2000 e 2024, segundo o MapBiomas, "
                    "e fração de vegetação alta fixa usada pelo ERA5.", region=_slug)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 🧭 O que os dados permitem dizer

    A pergunta do trabalho era se a perturbação da floresta se associa à dinâmica climática
    diária. A resposta que os dados do ERA5 permitem dar tem três partes, e as três são
    necessárias.

    Primeiro, sim: entre células comparáveis em latitude, água e relevo, as que tinham mais
    conversão da floresta até 2000 têm uma dinâmica diária menos estruturada, com padrões
    ordinais do déficit de pressão de vapor mais próximos dos de um processo aleatório e
    menos determinismo nas recorrências da temperatura. O padrão se repete nas duas bacias e,
    no caso do déficit de pressão de vapor, não é efeito da vegetação natural do Cerrado: ele
    acompanha a conversão da floresta para a agropecuária.

    Segundo, essa diferença passa em boa parte pelo mapa de vegetação que o próprio ERA5 usa.
    Quando ele é levado em conta, a associação diminui ou desaparece. O contraste entre
    células, portanto, é em grande medida o contraste que o modelo calcula entre superfícies
    de floresta e de pasto, tal como estavam no início da década de 1990, e não uma
    consequência observada do desmatamento que veio depois.

    Terceiro, o desmatamento ocorrido durante a janela de análise não deixou marca na
    dinâmica das séries do ERA5: as células que mais perderam floresta entre 2001 e 2012 não
    mudaram mais do que as outras. A temperatura da superfície observada pelo satélite MODIS
    mostra que isso não é ausência de efeito: as mesmas células ficaram muito mais quentes
    que as preservadas, enquanto no ERA5 aqueceram igual a todas. Com uma reanálise de
    vegetação fixa, portanto, não é possível responder se o desmatamento em curso altera a
    dinâmica do clima; a resposta exigiria séries diárias que acompanhem a paisagem, como as
    de estações meteorológicas ou de um modelo com vegetação dinâmica.

    Nenhuma dessas partes autoriza falar em caos induzido pelo desmatamento ou em aproximação
    de um ponto de não retorno. O que os dados mostram é mais modesto e mais firme: as séries
    climáticas da Amazônia são não lineares, essa não linearidade varia com a geografia e com
    a história de uso da terra registrada no próprio modelo, o desmatamento aquece
    fortemente a superfície, como o satélite mostra, e a reanálise, sozinha, não consegue
    acompanhar essas mudanças da paisagem.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 📚 Referências

    [1] Hersbach, H. et al. The ERA5 global reanalysis. *Quarterly Journal of the Royal
    Meteorological Society*, v. 146, p. 1999–2049, 2020.

    [2] ECMWF. *IFS Documentation CY41R2, Part IV: Physical processes*. Reading: European
    Centre for Medium-Range Weather Forecasts, 2016.

    [3] Loveland, T. R. et al. Development of a global land cover characteristics database
    and IGBP DISCover from 1 km AVHRR data. *International Journal of Remote Sensing*,
    v. 21, p. 1303–1330, 2000.

    [4] Legendre, P. Spatial autocorrelation: trouble or new paradigm? *Ecology*, v. 74,
    p. 1659–1673, 1993.

    [5] Lawrence, D.; Vandecar, K. Effects of tropical deforestation on climate and
    agriculture. *Nature Climate Change*, v. 5, p. 27–36, 2015.

    [6] Khanna, J.; Medvigy, D.; Fueglistaler, S.; Walko, R. Regional dry-season climate
    changes due to three decades of Amazonian deforestation. *Nature Climate Change*, v. 7,
    p. 200–204, 2017.

    [7] Wan, Z. New refinements and validation of the collection-6 MODIS land-surface
    temperature/emissivity product. *Remote Sensing of Environment*, v. 140, p. 36–45, 2014.

    [8] Baker, J. C. A.; Spracklen, D. V. Climate benefits of intact Amazon forests and the
    biophysical consequences of disturbance. *Frontiers in Forests and Global Change*, v. 2,
    47, 2019.
    """)
    return


if __name__ == "__main__":
    app.run()
