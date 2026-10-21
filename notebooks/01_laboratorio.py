import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium", app_title="01 · Laboratório de sistemas dinâmicos")

with app.setup(hide_code=True):
    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    from amazon_chaos import nb
    from amazon_chaos.nonlinear.embedding import delay_embedding
    from amazon_chaos.nonlinear.lyapunov import rosenstein
    from amazon_chaos.nonlinear.models import MemoryMap, MoistureVegetation
    from amazon_chaos.nonlinear.recurrence import recurrence_threshold
    from amazon_chaos.nonlinear.suite import surrogates
    from amazon_chaos.nonlinear.synthetic import ar1
    from amazon_chaos.viz import COLORS

    book = nb.notebook("01_laboratorio")
    FLOW = MoistureVegetation()
    MAP = MemoryMap()
    MU_CHAOS = 11.5


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # 🌀 Laboratório de sistemas dinâmicos

    Antes de perguntar se o clima da Amazônia esconde algum traço de caos, precisamos saber
    reconhecer caos quando ele está diante de nós, e, talvez mais importante, saber quando
    ele não está. Este capítulo é um laboratório: trabalhamos com sistemas cujas equações
    conhecemos por inteiro, de modo que cada resposta pode ser conferida. É aqui que
    aprendemos o vocabulário que o resto do trabalho usa, o que é um equilíbrio, quando ele
    é estável, o que é uma bifurcação, o que mede o expoente de Lyapunov, e é aqui também que
    descobrimos as armadilhas em que é fácil cair quando só temos uma série de dados.

    O percurso tem cinco movimentos. Começamos por um modelo mínimo de floresta e umidade,
    um sistema contínuo de duas variáveis, onde estudamos equilíbrios, estabilidade e a
    perda da vegetação quando a umidade disponível cai abaixo de um limiar. Em seguida
    passamos a um mapa discreto com memória, capaz de ciclos e de caos, e acompanhamos o
    caminho que leva da ordem à desordem. No terceiro movimento medimos o caos de duas
    maneiras, primeiro pela equação e depois fingindo não conhecê-la, a partir de uma única
    série observada, que é a situação real dos dados climáticos. O quarto movimento
    contamina essa série com sazonalidade e ruído e coloca ao lado um processo puramente
    aleatório, para mostrar como um indicador de caos pode enganar. Por fim, apresentamos as
    duas ferramentas que nos protegem desse engano, as séries substitutas e os gráficos de
    recorrência, e explicamos como tudo isso desemboca na análise das bacias do Xingu e do
    Tapajós.

    Os modelos daqui não pretendem reproduzir a Amazônia em números. São caricaturas
    propositais, simples o bastante para que cada efeito possa ser rastreado até a sua
    causa. O código que gera cada figura está recolhido; quem quiser vê-lo pode abrir a
    célula correspondente.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 🌱 Um modelo mínimo de floresta e umidade

    A floresta amazônica não apenas recebe chuva: ela a devolve. Uma parte importante do
    vapor que chove sobre a bacia foi transpirada por árvores mais a leste, e esse
    reaproveitamento é uma das razões pelas quais se teme que o desmatamento, acima de certo
    ponto, reduza a própria umidade que mantém a floresta de pé [9, 10]. Vamos traduzir essa
    ideia na linguagem dos sistemas dinâmicos com o menor número possível de ingredientes.

    Considere dois índices adimensionais que variam no tempo: $m(t)$, a disponibilidade de
    umidade, e $v(t)$, a condição da vegetação, entre 0 (ausente) e 1 (plena). A umidade
    recebe uma entrada externa constante $P$, que pensamos como a umidade trazida do oceano,
    ganha um reforço proporcional à vegetação, $\alpha v$, que representa a reciclagem pela
    transpiração, e se perde a uma taxa $\beta m$. A vegetação cresce de forma logística, com
    uma taxa máxima $r$ que depende da umidade de modo saturante, e morre a uma taxa $d$.
    Escrevemos isso como

    $$
    \dot m = P + \alpha v - \beta m,
    \qquad
    \dot v = v\left[r(1-v)\,\frac{m}{h+m} - d\right],
    $$

    em que o ponto indica derivada no tempo. O fator $m/(h+m)$ é uma resposta de saturação
    (do tipo Michaelis–Menten): quando $m$ é pequeno, cada acréscimo de umidade faz muita
    diferença para a vegetação; quando $m$ já é grande, quase nenhuma. A constante $h$ é a
    umidade com que a vegetação cresce à metade da sua taxa máxima. Usaremos $\alpha=0{,}10$,
    $\beta=0{,}80$, $r=1{,}60$, $h=0{,}25$ e $d=0{,}45$, e deixaremos $P$ variar: é o botão que
    imita um clima mais seco ou mais úmido.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## ⚖️ Equilíbrios e estabilidade

    Um equilíbrio é um estado em que nada muda, ou seja, em que $\dot m = 0$ e $\dot v = 0$
    ao mesmo tempo. Mas existir não basta: um lápis equilibrado sobre a ponta também está em
    equilíbrio, só que qualquer sopro o derruba. Dizemos que um equilíbrio é estável quando
    pequenas perturbações se apagam com o tempo, e instável quando crescem.

    Formalmente, seja $\mathbf x = (m, v)$ e $\dot{\mathbf x} = \mathbf f(\mathbf x)$. Perto
    de um equilíbrio $\mathbf x^*$, escrevemos $\mathbf x = \mathbf x^* + \boldsymbol\delta$
    e expandimos em série de Taylor:

    $$
    \dot{\boldsymbol\delta} = \mathbf f(\mathbf x^* + \boldsymbol\delta)
    \approx \underbrace{\mathbf f(\mathbf x^*)}_{=\,0} + J(\mathbf x^*)\,\boldsymbol\delta,
    \qquad
    J_{ij} = \frac{\partial f_i}{\partial x_j}.
    $$

    A matriz jacobiana $J$ governa a evolução das perturbações pequenas. Se $J$ tem
    autovalores $\lambda_k$ e autovetores $\mathbf u_k$, a perturbação se decompõe em modos
    que evoluem como $e^{\lambda_k t}\,\mathbf u_k$. Daí o critério de estabilidade linear
    para sistemas contínuos: o equilíbrio é estável se todos os autovalores têm parte real
    negativa, $\operatorname{Re}\lambda_k < 0$, e instável se algum tem parte real positiva
    [1]. No nosso modelo,

    $$
    J(m, v) =
    \begin{pmatrix}
    -\beta & \alpha \\[4pt]
    r\,v(1-v)\,\dfrac{h}{(h+m)^2} & r(1-2v)\,\dfrac{m}{h+m} - d
    \end{pmatrix}.
    $$

    Há sempre um equilíbrio sem vegetação, $E_0 = (P/\beta,\, 0)$. Nele a jacobiana é
    triangular, e seus autovalores são os elementos da diagonal: $\lambda_1 = -\beta < 0$,
    sempre estabilizador, e

    $$
    \lambda_2 = r\,\frac{P/\beta}{h + P/\beta} - d .
    $$

    O sinal de $\lambda_2$ responde a uma pergunta ecológica simples: se aparecer um pouco
    de vegetação num lugar sem nenhuma, ela consegue se estabelecer? Ela consegue se
    $\lambda_2 > 0$. A fronteira $\lambda_2 = 0$ define um limiar de umidade externa:

    $$
    r\,\frac{P_c/\beta}{h + P_c/\beta} = d
    \quad\Longrightarrow\quad
    \boxed{\,P_c = \frac{\beta\, d\, h}{r - d}\,}.
    $$
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.callout(mo.md(nb.pt(
        f"Com os parâmetros escolhidos, o limiar vale P_c = {FLOW.critical_p:.4f}. Abaixo dele, "
        "o deserto é estável e nenhuma vegetação se sustenta; acima, o deserto se torna "
        "instável e a vegetação ocupa o sistema. Toda a física do modelo, nesse ponto, cabe "
        "em uma única desigualdade.")), kind="success")
    return


@app.cell(hide_code=True)
def _():
    p_slider = mo.ui.slider(0.02, 0.40, value=0.25, step=0.01,
                            label="Entrada externa de umidade P", show_value=True)
    return (p_slider,)


@app.function(hide_code=True)
def plot_flow(p):
    t, y = FLOW.simulate(p)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.3), layout="constrained")
    ax1.plot(t, y[0], color=COLORS["precip"], lw=2, label="m(t), umidade")
    ax1.plot(t, y[1], color=COLORS["q"], lw=2, label="v(t), vegetação")
    ax1.set(xlabel="tempo", ylabel="estado (adimensional)",
            title=nb.pt(f"Uma trajetória a partir de (0,45; 0,35) · P = {p:.2f}"))
    ax1.legend()
    for z0 in [(0.15, 0.1), (0.3, 0.7), (0.6, 0.2), (1.0, 0.8), (1.2, 0.45)]:
        _, y = FLOW.simulate(p, z0=z0, t_max=35)
        ax2.plot(y[0], y[1], lw=1.5)
        ax2.scatter(y[0, 0], y[1, 0], s=22, zorder=3)
    ax2.set(xlabel="m, umidade", ylabel="v, vegetação",
            title="Retrato de fase: cinco estados iniciais")
    return fig


@app.cell(hide_code=True)
def _(p_slider):
    _side = "acima" if p_slider.value > FLOW.critical_p else "abaixo"
    mo.vstack([
        mo.md(r"""
        Vamos ver o limiar em ação. O controle abaixo muda a entrada de umidade $P$, e as
        duas figuras se recalculam. À esquerda está uma única trajetória ao longo do tempo,
        com a umidade em azul e a vegetação em verde. À direita está o retrato de fase: cada
        curva parte de um estado inicial diferente (o ponto) e mostra o caminho que o sistema
        percorre no plano $(m, v)$. Comece no valor inicial, bem acima do limiar, e depois
        desça $P$ devagar, passando por 0,08.
        """),
        p_slider,
        mo.as_html(plot_flow(p_slider.value)),
        mo.md(nb.pt(
            f"Com P = {p_slider.value:.2f}, estamos {_side} do limiar P_c ≈ "
            f"{FLOW.critical_p:.3f}. " + (
                "Todas as curvas do retrato de fase convergem para um mesmo ponto com "
                "vegetação: é o equilíbrio vegetado, estável, que atrai qualquer estado "
                "inicial razoável. Na série temporal, a vegetação sobe e se acomoda num "
                "patamar, e a umidade fica acima do que a entrada externa sustentaria "
                "sozinha, porque a vegetação recicla parte dela." if _side == "acima" else
                "Agora todas as curvas terminam sobre o eixo horizontal, com v = 0: a "
                "vegetação desaparece, não importa de onde começou, e a umidade se acomoda "
                "em P/β, só com a contribuição externa. O equilíbrio sem vegetação passou a "
                "ser o atrator."))),
    ])
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    Duas dúvidas costumam surgir aqui. A primeira é por que a vegetação não some de uma vez
    quando $P$ cruza o limiar: perto de $P_c$ o autovalor $\lambda_2$ é quase zero, e as
    perturbações se desfazem cada vez mais devagar. Esse alongamento do tempo de resposta
    perto de uma mudança de estabilidade é a base dos chamados sinais precoces, que
    retomaremos na análise dos dados. A segunda é se o desaparecimento da vegetação aqui é
    um "ponto de não retorno". Não exatamente, como mostra a próxima figura.
    """)
    return


@app.function(hide_code=True)
def plot_stability():
    ps = np.linspace(0.015, 0.40, 280)
    bare, vegetated, stable = FLOW.equilibria(ps)
    fig, ax = plt.subplots(figsize=(10, 4.6), layout="constrained")
    ax.plot(ps[bare], np.zeros(bare.sum()), ".", ms=4, color=COLORS["ink"],
            label="sem vegetação, estável")
    ax.plot(ps[~bare], np.zeros((~bare).sum()), ".", ms=4, color="#c9ced2",
            label="sem vegetação, instável")
    ok = np.isfinite(vegetated) & stable
    ax.plot(ps[ok], vegetated[ok], ".", ms=4, color=COLORS["q"], label="vegetado, estável")
    ax.axvline(FLOW.critical_p, ls="--", color=COLORS["t2m"],
               label=nb.pt(f"limiar P_c = {FLOW.critical_p:.3f}"))
    ax.set(xlabel="P, entrada externa de umidade", ylabel="v*, vegetação no equilíbrio",
           title="Equilíbrios do modelo umidade–vegetação em função de P")
    ax.legend()
    return fig


@app.cell(hide_code=True)
def _():
    mo.vstack([
        mo.md(r"""
        ## 🔀 Uma troca de estabilidade

        Em vez de mover o controle à mão, podemos varrer muitos valores de $P$ e marcar, para
        cada um, os equilíbrios e a sua estabilidade. O resultado é um diagrama de
        bifurcação: no eixo horizontal está o parâmetro, no vertical o valor de equilíbrio da
        vegetação. Uma bifurcação é uma mudança qualitativa do comportamento de longo prazo
        quando um parâmetro cruza um valor crítico [1].
        """),
        book.figure(plot_stability(), "troca_estabilidade",
                    "Figura 1. Equilíbrios do modelo umidade–vegetação. Pontos escuros: "
                    "equilíbrio sem vegetação estável; claros: o mesmo equilíbrio, instável; "
                    "verdes: equilíbrio vegetado estável. A linha tracejada marca P_c."),
        mo.md(r"""
        Leia a figura da esquerda para a direita. Enquanto $P < P_c$, só existe o estado sem
        vegetação, e ele é estável. Em $P = P_c$ os dois ramos se encontram, e a partir daí o
        estado sem vegetação continua existindo, mas instável (pontos claros), enquanto um
        ramo vegetado estável cresce continuamente. Esse cruzamento, em que dois equilíbrios
        trocam de estabilidade ao se encontrarem, chama-se bifurcação transcrítica.

        O detalhe importante está na palavra "continuamente". Ao reduzir $P$, a vegetação de
        equilíbrio diminui aos poucos até chegar a zero em $P_c$, sem saltos, e se $P$ voltar
        a subir ela volta pelo mesmo caminho. Isso é uma transição, mas não é um ponto de não
        retorno. Os pontos de não retorno discutidos para a Amazônia supõem biestabilidade:
        dois estados estáveis coexistindo, floresta e savana, separados por um limiar a
        partir do qual o sistema salta de um ao outro e não volta pelo mesmo caminho
        (histerese) [10, 13]. Nosso modelo mínimo não tem essa propriedade, e é bom que o
        leitor saiba disso antes de ver qualquer gráfico de dados reais.
        """),
        mo.callout(mo.md(
            "Caos e ponto de não retorno são conceitos diferentes. Uma transição pode ser "
            "suave, como aqui; pode ser abrupta e com histerese, numa biestabilidade; e "
            "nenhuma das duas exige caos. Ao longo do trabalho, nunca tratamos um indicador "
            "de caos como evidência de um ponto de não retorno."), kind="warn"),
    ])
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 🔁 Um mapa com memória

    Sistemas contínuos de duas variáveis, como o anterior, não podem ser caóticos: o teorema
    de Poincaré–Bendixson garante que suas trajetórias limitadas terminam em equilíbrios ou
    em ciclos [1]. Para encontrar caos com poucas variáveis, passamos a um sistema discreto,
    em que o tempo avança em passos, como de um ano para o outro.

    Seja $x_n \in (0, 1)$ um índice agregado do estado floresta–atmosfera no passo $n$.
    Propomos

    $$
    x_{n+1} = S\!\left[\, b + \mu\, x_n (1 - x_n) - \kappa\, x_{n-1} \right],
    \qquad
    S(q) = \frac{1}{1 + e^{-a q}} .
    $$

    O termo $\mu x_n(1 - x_n)$ é uma realimentação não linear do estado atual, a mesma do
    célebre mapa logístico: favorece crescimento em estados intermediários e o freia nos
    extremos. O termo $-\kappa x_{n-1}$ é uma memória: o passo anterior ainda pesa no
    presente, como solo seco de um ano que reduz a umidade do seguinte. O forçamento $b$ é
    um nível basal, e a sigmoide $S$ mantém o índice entre 0 e 1. Usamos $a = 2$,
    $\kappa = 1$ e $b = -0{,}4$, e o parâmetro de controle é a intensidade da realimentação,
    $\mu$.

    Embora observemos uma única variável, o estado completo é bidimensional,
    $\mathbf z_n = (x_n,\, x_{n-1})$, e o mapa se escreve como
    $\mathbf z_{n+1} = F(\mathbf z_n)$. Essa observação parece um detalhe técnico, mas é a
    semente de uma ideia central deste trabalho: valores atrasados da própria série podem
    reconstruir o estado de um sistema que não observamos por inteiro.

    Um ponto fixo satisfaz $x^* = S[\,b + \mu x^*(1 - x^*) - \kappa x^*]$, que resolvemos
    numericamente. Para estudar sua estabilidade, repetimos o raciocínio do caso contínuo,
    agora com $\boldsymbol\delta_{n+1} \approx J(\mathbf z^*)\,\boldsymbol\delta_n$. Num
    mapa, os modos evoluem como $\lambda_k^n$, e não como $e^{\lambda_k t}$, de modo que o
    critério muda: o ponto fixo é estável se todos os autovalores estiverem dentro do
    círculo unitário, $|\lambda_k| < 1$ [1]. A jacobiana é

    $$
    J(x, y) =
    \begin{pmatrix}
    S'(q)\,\mu\,(1 - 2x) & -\,S'(q)\,\kappa \\[2pt]
    1 & 0
    \end{pmatrix},
    \qquad
    S'(q) = a\,S(q)\,[1 - S(q)],
    $$

    com $q = b + \mu x(1-x) - \kappa y$. A segunda linha, $(1, 0)$, apenas diz que o novo
    "valor anterior" é o valor atual.
    """)
    return


@app.cell(hide_code=True)
def _():
    _rows = []
    for _mu in [7.0, 8.0, 10.0, 11.5, 12.5, 14.0]:
        _x, _eig = MAP.fixed_point(_mu)
        _rows.append({"μ": _mu, "x*": round(_x, 4), "maior |λ|": round(np.abs(_eig).max(), 3),
                      "ponto fixo estável": "sim" if np.abs(_eig).max() < 1 else "não",
                      "λ₁ de Lyapunov": round(MAP.lyapunov(_mu), 3)})
    mo.vstack([
        mo.md("A tabela mostra, para alguns valores de $\\mu$, o ponto fixo, o maior módulo "
              "dos autovalores da jacobiana nele e o expoente de Lyapunov, que definiremos "
              "logo adiante."),
        book.table(pd.DataFrame(_rows), "pontos_fixos",
                   "Tabela 1. Ponto fixo do mapa com memória, maior módulo dos autovalores da "
                   "jacobiana e maior expoente de Lyapunov, para alguns valores de μ.",
                   selection=None),
        mo.md(r"""
        Entre $\mu = 7$ e $\mu = 8$ o maior módulo atravessa 1 e o ponto fixo perde a
        estabilidade. Note que o ponto fixo continua existindo; o que muda é que as
        trajetórias deixam de ser atraídas para ele. Para onde elas vão então? Como a
        sigmoide impede que $x$ escape de $(0, 1)$, elas não divergem: passam a oscilar,
        primeiro de forma regular e, para $\mu$ maior, de forma irregular. A última coluna
        antecipa o desfecho: o expoente de Lyapunov, negativo enquanto há um atrator
        regular, torna-se positivo quando a dinâmica é caótica, como em $\mu = 11{,}5$ e
        $12{,}5$. O valor negativo em $\mu = 14$ não é um erro: ali o mapa cai numa janela
        de ordem, um intervalo estreito de $\mu$ em que um ciclo estável reaparece no meio
        do caos, como veremos no diagrama de bifurcação.
        """),
    ])
    return


@app.cell(hide_code=True)
def _():
    mu_slider = mo.ui.slider(6.0, 16.0, value=11.5, step=0.1,
                             label="Intensidade da realimentação μ", show_value=True)
    return (mu_slider,)


@app.function(hide_code=True)
def plot_map(mu):
    tr = MAP.simulate(mu, n=5000, discard=1000)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.2), layout="constrained")
    ax1.plot(tr[:200, 0], lw=1, color=COLORS["ink"], marker=".", ms=3)
    ax1.set(xlabel="passo n", ylabel="x_n", title=nb.pt(f"Série · μ = {mu:.1f}"))
    ax2.scatter(tr[:, 0], tr[:, 1], s=2, alpha=0.5, color=COLORS["t2m"])
    ax2.set(xlabel="x_n", ylabel="x_{n−1}", title="Espaço de estados (4.000 passos)")
    return fig


@app.cell(hide_code=True)
def _(mu_slider):
    _lam = MAP.lyapunov(mu_slider.value)
    mo.vstack([
        mo.md(r"""
        Experimente. O controle muda $\mu$. À esquerda vemos 200 passos da série, já sem o
        transiente inicial; à direita, os 4.000 estados seguintes no plano
        $(x_n, x_{n-1})$. Um ponto fixo aparece como um único ponto; um ciclo de período
        $k$, como $k$ pontos; um regime caótico, como uma nuvem com forma definida, que não
        se fecha nunca. Procure $\mu = 7$, $8$, $10$, $11{,}5$ e $14$.
        """),
        mu_slider,
        mo.as_html(plot_map(mu_slider.value)),
        mo.callout(mo.md(nb.pt(
            f"Para μ = {mu_slider.value:.1f}, o expoente de Lyapunov calculado pela equação "
            f"é λ₁ = {_lam:+.3f} por passo. " + (
                "Positivo: perturbações minúsculas crescem exponencialmente e a nuvem do "
                "espaço de estados é um atrator caótico." if _lam > 0.005 else
                "Negativo ou nulo: as perturbações se contraem e a trajetória se acomoda num "
                "atrator regular, um ponto ou um ciclo."))),
            kind="success" if _lam > 0.005 else "info"),
    ])
    return


@app.function(hide_code=True)
def plot_bifurcation():
    mus = np.linspace(6.0, 16.0, 750)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7.8), sharex=True, layout="constrained")
    for mu in mus:
        values = MAP.simulate(mu, n=1400, discard=1260)[:, 0]
        ax1.plot(np.full(len(values), mu), values, ",k", alpha=0.35)
    ax1.set(ylabel="valores de x no longo prazo",
            title="Diagrama de bifurcação do mapa com memória")
    grid = np.linspace(6.0, 16.0, 260)
    lyap = np.array([MAP.lyapunov(mu, n=4200, transient=700) for mu in grid])
    ax2.fill_between(grid, 0, lyap, where=lyap > 0, color=COLORS["t2m"], alpha=0.25)
    ax2.plot(grid, lyap, lw=1.2, color=COLORS["t2m"])
    ax2.axhline(0, ls="--", color=COLORS["ink"])
    ax2.set(xlabel="μ, intensidade da realimentação", ylabel="λ₁ por passo",
            title="Maior expoente de Lyapunov, calculado pela equação")
    return fig


@app.cell(hide_code=True)
def _():
    mo.vstack([
        mo.md(r"""
        ## 🌳 Da ordem ao caos, num único gráfico

        Para cada um de 750 valores de $\mu$, iteramos o mapa, descartamos os primeiros
        1.260 passos e marcamos os 140 valores seguintes de $x$. Se o atrator é um ponto
        fixo, todos caem no mesmo lugar e vemos um ponto; se é um ciclo de período 2, dois;
        se é caótico, um segmento inteiro se preenche. Embaixo, o expoente de Lyapunov para
        os mesmos valores de $\mu$.
        """),
        book.figure(plot_bifurcation(), "bifurcacao_lyapunov",
                    "Figura 2. Acima, valores de longo prazo de x em função de μ. Abaixo, o "
                    "maior expoente de Lyapunov pela dinâmica tangente; em vermelho, os "
                    "intervalos com λ₁ > 0."),
        mo.md(r"""
        Percorrendo o diagrama da esquerda para a direita, o ponto fixo único se divide em
        dois ramos, um ciclo de período 2, e depois os ramos se multiplicam e se misturam
        numa faixa densa: é o regime caótico. Dentro dele aparecem janelas estreitas em que
        a ordem volta por um intervalo curto de $\mu$, um fenômeno típico de mapas
        não lineares. O painel de baixo confirma a leitura: enquanto o atrator é regular,
        $\lambda_1 < 0$, tocando zero exatamente nas bifurcações; nas faixas densas,
        $\lambda_1 > 0$; nas janelas de ordem, ele mergulha de novo abaixo de zero.

        Uma pergunta natural é se "caótico" quer dizer "aleatório". Não quer. O mapa é
        inteiramente determinístico: o mesmo estado inicial produz sempre a mesma
        sequência. O que o caos acrescenta é a impossibilidade prática de prever a longo
        prazo, porque qualquer imprecisão no estado inicial cresce exponencialmente. É isso
        que medimos a seguir.
        """),
    ])
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 🦋 Medindo o caos pela equação

    Tome dois estados muito próximos, separados por uma perturbação $\boldsymbol\delta_0$.
    Num sistema caótico, a distância entre as trajetórias cresce, em média, como

    $$
    \|\boldsymbol\delta_n\| \approx \|\boldsymbol\delta_0\|\, e^{\lambda_1 n},
    $$

    e o número $\lambda_1$ é o maior expoente de Lyapunov. Em termos precisos, como a
    perturbação evolui pela linearização,
    $\boldsymbol\delta_{n+1} \approx J(\mathbf z_n)\,\boldsymbol\delta_n$, temos
    $\boldsymbol\delta_n \approx J(\mathbf z_{n-1}) \cdots J(\mathbf z_1)\, J(\mathbf z_0)\,
    \boldsymbol\delta_0$ e

    $$
    \lambda_1 = \lim_{n \to \infty} \frac{1}{n}
    \ln \frac{\|\boldsymbol\delta_n\|}{\|\boldsymbol\delta_0\|} .
    $$

    Para quase todo $\boldsymbol\delta_0$, esse limite seleciona a direção de maior
    expansão [1, 2]. Calcular o produto de jacobianas diretamente estoura a precisão
    numérica, porque o vetor cresce sem limite. O algoritmo de Benettin [5] contorna isso:
    a cada passo aplicamos $J$ ao vetor tangente, guardamos o logaritmo do seu
    comprimento e o renormalizamos para comprimento 1,

    $$
    \mathbf w_{n} = J(\mathbf z_n)\,\mathbf v_n, \qquad
    \mathbf v_{n+1} = \frac{\mathbf w_n}{\|\mathbf w_n\|}, \qquad
    \lambda_1 \approx \frac{1}{N} \sum_{n=1}^{N} \ln \|\mathbf w_n\| .
    $$

    Foi assim que calculamos a Tabela 1 e o painel inferior da Figura 2. O sinal tem uma
    leitura direta: $\lambda_1 < 0$ significa que as perturbações se contraem, $\lambda_1 = 0$
    marca a fronteira e $\lambda_1 > 0$ significa dependência sensível às condições
    iniciais, a assinatura do caos determinístico. O inverso $1/\lambda_1$ é um tempo
    característico de previsibilidade: a cada $1/\lambda_1$ passos, um erro inicial cresce
    por um fator $e$.

    ## 🔭 E se não conhecêssemos a equação?

    Com dados climáticos, não temos $F$ nem $J$: temos uma série de números. O teorema de
    imersão de Takens [3] diz que, para um sistema determinístico cujo atrator tem dimensão
    $d$, os vetores de atraso

    $$
    \mathbf X_n = \left(x_n,\; x_{n-\tau},\; \ldots,\; x_{n-(m-1)\tau}\right)
    $$

    reconstroem uma cópia do atrator, com a mesma topologia e os mesmos invariantes, como o
    expoente de Lyapunov, desde que a dimensão de imersão satisfaça $m > 2d$. O atraso
    $\tau$ e a dimensão $m$ são escolhas nossas; no laboratório sabemos que $\tau = 1$ e um
    $m$ pequeno bastam, e nos dados reais eles serão escolhidos por regras fixadas de
    antemão: a informação mútua para $\tau$ [12] e os falsos vizinhos mais próximos para
    $m$ [11].

    O método de Rosenstein [4] estima $\lambda_1$ só a partir desses vetores. Para cada
    $\mathbf X_i$, procuramos o vizinho mais próximo $\mathbf X_{j(i)}$ que esteja longe no
    tempo, $|i - j| > w$; essa exclusão, a janela de Theiler [8], impede que o "vizinho"
    seja apenas o instante seguinte da mesma trajetória. Acompanhamos então a distância
    entre os dois ao longo de $k$ passos, $d_i(k) = \|\mathbf X_{i+k} - \mathbf X_{j(i)+k}\|$,
    e, se a separação for exponencial,

    $$
    \langle \ln d_i(k) \rangle \approx \langle \ln d_i(0) \rangle + \lambda_1\, k\,\Delta t ,
    $$

    em que $\langle\cdot\rangle$ é a média sobre todos os pares. A inclinação do trecho
    linear dessa curva estima $\lambda_1$. A curva não sobe para sempre: quando a distância
    chega ao tamanho do atrator, ela satura.
    """)
    return


@app.function(hide_code=True)
def plot_sensitivity_and_rosenstein():
    z1, z2 = np.array([0.30, 0.31]), np.array([0.30000001, 0.31])
    d, x1, x2 = [], [], []
    for _ in range(80):
        x1.append(z1[0])
        x2.append(z2[0])
        d.append(np.linalg.norm(z2 - z1))
        z1, z2 = MAP.step(z1, MU_CHAOS), MAP.step(z2, MU_CHAOS)
    series = MAP.simulate(MU_CHAOS, n=5500, discard=1000)[:, 0]
    result = rosenstein(series, 3, 1, theiler=20, fit=(1, 8), max_steps=30)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.4), layout="constrained")
    axes[0].plot(x1, color=COLORS["ink"], lw=1.2, label="trajetória A")
    axes[0].plot(x2, "--", color=COLORS["t2m"], lw=1.2, label="trajetória B, Δx₀ = 10⁻⁸")
    axes[0].set(xlabel="passo n", ylabel="x_n", title="Duas condições iniciais quase iguais")
    axes[0].legend(fontsize=8)
    axes[1].semilogy(np.maximum(d, 1e-16), color=COLORS["ink"])
    axes[1].set(xlabel="passo n", ylabel="distância (escala log)",
                title="A distância entre elas")
    k = np.arange(len(result.divergence))
    axes[2].plot(k, result.divergence, "o-", ms=3, color=COLORS["ink"], label="⟨ln d(k)⟩")
    fit = np.arange(result.fit[0], result.fit[1] + 1)
    axes[2].plot(fit, result.intercept + result.exponent * fit, lw=3, color=COLORS["t2m"],
                 label=nb.pt(f"inclinação = {result.exponent:.3f}"))
    axes[2].set(xlabel="k, passos à frente", ylabel="⟨ln d(k)⟩",
                title="Rosenstein, só com a série")
    axes[2].legend(fontsize=8)
    return fig, result.exponent


@app.cell(hide_code=True)
def _():
    _fig, _estimate = plot_sensitivity_and_rosenstein()
    _exact = MAP.lyapunov(MU_CHAOS)
    mo.vstack([
        mo.md(nb.pt(
            "A Figura 3 junta as duas maneiras de ver o caos, com μ = 11,5. No painel da "
            "esquerda, duas trajetórias que começam a 0,00000001 uma da outra; no do meio, a "
            "distância entre elas em escala logarítmica; no da direita, a curva de "
            "Rosenstein calculada apenas a partir da série de x, como se não soubéssemos "
            "nada da equação.")),
        book.figure(_fig, "sensibilidade_rosenstein",
                    "Figura 3. Mapa com memória, μ = 11,5. Esquerda: duas trajetórias com "
                    "estados iniciais a 10⁻⁸ uma da outra. Centro: a distância entre elas, em "
                    "escala log. Direita: curva de divergência de Rosenstein (m = 3, τ = 1, "
                    "janela de Theiler de 20 passos) e o ajuste nos passos 1 a 8."),
        mo.md(nb.pt(
            "As duas trajetórias da esquerda são indistinguíveis por uns quarenta passos e "
            "depois seguem caminhos sem relação. O painel do meio explica o porquê: numa "
            "escala logarítmica, a distância cresce como uma reta, isto é, exponencialmente, "
            "até atingir o tamanho do atrator, onde se estabiliza. A inclinação dessa reta é "
            "o expoente de Lyapunov. O painel da direita mostra o mesmo fenômeno visto a "
            "partir dos dados: a curva média de Rosenstein tem um trecho linear seguido de "
            "saturação, e a inclinação do trecho linear estima λ₁ sem usar a equação.\n\n"
            f"Pela equação obtivemos λ₁ = {_exact:.3f} por passo; pela série, "
            f"{_estimate:.3f}. Os valores não precisam coincidir: um usa a dinâmica exata, o "
            "outro uma série finita, uma reconstrução escolhida por nós e uma janela de "
            "ajuste. Que fiquem próximos num sistema conhecido é a primeira validação do "
            "método. A pergunta que o resto do capítulo faz é mais incômoda: o método também "
            "dá um número positivo quando não há caos nenhum?")),
    ])
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 🌧️ Quando a série parece ambiental

    Séries climáticas reais têm sazonalidade, ruído de medição, tendências e forte
    autocorrelação. Para ver como isso afeta o método, construímos três séries de mesmo
    comprimento. A primeira é o mapa caótico, limpo. A segunda é a mesma dinâmica
    contaminada,

    $$
    y_n = x_n + A \sin\!\left(\frac{2\pi n}{T}\right) + \eta_n ,
    \qquad \eta_n \sim \mathcal N(0, \sigma^2),
    $$

    com uma oscilação de período $T = 60$ passos e um ruído de observação $\eta_n$. A
    terceira não tem caos algum: é um processo autorregressivo de primeira ordem,

    $$
    u_n = \phi\, u_{n-1} + \varepsilon_n, \qquad \varepsilon_n \sim \mathcal N(0, s^2),
    $$

    com $\phi = 0{,}92$. O AR(1) é o modelo mais simples de uma série com memória: cada
    valor lembra o anterior, mas tudo o que é novo vem de sorteios independentes. Muitas
    séries climáticas se parecem mais com ele do que com um atrator caótico, e por isso ele
    é o adversário que qualquer indicador de caos precisa vencer.
    """)
    return


@app.cell(hide_code=True)
def _():
    noise_slider = mo.ui.slider(0.0, 0.3, value=0.05, step=0.01,
                                label="Ruído de observação σ (em desvios-padrão da série)",
                                show_value=True)
    return (noise_slider,)


@app.function(hide_code=True)
def contaminated(noise, n=3500, seed=2026):
    rng = np.random.default_rng(seed)
    clean = MAP.simulate(MU_CHAOS, n=n + 1000, discard=1000)[:, 0]
    t = np.arange(n)
    observed = (clean + 0.07 * np.sin(2 * np.pi * t / 60)
                + noise * clean.std() * rng.normal(size=n))
    noise_ar = ar1(phi=0.92, n=n + 500, seed=seed)[500:]
    noise_ar = clean.mean() + noise_ar / noise_ar.std() * clean.std()
    return {"determinístico limpo": clean, "com sazonalidade e ruído": observed,
            "AR(1), sem caos": noise_ar}


@app.function(hide_code=True)
def plot_contamination(series):
    fig, axes = plt.subplots(2, 3, figsize=(15, 7.2), layout="constrained")
    colors = [COLORS["ink"], COLORS["t2m"], COLORS["precip"]]
    for col, ((name, s), color) in enumerate(zip(series.items(), colors, strict=True)):
        axes[0, col].plot(s[:300], lw=0.9, color=color)
        axes[0, col].set(title=name, xlabel="passo n")
        result = rosenstein(s, 3, 1, theiler=25, fit=(1, 8), max_steps=30)
        axes[1, col].plot(result.divergence, "o-", ms=3, color=color)
        fit = np.arange(1, 9)
        axes[1, col].plot(fit, result.intercept + result.exponent * fit, lw=3, color="#222",
                          alpha=0.6)
        axes[1, col].set(xlabel="k, passos à frente", ylabel="⟨ln d(k)⟩",
                         title=nb.pt(f"inclinação {result.exponent:.3f} · "
                                     f"R² do ajuste {result.r2:.2f}"))
    return fig


@app.cell(hide_code=True)
def _(noise_slider):
    mo.vstack([
        mo.md(r"""
        Na linha de cima de cada figura estão 300 passos de cada série; na de baixo, a curva
        de Rosenstein correspondente, com a reta ajustada nos passos 1 a 8, a mesma
        configuração para as três. O título de cada curva mostra a inclinação e o
        coeficiente de determinação $R^2$, que mede quão retilíneo é o trecho ajustado. O
        controle muda o ruído da série do meio.
        """),
        noise_slider,
        mo.as_html(plot_contamination(contaminated(noise_slider.value))),
    ])
    return


@app.cell(hide_code=True)
def _():
    mo.vstack([
        book.figure(plot_contamination(contaminated(0.05)), "contaminacao",
                    "Figura 4. Três séries (acima) e suas curvas de Rosenstein (abaixo), com "
                    "m = 3, τ = 1, janela de Theiler de 25 passos e ajuste nos passos 1 a 8: "
                    "dinâmica caótica limpa, a mesma com sazonalidade e 5% de ruído, e um "
                    "AR(1) com φ = 0,92."),
        mo.md(r"""
        A Figura 4 é talvez a mais importante do capítulo. A série caótica limpa produz o
        que esperamos: uma subida retilínea seguida de saturação, $R^2$ próximo de 1. Com
        sazonalidade e ruído, a curva começa mais alta, porque o ruído afasta os vizinhos
        desde o início, e o trecho linear encurta; aumente o ruído no controle acima e veja
        a inclinação se deformar. O AR(1), que não tem caos nenhum, também devolve uma
        inclinação positiva.

        Por que um processo aleatório "parece" caótico ao método? Porque, entre dois
        vizinhos próximos, o primeiro sorteio de ruído já os separa por uma distância da
        ordem do próprio ruído. A curva dá um salto nos primeiros passos e satura logo, e a
        reta ajustada sobre esse salto tem inclinação positiva. O formato da curva denuncia
        a diferença, um salto e não uma subida gradual, e o $R^2$ do ajuste é menor. Mas
        olhar formatos de curva não é um teste, e um número positivo sozinho não distingue
        caos de acaso.
        """),
        mo.callout(mo.md(
            "Um expoente de Lyapunov positivo, estimado a partir de dados, não é prova de "
            "caos. Ruído, sazonalidade e autocorrelação produzem inclinações positivas sem "
            "nenhuma dinâmica caótica por trás. Para interpretar qualquer descritor, "
            "precisamos compará-lo com o que um processo sem não linearidade produziria."),
            kind="danger"),
    ])
    return


@app.function(hide_code=True)
def plot_surrogate_and_recurrence(series):
    clean = series["determinístico limpo"]
    sur = next(surrogates(clean, 1, method="FT", seed=7))
    examples = {"determinístico": clean, "substituta do determinístico": sur,
                "AR(1)": series["AR(1), sem caos"]}
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), layout="constrained")
    for ax, (name, s) in zip(axes, examples.items(), strict=True):
        vectors = delay_embedding(s, 3, 1)[:550]
        eps = recurrence_threshold(vectors, 0.08, theiler=0)
        d = np.linalg.norm(vectors[:, None] - vectors[None, :], axis=2)
        ax.imshow(d <= eps, origin="lower", cmap="binary", interpolation="nearest")
        lam = rosenstein(s, 3, 1, theiler=25, fit=(1, 8)).exponent
        ax.set(title=nb.pt(f"{name}\ninclinação de Rosenstein {lam:.3f}"), xlabel="tempo j",
               ylabel="tempo i")
        ax.grid(False)
    return fig


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 🎭 Substitutas e recorrência: aprendendo a duvidar

    A saída para o impasse anterior é transformar a pergunta "o número é positivo?" em
    outra, que pode ser testada: "o número é diferente do que obteríamos de uma série que
    tem as mesmas propriedades lineares, mas nenhuma estrutura não linear?". Essas séries de
    comparação são as substitutas [6]. A mais simples preserva o espectro de potência da
    série original e embaralha as fases. Se $X_k$ são os coeficientes da transformada de
    Fourier de $x_n$, a substituta tem coeficientes

    $$
    \tilde X_k = |X_k|\, e^{i \varphi_k},
    \qquad \varphi_k \sim \mathcal U[0, 2\pi),
    $$

    com $\varphi_{N-k} = -\varphi_k$ para que a série volte a ser real. Pelo teorema de
    Wiener–Khinchin, preservar $|X_k|$ preserva a autocorrelação inteira; o que se perde é
    qualquer relação de fases, que é onde mora a não linearidade. A hipótese nula que essas
    substitutas representam é precisa: a série é a realização de um processo linear,
    gaussiano e estacionário. Se a estatística da série original cai fora da distribuição
    obtida em muitas substitutas, rejeitamos essa hipótese. Note o que isso não diz: rejeitar
    um processo linear gaussiano não prova caos, só elimina uma explicação.

    A segunda ferramenta é o gráfico de recorrência [7]. Depois de reconstruir os estados
    $\mathbf X_i$, marcamos

    $$
    R_{ij} = \Theta\!\left(\varepsilon - \|\mathbf X_i - \mathbf X_j\|\right),
    $$

    em que $\Theta$ é a função degrau: $R_{ij} = 1$ quando o estado no instante $j$ volta a
    menos de $\varepsilon$ do estado no instante $i$. Escolhemos $\varepsilon$ de modo que
    uma fração fixa dos pares seja recorrente, a taxa de recorrência, aqui de 8%. Linhas
    diagonais no gráfico indicam trechos em que o sistema refaz um percurso parecido por
    vários passos seguidos, uma marca de determinismo; pontos isolados, sem diagonais,
    indicam que os retornos são casuais.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.vstack([
        book.figure(plot_surrogate_and_recurrence(contaminated(0.05)), "recorrencia",
                    "Figura 5. Gráficos de recorrência (m = 3, τ = 1, taxa de recorrência de "
                    "8%, primeiros 550 estados) da série caótica, de uma substituta com o "
                    "mesmo espectro e de um AR(1). Pontos pretos: pares de instantes cujos "
                    "estados estão próximos."),
        mo.md(r"""
        Cada painel é uma matriz de 550 por 550 instantes, e o ponto $(j, i)$ está preto
        quando os estados nesses dois instantes estão próximos. A diagonal principal é
        sempre preta, porque todo estado é próximo de si mesmo; a informação está fora dela.
        Na série caótica, à esquerda, aparecem muitos segmentos curtos paralelos à diagonal:
        o sistema volta a regiões já visitadas e as percorre de modo parecido por alguns
        passos. Na substituta, ao centro, que tem exatamente o mesmo espectro e portanto a
        mesma autocorrelação, a textura muda de natureza: as diagonais curtas e regulares dão
        lugar a um quadriculado de blocos, em que os retornos acontecem, mas sem que o
        sistema refaça o mesmo caminho. No AR(1), à direita, os retornos formam manchas e
        blocos maiores, reflexo de uma série que demora a esquecer onde estava, mas também
        sem a organização fina do caos.

        Repare também nos títulos: a inclinação de Rosenstein da substituta e a do AR(1) são
        positivas, como a da série caótica. O expoente sozinho não separa os três casos; a
        comparação com substitutas e a estrutura das recorrências, sim. Essa é a razão pela
        qual, nos dados reais, nenhum descritor é olhado isoladamente: todos são comparados,
        célula por célula, com dezenas de substitutas.
        """),
    ])
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 🧭 Do laboratório para a Amazônia

    O que este capítulo deixa para o resto do trabalho é, antes de mais nada, uma atitude.
    Num sistema conhecido, vimos que os equilíbrios e sua estabilidade se leem nos
    autovalores da jacobiana, que um parâmetro pode atravessar um limiar e mudar o destino
    do sistema, e que essa mudança pode ser suave, sem ser um ponto de não retorno. Vimos
    também que um mapa simples com memória vai da ordem ao caos, e que o caos tem uma
    medida, o expoente de Lyapunov, que pode ser obtida tanto da equação quanto de uma série
    observada. E vimos, sobretudo, que a estimativa a partir de dados se deixa enganar por
    ruído, sazonalidade e autocorrelação, a ponto de um processo sem caos nenhum produzir um
    número positivo.

    Por isso os dados das bacias passam por um caminho mais longo do que "calcular o
    expoente". Antes de olhar para qualquer série real, submetemos todos os descritores a um
    teste com controles sintéticos de resposta conhecida, caóticos e não caóticos, com o
    comprimento e o ruído das nossas séries; esse é o assunto do capítulo de validação dos
    métodos. As regras de escolha de $\tau$, $m$ e da janela de Theiler, o número de
    substitutas e a direção de cada teste foram fixadas por escrito antes de qualquer
    cálculo com dados, para que não pudéssemos, mesmo sem querer, ajustar a análise até ela
    contar a história que gostaríamos de ouvir. E a conclusão final nunca se apoia num único
    número, mas na concordância entre descritores diferentes, comparados com substitutas e
    entre regiões com histórias distintas de desmatamento e fogo.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## 📚 Referências

    [1] Strogatz, S. H. *Nonlinear Dynamics and Chaos: With Applications to Physics,
    Biology, Chemistry, and Engineering*. 2. ed. Boulder: Westview Press, 2015.

    [2] Kantz, H.; Schreiber, T. *Nonlinear Time Series Analysis*. 2. ed. Cambridge:
    Cambridge University Press, 2004.

    [3] Takens, F. Detecting strange attractors in turbulence. In: Rand, D.; Young, L.-S.
    (org.). *Dynamical Systems and Turbulence, Warwick 1980*. Lecture Notes in Mathematics,
    v. 898. Berlin: Springer, 1981. p. 366–381.

    [4] Rosenstein, M. T.; Collins, J. J.; De Luca, C. J. A practical method for
    calculating largest Lyapunov exponents from small data sets. *Physica D*, v. 65,
    p. 117–134, 1993.

    [5] Benettin, G.; Galgani, L.; Giorgilli, A.; Strelcyn, J.-M. Lyapunov characteristic
    exponents for smooth dynamical systems and for Hamiltonian systems: a method for
    computing all of them. Part 1: Theory. *Meccanica*, v. 15, p. 9–20, 1980.

    [6] Theiler, J.; Eubank, S.; Longtin, A.; Galdrikian, B.; Farmer, J. D. Testing for
    nonlinearity in time series: the method of surrogate data. *Physica D*, v. 58,
    p. 77–94, 1992.

    [7] Marwan, N.; Romano, M. C.; Thiel, M.; Kurths, J. Recurrence plots for the analysis
    of complex systems. *Physics Reports*, v. 438, p. 237–329, 2007.

    [8] Theiler, J. Spurious dimension from correlation algorithms applied to limited
    time-series data. *Physical Review A*, v. 34, p. 2427–2432, 1986.

    [9] Spracklen, D. V.; Arnold, S. R.; Taylor, C. M. Observations of increased tropical
    rainfall preceded by air passage over forests. *Nature*, v. 489, p. 282–285, 2012.

    [10] Lovejoy, T. E.; Nobre, C. Amazon tipping point. *Science Advances*, v. 4,
    eaat2340, 2018.

    [11] Kennel, M. B.; Brown, R.; Abarbanel, H. D. I. Determining embedding dimension for
    phase-space reconstruction using a geometrical construction. *Physical Review A*,
    v. 45, p. 3403–3411, 1992.

    [12] Fraser, A. M.; Swinney, H. L. Independent coordinates for strange attractors from
    mutual information. *Physical Review A*, v. 33, p. 1134–1140, 1986.

    [13] Hirota, M.; Holmgren, M.; Van Nes, E. H.; Scheffer, M. Global resilience of
    tropical forest and savanna to critical transitions. *Science*, v. 334, p. 232–235,
    2011.
    """)
    return


if __name__ == "__main__":
    app.run()
