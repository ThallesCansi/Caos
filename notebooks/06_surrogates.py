# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "amazon-chaos @ git+https://github.com/ThallesCansi/Caos.git",
#     "marimo>=0.23",
# ]
# [tool.marimo.opengraph]
# title = "06 · Séries substitutas"
# description = "O clima sem não linearidade"
# ///
import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium", app_title="06 · Séries substitutas")

with app.setup(hide_code=True):
    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    from scipy.signal import welch
    from scipy.stats import skew
    from statsmodels.tsa.stattools import acf

    from amazon_chaos import nb
    from amazon_chaos.config import load_region
    from amazon_chaos.nonlinear import basin_test as B
    from amazon_chaos.nonlinear import results as R
    from amazon_chaos.nonlinear.suite import load_spec, surrogates
    from amazon_chaos.viz import COLORS

    book = nb.notebook("06_surrogates")
    SPEC = load_spec()
    SLUGS = ["xingu", "tapajos"]
    ORDER = ["rqa_det", "pe_entropy", "pe_complexity", "prediction", "d2", "rqa_lam",
             "asymmetry", "lyapunov"]
    SERIES_COLORS = {"original": COLORS["ink"], "FT": COLORS["precip"],
                     "IAAFT": COLORS["vpd"]}


@app.function(hide_code=True)
@mo.cache
def basin_series(slug, variable):
    return B.basin_series(load_region(slug), variable, SPEC)


@app.function(hide_code=True)
@mo.cache
def basin_results():
    tables, nulls = zip(*[B.load(load_region(s), SPEC) for s in SLUGS], strict=True)
    return pd.concat(tables, ignore_index=True), pd.concat(nulls, ignore_index=True)


@app.function(hide_code=True)
@mo.cache
def cell_z():
    rows = []
    for slug in SLUGS:
        t = R.load(load_region(slug), SPEC)
        t = t[(t.kind == "teste") & (t.window == "2001_2024")]
        rows.append(t[["region", "cell_id", "variable", "descriptor", "z", "pvalue"]])
    return pd.concat(rows, ignore_index=True)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # 🎭 Séries substitutas: o clima sem não linearidade

    Todo descritor não linear devolve um número, e nenhum número, sozinho, diz se a série
    tem estrutura não linear. No laboratório vimos um expoente de Lyapunov positivo surgir de
    um processo puramente aleatório e aprendemos a saída: comparar o número com o que se
    obteria de séries que têm as mesmas propriedades lineares da original, mas nada além
    delas. Essas séries de comparação, as substitutas, são o instrumento de inferência de
    todo o trabalho, e este capítulo é dedicado a elas.

    Fazemos isso em três passos. Primeiro olhamos por dentro de uma substituta: o que ela
    preserva e o que ela destrói, usando a série diária média de cada bacia. Depois
    discutimos as premissas do método, que são exigentes, e o que fizemos para que as
    nossas séries as respeitem. Por fim aplicamos o teste completo às séries das duas bacias
    com uma resolução bem maior que a possível célula a célula, comparando duas hipóteses
    nulas diferentes, e usamos o resultado como ponte para o capítulo seguinte, em que o
    mesmo teste é repetido em cada uma das 1.541 células.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 🎲 Duas maneiras de apagar a não linearidade

    Uma série temporal $x_1, \ldots, x_N$ pode ser escrita pela transformada de Fourier como
    uma soma de ondas, cada uma com uma amplitude $|X_k|$ e uma fase $\varphi_k$. As
    amplitudes guardam o espectro de potência e, pelo teorema de Wiener–Khinchin, toda a
    função de autocorrelação; é tudo o que um processo linear gaussiano tem a oferecer. A
    não linearidade mora nas relações entre as fases: picos que sobem devagar e caem
    depressa, episódios que se repetem com a mesma forma, assimetrias entre frente e trás.
    A primeira substituta, chamada FT [1], mantém as amplitudes e sorteia fases novas,

    $$
    \tilde X_k = |X_k|\, e^{i \varphi_k}, \qquad \varphi_k \sim \mathcal U[0, 2\pi),
    \qquad \varphi_{N-k} = -\varphi_k,
    $$

    e volta ao tempo pela transformada inversa. O resultado é uma realização de um processo
    linear, gaussiano e estacionário com exatamente o espectro observado. Essa é a hipótese
    nula $H_0^{\mathrm{FT}}$.

    Ela tem um defeito prático. Uma série climática pode ter uma distribuição assimétrica,
    como o déficit de pressão de vapor, que nunca é negativo e tem uma cauda longa nos dias
    secos, sem que haja nada de dinâmico nisso: basta que um processo linear seja visto
    através de uma função não linear fixa, como uma exponencial. A substituta FT, que é
    sempre gaussiana, seria rejeitada por esse motivo trivial. A substituta IAAFT [2]
    resolve o problema alternando dois ajustes até que ambos se satisfaçam: impõe o espectro
    original, trocando as amplitudes de Fourier e mantendo as fases; depois impõe a
    distribuição original, substituindo cada valor pelo valor original de mesmo posto,

    $$
    s^{(j+1)} = \operatorname{rank}^{-1}_{x}\!\left(\mathcal F^{-1}\!\left[\,|X_k|\,
    e^{i \arg \mathcal F[s^{(j)}]_k}\right]\right),
    $$

    em que $\operatorname{rank}^{-1}_x$ devolve, a cada posição, o valor de $x$ com o mesmo
    posto. A hipótese nula passa a ser $H_0^{\mathrm{IAAFT}}$: a série é uma transformação
    monotônica fixa de um processo linear gaussiano estacionário. Rejeitá-la é mais
    exigente e mais informativo, e por isso é a nula do pré-registro.
    """)
    return


@app.cell(hide_code=True)
def _():
    anat_region = mo.ui.dropdown(options={load_region(s)["name"]: s for s in SLUGS},
                                 value="Bacia do Rio Tapajós", label="Bacia")
    anat_variable = mo.ui.radio(options={v: k for k, v in R.VARIABLES.items()},
                                value="temperatura", label="Variável",
                                inline=True)
    anat_seed = mo.ui.slider(1, 50, value=1, step=1, label="Sorteio da substituta",
                             show_value=True)
    return anat_region, anat_seed, anat_variable


@app.function(hide_code=True)
def plot_anatomy(slug, variable, seed):
    z = basin_series(slug, variable)
    x = z.to_numpy(dtype=float)
    series = {"original": x,
              "FT": next(surrogates(x, 1, method="FT", seed=seed)),
              "IAAFT": next(surrogates(x, 1, method="IAAFT", seed=seed))}
    fig = plt.figure(figsize=(15, 8.4), layout="constrained")
    grid = fig.add_gridspec(2, 4, height_ratios=[1.15, 1])
    ax = fig.add_subplot(grid[0, :])
    window = slice(-3 * 365, None)
    for k, (name, y) in enumerate(series.items()):
        ax.plot(z.index[window], y[window] - 7 * k, color=SERIES_COLORS[name], lw=0.8)
        ax.text(z.index[window][0], 3.4 - 7 * k, name, color=SERIES_COLORS[name],
                fontsize=10, fontweight="bold")
    ax.set_yticks([])
    ax.set_title("Os três últimos anos (deslocadas na vertical)")
    ax_s, ax_v, ax_d, ax_c = (fig.add_subplot(grid[1, i]) for i in range(4))
    bins = np.linspace(-5, 5, 81)
    for name, y in series.items():
        f, p = welch(y, nperseg=1024)
        ax_s.loglog(f[1:], p[1:], color=SERIES_COLORS[name], lw=1.4,
                    ls="-" if name == "original" else "--", label=name)
        ax_v.hist(y, bins=bins, histtype="step", density=True, lw=1.4,
                  color=SERIES_COLORS[name], label=f"{name} · assimetria {skew(y):+.2f}")
        ax_d.hist(np.diff(y), bins=bins, histtype="step", density=True, lw=1.4,
                  color=SERIES_COLORS[name], label=f"{name} · {skew(np.diff(y)):+.2f}")
        shock = innovations(y)
        ax_c.plot(range(1, 31), acf(shock ** 2, nlags=30, fft=True)[1:], marker=".",
                  color=SERIES_COLORS[name], lw=1.2, label=name)
    ax_s.set(xlabel="frequência (ciclos por dia)", ylabel="potência", title="Espectro")
    ax_v.set(xlabel="z", ylabel="densidade", title="Distribuição dos valores")
    ax_d.set(xlabel="$z_{t+1} - z_t$", ylabel="densidade",
             title="Distribuição das variações diárias")
    ax_s.legend(fontsize=8.5)
    for axis in (ax_v, ax_d):
        axis.set_ylim(top=axis.get_ylim()[1] * 1.45)
    ax_v.legend(fontsize=8, loc="upper left")
    ax_d.legend(fontsize=8, loc="upper left", title="assimetria", title_fontsize=8)
    ax_c.axhline(0, color=COLORS["muted"], lw=1)
    ax_c.set(xlabel="defasagem (dias)", ylabel="autocorrelação",
             title="Autocorrelação dos choques ao quadrado")
    ax_c.legend(fontsize=8.5)
    fig.suptitle(f"{load_region(slug)['name']} · {R.VARIABLES[variable]}", x=0.02,
                 ha="left", fontsize=12)
    stats = {name: (skew(y), skew(np.diff(y)),
                    acf(innovations(y) ** 2, nlags=5, fft=True)[5])
             for name, y in series.items()}
    return fig, stats


@app.function(hide_code=True)
def innovations(y):
    """Choques de um passo: o que sobra de y depois da melhor previsão linear AR(1)."""
    slope = np.polyfit(y[:-1], y[1:], 1)
    return y[1:] - np.polyval(slope, y[:-1])


@app.cell(hide_code=True)
def _(anat_region, anat_seed, anat_variable):
    _fig, _stats = plot_anatomy(anat_region.value, anat_variable.value, anat_seed.value)
    mo.vstack([
        mo.md(r"""
        A Figura 1 abre uma substituta de cada tipo. A série original é a média diária da
        bacia, ponderada pela área de cada célula, depois de retirado o ciclo sazonal e
        dividido o resultado pelo desvio-padrão sazonal, exatamente como no lote por célula;
        a janela é 2001–2024, com 8.766 dias. No alto estão os três últimos anos da original
        e de uma substituta FT e uma IAAFT, sorteadas com a mesma semente; embaixo, o espectro
        das três, a distribuição dos valores e a distribuição das variações de um dia para o
        outro. O controle deslizante sorteia outras substitutas.
        """),
        mo.hstack([anat_region, anat_variable, anat_seed], justify="start", gap=1),
        book.figure(_fig, "anatomia",
                    "Figura 1. Série média da bacia (anomalia padronizada, 2001–2024) e uma "
                    "substituta FT e uma IAAFT: os três últimos anos, o espectro de potência "
                    "(estimador de Welch), a distribuição dos valores, a das variações "
                    "diárias, com a assimetria de cada uma, e a autocorrelação dos choques de "
                    "um passo ao quadrado. Na versão impressa, temperatura do Tapajós.",
                    save=(anat_region.value, anat_variable.value, anat_seed.value)
                    == ("tapajos", "t2m", 1)),
        mo.callout(mo.md(nb.pt(
            f"Assimetria dos valores: original {_stats['original'][0]:+.2f}, FT "
            f"{_stats['FT'][0]:+.2f}, IAAFT {_stats['IAAFT'][0]:+.2f}. Assimetria das "
            f"variações diárias: original {_stats['original'][1]:+.2f}, FT "
            f"{_stats['FT'][1]:+.2f}, IAAFT {_stats['IAAFT'][1]:+.2f}. Autocorrelação dos "
            f"choques ao quadrado a 5 dias: original {_stats['original'][2]:+.2f}, FT "
            f"{_stats['FT'][2]:+.2f}, IAAFT {_stats['IAAFT'][2]:+.2f}.")), kind="info"),
        mo.md(r"""
        O espectro das três séries coincide, como deveria: as substitutas são construídas para
        isso, e é por essa razão que, a olho nu, os três traços do alto parecem igualmente
        plausíveis. As diferenças aparecem nas outras medidas. A distribuição dos valores da
        temperatura do Tapajós tem uma cauda mais longa do lado frio, com assimetria
        negativa; a IAAFT a reproduz exatamente, porque usa os mesmos valores em outra ordem
        (sua curva cobre a da original), e a FT a perde, porque é gaussiana por construção.

        A distribuição das variações de um dia para o outro conta outra história. Na série
        original ela é claramente assimétrica: as quedas de temperatura são mais bruscas que
        as subidas, como acontece quando uma tarde de chuva forte ou uma incursão de ar
        frio do sul derruba a temperatura de uma vez e ela se recupera aos poucos nos dias
        seguintes. Nenhuma das substitutas guarda essa assimetria, porque ela depende da
        ordem dos dias, e não só dos valores. Ela se vê a olho nu no painel de cima: os
        mergulhos bruscos da série original, como os de meados de 2022 e de 2023, não têm
        equivalente nas substitutas, que oscilam de modo mais simétrico. O último painel mostra uma terceira propriedade
        que as substitutas destroem. Chamamos de choque o que sobra de cada dia depois da
        melhor previsão linear feita a partir do dia anterior. Se os choques grandes vêm
        agrupados, o quadrado do choque de hoje se correlaciona com o de dias depois. Na FT,
        gaussiana, essa correlação é nula desde o início; na IAAFT, ela começa igual à da
        original no primeiro dia, efeito da cauda da distribuição, e some em poucos dias. Só
        na original ela continua positiva por semanas. Na temperatura o efeito é fraco; no déficit de pressão de vapor, que
        o menu permite escolher, ele é bem mais forte, com correlação perto de 0,14 ainda a
        cinco dias. Períodos calmos e períodos agitados se alternam no clima real de um modo
        que nenhum processo linear reproduz.

        Assimetria temporal, agrupamento da variabilidade e padrões de ordem são justamente o
        tipo de estrutura que os descritores não lineares tentam capturar, cada um à sua
        maneira. O teste consiste em perguntar se o valor de um descritor na série original
        fica fora da nuvem de valores que ele assume nas substitutas.
        """),
    ])
    return


@app.cell(hide_code=True)
def _():
    _rows = []
    for _slug in SLUGS:
        for _var in R.VARIABLES:
            _diag, _ = B.stationarity_diagnostics(basin_series(_slug, _var).to_numpy())
            _rows.append({
                "Bacia": load_region(_slug)["name"].replace("Bacia do Rio ", ""),
                "Variável": R.VARIABLES[_var],
                "ADF (p)": _diag["adf_p"], "KPSS (p)": _diag["kpss_p"],
                "Tendência em 24 anos (σ)": _diag["trend_total"],
                "Tendência (p, HAC)": _diag["trend_hac_p"],
                "Razão de desvios entre blocos": _diag["block_std_ratio"]})
    _tab = pd.DataFrame(_rows).round(3)
    mo.vstack([
        mo.md(r"""
        ## 📐 O que o método pressupõe

        As duas hipóteses nulas descrevem processos estacionários, isto é, processos cujas
        propriedades estatísticas são as mesmas em qualquer trecho da série. Uma série
        climática diária se afasta disso de duas maneiras evidentes. A primeira é a
        sazonalidade: não só a média, mas também a variabilidade muda ao longo do ano, e há
        épocas em que os dias se afastam muito mais da normal do que em outras. Se essa diferença ficar na série,
        os descritores a detectam como estrutura, e as substitutas, que espalham a
        variabilidade por igual, a rejeitam. Na validação dos métodos, a fração de falsos
        positivos do determinismo da recorrência em séries apenas sazonais caía de 80% para
        zero depois que dividimos cada dia pelo desvio-padrão típico daquele dia do ano. É
        por isso que todas as séries analisadas são anomalias padronizadas.

        A segunda é a tendência. A Amazônia esquentou e secou no período, e a pergunta é se
        isso compromete o teste. A Tabela 1 reúne alguns diagnósticos de estacionariedade
        das quatro séries de bacia [7].
        """),
        book.table(_tab, "estacionariedade",
                   "Tabela 1. Diagnósticos de estacionariedade das séries médias das bacias "
                   "(anomalia padronizada, 2001–2024): p do teste ADF (hipótese nula: raiz "
                   "unitária) e do KPSS (hipótese nula: estacionariedade em nível), "
                   "tendência linear total em desvios-padrão com p robusto à autocorrelação "
                   "(HAC) e razão entre o maior e o menor desvio-padrão em quatro blocos de "
                   "seis anos.", selection=None),
        mo.md(r"""
        O teste ADF rejeita, em todas as séries, a hipótese de raiz unitária: as séries não
        são passeios aleatórios e sempre voltam a um nível. O KPSS, que tem a hipótese oposta,
        rejeita em todas a estacionariedade em torno de um nível fixo. Os dois resultados são
        compatíveis e contam a mesma história: as séries oscilam em torno de um nível que
        sobe. A tendência linear acumulada é de 0,8 a 1,1 desvio-padrão em 24 anos, nas duas
        bacias e nas duas variáveis, e é estatisticamente clara mesmo levando em conta a
        autocorrelação. A variabilidade, por sua vez, é estável: a razão entre o maior e o
        menor desvio-padrão em quatro blocos de seis anos fica entre 1,09 e 1,28.

        A tendência não é removida no pré-registro, por uma razão de princípio: ela é parte
        do sinal climático, e retirá-la exigiria escolher uma forma para ela. Mas nenhuma das
        duas hipóteses nulas a contempla, e uma substituta de uma série com tendência a trata
        como potência em baixa frequência, distribuída em oscilações lentas sem direção. Para
        saber se isso pesa no resultado, repetimos o teste IAAFT depois de retirar a
        tendência linear de cada série. Veremos na próxima seção que a resposta é não.
        """),
    ])
    return


@app.cell(hide_code=True)
def _():
    null_region = mo.ui.dropdown(options={load_region(s)["name"]: s for s in SLUGS},
                                 value="Bacia do Rio Xingu", label="Bacia")
    null_variable = mo.ui.radio(options={v: k for k, v in R.VARIABLES.items()},
                                value="temperatura", label="Variável", inline=True)
    null_method = mo.ui.radio(options=["IAAFT", "FT", "IAAFT sem tendência"], value="IAAFT",
                              label="Substitutas", inline=True)
    return null_method, null_region, null_variable


@app.function(hide_code=True)
def plot_nulls(slug, variable, method):
    table, nulls = basin_results()
    sel = (table.region == slug) & (table.variable == variable) & (table.method == method)
    rows = table[sel].set_index("descriptor")
    nul = nulls[(nulls.region == slug) & (nulls.variable == variable)
                & (nulls.method == method)]
    fig, axes = plt.subplots(2, 4, figsize=(15, 6.6), layout="constrained")
    for ax, d in zip(axes.flat, ORDER, strict=True):
        values = nul[nul.descriptor == d].value.dropna()
        obs = rows.loc[d, "observed"]
        ax.hist(values, bins=25, color=SERIES_COLORS[method.split()[0]], alpha=0.55)
        ax.axvline(obs, color=COLORS["ink"], lw=2.2)
        lo, hi = min(values.min(), obs), max(values.max(), obs)
        pad = 0.08 * (hi - lo or 1)
        ax.set_xlim(lo - pad, hi + pad)
        ax.set_title(R.NAMES[d], fontsize=10)
        ax.set_yticks([])
        ax.xaxis.set_major_locator(plt.MaxNLocator(4))
        ax.text(0.03, 0.95, nb.pt(f"z = {rows.loc[d, 'z']:+.1f}\np = {rows.loc[d, 'pvalue']:.3f}"),
                transform=ax.transAxes, va="top", fontsize=9,
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.8})
    fig.suptitle(f"{load_region(slug)['name']} · {R.VARIABLES[variable]} · {method} "
                 f"({B.N_SURROGATES} substitutas)", x=0.02, ha="left", fontsize=12)
    return fig


@app.cell(hide_code=True)
def _(null_method, null_region, null_variable):
    mo.vstack([
        mo.md(r"""
        ## 🧪 O teste nas duas bacias

        Como há uma só série por bacia e variável, podemos gastar muito mais esforço com cada
        uma do que no lote por célula. Usamos 199 substitutas de cada tipo, o que dá um p de
        Monte Carlo mínimo de $1/200 = 0{,}005$ no teste unilateral [5], contra $1/40$ com as
        39 substitutas de cada célula, e calculamos os oito descritores com os mesmos
        parâmetros de reconstrução escolhidos na série original: $\tau = 1$ dia, $m = 5$ e
        janela de Theiler de 10 dias. A Figura 2 mostra, para cada descritor, a distribuição
        dos seus valores nas substitutas e o valor na série original.
        """),
        mo.hstack([null_region, null_variable, null_method], justify="start", gap=1),
        book.figure(plot_nulls(null_region.value, null_variable.value, null_method.value),
                    "nulas",
                    "Figura 2. Distribuição de cada descritor nas 199 substitutas (barras) e "
                    "valor na série observada (linha), com o escore z e o p de Monte Carlo. "
                    "Na versão impressa, temperatura do Xingu com substitutas IAAFT.",
                    save=(null_region.value, null_variable.value, null_method.value)
                    == ("xingu", "t2m", "IAAFT")),
        mo.md(r"""
        Na temperatura do Xingu, a figura separa os descritores em três grupos. No primeiro, o
        valor original está muito longe das substitutas: o determinismo e a laminaridade da
        recorrência ficam a cerca de 10 desvios-padrão acima, a assimetria temporal a quase
        10 abaixo e a dimensão de correlação a 5 abaixo. São rejeições inequívocas, de séries
        mais organizadas e mais assimétricas do que qualquer processo linear com o mesmo
        espectro e a mesma distribuição. No segundo grupo, a entropia de permutação e a
        complexidade estatística, o valor original fica na borda da nuvem, com $|z|$ perto de
        2: há estrutura nos padrões de ordem, mas pouca.

        O terceiro grupo é o mais instrutivo. O expoente de Lyapunov fica dentro da nuvem,
        como já esperávamos depois da validação. E o erro de previsão não linear fica fora
        dela, mas do lado oposto ao que o caos produziria: a série original é mais difícil
        de prever um dia à frente pelo método dos vizinhos mais próximos do que as suas
        substitutas lineares. Num sistema caótico de baixa dimensão, os vizinhos no espaço de
        fases seguem caminhos parecidos por algum tempo, e a previsão melhora. Aqui ela
        piora, o que combina com o agrupamento da variabilidade da Figura 1: os vizinhos de
        um dia agitado são muitas vezes dias calmos, que não antecipam o que vem.
        """),
    ])
    return


@app.function(hide_code=True)
def plot_methods():
    table, _ = basin_results()
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.6), sharey=True, layout="constrained")
    for ax, var in zip(axes, R.VARIABLES, strict=True):
        for k, slug in enumerate(SLUGS):
            for j, (method, marker) in enumerate([("FT", "o"), ("IAAFT", "D"),
                                                  ("IAAFT sem tendência", "x")]):
                rows = table[(table.region == slug) & (table.variable == var)
                             & (table.method == method)].set_index("descriptor").reindex(ORDER)
                y = np.arange(len(ORDER)) + (k - 0.5) * 0.42 + (j - 1) * 0.11
                color = COLORS["ink"] if slug == "xingu" else COLORS["t2m"]
                ax.scatter(rows.z, y, marker=marker, s=36, color=color,
                           facecolor="white" if method == "FT" else color,
                           label=f"{load_region(slug)['name'].replace('Bacia do Rio ', '')}"
                           f" · {method}")
        ax.axvspan(-1.96, 1.96, color=COLORS["muted"], alpha=0.15, lw=0)
        ax.axvline(0, color=COLORS["muted"], lw=1)
        ax.set_xscale("symlog", linthresh=2)
        ax.set_yticks(range(len(ORDER)), [R.NAMES[d] for d in ORDER])
        ax.invert_yaxis()
        ax.set(xlabel="z contra as substitutas (escala simétrica logarítmica)",
               title=R.VARIABLES[var].capitalize())
    handles, names = axes[0].get_legend_handles_labels()
    fig.legend(handles, names, loc="outside lower center", ncol=3, frameon=False,
               fontsize=9)
    return fig


@app.cell(hide_code=True)
def _():
    _table, _ = basin_results()
    _tab = _table[_table.method == "IAAFT"].copy()
    _tab["Bacia"] = _tab.region.map(lambda s: load_region(s)["name"].replace("Bacia do Rio ", ""))
    _tab["Variável"] = _tab.variable.map(R.VARIABLES)
    _tab["Descritor"] = _tab.descriptor.map(R.NAMES)
    _tab["ordem"] = _tab.descriptor.map(ORDER.index)
    _tab = _tab.sort_values(["Bacia", "Variável", "ordem"])
    _ft = _table[_table.method == "FT"].set_index(["region", "variable", "descriptor"]).z
    _nt = _table[_table.method == "IAAFT sem tendência"].set_index(
        ["region", "variable", "descriptor"]).z
    _keys = list(zip(_tab.region, _tab.variable, _tab.descriptor, strict=True))
    _tab["z (FT)"] = [_ft[k] for k in _keys]
    _tab["z (sem tendência)"] = [_nt[k] for k in _keys]
    _tab = _tab[["Bacia", "Variável", "Descritor", "observed", "z", "pvalue", "holm",
                 "z (FT)", "z (sem tendência)"]].rename(columns={"observed": "Observado", "z": "z (IAAFT)",
                                            "pvalue": "p (IAAFT)", "holm": "p Holm"})
    mo.vstack([
        mo.md(r"""
        A Figura 3 reúne o escore $z$ de todos os descritores nas duas bacias, nas duas
        variáveis e nas três variantes do teste. A faixa cinza marca $|z| < 1{,}96$, a região
        em que o valor original não se distinguiria das substitutas se a distribuição nula
        fosse gaussiana.
        """),
        book.figure(plot_methods(), "ft_iaaft",
                    "Figura 3. Escore z de cada descritor contra 199 substitutas FT (círculos "
                    "vazios), IAAFT (losangos) e IAAFT depois de retirar a tendência linear "
                    "(cruzes), nas duas bacias e nas duas variáveis. Faixa cinza: "
                    "|z| < 1,96. Eixo em escala simétrica logarítmica, linear entre −2 e 2."),
        mo.md(r"""
        Três padrões se repetem. O primeiro é a robustez das rejeições fortes: o determinismo,
        a laminaridade e a dimensão de correlação ficam longe das substitutas em todas as
        combinações, com $|z|$ entre 5 e 23, e a assimetria temporal da temperatura também,
        com $z$ entre $-10$ e $-22$. Os padrões ordinais rejeitam com folga no déficit de
        pressão de vapor e pouco na temperatura; no Tapajós, a complexidade da temperatura
        deixa de rejeitar com a IAAFT. A assimetria do déficit de pressão de vapor do Xingu
        fica perto do limiar com qualquer das nulas.

        O segundo padrão é a diferença entre as duas nulas. Os escores contra a FT são, quase
        sempre, maiores que contra a IAAFT, e a diferença mede a parte da aparente não
        linearidade que vem só da forma da distribuição. Na assimetria temporal da
        temperatura do Tapajós, por exemplo, o escore cai de $-21{,}5$ para $-11{,}3$: metade da
        evidência contra a FT era a cauda fria da distribuição, e não a ordem dos dias. Por
        isso o pré-registro adota a IAAFT, mais exigente. O terceiro padrão é a irrelevância
        da tendência: os escores da IAAFT com e sem tendência ficam muito próximos, e nenhuma
        conclusão muda. O expoente de Lyapunov não rejeita em nenhuma combinação, e o erro de
        previsão fica, em todas, do lado oposto ao esperado para o caos. A Tabela 2 traz os
        valores, com o p corrigido pelo método de Holm [6] sobre os descritores primários.
        """),
        book.table(_tab.round(3), "resultado_bacias",
                   "Tabela 2. Teste de substitutas nas séries médias das bacias: valor "
                   "observado, escore z e p de Monte Carlo contra 199 substitutas IAAFT, p "
                   "corrigido por Holm sobre os descritores primários das duas variáveis em "
                   "cada bacia, e escore z contra 199 substitutas FT e contra 199 IAAFT da "
                   "série sem a tendência linear.", selection=None),
    ])
    return


@app.cell(hide_code=True)
def _():
    cells_variable = mo.ui.radio(options={v: k for k, v in R.VARIABLES.items()},
                                 value="temperatura", label="Variável", inline=True)
    return (cells_variable,)


@app.function(hide_code=True)
def plot_cells(variable):
    table, _ = basin_results()
    cz = cell_z()
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.6), sharey=True, layout="constrained")
    for ax, slug in zip(axes, SLUGS, strict=True):
        part = cz[(cz.region == slug) & (cz.variable == variable)]
        data = [part[part.descriptor == d].z.dropna().to_numpy() for d in ORDER]
        ax.boxplot(data, orientation="horizontal", positions=range(len(ORDER)), widths=0.55,
                   showfliers=False, patch_artist=True,
                   boxprops={"facecolor": "#dfe5e8", "edgecolor": COLORS["muted"]},
                   medianprops={"color": COLORS["ink"]},
                   whiskerprops={"color": COLORS["muted"]}, capprops={"color": COLORS["muted"]})
        rows = table[(table.region == slug) & (table.variable == variable)
                     & (table.method == "IAAFT")].set_index("descriptor").reindex(ORDER)
        ax.scatter(rows.z, range(len(ORDER)), marker="*", s=180, color=COLORS["t2m"],
                   zorder=3, label="série média da bacia")
        ax.axvspan(-1.96, 1.96, color=COLORS["muted"], alpha=0.15, lw=0)
        ax.set_xscale("symlog", linthresh=2)
        ax.set_yticks(range(len(ORDER)), [R.NAMES[d] for d in ORDER])
        ax.set(xlabel="z contra substitutas IAAFT", title=load_region(slug)["name"])
    axes[0].invert_yaxis()
    fig.legend(*axes[1].get_legend_handles_labels(), loc="outside lower center",
               frameon=False, fontsize=9)
    return fig


@app.cell(hide_code=True)
def _(cells_variable):
    mo.vstack([
        mo.md(r"""
        ## 🔭 Da bacia para as células

        O teste na série da bacia responde se a bacia, como um todo, tem estrutura não linear.
        O capítulo seguinte faz a mesma pergunta para cada uma das 1.541 células, com 39
        substitutas por célula. Antes de passar a ele, convém verificar se as duas escalas
        contam a mesma história. Há razões para que não contassem: a média de centenas de
        células pode apagar estruturas locais que não estão em fase entre si, ou criar uma
        estrutura que nenhuma célula tem, ao misturar lugares com dinâmicas diferentes. A
        Figura 4 compara o escore $z$ de cada descritor na série da bacia com a distribuição
        dos escores nas células, todos contra substitutas IAAFT. O escore $z$ é comparável
        entre as duas escalas; o p, não, porque depende do número de substitutas.
        """),
        cells_variable,
        book.figure(plot_cells(cells_variable.value), "bacia_celulas",
                    "Figura 4. Escore z contra substitutas IAAFT: distribuição nas células de "
                    "cada bacia (caixas: quartis; hastes: 1,5 intervalo interquartil; 39 "
                    "substitutas por célula) e valor na série média da bacia (estrela; 199 "
                    "substitutas). Na versão impressa, temperatura.",
                    save=cells_variable.value == "t2m"),
        mo.md(r"""
        A estrela da bacia cai quase sempre dentro da caixa das células, em geral perto da
        mediana. A série média tem o mesmo tipo e a mesma intensidade de estrutura que uma
        célula típica: a média não apaga nem cria a não linearidade. Isso tem duas
        consequências práticas. Os resultados por célula, com uma resolução de Monte Carlo
        bem menor, são coerentes com o teste de alta resolução feito na bacia; e a estrutura
        que encontramos é uma propriedade disseminada do clima da região, e não de umas
        poucas células excepcionais. O que varia de célula para célula é a intensidade, e é
        essa variação que o capítulo seguinte mapeia.
        """),
    ])
    return


@app.function(hide_code=True)
@mo.cache
def extra_basin():
    """Wolf, Kantz e Cao nas séries das bacias (F2d, F2h) e temperatura + umidade contra
    nulas multivariadas (F2c), com Holm sobre 2 bacias × 2 alvos (D-027)."""
    from amazon_chaos import gradient as G
    from amazon_chaos.nonlinear import estimators as E
    from amazon_chaos.nonlinear import multivariate as M

    lyap, multi = [], []
    for slug in SLUGS:
        cfg = load_region(slug)
        lyap.append(pd.read_parquet(E.output_dir(cfg, SPEC) / "bacia.parquet"))
        table = pd.read_parquet(M.output_dir(cfg, SPEC) / "bacia.parquet")
        multi.append(M.pvalues(table))
    multi = pd.concat(multi, ignore_index=True)
    multi["holm"] = multi.groupby(["null", "metodo", "estatistica"]).pvalue.transform(
        lambda p: G.adjust(p, "holm"))
    return pd.concat(lyap, ignore_index=True), multi


@app.cell(hide_code=True)
def _():
    _lyap, _multi = extra_basin()
    _names = {"wolf": "Lyapunov (Wolf)", "kantz": "Lyapunov (Kantz)", "cao_de2": "Cao · D_E2"}
    _t3 = pd.DataFrame({
        "Bacia": _lyap.region.map(lambda s: load_region(s)["name"].replace("Bacia do Rio ", "")),
        "Variável": _lyap.variable.map(R.VARIABLES), "Estimador": _lyap.descriptor.map(_names),
        "Observado": _lyap.observed.round(3), "Média das substitutas": _lyap.null_mean.round(3),
        "z": _lyap.z.round(1), "p": _lyap.pvalue.round(3),
        "m de saturação (Cao)": _lyap.cao_m.astype(int)})
    _m = _multi[_multi.estatistica == "ganho"]
    _t4 = pd.DataFrame({
        "Bacia": _m.region.map(lambda s: load_region(s)["name"].replace("Bacia do Rio ", "")),
        "Alvo": _m.alvo.map({"t2m": "temperatura", "q": "umidade específica"}),
        "Previsor": _m.metodo.map({"nn": "vizinhos", "smap": "S-map"}), "Nula": _m["null"],
        "Ganho observado": _m.observado.round(4), "Ganho nas substitutas": _m.nulo_media.round(4),
        "p": _m.pvalue.round(3), "p Holm": _m.holm.round(3)})
    mo.vstack([
        mo.md(r"""
        ## 🧮 Mais três estimadores e as duas variáveis juntas (comparativo)

        Depois da revisão crítica, acrescentamos às séries das bacias, com as mesmas 199
        substitutas IAAFT, três estimadores que o pré-registro não tinha (D-027): os
        expoentes de Lyapunov de Wolf e de Kantz, ao lado do de Rosenstein, e o afastamento
        $D_{E2}$ do método de Cao, que mede se o valor seguinte depende do passado
        reconstruído além do que um processo sem memória determinística permitiria [8, 9,
        10]. A Tabela 3 traz os resultados.
        """),
        book.table(_t3, "estimadores_bacia",
                   "Tabela 3. Comparativo (D-027). Lyapunov de Wolf e de Kantz e afastamento "
                   "D_E2 de Cao nas séries médias das bacias, contra 199 substitutas IAAFT, com "
                   "a dimensão em que o E1 de Cao satura.", selection=None),
        mo.md(r"""
        Os três contam a história da Tabela 2 por outros caminhos. O Kantz fica acima das
        substitutas, mas o capítulo 5 mostra que ele faz o mesmo num processo estocástico
        com variância condicional; o Wolf fica abaixo delas. O $D_{E2}$ de Cao, o único dos
        três que separa caos de processos estocásticos no portão, fica entre 0,02 e 0,05.
        Na temperatura, ele não se distingue das substitutas; no VPD, fica um pouco acima
        delas nas duas bacias, e no Tapajós acima também de quase todas as séries das nulas
        estocásticas. Mesmo assim, é de quatro a dez vezes menor que nos sistemas caóticos
        do portão (0,08 a 0,32), e a dimensão só satura em 8 ou 9: os valores futuros
        dependem pouco do passado reconstruído, com um traço de dependência a mais no VPD.

        A segunda pergunta é se temperatura e umidade, juntas, têm uma estrutura que cada
        uma sozinha não tem. Prevemos cada variável a partir do seu próprio passado, do
        passado da outra e dos dois juntos, por vizinhos próximos e por S-map, e medimos o
        ganho de juntar as duas. A nula preserva os dois espectros e a correlação entre as
        variáveis em cada escala de tempo, com a mesma fase aleatória nos dois canais
        (Prichard e Theiler [11]) ou na sua versão IAAFT; substitutas independentes para
        cada variável destruiriam a correlação entre elas e rejeitariam por construção.
        """),
        book.table(_t4, "multivariado_bacia",
                   "Tabela 4. Comparativo (D-027). Ganho de prever cada variável com as duas "
                   "juntas, em vez da melhor isolada (erro relativo ao desvio do treino), na "
                   "série média de cada bacia e na média de 199 substitutas multivariadas FT e "
                   "IAAFT, com p unilateral e Holm sobre as duas bacias e os dois alvos.",
                   selection=None),
        mo.md(r"""
        Com vizinhos próximos, juntar as duas variáveis piora a previsão, nos dados e nas
        substitutas: o espaço fica grande demais para cinco vizinhos. Com o S-map, juntar
        as duas melhora um pouco a previsão, mais nos dados do que nas substitutas, mas o
        ganho é de 0,2% a 1% do erro e, corrigido para as quatro comparações, só se sustenta
        no Tapajós, nas duas variáveis, contra a nula de fase comum. Um modelo linear
        com os mesmos atrasos prevê quase tão bem quanto o S-map conjunto. A interação entre
        temperatura e umidade nas séries das bacias é, portanto, essencialmente a que a
        correlação linear entre elas já descreve.

        Repetimos a análise nas cerca de 60 células da subamostra de cada bacia, com 39
        substitutas IAAFT multivariadas por célula. O erro conjunto nunca fica abaixo do das
        substitutas, e o ganho do S-map conjunto na previsão da temperatura passa do nível de
        5% em 13% das células do Xingu e 23% das do Tapajós, nenhuma delas depois da correção
        de Benjamini–Hochberg. Na umidade específica, o ganho passa do nível de 5% em 73% das
        células do Xingu e 50% das do Tapajós, e a correção mantém 57% das do Xingu e nenhuma
        do Tapajós. Há, portanto, um pouco de estrutura conjunta não linear na previsão da
        umidade, mais clara no Xingu, mas de novo com ganhos pequenos: a mediana nas células
        é de 0,6% do erro no Xingu e de 1,2% no Tapajós.
        """),
    ])
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 🧭 O que levamos para o próximo capítulo

    As séries diárias médias das duas bacias não são compatíveis com um processo linear
    gaussiano, nem com um processo assim visto através de uma transformação fixa dos
    valores. Essa conclusão não depende da tendência de aquecimento, que retiramos sem
    mudar o resultado, nem da forma da distribuição, que a IAAFT preserva. A estrutura que
    sobra é de um tipo específico: recorrências mais organizadas, padrões de ordem menos
    uniformes, quedas mais bruscas que subidas e períodos agitados que se agrupam. Ela não
    inclui o que distinguiria um caos de baixa dimensão: o expoente de Lyapunov não se
    separa das substitutas, e a previsão não linear fica pior, e não melhor, do que nas
    séries lineares equivalentes. Os estimadores acrescentados depois, sobretudo o teste de
    Cao, e a análise conjunta de temperatura e umidade apontam na mesma direção.

    O quadro mais coerente com esses resultados é o de um processo não linear e
    estocástico, em que o ruído não é um acessório que esconde uma dinâmica simples, mas
    parte da própria dinâmica. É com essa leitura, e com a confirmação de que bacia e
    células contam a mesma história, que passamos à análise célula a célula.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 📚 Referências

    [1] Theiler, J.; Eubank, S.; Longtin, A.; Galdrikian, B.; Farmer, J. D. Testing for
    nonlinearity in time series: the method of surrogate data. *Physica D*, v. 58,
    p. 77–94, 1992.

    [2] Schreiber, T.; Schmitz, A. Improved surrogate data for nonlinearity tests.
    *Physical Review Letters*, v. 77, p. 635–638, 1996.

    [3] Schreiber, T.; Schmitz, A. Surrogate time series. *Physica D*, v. 142, p. 346–382,
    2000.

    [4] Lancaster, G.; Iatsenko, D.; Pidde, A.; Ticcinelli, V.; Stefanovska, A. Surrogate
    data for hypothesis testing of physical systems. *Physics Reports*, v. 748, p. 1–60,
    2018.

    [5] Theiler, J.; Prichard, D. Constrained-realization Monte-Carlo method for
    hypothesis testing. *Physica D*, v. 94, p. 221–235, 1996.

    [6] Holm, S. A simple sequentially rejective multiple test procedure. *Scandinavian
    Journal of Statistics*, v. 6, p. 65–70, 1979.

    [7] Kwiatkowski, D.; Phillips, P. C. B.; Schmidt, P.; Shin, Y. Testing the null
    hypothesis of stationarity against the alternative of a unit root. *Journal of
    Econometrics*, v. 54, p. 159–178, 1992.

    [8] Wolf, A.; Swift, J. B.; Swinney, H. L.; Vastano, J. A. Determining Lyapunov
    exponents from a time series. *Physica D*, v. 16, p. 285–317, 1985.

    [9] Kantz, H. A robust method to estimate the maximal Lyapunov exponent of a time
    series. *Physics Letters A*, v. 185, p. 77–87, 1994.

    [10] Cao, L. Practical method for determining the minimum embedding dimension of a
    scalar time series. *Physica D*, v. 110, p. 43–50, 1997.

    [11] Prichard, D.; Theiler, J. Generating surrogate data for time series with several
    simultaneously measured variables. *Physical Review Letters*, v. 73, p. 951–954, 1994.
    """)
    return


if __name__ == "__main__":
    app.run()
