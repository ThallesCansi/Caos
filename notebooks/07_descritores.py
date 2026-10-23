# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "amazon-chaos @ git+https://github.com/ThallesCansi/Caos.git",
#     "marimo>=0.23",
# ]
# [tool.marimo.opengraph]
# title = "07 · Descritores não lineares"
# description = "1.541 células, oito descritores"
# ///
import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium", app_title="07 · Descritores não lineares por célula")

with app.setup(hide_code=True):
    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    from matplotlib.colors import TwoSlopeNorm
    from scipy.stats import spearmanr

    from amazon_chaos import nb, regions
    from amazon_chaos.config import load_region
    from amazon_chaos.nonlinear import results as R
    from amazon_chaos.nonlinear.suite import load_spec
    from amazon_chaos.viz import COLORS, map_cells

    book = nb.notebook("07_descritores")
    SPEC = load_spec()
    SLUGS = ["xingu", "tapajos"]
    ORDER = ["rqa_det", "pe_entropy", "pe_complexity", "prediction", "d2", "rqa_lam",
             "asymmetry", "lyapunov"]
    FAMILY_PT = {"primary": "primária", "secondary": "secundária", "exploratory": "exploratória"}
    SPEC_FAMILY = {d: f for f, ds in SPEC["families"].items() for d in ds}


@app.function(hide_code=True)
@mo.cache
def region_data(slug):
    cfg = load_region(slug)
    table = R.load(cfg, SPEC)
    return cfg, table, R.with_cells(cfg, table), R.global_rejection(table, cfg)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # 🧩 Descritores não lineares, célula por célula

    No laboratório aprendemos a desconfiar de um expoente de Lyapunov positivo e a
    comparar qualquer descritor com séries substitutas. Na validação dos métodos, vimos
    quais descritores separam caos de processos lineares em séries do tamanho das nossas e
    quais se deixam enganar pela variância sazonal. Agora aplicamos esse conjunto, sem mudar
    uma vírgula das regras fixadas de antemão, às 1.541 células ERA5 das bacias do Xingu e do
    Tapajós. Para cada célula, duas variáveis e três janelas de tempo, oito descritores foram
    comparados com 39 substitutas; são cerca de 180 mil números, que este capítulo organiza.

    A pergunta deste capítulo ainda não é sobre desmatamento. É mais básica: as séries
    climáticas diárias da Amazônia têm estrutura que um processo linear não explica? Se têm,
    que tipo de estrutura é essa, ela parece caos de baixa dimensão, e como ela se distribui
    no espaço e no tempo? Só depois de responder a isso faz sentido perguntar, no próximo
    capítulo, se a estrutura acompanha a perturbação da floresta.

    O percurso começa relembrando o que cada descritor mede e como uma célula "rejeita" a
    hipótese linear. Em seguida vemos o retrato geral, quantas células rejeitam em cada
    descritor, e uma limitação estatística que o próprio retrato revela. Depois olhamos para
    os mapas, que mostram que a geografia pesa muito; para a sensibilidade aos parâmetros
    de reconstrução; para a comparação entre as duas metades do período; e para os sinais
    precoces de transição. Fechamos com o que esses números autorizam e o que não autorizam
    concluir.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 🧪 O que foi calculado em cada célula

    Partimos da série diária de temperatura a 2 m e de déficit de pressão de vapor (VPD) de
    cada célula. De cada uma retiramos o ciclo sazonal médio da normal 1991–2020 e dividimos o
    resultado pelo desvio-padrão sazonal, também suavizado ao longo do ano:

    $$
    z_t = \frac{x_t - \bar x_{d(t)}}{s_{d(t)}},
    $$

    em que $d(t)$ é o dia do ano. A divisão por $s_{d(t)}$ não é cosmética: na validação dos
    métodos, a variância maior da estação seca fazia o expoente de Lyapunov e o determinismo
    da recorrência "detectarem" estrutura onde só havia sazonalidade. A tendência de longo
    prazo não foi removida.

    A série $z_t$ é então reconstruída em vetores de atraso
    $\mathbf X_t = (z_t, z_{t-\tau}, \ldots, z_{t-(m-1)\tau})$, com $\tau$ escolhido pela
    informação mútua [4] e $m$ pelos falsos vizinhos mais próximos [5], e uma janela de
    Theiler $w = \max(10, \tau m)$ dias. Sobre essa reconstrução calculamos oito descritores.
    O determinismo da recorrência é a fração de pontos recorrentes que formam linhas
    diagonais de comprimento $\ell \geq 2$,

    $$
    \mathrm{DET} = \frac{\sum_{\ell \ge 2} \ell\, P(\ell)}{\sum_{i \ne j} R_{ij}},
    $$

    em que $P(\ell)$ é o histograma das diagonais [6]; a laminaridade (LAM) é o mesmo com
    linhas verticais, que indicam estados que se demoram. A entropia de permutação conta com
    que frequência cada um dos $d! = 120$ padrões de ordenação aparece em janelas de $d = 5$
    dias e mede, numa escala de 0 a 1, quão uniformes são essas frequências [7],

    $$
    H = -\frac{1}{\ln d!} \sum_{\pi} p(\pi) \ln p(\pi),
    $$

    e a complexidade estatística $C = Q_J[P, P_e]\, H$ multiplica essa entropia pela
    divergência de Jensen–Shannon entre a distribuição observada e a uniforme [8]: ruído
    puro tem $H \approx 1$ e $C \approx 0$, e o caos ocupa uma faixa intermediária, com $C$
    alto. A assimetria temporal

    $$
    A = \frac{\langle (z_{t+1} - z_t)^3 \rangle}{\sigma_z^{3}}
    $$

    é nula para qualquer processo linear gaussiano, que é estatisticamente igual de frente
    para trás e de trás para frente [9]. O erro de previsão não linear treina um previsor
    de vizinhos próximos nos primeiros 60% da série e mede o erro um passo à frente no
    restante, em unidades do desvio-padrão [10]; a dimensão de correlação $D_2$ é a inclinação
    de $\ln C(r) \times \ln r$, em que $C(r)$ é a fração de pares a distância menor que $r$
    [11]; e o expoente de Lyapunov vem do método de Rosenstein.

    Para cada descritor $T$, comparamos o valor observado $T_0$ com os valores
    $T_1, \ldots, T_M$ em $M = 39$ substitutas IAAFT [12], que preservam o espectro e a
    distribuição da série e destroem o resto. Resumimos a comparação de duas maneiras. O
    escore

    $$
    z = \frac{T_0 - \overline{T}_{\text{subst}}}{s_{T,\text{subst}}}
    $$

    diz a quantos desvios-padrão da nuvem de substitutas o valor observado está, e o p de
    Monte Carlo, $p = (1 + \#\{T_k \geq T_0\})/(M + 1)$ no caso unilateral, diz que fração das
    séries (contando a original) é pelo menos tão extrema quanto ela. A direção de cada teste
    foi fixada antes de olhar os dados: espera-se, sob dinâmica não linear, DET e
    complexidade maiores, entropia, erro de previsão e $D_2$ menores que nas substitutas, e a
    assimetria diferente de zero.
    """)
    return


@app.function(hide_code=True)
def plot_global(window):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.6), sharex=True, layout="constrained")
    for ax, slug in zip(axes, SLUGS, strict=True):
        cfg, _, _, g = region_data(slug)
        part = g[(g.kind == "teste") & (g.window == window)].set_index(["descriptor", "variable"])
        y = np.arange(len(ORDER))
        for k, (var, color) in enumerate([("t2m", COLORS["t2m"]), ("vpd", COLORS["vpd"])]):
            rows = part.xs(var, level="variable").reindex(ORDER)
            yy = y + (k - 0.5) * 0.36
            ax.barh(yy, rows.fracao, 0.34, color=color, alpha=0.85, label=R.VARIABLES[var])
            ax.errorbar(rows.fracao, yy, xerr=[rows.fracao - rows.ic_inf,
                                              rows.ic_sup - rows.fracao],
                        fmt="none", ecolor="#333", elinewidth=0.8, capsize=2)
            for yk, value in zip(yy, rows.fracao, strict=True):
                if value < 0.01:
                    ax.text(0.01, yk, "0%", va="center", fontsize=8, color=color)
        ax.axvline(SPEC["surrogates"]["alpha"], color=COLORS["ink"], ls="--", lw=1)
        ax.set_yticks(y, [f"{R.NAMES[d]}\n({FAMILY_PT[SPEC_FAMILY[d]]})" for d in ORDER],
                      fontsize=9)
        ax.invert_yaxis()
        ax.set(xlim=(0, 1.02), xlabel="fração das células com p ≤ 0,05", title=cfg["name"])
    axes[0].legend(loc="lower right")
    return fig


@app.cell(hide_code=True)
def _():
    window_pick = mo.ui.dropdown(options={v: k for k, v in R.WINDOWS.items()},
                                 value="2001–2024", label="Janela")
    return (window_pick,)


@app.cell(hide_code=True)
def _(window_pick):
    _win = window_pick.value
    _rows = []
    for _slug in SLUGS:
        _cfg, _t, _, _g = region_data(_slug)
        _s = R.summary(_t)
        _s = _s[_s.window == _win]
        for _, _r in _s.iterrows():
            _rows.append({"Bacia": _cfg["name"].replace("Bacia do Rio ", ""),
                          "Descritor": R.NAMES[_r.descriptor],
                          "Família": FAMILY_PT[_r.family], "Variável": R.VARIABLES[_r.variable],
                          "Rejeitam (BH)": f"{100 * _r.rejeitam:.0f}%",
                          "BH por descritor": f"{100 * _r.rejeitam_por_descritor:.0f}%",
                          "z mediano": round(_r.z_mediano, 1)})
    mo.vstack([
        mo.md(r"""
        ## 🎯 O retrato geral

        A Figura 1 mostra, para cada descritor e cada bacia, a fração das células em que o
        valor observado ficou fora da nuvem de substitutas ($p \leq 0{,}05$). Se a hipótese
        linear valesse em toda parte, esperaríamos cerca de 5% de células assim apenas por
        acaso, a linha tracejada. As barras de erro são intervalos de 95% obtidos por
        reamostragem de blocos de 1° por 1°, e não de células isoladas, porque células
        vizinhas têm climas parecidos e não contam como evidências independentes. À direita
        de cada barra está a família do descritor no pré-registro.
        """),
        window_pick,
        book.figure(plot_global(_win), "rejeicao_global",
                    "Figura 1. Fração das células com p ≤ 0,05 contra 39 substitutas IAAFT, por "
                    "descritor, variável e bacia, com IC 95% por bootstrap em blocos de 1°. "
                    "Linha tracejada: 5%, o esperado se não houvesse estrutura não linear. Na "
                    "versão impressa, janela 2001–2024.", save=_win == "2001_2024"),
        mo.md(r"""
        A figura se divide em três grupos. O determinismo e a laminaridade da recorrência, a
        dimensão de correlação e a assimetria da temperatura estão no teto: praticamente
        todas as células, nas duas bacias, se afastam das substitutas. A entropia de
        permutação e a complexidade estatística ficam no meio, com mais da metade das células
        acima do acaso e intervalos que excluem os 5%; no VPD a fração é maior do que na
        temperatura. E o erro de previsão não linear fica em zero: em nenhuma célula a
        dinâmica é mais previsível do que nas substitutas. O expoente de Lyapunov, tratado
        como exploratório, aparece com frações intermediárias, mas a validação mostrou que
        ele rejeita a hipótese linear em até 60% das séries que só têm variância sazonal, e
        por isso esse número não é interpretado.

        Esse padrão tem uma leitura clara. As séries climáticas diárias são não lineares,
        assimétricas no tempo e mais organizadas, no sentido da recorrência, do que um
        processo linear com o mesmo espectro. Mas a assinatura do caos de baixa dimensão não
        aparece: se a dinâmica fosse governada por poucos graus de liberdade determinísticos,
        um previsor de vizinhos próximos deveria superar as substitutas, e isso não acontece
        em nenhuma célula. É o comportamento esperado de um sistema de alta dimensão, com
        forçamentos externos e não linearidades fracas, mais do que de um atrator caótico.
        """),
        mo.callout(mo.md(
            "Rejeitar a hipótese linear não é encontrar caos. A hipótese das substitutas IAAFT "
            "é a de um processo linear, gaussiano e estacionário, transformado de modo "
            "monotônico. Ela cai tanto por não linearidade quanto por não estacionariedade que "
            "a padronização não removeu, como mudanças de variância entre anos de El Niño e "
            "de La Niña. O conjunto dos descritores, e não um deles, é que sustenta a leitura."),
            kind="warn"),
        mo.md(r"""
        Há, porém, uma diferença entre a Figura 1 e o resultado formal pré-registrado, a
        Tabela 1, que aplica a correção de Benjamini–Hochberg [13] para os muitos testes
        simultâneos. Como manda o pré-registro, ela é feita dentro de cada família de
        descritores, isto é, juntando os testes de todas as células e de todos os descritores
        da família, para cada bacia, variável e janela. A correção ordena esses $n$ valores
        de $p$,
        $p_{(1)} \leq \cdots \leq p_{(n)}$, e declara significativos os $k$ primeiros, com $k$
        o maior índice tal que $p_{(k)} \leq k\alpha/n$. Com 39 substitutas, o menor $p$
        possível é $1/40 = 0{,}025$ num teste unilateral. Se $k$ células estão nesse piso, a
        condição vira $0{,}025 \leq k \times 0{,}05/n$, isto é, $k \geq n/2$: ou pelo menos
        metade das células atinge o piso, ou nenhuma é declarada significativa, por mais
        extremo que seja o seu z. Nos testes bilaterais, cujo piso é 0,05, é preciso que todas
        atinjam.
        """),
        book.table(pd.DataFrame(_rows), "rejeicao_bh",
                   "Tabela 1. Resultado pré-registrado: fração das células que rejeitam a "
                   "hipótese linear depois da correção de Benjamini–Hochberg, por bacia, "
                   "descritor e variável, com a correção feita dentro de cada família de "
                   "descritores, como no pré-registro, e, como sensibilidade, dentro de cada "
                   "descritor; e z mediano.", selection=None),
        mo.md(r"""
        A tabela mostra o efeito. Onde quase todas as células estão no piso, a correção
        confirma 100%. Onde a evidência é forte, mas espalhada, a correção vira tudo ou nada:
        a complexidade da temperatura no Tapajós aparece com 0%, embora um décimo das células
        tenha z acima de 9. O exemplo mais claro está na última coluna, que repete a correção
        dentro de cada descritor em vez de cada família. O determinismo da temperatura no
        Tapajós passa de 0% para 100%, e a laminaridade do VPD no Xingu também: quando o
        descritor é corrigido sozinho, todas as suas células estão no piso; quando divide a
        família com descritores em que algumas células não estão, nenhuma sobrevive. Entre as
        duas colunas, mudou só o conjunto de testes sobre o qual a correção é feita: o tudo ou
        nada não é uma propriedade da Amazônia, mas da resolução do teste. Por isso relatamos
        o resultado pré-registrado tal como ele saiu e, ao lado dele, a Figura 1 e os
        z-scores, como análise complementar, registrada antes de qualquer comparação com o
        desmatamento. Mais substitutas resolveriam o problema, ao custo de cerca de cem horas
        de processamento.
        """),
    ])
    return



@app.cell(hide_code=True)
def _():
    map_region = mo.ui.dropdown(options={load_region(s)["name"]: s for s in SLUGS},
                                value="Bacia do Rio Xingu", label="Bacia")
    map_descriptor = mo.ui.dropdown(options={R.NAMES[d]: d for d in ORDER},
                                    value=R.NAMES["pe_complexity"], label="Descritor")
    map_variable = mo.ui.radio(options={v: k for k, v in R.VARIABLES.items()},
                               value="temperatura", label="Variável", inline=True)
    return map_descriptor, map_region, map_variable


@app.function(hide_code=True)
def plot_map(slug, descriptor, variable):
    cfg, _, g, _ = region_data(slug)
    part = g[(g.kind == "teste") & (g.window == "2001_2024") & (g.descriptor == descriptor)
             & (g.variable == variable)]
    field = part.set_index(["latitude", "longitude"]).z.to_xarray()
    limit = regions.boundary(cfg)
    rivers = regions.load_context(cfg).get("rios")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 7.5), layout="constrained",
                                   width_ratios=[1.2, 1])
    lim = float(np.nanpercentile(np.abs(part.z), 98))
    map_cells(ax1, regions.cells(cfg), field, "RdBu_r", "z contra as substitutas",
              outline=limit, lines=rivers, norm=TwoSlopeNorm(0, -lim, lim))
    ax1.set_title(f"{R.NAMES[descriptor]} · {R.VARIABLES[variable]}")
    ax2.scatter(part.z, part.latitude, s=9, color=COLORS["ink"], alpha=0.5)
    ax2.axvline(0, color=COLORS["muted"], lw=1)
    ax2.set(xlabel="z contra as substitutas", ylabel="latitude (°)",
            title="O mesmo z em função da latitude")
    return fig, spearmanr(part.z, part.latitude).statistic


@app.cell(hide_code=True)
def _(map_descriptor, map_region, map_variable):
    _fig, _rho = plot_map(map_region.value, map_descriptor.value, map_variable.value)
    mo.vstack([
        mo.md(r"""
        ## 🗺️ Onde a estrutura é mais forte

        O retrato geral esconde a geografia. A Figura 2 mostra, à esquerda, o mapa do $z$ de
        um descritor em cada célula e, à direita, o mesmo $z$ contra a latitude da célula.
        Cores quentes indicam valores observados acima da nuvem de substitutas; frias, abaixo.
        Os controles escolhem a bacia, o descritor e a variável.
        """),
        mo.hstack([map_region, map_descriptor, map_variable], justify="start", gap=1),
        book.figure(_fig, f"mapa_z_{map_descriptor.value}_{map_variable.value}",
                    "Figura 2. z do descritor escolhido contra 39 substitutas IAAFT em cada "
                    "célula ERA5, janela 2001–2024 (esquerda), e o mesmo z em função da "
                    "latitude (direita). Na versão impressa, complexidade estatística da "
                    "temperatura, nas duas bacias.", region=map_region.value, save=False),
        mo.callout(mo.md(nb.pt(
            f"Para {R.NAMES[map_descriptor.value].lower()} da "
            f"{R.VARIABLES[map_variable.value]}, a correlação de postos entre o z e a "
            f"latitude é ρ = {_rho:+.2f}. " + (
                "Uma correlação desse tamanho quer dizer que a posição norte–sul, sozinha, "
                "ordena boa parte das células." if abs(_rho) > 0.5 else
                "A latitude explica pouco da variação desse descritor entre as células."))),
            kind="info"),
        mo.md(r"""
        O caso mais marcante é a complexidade estatística da temperatura, que cresce de sul
        para norte de modo quase monotônico nas duas bacias ($\rho \approx 0{,}9$). As
        cabeceiras, no Cerrado de Mato Grosso, têm anomalias de temperatura com padrões
        ordinais próximos dos de um processo linear; o baixo curso, perto do equador, tem
        padrões mais organizados. O determinismo e a assimetria também variam com a latitude,
        mais fracamente. Isso tem uma consequência direta para o próximo capítulo: como o
        desmatamento também se concentra no sul das duas bacias, qualquer comparação entre
        perturbação e descritores que ignore a latitude confundiria geografia com
        desmatamento. É por isso que o pré-registro inclui a latitude como controle.
        """),
        mo.callout(mo.md(
            "O ERA5 representa a vegetação com um mapa fixo e não acompanha o desmatamento ano "
            "a ano. Um gradiente espacial nos descritores pode refletir o clima de fundo, a "
            "distância do equador ou a circulação regional, e não a cobertura do solo."),
            kind="warn"),
    ])
    return


@app.function(hide_code=True)
def plot_distributions(variable):
    fig, ax = plt.subplots(figsize=(13, 5.2), layout="constrained")
    pos = np.arange(len(ORDER))
    for k, (slug, color) in enumerate(zip(SLUGS, [COLORS["ink"], COLORS["t2m"]], strict=True)):
        _, t, _, _ = region_data(slug)
        part = t[(t.kind == "teste") & (t.window == "2001_2024") & (t.variable == variable)]
        data = [part[part.descriptor == d].z.dropna().to_numpy() for d in ORDER]
        bp = ax.boxplot(data, positions=pos + (k - 0.5) * 0.36, widths=0.32, patch_artist=True,
                        showfliers=False, medianprops=dict(color="white", lw=1.5))
        for patch in bp["boxes"]:
            patch.set(facecolor=color, alpha=0.8, edgecolor=color)
        ax.plot([], [], color=color, lw=8, alpha=0.8, label=load_region(slug)["name"])
    ax.axhline(0, color=COLORS["muted"], lw=1)
    for z in (-1.96, 1.96):
        ax.axhline(z, color=COLORS["muted"], lw=0.8, ls=":")
    ax.set_xticks(pos, [R.NAMES[d] for d in ORDER], rotation=20, ha="right")
    ax.set(ylabel="z contra as substitutas",
           title=f"Distribuição do z nas células · {R.VARIABLES[variable]}, 2001–2024")
    ax.legend(loc="upper right")
    return fig


@app.cell(hide_code=True)
def _():
    dist_variable = mo.ui.radio(options={v: k for k, v in R.VARIABLES.items()},
                                value="temperatura", label="Variável", inline=True)
    return (dist_variable,)


@app.cell(hide_code=True)
def _(dist_variable):
    mo.vstack([
        mo.md(r"""
        ## 📦 A força da evidência

        A fração de células que rejeitam diz se a estrutura existe; o $z$ diz quão longe da
        nuvem de substitutas ela está. A Figura 3 resume, para cada descritor, a distribuição
        do $z$ nas células das duas bacias. Cada caixa vai do primeiro ao terceiro quartil, a
        linha branca é a mediana e as hastes cobrem o restante, sem os valores extremos. As
        linhas pontilhadas marcam $\pm 1{,}96$, a faixa em que um valor gaussiano cairia em
        95% das vezes.
        """),
        dist_variable,
        book.figure(plot_distributions(dist_variable.value), f"distribuicao_z_{dist_variable.value}",
                    "Figura 3. Distribuição do z contra as substitutas nas células de cada "
                    "bacia, por descritor, janela 2001–2024. Pontilhado: ±1,96. Na versão "
                    "impressa, as duas variáveis.", save=dist_variable.value == "t2m"),
        mo.md(r"""
        O determinismo e a laminaridade estão a 10 ou 15 desvios-padrão acima das
        substitutas em quase todas as células, e a dimensão de correlação e a assimetria da
        temperatura, a distâncias parecidas abaixo. São afastamentos enormes, o que mostra que
        a estrutura de recorrência das anomalias diárias é muito mais organizada do que a de um
        processo linear com o mesmo espectro. A entropia e a complexidade se afastam menos e
        variam mais entre as células, o que combina com o gradiente de latitude visto no mapa.
        O erro de previsão fica acima de zero em todas as células: o previsor não linear erra
        mais na série original do que nas substitutas, ao contrário do que um atrator
        caótico de baixa dimensão produziria. O $D_2$ abaixo das substitutas, por sua vez, não
        indica um atrator: mostra apenas que a série ocupa o espaço de reconstrução de modo
        menos uniforme do que um processo linear, e sem um platô de $D_2$ ao variar $m$ não
        há dimensão de atrator a relatar.
        """),
    ])
    return


@app.function(hide_code=True)
def plot_sensitivity(variable):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True, layout="constrained")
    for ax, slug in zip(axes, SLUGS, strict=True):
        _, t, _, _ = region_data(slug)
        s = R.sensitivity(t)
        s = s[s.variable == variable]
        s["rel"] = 100 * (s.observed / s.observed_base - 1)
        variants = ["τ = 2", "m = m₀ − 1", "m = m₀ + 1"]
        colors = [COLORS["t2m"], COLORS["precip"], COLORS["q"]]
        pos = np.arange(len(ORDER))
        for k, (variant, color) in enumerate(zip(variants, colors, strict=True)):
            data = [s[(s.descriptor == d) & (s.variante == variant)].rel.dropna().to_numpy()
                    for d in ORDER]
            data = [d if len(d) else np.array([np.nan]) for d in data]
            bp = ax.boxplot(data, positions=pos + (k - 1) * 0.27, widths=0.24, showfliers=False,
                            patch_artist=True, medianprops=dict(color="white"))
            for patch in bp["boxes"]:
                patch.set(facecolor=color, alpha=0.85, edgecolor=color)
            ax.plot([], [], color=color, lw=8, label=variant)
        ax.axhline(0, color=COLORS["muted"], lw=1)
        ax.set_xticks(pos, [R.NAMES[d] for d in ORDER], rotation=25, ha="right")
        ax.set(title=load_region(slug)["name"], ylabel="variação em relação à regra (%)")
    axes[0].legend(loc="lower left")
    return fig


@app.cell(hide_code=True)
def _():
    sens_variable = mo.ui.radio(options={v: k for k, v in R.VARIABLES.items()},
                                value="temperatura", label="Variável", inline=True)
    return (sens_variable,)


@app.cell(hide_code=True)
def _(sens_variable):
    mo.vstack([
        mo.md(r"""
        ## 🔧 Quanto os resultados dependem de $\tau$ e $m$

        A regra pré-registrada escolheu $\tau = 1$ dia em todas as 1.541 células, e $m$ entre 5
        e 7. Esse $\tau$ uniforme merece explicação. A regra toma o menor valor entre o
        primeiro mínimo da informação mútua e o primeiro atraso em que ela cai abaixo de
        $1/e$ do seu valor em $\tau = 0$. Em anomalias diárias padronizadas, a informação
        mútua com o próprio valor ($\tau = 0$) é a entropia da distribuição, alta, e já no
        atraso de um dia ela cai abaixo desse limiar, de modo que o segundo critério decide
        sempre. A regra foi seguida à risca, mas o resultado é que não exploramos atrasos
        maiores, e é para isso que serve a grade de sensibilidade: recalculamos todos os
        descritores com $\tau = 2$ e com $m$ uma unidade abaixo e acima do escolhido, sem
        novas substitutas. A Figura 4 mostra a variação relativa de cada descritor.
        """),
        sens_variable,
        book.figure(plot_sensitivity(sens_variable.value), f"sensibilidade_{sens_variable.value}",
                    "Figura 4. Variação relativa de cada descritor, em %, ao trocar τ = 1 por "
                    "τ = 2 ou m pelo valor vizinho, em relação aos parâmetros da regra. "
                    "Entropia, complexidade e assimetria não dependem de τ e m. Na versão "
                    "impressa, as duas variáveis.", save=sens_variable.value == "t2m"),
        mo.md(r"""
        Três descritores não se movem, e não por acaso: a entropia de permutação e a
        complexidade usam uma ordem e um atraso próprios, fixados em $d = 5$ e 1, e a
        assimetria usa o atraso de um dia, independentemente da reconstrução. O erro de
        previsão e a dimensão de correlação mudam pouco. O determinismo, por outro lado, cai
        cerca de 60% quando $\tau$ passa de 1 para 2, e o expoente de Lyapunov cerca de um
        terço. Isso não invalida o resultado da Figura 1, porque as substitutas foram
        calculadas com os mesmos parâmetros da série original, mas mostra que o valor
        absoluto do determinismo depende fortemente da escala de tempo da reconstrução. Por
        isso, no próximo capítulo, comparamos células pelo seu $z$ e pelo seu valor com
        parâmetros idênticos, nunca valores obtidos com parâmetros diferentes.
        """),
        mo.callout(mo.md(
            "τ = 1 em todas as células é uma consequência da regra pré-registrada, e não uma "
            "escolha posterior. É uma limitação a relatar: a reconstrução privilegia a escala "
            "de um dia, e estruturas em escalas de semanas não foram exploradas pelos "
            "descritores que dependem de τ."), kind="warn"),
    ])
    return


@app.cell(hide_code=True)
def _():
    win_descriptor = mo.ui.dropdown(options={R.NAMES[d]: d for d in ORDER},
                                    value=R.NAMES["rqa_det"], label="Descritor")
    win_variable = mo.ui.radio(options={v: k for k, v in R.VARIABLES.items()},
                               value="temperatura", label="Variável", inline=True)
    return win_descriptor, win_variable


@app.function(hide_code=True)
def plot_windows(descriptor, variable):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.6), layout="constrained")
    shares = {}
    for ax, slug in zip(axes, SLUGS, strict=True):
        cfg, t, _, _ = region_data(slug)
        part = t[(t.kind == "teste") & (t.descriptor == descriptor) & (t.variable == variable)
                 & t.window.isin(["2001_2012", "2013_2024"])]
        w = part.pivot_table(index="cell_id", columns="window", values="observed").dropna()
        lo, hi = np.nanpercentile(w.to_numpy(), [1, 99])
        ax.scatter(w["2001_2012"], w["2013_2024"], s=8, alpha=0.5, color=COLORS["ink"])
        ax.plot([lo, hi], [lo, hi], color=COLORS["t2m"], lw=1.2, ls="--")
        ax.set(xlim=(lo, hi), ylim=(lo, hi), xlabel="2001–2012", ylabel="2013–2024",
               title=cfg["name"], aspect="equal")
        shares[slug] = float((w["2013_2024"] > w["2001_2012"]).mean())
    fig.suptitle(f"{R.NAMES[descriptor]} · {R.VARIABLES[variable]}: cada ponto é uma célula",
                 x=0.02, ha="left", fontsize=12)
    return fig, shares


@app.cell(hide_code=True)
def _(win_descriptor, win_variable):
    _fig, _shares = plot_windows(win_descriptor.value, win_variable.value)
    _default = (win_descriptor.value, win_variable.value) == ("rqa_det", "t2m")
    mo.vstack([
        mo.md(r"""
        ## ⏳ As duas metades do período

        A comparação longitudinal do próximo capítulo usa a mudança de cada descritor entre
        2001–2012 e 2013–2024, dentro da mesma célula. A Figura 5 mostra essa mudança: cada
        ponto é uma célula, com o valor do descritor na primeira metade no eixo horizontal e
        na segunda no vertical. Pontos acima da diagonal tracejada aumentaram; abaixo,
        diminuíram.
        """),
        mo.hstack([win_descriptor, win_variable], justify="start", gap=1),
        book.figure(_fig, f"janelas_{win_descriptor.value}_{win_variable.value}",
                    "Figura 5. Valor do descritor em cada célula em 2001–2012 (horizontal) e "
                    "2013–2024 (vertical); tracejado: sem mudança. Na versão impressa, "
                    "determinismo da recorrência da temperatura.", save=_default),
        mo.callout(mo.md(nb.pt(
            f"O descritor aumentou da primeira para a segunda metade em "
            f"{100 * _shares['xingu']:.0f}% das células do Xingu e em "
            f"{100 * _shares['tapajos']:.0f}% das do Tapajós.")), kind="info"),
        mo.md(r"""
        Os pontos se alinham perto da diagonal: as células que tinham mais estrutura na
        primeira década continuam tendo mais na segunda, o que mostra que os descritores
        capturam algo estável de cada lugar, e não ruído de estimativa. Ao mesmo tempo, há
        deslocamentos sistemáticos. O determinismo e a laminaridade aumentam em cerca de 80%
        das células, a assimetria fica mais negativa em quase todas e o erro de previsão sobe
        em boa parte delas. No determinismo e na laminaridade, parte desse movimento vem de
        um detalhe de método: a dimensão de imersão é escolhida em cada década, muda em um
        quinto a um terço das células, e esses descritores saltam junto com ela, o que
        aparece como faixas na figura; nas células em que ela não muda, o aumento persiste,
        mas é menor. Esses deslocamentos atingem as bacias inteiras ao mesmo tempo e
        coincidem com uma década mais quente e com dois eventos fortes de El Niño
        (2015–2016 e 2023–2024); antes de atribuí-los a qualquer mudança local, o próximo
        capítulo pergunta se as células mais desmatadas mudaram mais do que as preservadas.
        """),
    ])
    return


@app.cell(hide_code=True)
def _():
    ews_region = mo.ui.dropdown(options={load_region(s)["name"]: s for s in SLUGS},
                                value="Bacia do Rio Xingu", label="Bacia")
    ews_variable = mo.ui.radio(options={v: k for k, v in R.VARIABLES.items()},
                               value="temperatura", label="Variável", inline=True)
    return ews_region, ews_variable


@app.function(hide_code=True)
def plot_ews(slug, variable):
    cfg, _, g, _ = region_data(slug)
    part = g[(g.kind == "ews") & (g.variable == variable)]
    limit = regions.boundary(cfg)
    cells = regions.cells(cfg)
    fig, axes = plt.subplots(1, 2, figsize=(12, 7.2), layout="constrained")
    for ax, indicator in zip(axes, ["variance", "ar1"], strict=True):
        sel = part[part.descriptor == indicator].set_index(["latitude", "longitude"])
        field = sel.observed.astype(float).to_xarray()
        stipple = (sel.pvalue <= SPEC["surrogates"]["alpha"] + R.TOLERANCE).to_xarray()
        map_cells(ax, cells, field, "PuOr_r", "τ de Kendall da tendência", outline=limit,
                  norm=TwoSlopeNorm(0, -1, 1), stipple=stipple)
        ax.set_title(R.NAMES[indicator])
    return fig, part


@app.cell(hide_code=True)
def _(ews_region, ews_variable):
    _fig, _part = plot_ews(ews_region.value, ews_variable.value)
    _var = _part[_part.descriptor == "variance"]
    _ar1 = _part[_part.descriptor == "ar1"]
    mo.vstack([
        mo.md(r"""
        ## 📉 Sinais precoces de transição

        Se um sistema se aproxima de uma perda de estabilidade, ele passa a se recuperar mais
        devagar de cada perturbação. Nas séries, isso aparece como um aumento conjunto da
        variância e da autocorrelação de um passo ao longo do tempo, o chamado
        *critical slowing down* [14, 15]. Para cada célula, calculamos esses dois indicadores em
        janelas móveis de 12 anos sobre as anomalias, depois de retirar uma tendência suave, e
        medimos a sua tendência pelo $\tau$ de Kendall, comparado com 39 substitutas. A
        Figura 6 mostra esse $\tau$ em cada célula; os pontos marcam células com $p \leq 0{,}05$.
        """),
        mo.hstack([ews_region, ews_variable], justify="start", gap=1),
        book.figure(_fig, f"ews_{ews_variable.value}",
                    "Figura 6. Tendência, pelo τ de Kendall, da variância (esquerda) e da "
                    "autocorrelação de um passo (direita) em janelas móveis de 12 anos, por "
                    "célula; pontos: p ≤ 0,05 contra 39 substitutas. Na versão impressa, "
                    "temperatura, nas duas bacias.", region=ews_region.value, save=False),
        mo.callout(mo.md(nb.pt(
            f"Na {ews_region.selected_key.replace('Bacia do Rio ', 'bacia do ')}, a variância "
            f"da {R.VARIABLES[ews_variable.value]} cresce de modo significativo em "
            f"{100 * (_var.pvalue <= 0.05 + R.TOLERANCE).mean():.0f}% das células, e a "
            f"autocorrelação em {100 * (_ar1.pvalue <= 0.05 + R.TOLERANCE).mean():.0f}%.")),
            kind="info"),
        mo.md(r"""
        Os dois indicadores contam histórias diferentes. A variância cresce de modo quase
        generalizado, e de forma significativa em boa parte das células, mais no Tapajós do
        que no Xingu. A tendência da autocorrelação, ao contrário, muda de sinal no espaço:
        tende a subir no norte das bacias e a cair no sul, mas em nenhuma região ela se
        distingue das substitutas, que, com janelas móveis tão longas, também produzem
        tendências fortes por acaso. Isso não é o padrão do *critical slowing down*, que exige
        variância e memória subindo juntas e de forma consistente: uma variância maior sem
        aumento claro da memória é o que se espera de perturbações externas mais fortes, como
        os El Niño recentes e as secas de 2015 e 2024, agindo sobre um sistema que continua se
        recuperando em ritmo parecido. Os sinais precoces, portanto, não indicam aproximação
        de uma transição crítica no clima regional representado pelo ERA5.
        """),
    ])
    return


@app.cell(hide_code=True)
def _():
    # Versões de referência para a monografia (sem exibição).
    book.figure(plot_distributions("vpd"), "distribuicao_z_vpd",
                "Distribuição do z contra as substitutas nas células de cada bacia, por "
                "descritor, déficit de pressão de vapor, 2001–2024.")
    book.figure(plot_sensitivity("vpd"), "sensibilidade_vpd",
                "Variação relativa de cada descritor do déficit de pressão de vapor ao trocar "
                "τ = 1 por τ = 2 ou m pelo valor vizinho.")
    for _slug in SLUGS:
        book.figure(plot_map(_slug, "pe_complexity", "t2m")[0], "mapa_z_pe_complexity_t2m",
                    "Complexidade estatística da temperatura: z contra 39 substitutas IAAFT por "
                    "célula, 2001–2024, e o mesmo z em função da latitude.", region=_slug)
        book.figure(plot_ews(_slug, "t2m")[0], "ews_t2m",
                    "Tendência (τ de Kendall) da variância e da autocorrelação de um passo da "
                    "temperatura em janelas móveis de 12 anos; pontos: p ≤ 0,05.", region=_slug)
    return


@app.function(hide_code=True)
@mo.cache
def sensitivity_table():
    from amazon_chaos import gradient as G
    from amazon_chaos.nonlinear import sensitivity as S

    rows = []
    for slug in SLUGS:
        cfg = load_region(slug)
        rows.append(S.compare(cfg, SPEC, G.cell_table(cfg, SPEC)).assign(region=slug))
    return pd.concat(rows, ignore_index=True)


@app.cell(hide_code=True)
def _():
    _r = sensitivity_table()
    _rows = []
    for (_slug, _var, _desc), _g in _r.groupby(["region", "variable", "descriptor"], sort=False):
        _g = _g.set_index("variant")
        _row = {"Bacia": load_region(_slug)["name"].replace("Bacia do Rio ", ""),
                "Variável": R.VARIABLES[_var], "Descritor": R.NAMES[_desc],
                "Células": int(_g.cells.iloc[0]),
                "Lote original": f"{_g.loc['lote original', 'rho_parcial']:+.2f}"}
        for _v in ["199 substitutas", "τ = 2", "ruído EDH"]:
            _row[_v] = (f"{_g.loc[_v, 'rho_parcial']:+.2f} "
                        f"({_g.loc[_v, 'rho_z_lote']:.2f})")
        _rows.append(_row)
    _corr = _r[_r.variant != "lote original"].rho_z_lote
    _drho = (_r[_r.variant != "lote original"].set_index(
        ["region", "variable", "descriptor", "variant"]).rho_parcial
        - _r[_r.variant == "lote original"].set_index(
        ["region", "variable", "descriptor"]).rho_parcial).abs()
    mo.vstack([
        mo.md(r"""
        ## 🔩 Três testes do próprio lote

        Três escolhas do lote podiam, em princípio, mudar os resultados. A primeira é o
        número de substitutas: com 39, o menor $p$ possível é 0,025, e isso cria o tudo ou
        nada da Tabela 1. A segunda é o atraso de imersão: a regra deu $\tau = 1$ dia em
        quase todas as células, e o determinismo muda bastante com $\tau$. A terceira é a
        precisão dos dados: o espelho do ERA5 que usamos guarda os números com a mantissa
        arredondada, e os descritores não lineares podem ser sensíveis a esse ruído.

        Para testá-las sem refazer todo o lote, sorteamos cerca de 60 células elegíveis por
        bacia, em partes iguais entre os nove estratos de latitude e perturbação, e
        recalculamos os descritores primários de 2001 a 2024 de três modos: com 199
        substitutas; com $\tau = 2$; e com um ruído somado à série diária do dobro da
        diferença medida entre o espelho e o arquivo original do ERA5. A Tabela 2 compara
        cada variante com o lote original nas mesmas células: a correlação parcial com a
        perda antecedente, como no capítulo 08, e, entre parênteses, a correlação de postos
        entre o $z$ da variante e o do lote (D-024).
        """),
        book.table(pd.DataFrame(_rows), "sensibilidade_lote",
                   "Tabela 2. Sensibilidade do lote numa subamostra estratificada: correlação "
                   "parcial (controles: latitude, água e altitude) entre a perda antecedente e o "
                   "z de cada descritor primário no lote original e em três variantes (199 "
                   "substitutas; τ = 2; ruído do dobro da diferença entre o Earth Data Hub e o "
                   "CDS) e, entre parênteses, a correlação de postos entre o z da variante e o "
                   "do lote, nas mesmas células, 2001–2024.", selection=None),
        mo.callout(mo.md(nb.pt(
            f"Correlação entre o z das variantes e o do lote: mediana de "
            f"{_corr.median():.2f}, mínimo de {_corr.min():.2f}. Mudança da correlação "
            f"parcial com a perturbação: mediana de {_drho.median():.2f}, máximo de "
            f"{_drho.max():.2f}.")), kind="info"),
        mo.md(r"""
        As três variantes reproduzem o lote. O $z$ de cada célula muda pouco, e a ordem das
        células quase não muda: a correlação com o lote fica acima de 0,9 na maior parte dos
        casos. As exceções são o determinismo com $\tau = 2$, que mede outra escala de
        tempo, e o erro de previsão com 199 substitutas, cuja distribuição nula fica mais
        bem definida. A entropia e a complexidade não mudam com $\tau$ porque os padrões
        ordinais têm atraso próprio, fixado no pré-registro. A fração de células que
        rejeitam a hipótese linear e a associação com
        a perturbação também ficam onde estavam, com mudanças da ordem de 0,1 na correlação
        parcial, menores que os intervalos de confiança de uma amostra de 60 células. Os
        resultados dos capítulos 07 e 08 não dependem da resolução das substitutas, do
        atraso escolhido pela regra, nem do arredondamento do espelho do ERA5.
        """),
    ])
    return


@app.function(hide_code=True)
def lyapunov_table():
    rows = []
    for slug in SLUGS:
        _, t, _, _ = region_data(slug)
        part = t[(t.kind == "teste") & (t.window == "2001_2024") & (t.descriptor == "lyapunov")]
        rows.append(part.assign(region=slug))
    return pd.concat(rows, ignore_index=True)


@app.function(hide_code=True)
def plot_lyapunov():
    lya = lyapunov_table()
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.6), sharex=True, sharey=True,
                             layout="constrained")
    markers = {"xingu": "o", "tapajos": "s"}
    colors = {5: COLORS["precip"], 6: COLORS["t2m"], 7: COLORS["ink"]}
    for ax, var in zip(axes, R.VARIABLES, strict=True):
        part = lya[lya.variable == var]
        for (slug, m), g in part.groupby(["region", "m"]):
            ax.scatter(g.null_mean, g.observed, s=10, alpha=0.5, marker=markers[slug],
                       color=colors.get(int(m), COLORS["muted"]),
                       label=f"{load_region(slug)['name'].replace('Bacia do Rio ', '')}, "
                             f"m = {int(m)}")
        lo, hi = part[["null_mean", "observed"]].min().min(), part[
            ["null_mean", "observed"]].max().max()
        ax.plot([lo, hi], [lo, hi], color=COLORS["muted"], lw=1, ls="--")
        ax.set(xlabel="λ médio das 39 substitutas IAAFT (por dia)",
               ylabel="λ observado (por dia)", title=R.VARIABLES[var].capitalize())
    handles, names = axes[0].get_legend_handles_labels()
    keep = [k for k, n in enumerate(names) if not n.endswith("m = 7")]
    fig.legend([handles[k] for k in keep], [names[k] for k in keep], loc="outside lower center",
               ncol=4, frameon=False, markerscale=2)
    return fig


@app.cell(hide_code=True)
def _():
    _lya = lyapunov_table()
    _lines = []
    for (_slug, _var), _g in _lya.groupby(["region", "variable"], sort=False):
        _lines.append(
            f"{load_region(_slug)['name'].replace('Bacia do Rio ', '')}, "
            f"{R.VARIABLES[_var]}: λ positivo em {100 * (_g.observed > 0).mean():.0f}% das "
            f"células, mediana de {_g.observed.median():.3f} por dia contra "
            f"{_g.null_mean.median():.3f} nas substitutas; p ≤ 0,05 em "
            f"{100 * (_g.pvalue <= 0.05 + R.TOLERANCE).mean():.0f}% das células")
    mo.vstack([
        mo.md(r"""
        ## 🦋 O expoente de Lyapunov nos dados reais

        O maior expoente de Lyapunov é a medida que dá nome à teoria do caos e era um dos
        objetivos do projeto: estimá-lo nas séries reais. Ele foi calculado em todas as
        células pelo método de Rosenstein, com os mesmos $\tau$, $m$ e janela de Theiler dos
        outros descritores, e nas 39 substitutas de cada uma. A validação dos métodos o
        rebaixou a exploratório, porque ele rejeitava a hipótese linear em boa parte das
        séries sem caos nenhum. A Figura 7 mostra por que essa cautela era necessária.
        """),
        book.figure(plot_lyapunov(), "lyapunov",
                    "Figura 7. Maior expoente de Lyapunov (Rosenstein) observado em cada célula "
                    "contra a média do mesmo expoente nas suas 39 substitutas IAAFT, para a "
                    "temperatura e o VPD de 2001 a 2024, nas duas bacias (círculos: Xingu; "
                    "quadrados: Tapajós), com a cor pela dimensão de imersão m (pontos escuros: as "
                    "células com m = 7). Tracejado: observado igual às substitutas."),
        mo.callout(mo.md(nb.pt("; ".join(_lines) + ".")), kind="info"),
        mo.md(r"""
        O expoente é positivo em todas as células, perto de 0,3 por dia, o que, lido
        sozinho, sugeriria que duas situações do tempo quase iguais se afastam pela metade a
        cada dois ou três dias. Mas os pontos caem sobre a diagonal: as substitutas, que são
        processos lineares sem nenhuma dinâmica caótica, dão o mesmo expoente. O valor é
        fixado pelo ruído e pela forma da reconstrução, e não pela dinâmica. Os dois grupos
        de pontos, em torno de 0,30 e 0,37, não são dois regimes de clima, e sim as duas
        dimensões de imersão que a regra escolheu, m = 6 e m = 5. Onde o expoente se afasta
        das substitutas, ele fica um pouco abaixo delas, e nenhuma dessas diferenças
        sobrevive à correção para múltiplos testes.
        """),
        mo.callout(mo.md(
            "O expoente de Lyapunov das séries diárias é positivo em toda parte, e é igual ao "
            "de processos lineares com o mesmo espectro. Um λ positivo, aqui, não é sinal de "
            "caos: é o que o ruído produz."), kind="danger"),
    ])
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 🧭 O que levamos para o próximo capítulo

    As séries diárias de temperatura e de VPD das duas bacias não se comportam como
    processos lineares. A estrutura de recorrência é muito mais organizada, a temperatura é
    assimétrica no tempo e os padrões ordinais se afastam dos de um processo com o mesmo
    espectro, sobretudo no norte das bacias. Ao mesmo tempo, nenhuma célula mostra a
    previsibilidade de curto prazo que um caos de baixa dimensão permitiria, o expoente de
    Lyapunov não se distingue de forma confiável das substitutas, e a dimensão de correlação
    não indica um atrator. O retrato mais honesto é o de um sistema não linear de alta
    dimensão, sob forçamento externo, e não o de um atrator caótico simples.

    Três cuidados acompanham esse retrato. A geografia organiza fortemente os descritores,
    em particular a complexidade da temperatura, de sul para norte; a reconstrução usou
    $\tau = 1$ dia em toda parte, por consequência da regra; e o resultado formal com
    correção para múltiplos testes é limitado pela resolução de 39 substitutas, razão pela
    qual o acompanhamos da fração de rejeições e dos $z$. Com esses cuidados, a pergunta do
    próximo capítulo fica bem posta: depois de controlar a latitude, as células com mais
    desmatamento e fogo têm descritores diferentes das preservadas, ou mudaram de modo
    diferente entre as duas décadas?
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 📚 Referências

    [1] Kantz, H.; Schreiber, T. *Nonlinear Time Series Analysis*. 2. ed. Cambridge:
    Cambridge University Press, 2004.

    [2] Theiler, J.; Eubank, S.; Longtin, A.; Galdrikian, B.; Farmer, J. D. Testing for
    nonlinearity in time series: the method of surrogate data. *Physica D*, v. 58,
    p. 77–94, 1992.

    [3] Hersbach, H. et al. The ERA5 global reanalysis. *Quarterly Journal of the Royal
    Meteorological Society*, v. 146, p. 1999–2049, 2020.

    [4] Fraser, A. M.; Swinney, H. L. Independent coordinates for strange attractors from
    mutual information. *Physical Review A*, v. 33, p. 1134–1140, 1986.

    [5] Kennel, M. B.; Brown, R.; Abarbanel, H. D. I. Determining embedding dimension for
    phase-space reconstruction using a geometrical construction. *Physical Review A*,
    v. 45, p. 3403–3411, 1992.

    [6] Marwan, N.; Romano, M. C.; Thiel, M.; Kurths, J. Recurrence plots for the analysis
    of complex systems. *Physics Reports*, v. 438, p. 237–329, 2007.

    [7] Bandt, C.; Pompe, B. Permutation entropy: a natural complexity measure for time
    series. *Physical Review Letters*, v. 88, 174102, 2002.

    [8] Rosso, O. A.; Larrondo, H. A.; Martin, M. T.; Plastino, A.; Fuentes, M. A.
    Distinguishing noise from chaos. *Physical Review Letters*, v. 99, 154102, 2007.

    [9] Diks, C.; van Houwelingen, J. C.; Takens, F.; DeGoede, J. Reversibility as a
    criterion for discriminating time series. *Physics Letters A*, v. 201, p. 221–228, 1995.

    [10] Sugihara, G.; May, R. M. Nonlinear forecasting as a way of distinguishing chaos
    from measurement error in time series. *Nature*, v. 344, p. 734–741, 1990.

    [11] Grassberger, P.; Procaccia, I. Measuring the strangeness of strange attractors.
    *Physica D*, v. 9, p. 189–208, 1983.

    [12] Schreiber, T.; Schmitz, A. Surrogate time series. *Physica D*, v. 142,
    p. 346–382, 2000.

    [13] Benjamini, Y.; Hochberg, Y. Controlling the false discovery rate: a practical and
    powerful approach to multiple testing. *Journal of the Royal Statistical Society B*,
    v. 57, p. 289–300, 1995.

    [14] Scheffer, M. et al. Early-warning signals for critical transitions. *Nature*,
    v. 461, p. 53–59, 2009.

    [15] Dakos, V. et al. Methods for detecting early warnings of critical transitions in
    time series illustrated using simulated ecological data. *PLoS ONE*, v. 7, e41010,
    2012.
    """)
    return


if __name__ == "__main__":
    app.run()
