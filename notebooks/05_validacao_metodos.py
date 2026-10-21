import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium", app_title="05 · Os métodos diante de casos conhecidos")

with app.setup(hide_code=True):
    import json

    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    from amazon_chaos import nb
    from amazon_chaos.nonlinear.dimension import correlation_dimension
    from amazon_chaos.nonlinear.gate import GATE_DIR, rejection_rates, verdict
    from amazon_chaos.nonlinear.lyapunov import rosenstein
    from amazon_chaos.nonlinear.ordinal import complexity_entropy
    from amazon_chaos.nonlinear.suite import embedding_parameters, gate_hash, load_spec
    from amazon_chaos.nonlinear.synthetic import NEGATIVE, POSITIVE, control
    from amazon_chaos.viz import COLORS

    book = nb.notebook("05_validacao_metodos")
    SPEC = load_spec()
    RUN = GATE_DIR / gate_hash(SPEC)
    NAMES = {"lyapunov": "Lyapunov (Rosenstein)", "rqa_det": "RQA · determinismo",
             "rqa_lam": "RQA · laminaridade", "d2": "Dimensão de correlação",
             "pe_entropy": "Entropia de permutação", "pe_complexity": "Complexidade estatística",
             "asymmetry": "Assimetria temporal", "prediction": "Erro de previsão não linear"}
    CONTROL_NAMES = {"logistic": "logístico", "henon": "Hénon", "lorenz": "Lorenz",
                     "white": "ruído branco", "ar1": "AR(1)", "sine_noise": "seno + ruído",
                     "seasonal_trend": "AR(1) sazonal com tendência"}


@app.function(hide_code=True)
@mo.cache
def gate_results():
    results = pd.read_csv(RUN / "descritores.csv")
    spec = json.loads((RUN / "spec.json").read_text())
    rates = rejection_rates(results, spec["surrogates"]["alpha"])
    return results, spec, rates, verdict(rates, spec), pd.read_csv(RUN / "ews.csv"), \
        pd.read_csv(RUN / "padronizacao.csv")


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # 🧪 Os métodos diante de casos conhecidos

    No laboratório vimos um expoente de Lyapunov positivo surgir de um processo que não tem
    nada de caótico. A lição vale para todos os descritores não lineares: cada um deles pode
    dar um número convincente para a razão errada, e a única defesa é testá-los antes em
    séries cuja resposta conhecemos. Este capítulo faz esse teste. Ele submete os oito
    descritores do trabalho a séries sintéticas, umas caóticas e outras sem nenhum caos,
    com o mesmo comprimento, o mesmo ruído e exatamente as mesmas regras que depois serão
    aplicadas aos dados da Amazônia.

    Chamamos esse teste de portão, porque nenhum descritor é interpretado nos dados reais
    sem passar por ele, e as suas regras foram fixadas no pré-registro antes de qualquer
    descritor ser calculado no clima. Começamos pelo desenho: os casos de controle, o que se
    espera de cada um e o critério de aprovação. Depois vemos o veredito, como ele depende
    do comprimento e do ruído, e como cada descritor enxerga os controles. Em seguida
    tratamos da armadilha que mais pesa sobre séries climáticas, a sazonalidade, e da
    decisão que ela motivou. Fechamos com a calibração dos sinais precoces de transição.
    """)
    return


@app.cell(hide_code=True)
def _():
    demo_control = mo.ui.dropdown(options={v: k for k, v in CONTROL_NAMES.items()},
                                  value="Lorenz", label="Controle")
    demo_noise = mo.ui.slider(0, 0.6, value=0.2, step=0.1, label="Ruído de observação",
                              show_value=True)
    return demo_control, demo_noise


@app.function(hide_code=True)
def plot_control(kind, noise):
    x = control(kind, 8766, seed=3, noise=noise)
    params = embedding_parameters(x, SPEC)
    tau = params["tau"]
    fig = plt.figure(figsize=(14, 4.6), layout="constrained")
    grid = fig.add_gridspec(1, 3, width_ratios=[2.2, 1, 1])
    ax = fig.add_subplot(grid[0])
    ax.plot(x[:400], color=COLORS["ink"], lw=0.8)
    ax.set(xlabel="passo", ylabel="valor padronizado", title="Os primeiros 400 passos")
    clean = control(kind, 8766, seed=3)
    tau_clean = embedding_parameters(clean, SPEC)["tau"]
    for k, (y, lag, color, title) in enumerate([
            (x, tau, COLORS["t2m"], nb.pt(f"Com ruído {noise:g} (τ = {tau})")),
            (clean, tau_clean, COLORS["precip"], f"Sem ruído (τ = {tau_clean})")]):
        ax_k = fig.add_subplot(grid[1 + k])
        ax_k.scatter(y[:-lag], y[lag:], s=1.5, alpha=0.3, color=color, lw=0)
        ax_k.set(xlabel="$x_t$", ylabel=f"$x_{{t+{lag}}}$", title=title, aspect="equal")
    fig.suptitle(nb.pt(f"{CONTROL_NAMES[kind]} · ruído {noise:g}"), x=0.02, ha="left",
                 fontsize=12)
    return fig, params


@app.cell(hide_code=True)
def _(demo_control, demo_noise):
    _g, _c = SPEC["gate"], SPEC["gate"]["criterion"]
    _fig, _params = plot_control(demo_control.value, demo_noise.value)
    mo.vstack([
        mo.md(r"""
        ## 🎯 Os casos de controle

        Os controles positivos são três sistemas caóticos clássicos, de dimensão baixa e
        expoente de Lyapunov conhecido: o mapa logístico $x_{t+1} = 4 x_t (1 - x_t)$ [1], o
        mapa de Hénon $x_{t+1} = 1 - 1{,}4\, x_t^2 + y_t$, $y_{t+1} = 0{,}3\, x_t$ [2], e a
        coordenada $x$ do sistema de Lorenz [3],

        $$
        \dot x = 10\,(y - x), \qquad \dot y = x\,(28 - z) - y, \qquad
        \dot z = x y - \tfrac{8}{3} z,
        $$

        amostrada a cada 0,1 unidade de tempo. Os controles negativos não têm caos. O ruído
        branco gaussiano é o caso mais simples. O AR(1), $x_t = 0{,}8\, x_{t-1} +
        \varepsilon_t$, tem memória, como as anomalias climáticas, mas é linear. O seno com
        ruído, de período 365, é determinístico, mas periódico e não caótico. E o último, um
        AR(1) cuja variância e cuja média oscilam com período de 365 passos e que tem uma
        tendência linear, imita o que uma série climática mal tratada pode ter: ele viola de
        propósito a estacionariedade que as substitutas supõem.

        A Figura 1 mostra cada controle no tempo e reconstruído no espaço de fases, com o
        ruído de observação escolhido no controle deslizante, uma fração do desvio-padrão
        da série somada ponto a ponto como um erro de medida, e, para comparação, a mesma
        reconstrução sem ruído.
        """),
        mo.hstack([demo_control, demo_noise], justify="start", gap=1),
        book.figure(_fig, "controles",
                    "Figura 1. Um controle do portão: os primeiros 400 passos com o ruído "
                    "escolhido e a reconstrução em duas dimensões, com o atraso escolhido pela "
                    "informação mútua, com esse ruído e sem ruído. Na versão impressa, Lorenz "
                    "com ruído 0,2.",
                    save=(demo_control.value, demo_noise.value) == ("lorenz", 0.2)),
        mo.callout(mo.md(nb.pt(
            f"Parâmetros escolhidos pelas regras nesta série: τ = {_params['tau']}, "
            f"m = {_params['m']} e janela de Theiler de {_params['theiler']} passos.")),
            kind="info"),
        mo.md(rf"""
        Sem ruído, os controles caóticos desenham estruturas finas e reconhecíveis: a
        parábola do mapa logístico, a ferradura do Hénon e as duas asas do atrator de Lorenz.
        Os negativos formam nuvens sem forma, com ou sem ruído. À medida que o ruído cresce,
        as estruturas caóticas se borram, e com 0,2 a parábola e a ferradura já são só uma
        faixa larga; é nesse nível
        de ruído, comparável ao das séries reais, que o critério é aplicado. Note também que,
        com ruído, as regras escolhem $\tau = 1$ em quase todos os controles, o mesmo valor
        que escolheram em todas as células da Amazônia.

        Cada controle foi gerado {_g['repetitions']} vezes em dois comprimentos, 2.048 e
        8.766 passos, este último o número de dias de 2001 a 2024, e em dois níveis de ruído,
        zero e 0,2. Em cada série, os parâmetros da reconstrução saíram das mesmas regras dos
        dados, e cada descritor foi comparado com {SPEC['surrogates']['per_cell']}
        substitutas IAAFT. O critério, fixado antes de rodar, é aplicado no caso mais difícil,
        o maior comprimento com o maior ruído: o descritor passa se rejeitar a hipótese nula
        em pelo menos {_c['power']:.0%} das repetições em pelo menos
        {_c['positives_required']} dos 3 controles positivos e em no máximo
        {_c['size']:.0%} das repetições no ruído branco e no AR(1), onde a hipótese nula é
        verdadeira.
        """),
    ])
    return


@app.cell(hide_code=True)
def _():
    cond_n = mo.ui.radio(options={"2.048": 2048, "8.766": 8766}, value="8.766",
                         label="Comprimento", inline=True)
    cond_noise = mo.ui.radio(options={"0": 0.0, "0,2": 0.2}, value="0,2", label="Ruído",
                             inline=True)
    return cond_n, cond_noise


@app.function(hide_code=True)
def plot_rates(n, noise):
    _, _, rates, _, _, _ = gate_results()
    part = rates[(rates.n == n) & (rates.noise == noise)]
    order = [k for k in [*POSITIVE, *NEGATIVE] if k in set(part.control)]
    table = part.pivot(index="descriptor", columns="control", values="rate")[order]
    table = table.loc[list(NAMES)]
    fig, ax = plt.subplots(figsize=(11.5, 5.4), layout="constrained")
    im = ax.imshow(table.values, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(order)), [CONTROL_NAMES[k] for k in order], rotation=20, ha="right")
    ax.set_yticks(range(len(table)), [NAMES[d] for d in table.index])
    for i in range(table.shape[0]):
        for j in range(table.shape[1]):
            ax.text(j, i, f"{table.values[i, j]:.0%}", ha="center", va="center", fontsize=9)
    ax.axvline(len(POSITIVE) - 0.5, color="black", lw=2)
    ax.set_title(nb.pt(f"n = {n:,} · ruído {noise:g} · à esquerda, caos (quer-se alto); à "
                       "direita, sem caos (quer-se baixo)"), fontsize=10.5)
    ax.grid(False)
    fig.colorbar(im, ax=ax, shrink=0.8, label="fração das repetições com p ≤ 0,05")
    crit = SPEC["gate"]["criterion"]
    ok = [d for d in table.index
          if (table.loc[d, list(POSITIVE)] >= crit["power"]).sum() >= crit["positives_required"]
          and (table.loc[d, ["white", "ar1"]] <= crit["size"]).all()]
    return fig, ok


@app.cell(hide_code=True)
def _(cond_n, cond_noise):
    _, _, _, _gate, _, _ = gate_results()
    _fig, _ok = plot_rates(cond_n.value, cond_noise.value)
    _tab = _gate.copy()
    _tab.insert(0, "Descritor", _tab.pop("descriptor").map(NAMES))
    _tab["passa"] = _tab["passa"].map({True: "sim", False: "não"})
    mo.vstack([
        mo.md(r"""
        ## ✅ O veredito

        A Figura 2 mostra a fração das repetições em que cada descritor rejeitou a hipótese
        nula, para cada controle. À esquerda da linha preta estão os controles caóticos, em
        que se quer rejeitar; à direita, os sem caos, em que se quer não rejeitar. Os
        controles abaixo da figura mudam o comprimento e o ruído; a versão impressa é a do
        critério, com 8.766 passos e ruído 0,2.
        """),
        mo.hstack([cond_n, cond_noise], justify="start", gap=1),
        book.figure(_fig, "taxas_rejeicao",
                    "Figura 2. Fração das 10 repetições em que cada descritor rejeita a "
                    "hipótese nula IAAFT, por controle, no comprimento e no ruído escolhidos. "
                    "Na versão impressa, 8.766 passos e ruído 0,2.",
                    save=(cond_n.value, cond_noise.value) == (8766, 0.2)),
        mo.callout(mo.md(nb.pt(
            f"Nesta condição, {len(_ok)} dos 8 descritores satisfariam o critério"
            + (f": todos menos {', '.join(NAMES[d] for d in NAMES if d not in _ok)}."
               if 0 < len(_ok) < 8 else "."))), kind="info"),
        mo.md(r"""
        No caso do critério, todos os oito descritores passam. Todos rejeitam a hipótese nula
        em 100% das repetições dos mapas logístico e de Hénon, quase todos também no Lorenz,
        e nenhum rejeita mais de 20% das vezes no ruído branco e no AR(1). A única ausência
        no lado positivo é instrutiva: a assimetria temporal nunca rejeita no Lorenz, porque
        a coordenada $x$ do sistema de Lorenz é estatisticamente simétrica no tempo, e um
        descritor só enxerga o tipo de estrutura que mede. A Tabela 1 traz o veredito
        formal.

        As outras condições mostram por que o critério é aplicado no caso mais longo. Com
        2.048 passos e ruído, a dimensão de correlação perde quase todo o poder nos mapas
        logístico e de Lorenz, e o Lyapunov começa a rejeitar o AR(1) em 30% das vezes, um
        falso positivo inaceitável; com séries de 24 anos, esses problemas desaparecem.
        Duas colunas pedem atenção mesmo no melhor caso. No seno com ruído, o determinismo e
        a laminaridade da recorrência rejeitam em 50% e 70% das repetições: um ciclo forte e
        regular é exatamente o que a recorrência detecta, embora não seja caos. E no AR(1)
        sazonal com tendência, o Lyapunov rejeita sempre e o determinismo, em 80% das vezes.
        As duas colunas falam da mesma armadilha, a da sazonalidade, que tratamos adiante.
        """),
        book.table(_tab.round(2), "veredito",
                   "Tabela 1. Veredito do portão no maior comprimento (8.766) e no maior ruído "
                   "(0,2): número de controles positivos com poder de ao menos 80%, poder em "
                   "cada controle positivo, taxa de rejeição nos controles negativos e "
                   "aprovação pelo critério pré-registrado.", selection=None),
    ])
    return


@app.function(hide_code=True)
def plot_diagnostics(n=4000, seed=11):
    kinds = [*POSITIVE, *NEGATIVE]
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8), layout="constrained")
    colors = plt.cm.tab10(np.arange(len(kinds)))
    for kind, color in zip(kinds, colors, strict=True):
        x = control(kind, n, seed=seed, noise=0.2)
        p = embedding_parameters(x, SPEC)
        r = rosenstein(x, p["m"], p["tau"], p["theiler"], fit=(0, 5), max_steps=30)
        style = "-" if kind in POSITIVE else "--"
        axes[0].plot(r.divergence - r.divergence[0], style, color=color,
                     label=CONTROL_NAMES[kind])
        h, c = complexity_entropy(x, 5, 1)
        axes[1].scatter(h, c, color=color, s=60, marker="o" if kind in POSITIVE else "s")
        axes[1].annotate(CONTROL_NAMES[kind], (h, c), fontsize=8, xytext=(4, 3),
                         textcoords="offset points")
        if kind in ("lorenz", "ar1"):
            d2 = correlation_dimension(x, range(1, 7), p["tau"], p["theiler"])
            axes[2].plot(d2.dimensions, d2.d2, "o" + style, color=color,
                         label=CONTROL_NAMES[kind])
    axes[0].set(xlabel="k (passos)", ylabel="⟨ln d(k)⟩ − ⟨ln d(0)⟩",
                title="Rosenstein: curva de divergência")
    axes[0].legend(fontsize=7, ncol=2)
    axes[1].set(xlabel="entropia de permutação H", ylabel="complexidade C",
                title="Plano complexidade–entropia (d = 5)")
    axes[2].plot([1, 6], [1, 6], ":", color=COLORS["muted"], label="D2 = m (sem platô)")
    axes[2].set(xlabel="dimensão de imersão m", ylabel="D2",
                title="Dimensão de correlação contra m")
    axes[2].legend(fontsize=8)
    return fig


@app.cell(hide_code=True)
def _():
    mo.vstack([
        mo.md(r"""
        ## 🔍 Como os descritores enxergam os controles

        As taxas de rejeição dizem se um descritor separa os casos, mas não como. A Figura 3
        abre três deles numa repetição de cada controle, com ruído 0,2: as curvas de
        divergência do método de Rosenstein [4], que dão o expoente de Lyapunov pela
        inclinação inicial, o plano complexidade–entropia de Bandt e Pompe [5, 6] e a
        dimensão de correlação de Grassberger e Procaccia [7] em função da dimensão de
        imersão. Linhas cheias e círculos são controles caóticos; tracejadas e quadrados, os
        sem caos.
        """),
        book.figure(plot_diagnostics(), "diagnosticos",
                    "Figura 3. Uma repetição de cada controle com ruído 0,2 e 4.000 passos: "
                    "curvas de divergência de Rosenstein, posição no plano "
                    "complexidade–entropia (padrões de ordem 5) e dimensão de correlação "
                    "contra a dimensão de imersão, para Lorenz e AR(1)."),
        mo.md(r"""
        No painel da esquerda, as curvas dos controles caóticos sobem depressa nos primeiros
        passos e depois se achatam, quando a separação entre trajetórias vizinhas atinge o
        tamanho do atrator; é essa subida inicial que o expoente mede. As curvas dos
        controles sem caos também sobem, porque o ruído afasta qualquer par de pontos, e é
        por isso que o valor do expoente, sozinho, não distingue os dois casos: só a
        comparação com as substitutas o faz. No plano complexidade–entropia, o ruído branco
        fica no canto de entropia máxima e complexidade nula, junto com o seno de período
        longo, cujos padrões de cinco dias são dominados pelo ruído; o AR(1) se afasta um
        pouco desse canto, e os três sistemas caóticos ficam bem longe, com entropia menor e
        complexidade maior. O painel da direita mostra o limite da dimensão de correlação.
        Sem ruído, a do Lorenz se estabilizaria perto de 2,06, o valor conhecido do atrator;
        com ruído 0,2, ela continua subindo com a dimensão de imersão, quase como a do
        AR(1), porque o ruído preenche o espaço nas escalas pequenas em que a dimensão é
        medida. A diferença entre as duas curvas é pequena, mas sistemática, e é essa
        diferença que o teste contra substitutas detecta em séries longas; em séries
        curtas, ela se perde, como a Figura 2 mostrou.
        """),
    ])
    return


@app.function(hide_code=True)
def plot_standardization(table):
    variants = ["anomalia", "padronizada", "padronizada+sem tendência"]
    labels = {"anomalia": "anomalia simples", "padronizada": "anomalia padronizada",
              "padronizada+sem tendência": "padronizada, sem tendência"}
    names = ["lyapunov", "rqa_det", "d2", "pe_complexity"]
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.4), sharey=True, layout="constrained")
    for ax, kind in zip(axes, ["seasonal_trend", "sine_noise", "ar1", "lorenz"], strict=True):
        part = table[table.controle == kind].pivot(index="descritor", columns="variante",
                                                    values="taxa").loc[names, variants]
        x = np.arange(len(names))
        for k, (variant, color) in enumerate(zip(variants, ["#b0523b", COLORS["ink"],
                                                             COLORS["muted"]], strict=True)):
            ax.bar(x + (k - 1) * 0.27, part[variant], 0.27, color=color, label=labels[variant])
        ax.set_xticks(x, [NAMES[n].split(" (")[0] for n in names], rotation=30, ha="right",
                      fontsize=8)
        ax.set_title(CONTROL_NAMES[kind] + (" (poder)" if kind == "lorenz" else
                                            " (falso positivo)"), fontsize=10)
        ax.axhline(0.2, color=COLORS["muted"], ls=":", lw=1)
    axes[0].set_ylabel("taxa de rejeição")
    handles, names_ = axes[0].get_legend_handles_labels()
    fig.legend(handles, names_, loc="outside lower center", ncol=3, frameon=False, fontsize=9)
    return fig


@app.cell(hide_code=True)
def _():
    _, _, _, _, _, _std = gate_results()
    _f = SPEC["families"]
    mo.vstack([
        mo.md(r"""
        ## 🌦️ A armadilha da sazonalidade

        Uma série climática diária tem um ciclo anual na média e também na variância, e
        nenhuma das duas coisas é a dinâmica que queremos medir. As duas colunas problemáticas
        da Figura 2 mostram o risco: um ciclo forte engana a recorrência, e uma variância que
        oscila com as estações engana o Lyapunov e o determinismo. Para escolher o tratamento
        das séries, repetimos o teste em quatro controles, dez vezes cada, com 8.766 passos e
        ruído 0,2, em três versões: a anomalia simples, que retira o ciclo da média; a
        anomalia padronizada, que também divide cada dia pelo desvio típico daquela época do
        ano; e a padronizada sem a tendência linear. A Figura 4 mostra o resultado.
        """),
        book.figure(plot_standardization(_std), "padronizacao",
                    "Figura 4. Taxa de rejeição em quatro controles com a anomalia simples, a "
                    "anomalia padronizada pelo desvio sazonal e a padronizada sem tendência; "
                    "nos três primeiros, toda rejeição é falso positivo; no Lorenz, é poder. "
                    "Pontilhado: o máximo aceito de falsos positivos."),
        mo.md(r"""
        Retirar o ciclo da média já resolve o seno com ruído: sem o ciclo, sobra só o ruído,
        e nenhum descritor rejeita mais. A variância sazonal é mais traiçoeira. Na anomalia
        simples do AR(1) sazonal, o Lyapunov rejeita em 100% das vezes e o determinismo em
        80%, sem que haja nada de caótico na série. A padronização leva o falso positivo do
        determinismo a zero e o do Lyapunov a 60%; retirar também a tendência baixa o do
        Lyapunov a 40%, mas devolve parte do problema ao determinismo. Nenhuma das três
        versões tira poder no Lorenz.
        """),
        mo.callout(mo.md(
            "Decisão do pré-registro: todas as séries são analisadas como anomalias "
            "padronizadas, sem remoção de tendência. O expoente de Lyapunov, que continua "
            "vulnerável à variância sazonal mesmo depois da padronização, fica como "
            "descritor apenas exploratório."), kind="success"),
        mo.md(nb.pt(
            "Com isso, os descritores foram organizados em três famílias, fixadas antes da "
            "análise dos dados. A primária, que sustenta as conclusões, reúne "
            + ", ".join(NAMES[n].lower() for n in _f["primary"])
            + ". A secundária reúne " + ", ".join(NAMES[n].lower() for n in _f["secondary"])
            + ", que passaram no portão, mas cada uma com uma fraqueza que a Figura 2 "
            "mostrou: a dimensão de correlação perde poder com ruído em séries curtas, a "
            "laminaridade é a mais sensível a ciclos e a assimetria não enxerga o caos do "
            "Lorenz. A exploratória tem só o "
            + NAMES[_f["exploratory"][0]].lower() + ".")),
    ])
    return


@app.cell(hide_code=True)
def _():
    _, _, _, _, _ews, _ = gate_results()
    _tab = (_ews.assign(rejeita=_ews.pvalue <= SPEC["surrogates"]["alpha"])
            .groupby(["control", "indicator"])
            .agg(Repetições=("rejeita", "size"), Rejeições=("rejeita", "sum"),
                 **{"τ de Kendall médio": ("tau", "mean")}).reset_index())
    _tab.insert(0, "Série", _tab.pop("control").map(
        {"ar1_estacionario": "AR(1) estacionário", "ar1_rampa": "AR(1) com memória crescente"}))
    _tab.insert(1, "Indicador", _tab.pop("indicator").map(
        {"variance": "variância", "ar1": "autocorrelação de defasagem 1"}))
    mo.vstack([
        mo.md(r"""
        ## 🚨 Os sinais precoces de transição

        Além dos descritores de caos, calculamos dois sinais precoces de transição, que
        respondem a outra pergunta. Quando um sistema se aproxima de um ponto de bifurcação,
        ele se recupera cada vez mais devagar das perturbações, e isso aparece como um
        aumento da variância e da autocorrelação de defasagem 1 ao longo do tempo [8]. Medimos
        a tendência de cada indicador, calculado em janelas móveis de metade da série, pelo
        τ de Kendall, e a comparamos com substitutas, porque o τ calculado sobre janelas
        sobrepostas é muito autocorrelacionado e chega facilmente a valores altos num
        processo sem tendência nenhuma. A Tabela 2 mostra a calibração em duas séries: um
        AR(1) estacionário, em que não há transição, e um AR(1) cujo coeficiente sobe de 0,2
        a 0,95 ao longo da série, imitando a aproximação de uma bifurcação.
        """),
        book.table(_tab.round(2), "ews_calibracao",
                   "Tabela 2. Calibração dos sinais precoces: número de repetições em que a "
                   "tendência da variância e da autocorrelação rejeita a hipótese nula IAAFT, e "
                   "τ de Kendall médio, num AR(1) estacionário e num AR(1) que se aproxima da "
                   "instabilidade.", selection=None),
        mo.md(r"""
        O teste se comporta como deveria nos dois extremos: não rejeita nenhuma vez no AR(1)
        estacionário e rejeita sempre no que se aproxima da instabilidade, com τ perto de 1.
        Os sinais precoces não são descritores de caos e são tratados à parte: um sistema
        pode ser caótico sem estar perto de nenhuma transição, e pode se aproximar de uma
        transição sem nada de caótico.
        """),
    ])
    return


@app.cell(hide_code=True)
def _():
    mo.md(rf"""
    ## 🧭 O que levamos para os dados

    Com séries do tamanho das nossas e com ruído de observação, os oito descritores separam
    dinâmica caótica conhecida de processos lineares, e o fazem com as regras que serão
    usadas nos dados, sem nenhum ajuste à mão. O portão também mostrou os seus limites. A
    assimetria temporal só enxerga caos que seja assimétrico no tempo. A recorrência é
    sensível a ciclos fortes, o que exige retirar o ciclo anual. A variância sazonal produz
    falsos positivos que só a padronização controla, e não por completo no caso do Lyapunov,
    que por isso fica como exploratório. Essas lições definiram como as séries são tratadas
    e como os resultados são lidos nos capítulos seguintes. O pré-registro que as fixou
    está {SPEC['status']} desde {SPEC.get('frozen_on', 'o início da análise')}, e toda
    mudança posterior foi registrada como uma nova versão ou como análise complementar.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 📚 Referências

    [1] May, R. M. Simple mathematical models with very complicated dynamics. *Nature*,
    v. 261, p. 459–467, 1976.

    [2] Hénon, M. A two-dimensional mapping with a strange attractor. *Communications in
    Mathematical Physics*, v. 50, p. 69–77, 1976.

    [3] Lorenz, E. N. Deterministic nonperiodic flow. *Journal of the Atmospheric Sciences*,
    v. 20, p. 130–141, 1963.

    [4] Rosenstein, M. T.; Collins, J. J.; De Luca, C. J. A practical method for
    calculating largest Lyapunov exponents from small data sets. *Physica D*, v. 65,
    p. 117–134, 1993.

    [5] Bandt, C.; Pompe, B. Permutation entropy: a natural complexity measure for time
    series. *Physical Review Letters*, v. 88, 174102, 2002.

    [6] Rosso, O. A. et al. Distinguishing noise from chaos. *Physical Review Letters*,
    v. 99, 154102, 2007.

    [7] Grassberger, P.; Procaccia, I. Characterization of strange attractors. *Physical
    Review Letters*, v. 50, p. 346–349, 1983.

    [8] Dakos, V. et al. Methods for detecting early warnings of critical transitions in
    time series illustrated using simulated ecological data. *PLoS ONE*, v. 7, e41010,
    2012.
    """)
    return


if __name__ == "__main__":
    app.run()
