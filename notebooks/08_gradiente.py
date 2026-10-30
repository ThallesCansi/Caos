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


@app.function(hide_code=True)
@mo.cache
def preregistered():
    """Os 16 testes pré-registrados, com Holm, BH e a inferência espacial de D-028."""
    res = model_results()
    pre = res[res.modelo == "pré-registrado"].reset_index(drop=True)
    spatial = pd.DataFrame([
        G.spatial_inference(cells(row.bacia)[cells(row.bacia).elegivel], "perda_antecedente",
                            f"z_{row.variavel}_{row.descritor}")
        for row in pre.itertuples()]).drop(columns="moran_residuos")
    pre = pd.concat([pre, spatial], axis=1)
    pre["p_holm"] = G.adjust(pre.p_blocos, "holm")
    pre["p_bh"] = G.adjust(pre.p_blocos, "fdr_bh")
    pre["p_n_efetivo_holm"] = G.adjust(pre.p_n_efetivo, "holm")
    return pre


@app.cell(hide_code=True)
def _():
    _pre = preregistered().copy()
    _pre["Bacia"] = _pre.bacia.map(lambda s: load_region(s)["name"].replace("Bacia do Rio ", ""))
    _pre["Descritor"] = _pre.descritor.map(R.NAMES)
    _pre["Variável"] = _pre.variavel.map(R.VARIABLES)
    _pre["IC 95%"] = [f"[{a:+.2f}; {b:+.2f}]" for a, b in zip(_pre.ic_inf, _pre.ic_sup,
                                                             strict=True)]
    _tab = _pre[["Bacia", "Descritor", "Variável", "celulas", "rho_bruto", "rho_parcial",
                 "IC 95%", "p_holm", "p_bh", "moran_residuos", "n_efetivo",
                 "p_n_efetivo"]].rename(columns={
        "celulas": "Células", "rho_bruto": "ρ bruto", "rho_parcial": "ρ parcial",
        "p_holm": "p Holm", "p_bh": "p BH", "moran_residuos": "Moran dos resíduos",
        "n_efetivo": "n efetivo", "p_n_efetivo": "p (n efetivo)"}).round(
        {"ρ bruto": 2, "ρ parcial": 2, "Moran dos resíduos": 2, "n efetivo": 0,
         "p Holm": 3, "p BH": 3, "p (n efetivo)": 3})
    _tab["n efetivo"] = _tab["n efetivo"].astype(int)
    _n_holm = int((_pre.p_holm < 0.05).sum())
    _n_eff = int((_pre.p_n_efetivo < 0.05).sum())
    mo.vstack([
        mo.md(r"""
        ## 📊 O resultado principal e duas objeções

        A Tabela 1 traz o resultado pré-registrado para os quatro descritores primários, nas
        duas variáveis e nas duas bacias: a correlação bruta, a parcial, o intervalo de 95%
        obtido por reamostragem de blocos espaciais de 1° e o índice de Moran dos resíduos,
        que mede quanto da variação não explicada ainda se parece entre células vizinhas
        (zero indicaria independência; 1, semelhança total) [4]. Como são 16 testes, a
        tabela traz também o p-valor de cada um, obtido da mesma reamostragem que dá o
        intervalo, corrigido para comparações múltiplas por dois métodos: o de Holm, que
        controla a chance de um único falso positivo entre os 16, e o de Benjamini e
        Hochberg, que controla a fração esperada de falsos positivos entre os destacados.
        As duas últimas colunas fazem outra correção, explicada abaixo, para a semelhança
        entre células vizinhas (D-028).
        """),
        book.table(_tab, "resultado_preregistrado",
                   "Tabela 1. Resultado pré-registrado: correlação de Spearman entre perda "
                   "antecedente de floresta e z dos descritores primários, bruta e parcial "
                   "(controles: latitude, água e altitude), com IC 95% por bootstrap em blocos "
                   "de 1°, p-valor da mesma reamostragem corrigido por Holm e por "
                   "Benjamini–Hochberg sobre os 16 testes, I de Moran dos resíduos, n efetivo "
                   "de Clifford et al. e p-valor com esse n, sem correção (D-028).",
                   selection=None),
        mo.md(rf"""
        Nas duas bacias, a perturbação antecedente se associa a uma dinâmica menos
        estruturada. Quanto maior a perda até 2000, maior a entropia de permutação e menor a
        complexidade do VPD, e menor o determinismo da temperatura, com intervalos que não
        incluem zero. No Xingu, a associação também aparece no erro de previsão e no
        determinismo do VPD e nos padrões ordinais da temperatura; no Tapajós, nem os padrões
        ordinais nem o erro de previsão da temperatura mostram associação. Os valores
        parciais que se destacam ficam entre 0,2 e 0,46 em módulo: associações moderadas,
        bem menores que as brutas, que passavam de 0,6.

        Dos 16 testes, {_n_holm} continuam abaixo de 0,05 depois da correção de Holm, a mais
        exigente: o par ordinal do VPD e o determinismo da temperatura nas duas bacias e,
        no Xingu, também o determinismo e a previsão do VPD e a previsão da temperatura.

        O índice de Moran dos resíduos, entre 0,4 e 0,75, mostra que a variação não explicada
        continua organizada no espaço; nenhuma das 999 permutações dos resíduos entre as
        células chega perto dele. Isso tem duas consequências. A primeira é estatística:
        células vizinhas valem menos que células independentes, e os blocos de 1° só
        corrigem parte disso. Uma forma direta de medir quanto se perde é o tamanho efetivo
        da amostra de Clifford, Richardson e Hémon [9], que desconta da correlação a parte
        explicável por as duas grandezas variarem devagar no espaço. Ele cai de cerca de 650
        células para 22 a 55 no Xingu e 94 a 213 no Tapajós, e com esse n {_n_eff} dos 16
        testes ficam abaixo de 0,05: os mesmos pares que se repetem nas duas bacias, o
        determinismo da temperatura e a entropia e a complexidade do VPD, e a previsão do VPD
        no Xingu. Com a correção de Holm por cima, só o determinismo da temperatura no
        Tapajós resiste. A leitura que adotamos, a de só considerar sólidos os efeitos que se
        repetem nas duas bacias, é a que sobrevive a essa conta conservadora, e mesmo esses
        efeitos são evidência moderada, e não forte. A segunda consequência é substantiva:
        existe estrutura espacial que nem a perturbação nem os controles capturam, e é nela
        que podem estar os confundidores restantes. A seção final do capítulo volta a esse
        ponto.

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
        superfície, e não a do ar a 2 m; nas séries diárias do ERA5, a comparação mais
        próxima é a temperatura máxima diária do ar. Usamos as duas na estação seca, de junho
        a setembro, quando a diferença entre floresta e pasto é maior. No fim desta seção,
        uma comparação complementar usa a temperatura da superfície do próprio ERA5 no
        horário do satélite.

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


@app.function(hide_code=True)
@mo.cache
def overpass_results():
    """Comparativo F2e (D-027): skt e t2m do ERA5 às 10h30 solares contra o LST do MODIS."""
    rows = []
    veg = (*G.CONTROLS, "era5_veg_alta", "era5_veg_baixa")
    pairs = [("perda_antecedente", "lst_dia_seca_c", G.CONTROLS, "entre células",
              "MODIS, superfície"),
             ("perda_antecedente", "era5_skt_1030_seca", G.CONTROLS, "entre células",
              "ERA5, pele às 10h30"),
             ("perda_antecedente", "era5_skt_1030_seca_limpo", G.CONTROLS, "entre células",
              "ERA5, pele às 10h30, céu limpo"),
             ("perda_antecedente", "era5_t2m_1030_seca", G.CONTROLS, "entre células",
              "ERA5, ar às 10h30"),
             ("perda_antecedente", "era5_skt_1030_seca", veg, "entre células",
              "ERA5, pele às 10h30, com a vegetação do ERA5"),
             ("mb_perda_floresta_2001_2012", "delta_lst_seca", G.CONTROLS, "ao longo do tempo",
              "MODIS, superfície"),
             ("mb_perda_floresta_2001_2012", "delta_era5_skt_1030_seca", G.CONTROLS,
              "ao longo do tempo", "ERA5, pele às 10h30"),
             ("mb_perda_floresta_2001_2012", "delta_era5_t2m_1030_seca", G.CONTROLS,
              "ao longo do tempo", "ERA5, ar às 10h30")]
    for slug in SLUGS:
        e = cells(slug)[cells(slug).elegivel]
        for exposure, response, controls, kind, source in pairs:
            # o contraste em °C é bruto; na linha com a vegetação do ERA5 ele só se repetiria
            b = binned(e, exposure, response)
            contrast = b.y.iloc[-1] - b.y.iloc[0] if controls == G.CONTROLS else np.nan
            rows.append({"bacia": slug, "comparacao": kind, "fonte": source,
                         "contraste": contrast,
                         **G.associate(e, exposure, response, controls)})
    return pd.DataFrame(rows)


@app.function(hide_code=True)
def plot_overpass():
    fig, axes = plt.subplots(2, 2, figsize=(14, 9), layout="constrained", sharex="col")
    series = [("lst_dia_seca_c", "delta_lst_seca", "-o", COLORS["ink"], "MODIS, superfície"),
              ("era5_skt_1030_seca", "delta_era5_skt_1030_seca", "--s", COLORS["t2m"],
               "ERA5, pele às 10h30"),
              ("era5_skt_1030_seca_limpo", None, ":^", COLORS["vpd"],
               "ERA5, pele às 10h30, céu limpo"),
              ("era5_t2m_1030_seca", "delta_era5_t2m_1030_seca", "-.D", COLORS["muted"],
               "ERA5, ar a 2 m às 10h30")]
    for row, slug in zip(axes, SLUGS, strict=True):
        e = cells(slug)[cells(slug).elegivel]
        name = load_region(slug)["name"].replace("Bacia do Rio ", "")
        for ax, x, col, title in [
                (row[0], "perda_antecedente", 0, f"{name}: entre células"),
                (row[1], "mb_perda_floresta_2001_2012", 1, f"{name}: ao longo do tempo")]:
            for *columns, style, color, label in series:
                column = columns[col]
                if column is None:
                    continue
                b = binned(e, x, column)
                y = b.y - (e[column].mean() if col == 0 else 0)
                ax.errorbar(b.x, y, yerr=1.96 * b.s, fmt=style, color=color, ms=5,
                            capsize=2, lw=1.4, label=label)
            ax.axhline(0, color=COLORS["muted"], lw=1)
            ax.set(title=title, ylabel="anomalia em relação à média da bacia (°C)" if col == 0
                   else "aquecimento de 2001–2012 a 2013–2024 (°C)")
    axes[1, 0].set_xlabel("perda antecedente (fração sem floresta em 2000)")
    axes[1, 1].set_xlabel("perda de floresta 2001–2012 (fração)")
    handles, names = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, names, loc="outside lower center", ncol=4, frameon=False, fontsize=9)
    return fig


@app.cell(hide_code=True)
def _():
    _res = overpass_results()
    _tab = _res.assign(
        Bacia=_res.bacia.map(lambda s: load_region(s)["name"].replace("Bacia do Rio ", "")),
        **{"IC 95%": [f"[{a:+.2f}; {b:+.2f}]" for a, b in zip(_res.ic_inf, _res.ic_sup,
                                                             strict=True)]})
    _tab = _tab[["Bacia", "comparacao", "fonte", "rho_parcial", "IC 95%", "contraste"]].rename(
        columns={"comparacao": "Comparação", "fonte": "Medida", "rho_parcial": "ρ parcial",
                 "contraste": "Décimo mais − menos perturbado (°C)"}).round(2)
    mo.vstack([
        mo.md(r"""
        ### Uma comparação mais justa: a temperatura de pele do ERA5 na hora do satélite

        A comparação acima tem um ponto fraco evidente. O MODIS mede a temperatura radiativa
        da superfície perto das 10h30, em dias sem nuvem, e a máxima diária do ar a 2 m é
        outra grandeza, medida em outra hora e em todos os dias. Parte do contraste entre as
        duas fontes poderia vir só disso. O ERA5 também calcula uma temperatura de pele, a da
        própria superfície do modelo, e por isso fizemos uma comparação complementar, fixada
        antes do cálculo (decisão D-027): baixamos a temperatura de pele, a do ar a 2 m e a
        cobertura de nuvens às 13, 14 e 15 horas UTC na estação seca de 2001 a 2024 e, em
        cada célula, interpolamos para as 10h30 solares locais, o horário nominal da passagem
        do Terra. Calculamos a média de todos os dias e também a média só dos dias com menos
        de 30% de cobertura de nuvens nesse horário, o que aproxima a amostragem do satélite.
        Ela não substitui a Tabela 3; serve para saber quanto do contraste vinha da
        diferença de grandeza e de horário.

        A Figura 7 repete os décimos da Figura 6 com essas medidas, uma bacia em cada linha.
        À esquerda, entre células, a temperatura de pele do ERA5 às 10h30 sobe com a perda
        antecedente, ao contrário da máxima do ar, mas muito menos que a superfície do MODIS:
        do décimo menos ao mais perturbado, cerca de 2,4 °C no Xingu e 1,2 °C no Tapajós,
        contra 6 a 7 °C no satélite. Restringir aos dias de céu limpo não aproxima as duas
        fontes; a diferença até diminui um pouco. A temperatura do ar no mesmo horário fica
        mais fresca nas células com mais perda, como a máxima diária, porque elas estão no sul
        mais alto das bacias. À direita, ao longo do tempo, nenhuma medida do ERA5 acompanha o
        aquecimento de 1,3 a 1,4 °C que o MODIS vê nas células que mais perderam floresta
        entre 2001 e 2012. No Xingu, o ERA5 mostra o mesmo aquecimento regional, de meio
        grau, em todos os décimos; no Tapajós, ele aquece mais as células sem perda, as do
        norte da bacia, perto de 1 °C, do que as que mais desmataram, perto de meio grau, o
        oposto do satélite.
        """),
        book.figure(plot_overpass(), "passagem",
                    "Figura 7. Comparativo complementar (D-027). Temperatura da superfície na "
                    "estação seca pelo MODIS (diurna) e, no ERA5, temperatura de pele e do ar a "
                    "2 m interpoladas para as 10h30 solares (passagem do Terra), em todos os dias "
                    "e só nos dias com cobertura de nuvens abaixo de 0,3, por décimo das células "
                    "elegíveis. Esquerda: média de 2001 a 2024 contra a perda antecedente, como "
                    "anomalia em relação à média da bacia. Direita: mudança de 2001–2012 para "
                    "2013–2024 contra a perda de floresta de 2001 a 2012. Hastes: IC 95%."),
        mo.md(r"""
        A Tabela 4 traz as correlações parciais com os mesmos controles da Tabela 3 e o
        contraste em graus entre os décimos extremos. Entre células, a temperatura de pele do
        ERA5 se associa à perda antecedente com uma correlação parcial perto de 0,3 nas duas
        bacias, um terço da do MODIS, e o intervalo exclui zero. No Xingu essa associação
        desaparece quando a vegetação alta e baixa do próprio ERA5 entra nos controles: o que
        o modelo registra ali é o desmatamento anterior a 2000 que já estava no seu mapa de
        vegetação. No Tapajós ela resiste ao mesmo controle, o que sugere outra rota no
        modelo, como a umidade do solo mais baixa no planalto do sul. Ao longo do tempo,
        nenhuma associação do ERA5 é positiva; no Tapajós, a da pele chega a ser negativa,
        com as células que mais desmataram aquecendo um pouco menos que as outras na
        superfície do modelo.
        """),
        book.table(_tab, "passagem",
                   "Tabela 4. Comparativo complementar (D-027). Correlação parcial de Spearman "
                   "(controles: latitude, água e altitude; na linha indicada, também a "
                   "vegetação alta e baixa do ERA5) entre a perturbação e a temperatura da "
                   "estação seca às 10h30 solares no ERA5, ao lado do MODIS, com IC 95% por "
                   "blocos de 1° e a diferença bruta entre as médias do décimo mais e do menos "
                   "perturbado.",
                   selection=None),
        mo.callout(mo.md(
            "A comparação com a mesma grandeza e o mesmo horário qualifica a Tabela 3 sem "
            "mudar a sua leitura. Entre células, parte do contraste vinha da diferença de "
            "grandeza: a superfície do ERA5 às 10h30 registra cerca de um quarto a um terço "
            "do aquecimento que o satélite vê, e no Xingu só pelo mapa de vegetação fixo do "
            "modelo. Ao longo do tempo, a cegueira se confirma: nenhuma grandeza do ERA5 "
            "registra o aquecimento da superfície onde a floresta foi perdida depois de 2000."),
            kind="info"),
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


@app.function(hide_code=True)
@mo.cache
def residual_correlograms():
    """Correlograma dos resíduos dos postos, nos pares que se repetem nas duas bacias."""
    rows = []
    for slug in SLUGS:
        e = cells(slug)[cells(slug).elegivel]
        for var, d in [("t2m", "rqa_det"), ("vpd", "pe_entropy")]:
            data = e[["perda_antecedente", f"z_{var}_{d}", "latitude", "longitude",
                      *G.CONTROLS]].dropna()
            data = data.loc[:, ~data.columns.duplicated()]
            ctrl = data[list(G.CONTROLS)].to_numpy()
            rx = G._residual_ranks(data.perda_antecedente.to_numpy(), ctrl)
            ry = G._residual_ranks(data[f"z_{var}_{d}"].to_numpy(), ctrl)
            for name, values in [("exposição", rx), ("resposta", ry)]:
                rows.append(G.correlogram(values, data.latitude, data.longitude).assign(
                    bacia=slug, par=f"{R.NAMES[d]} · {R.VARIABLES[var]}", serie=name))
    return pd.concat(rows, ignore_index=True)


@app.function(hide_code=True)
def plot_correlogram():
    res = residual_correlograms()
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.6), sharey=True, layout="constrained")
    styles = {"exposição": ("-", "o"), "resposta": ("--", "s")}
    pairs = list(res.par.unique())
    colors = dict(zip(pairs, [COLORS["t2m"], COLORS["vpd"]], strict=True))
    for ax, slug in zip(axes, SLUGS, strict=True):
        part = res[res.bacia == slug]
        for (pair, serie), g in part.groupby(["par", "serie"], sort=False):
            if serie == "exposição" and pair != pairs[0]:
                continue  # a exposição é a mesma nos dois pares
            line, marker = styles[serie]
            label = ("perda antecedente (resíduo)" if serie == "exposição"
                     else f"z de {pair} (resíduo)")
            ax.plot(g.distancia, g.moran, line, marker=marker, ms=4,
                    color=COLORS["ink"] if serie == "exposição" else colors[pair], label=label)
        ax.axhline(0, color=COLORS["muted"], lw=1)
        ax.axvline(1.0, color=COLORS["muted"], lw=1, ls=":")
        ax.set(title=load_region(slug)["name"], xlabel="distância entre células (graus)",
               ylabel="I de Moran")
    handles, names = axes[0].get_legend_handles_labels()
    fig.legend(handles, names, loc="outside lower center", ncol=3, frameon=False)
    return fig


@app.function(hide_code=True)
@mo.cache
def placebo_results():
    """Exposição-placebo (D-028): perda de 2013–2024 contra o z de 2001–2012."""
    rows = []
    for slug in SLUGS:
        e = cells(slug)[cells(slug).elegivel]
        forest = e[e.floresta_frac_2000 >= 0.5 * e.fracao_terra]
        for var in R.VARIABLES:
            for d in PRIMARY:
                for exposure, label in [("perda_antecedente", "perda antecedente"),
                                        ("mb_perda_floresta_2013_2024",
                                         "placebo: perda de 2013–2024")]:
                    rows.append({"bacia": slug, "variavel": var, "descritor": d,
                                 "exposicao_rotulo": label,
                                 **G.associate(forest, exposure, f"z12_{var}_{d}")})
    return pd.DataFrame(rows)


@app.cell(hide_code=True)
def _():
    _pl = placebo_results()
    _pl["celula"] = [f"{r:+.2f} [{a:+.2f}; {b:+.2f}]" for r, a, b in zip(
        _pl.rho_parcial, _pl.ic_inf, _pl.ic_sup, strict=True)]
    _tab = _pl.pivot_table(index=["bacia", "variavel", "descritor"],
                           columns="exposicao_rotulo", values="celula", aggfunc="first",
                           sort=False).reset_index()
    _tab.insert(0, "Bacia", _tab.pop("bacia").map(
        lambda s: load_region(s)["name"].replace("Bacia do Rio ", "")))
    _tab.insert(1, "Variável", _tab.pop("variavel").map(R.VARIABLES))
    _tab.insert(2, "Descritor", _tab.pop("descritor").map(R.NAMES))
    _tab.columns.name = None
    _n = {s: int(_pl[(_pl.bacia == s)].celulas.iloc[0]) for s in SLUGS}
    mo.vstack([
        mo.md(r"""
        ## 🧪 Duas checagens da inferência

        A Tabela 1 mostrou que a variação não explicada continua organizada no espaço e que,
        descontada essa organização, o número efetivo de células independentes é bem menor
        que o número de células. A Figura 8 mostra de onde vem isso. Ela traz o correlograma
        dos resíduos dos dois pares que se repetem nas duas bacias: o índice de Moran entre
        células a cada distância, de um quarto de grau a cinco graus, para a perda
        antecedente e para o descritor, depois de retirados os controles. A linha
        pontilhada marca 1°, o tamanho dos blocos usados nos intervalos.
        """),
        book.figure(plot_correlogram(), "correlograma",
                    "Figura 8. Correlograma (I de Moran por classe de distância de 0,25°) dos "
                    "resíduos dos postos, depois de retirados a latitude, a água e a altitude, "
                    "da perda antecedente e do z do determinismo da temperatura e da entropia "
                    "de permutação do VPD, nas células elegíveis. Linha pontilhada: 1°, o "
                    "tamanho dos blocos do bootstrap (D-028)."),
        mo.md(r"""
        A semelhança entre células cai com a distância, mas não some dentro de um bloco.
        Depois de retirados os controles, a da perda antecedente se anula perto de 1° no
        Tapajós e perto de 2° no Xingu, onde o desmatamento avançou em frentes mais largas;
        a dos descritores vai mais longe, até 2 a 2,5°, sobretudo a da entropia do VPD.
        Os blocos de 1° capturam a parte mais forte dessa semelhança, mas não toda, e
        células de blocos vizinhos ainda se parecem: é por isso que o tamanho efetivo da
        amostra cai tanto e que os intervalos da Tabela 1 devem ser lidos como um pouco
        otimistas. A conclusão prática é a que já adotamos, só considerar os efeitos que
        se repetem nas duas bacias, e com o devido cuidado.

        A segunda checagem ataca a objeção mais séria a qualquer comparação entre lugares:
        o desmatamento não avança ao acaso, e sim onde o acesso, o relevo e o clima já o
        favoreciam. Se a associação da Tabela 1 vier só disso, ela deveria aparecer também
        com o desmatamento que ainda não tinha acontecido. A Tabela 5 testa essa ideia com
        uma exposição-placebo, fixada antes do cálculo (D-028): a perda de floresta de 2013 a
        2024, que não pode ter causado a dinâmica de 2001 a 2012, contra os descritores
        dessa primeira década, ao lado da perda antecedente, nas mesmas células, as que
        ainda eram ao menos metade floresta em 2000.
        """),
        book.table(_tab, "placebo",
                   "Tabela 5. Exposição-placebo (D-028, exploratória). Correlação parcial de "
                   "Spearman, com IC 95% por blocos de 1°, entre o z dos descritores primários "
                   "em 2001–2012 e a perda antecedente ou a perda de floresta de 2013 a 2024 "
                   f"(MapBiomas), nas células elegíveis com ao menos 50% de floresta em 2000 "
                   f"({_n['xingu']} no Xingu, {_n['tapajos']} no Tapajós).", selection=None),
        mo.md(r"""
        No Xingu, o placebo não se associa a nada: todas as correlações ficam perto de zero,
        enquanto a perda antecedente, nas mesmas células, mantém as associações do VPD e do
        determinismo da temperatura. Ali, a associação não é um retrato de onde o
        desmatamento iria avançar. No Tapajós, a leitura é mais dividida. O placebo também
        fica perto de zero no VPD e no determinismo da temperatura, os pares que se repetem
        nas duas bacias, mas aparece nos padrões ordinais e na previsão da temperatura,
        justamente onde a perda antecedente não mostra nada. As células do Tapajós que
        seriam desmatadas depois de 2012 já tinham uma temperatura com dinâmica diferente
        antes disso. Essa é a seleção
        geográfica de que a objeção fala: ela existe, mas não explica os efeitos que o
        trabalho destaca.
        """),
        mo.callout(mo.md(
            "As duas checagens tornam a conclusão mais modesta, não a invertem. A associação "
            "entre perda antecedente e dinâmica diária é moderada e, depois de descontada a "
            "semelhança entre vizinhas, só se sustenta nos pares que se repetem nas duas "
            "bacias; ela não é um retrato de onde o desmatamento viria a avançar, embora no "
            "Tapajós essa seleção exista em outros descritores."), kind="info"),
    ])
    return


@app.function(hide_code=True)
@mo.cache
def comparative_associations():
    """Perda antecedente contra os descritores dos comparativos de D-027 (exploratórios)."""
    from amazon_chaos.nonlinear import estimators as E
    from amazon_chaos.nonlinear import extremes as X
    from amazon_chaos.nonlinear import multivariate as M
    from amazon_chaos.nonlinear import smap as SM

    rows = []
    for slug in SLUGS:
        cfg = load_region(slug)
        e = cells(slug)[cells(slug).elegivel]
        sm = SM.load(cfg, SPEC)
        for (var, h), g in sm.groupby(["variable", "horizon"]):
            frame = e.join(g.set_index("cell_id").gain.rename("y"), how="inner")
            rows.append({"bacia": slug, "grupo": "S-map", "variavel": R.VARIABLES[var],
                         "medida": f"ganho sobre o linear, {int(h)} dia" + ("s" if h > 1 else ""),
                         **G.associate(frame, "perda_antecedente", "y")})
        sub = pd.read_parquet(E.output_dir(cfg, SPEC) / "subamostra.parquet")
        for (var, d), g in sub.groupby(["variable", "descriptor"]):
            frame = e.join(g.set_index("cell_id").z.rename("y"), how="inner")
            rows.append({"bacia": slug, "grupo": "Lyapunov e Cao (subamostra)",
                         "variavel": R.VARIABLES[var],
                         "medida": {"wolf": "z do Lyapunov de Wolf",
                                    "kantz": "z do Lyapunov de Kantz",
                                    "cao_de2": "z do D_E2 de Cao"}[d],
                         **G.associate(frame, "perda_antecedente", "y")})
        multi = pd.read_parquet(M.output_dir(cfg, SPEC) / "subamostra.parquet")
        multi = multi[multi.surrogate < 0].set_index("cell_id")
        for k, name in enumerate(M.RULES["channels"]):
            frame = e.join(multi[f"alvo{k}_smap_ganho"].rename("y"), how="inner")
            rows.append({"bacia": slug, "grupo": "Temperatura + umidade (subamostra)",
                         "variavel": {"t2m": "temperatura", "q": "umidade específica"}[name],
                         "medida": "ganho do S-map conjunto, 1 dia",
                         **G.associate(frame, "perda_antecedente", "y")})
        ext = X.cell_table(cfg, SPEC)
        ext = ext[ext.elegivel]
        for var, label in [("tmax", "máxima"), ("tmin", "mínima"), ("amplitude", "amplitude")]:
            for d in PRIMARY:
                column = f"z_{var}_{d}"
                if column in ext and ext[column].notna().sum() > 30:
                    rows.append({"bacia": slug, "grupo": "Mínima, máxima e amplitude",
                                 "variavel": label, "medida": f"z: {R.NAMES[d]}",
                                 **G.associate(ext, "perda_antecedente", column)})
    return pd.DataFrame(rows)


@app.cell(hide_code=True)
def _():
    _r = comparative_associations()
    _r["ci"] = [f"{r:+.2f} [{a:+.2f}; {b:+.2f}]" for r, a, b in zip(
        _r.rho_parcial, _r.ic_inf, _r.ic_sup, strict=True)]
    _r["sinal"] = np.where(_r.exclui_zero, np.sign(_r.rho_parcial), 0)
    _keys = ["grupo", "variavel", "medida"]
    _tab = _r.pivot_table(index=_keys, columns="bacia", values="ci", aggfunc="first",
                          sort=False)
    _both = _r.pivot_table(index=_keys, columns="bacia", values="sinal", sort=False)
    _tab["Nas duas bacias"] = np.where((_both.xingu == _both.tapajos) & (_both.xingu != 0),
                                       "sim", "")
    _tab = _tab.rename(columns={s: load_region(s)["name"].replace("Bacia do Rio ", "")
                                for s in SLUGS}).reset_index().rename(columns={
        "grupo": "Comparativo", "variavel": "Variável", "medida": "Medida"})
    _tab.columns.name = None
    mo.vstack([
        mo.md(r"""
        ## 🧩 Os comparativos diante da perturbação

        As extensões da revisão crítica (D-027) produziram, além dos descritores do
        pré-registro, outras medidas da dinâmica de cada célula: o ganho do S-map sobre a
        previsão linear, em todas as células; os expoentes de Wolf e de Kantz e o $D_{E2}$ de
        Cao, na subamostra de cerca de 60 células por bacia, junto com o ganho de prever cada
        variável com temperatura e umidade juntas; e os descritores da temperatura mínima, da
        máxima e da amplitude diária. A Tabela 6 dá a correlação parcial de cada
        uma com a perda antecedente, com os controles e a inferência da Tabela 1. Tudo aqui
        é exploratório, e a regra fixada antes foi só destacar o que aparece nas duas
        bacias, com o mesmo sinal e intervalos que excluem zero.
        """),
        book.table(_tab, "comparativos",
                   "Tabela 6. Comparativo, exploratório (D-027). Correlação parcial "
                   "(controles: latitude, água e altitude) entre a perda antecedente e as "
                   "medidas dos comparativos, com IC 95% por blocos de 1°; \"sim\": o intervalo "
                   "exclui zero com o mesmo sinal nas duas bacias.", selection=None),
        mo.md(r"""
        Três padrões aparecem nas duas bacias. O ganho do S-map é maior nas células com
        mais perda antecedente, na temperatura no horizonte de um dia e no VPD nos de três
        e sete dias: a previsão local tira um pouco mais de vantagem do estado atual onde a
        floresta já tinha sido convertida, embora o ganho continue minúsculo em toda parte,
        e no VPD a vários dias seja praticamente nulo na maioria das células. O $D_{E2}$ de Cao no VPD é menor
        nessas mesmas células, isto é, a dependência do passado reconstruído fica ainda mais
        perto da de um processo estocástico, o que combina com a entropia de permutação
        maior da Tabela 1. E o determinismo da amplitude diária, como o da temperatura
        média, é menor onde a perda é maior. Nas extremas, a máxima repete a média, com
        associações nos padrões ordinais no Xingu e nenhuma no Tapajós, e a mínima não se
        associa a nada. Nenhum desses padrões é um sinal novo que a média escondesse; eles
        reforçam, por outros caminhos e com a mesma cautela, a leitura de que as células
        convertidas têm uma dinâmica diária um pouco menos estruturada. O ganho de juntar
        temperatura e umidade, por sua vez, não se associa à perda em nenhuma das bacias: a
        interação entre as duas variáveis, que já era quase toda linear, não muda com a
        conversão da floresta.
        """),
    ])
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
    acompanha a conversão da floresta para a agropecuária. É uma associação moderada:
    descontada a semelhança entre células vizinhas, só os pares que se repetem nas duas
    bacias ficam de pé, e a exposição-placebo mostra que ela não é apenas um retrato de
    onde o desmatamento iria avançar.

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


@app.function(hide_code=True)
def support_table(models: list[str], by_exposure: bool = False) -> pd.DataFrame:
    res = model_results()
    res = res[res.modelo.isin(models)]
    return pd.DataFrame({
        "Bacia": res.bacia.map(lambda s: load_region(s)["name"].replace("Bacia do Rio ", "")),
        "Variável": res.variavel.map(R.VARIABLES), "Descritor": res.descritor.map(R.NAMES),
        ("Exposição" if by_exposure else "Modelo"):
            res.exposicao.map(G.EXPOSURES) if by_exposure else res.modelo,
        "Células": res.celulas,
        "ρ parcial [IC 95%]": [f"{r:+.2f} [{a:+.2f}; {b:+.2f}]" for r, a, b in zip(
            res.rho_parcial, res.ic_inf, res.ic_sup, strict=True)],
        "p (blocos)": res.p_blocos.round(3)})


@app.cell(hide_code=True)
def _():
    mo.vstack([
        mo.md(r"""
        ## 📎 Tabelas de apoio

        As Figuras 3, 4 e 5 mostram em gráficos resultados que também precisam estar em
        números. A Tabela A1 traz os três modelos da Figura 3, a Tabela A2 as outras medidas
        de perturbação da Figura 4 e a Tabela A3 a comparação ao longo do tempo da Figura 5,
        pré-registrada, com a sensibilidade das células em que a dimensão de imersão não
        mudou entre as metades. São pré-registradas só a linha correspondente da Tabela
        A1, que repete a Tabela 1, e a linha de todas as células da Tabela A3; o resto é
        exploratório ou de sensibilidade.
        """),
        book.table(support_table(list(MODELS)), "modelos",
                   "Tabela A1. Valores da Figura 3: correlação parcial entre a perturbação e "
                   "o z de cada descritor primário nos três modelos, com IC 95% e p por "
                   "bootstrap em blocos de 1°.", selection=None),
        book.table(support_table(["outras exposições"], by_exposure=True), "exposicoes",
                   "Tabela A2. Valores da Figura 4: correlação parcial (controles: latitude, "
                   "água e altitude) entre cada medida de perturbação e o z de cada descritor "
                   "primário, com IC 95% e p por bootstrap em blocos de 1°.", selection=None),
        book.table(support_table(["longitudinal", "longitudinal, m igual"]), "longitudinal",
                   "Tabela A3. Valores da Figura 5: correlação parcial entre a perda de "
                   "floresta de 2001 a 2012 e a mudança de cada descritor primário entre "
                   "2001–2012 e 2013–2024, em todas as células elegíveis e só nas que mantêm "
                   "a dimensão de imersão, com IC 95% e p por bootstrap em blocos de 1°.",
                   selection=None),
    ])
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

    [9] Clifford, P.; Richardson, S.; Hémon, D. Assessing the significance of the
    correlation between two spatial processes. *Biometrics*, v. 45, n. 1, p. 123–134, 1989.
    """)
    return


if __name__ == "__main__":
    app.run()
