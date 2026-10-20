import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium", app_title="01 · Laboratório de sistemas dinâmicos")

with app.setup:
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
    nb.header(
        "01 · Laboratório de sistemas dinâmicos",
        "O que estabilidade, bifurcação e o expoente de Lyapunov significam num sistema cujas "
        "equações conhecemos, e o que muda quando só temos uma série?",
        stage="F4 · fundamento teórico dos métodos (sem dados reais)",
        inputs=["nenhum: modelos em `amazon_chaos.nonlinear.models`"],
        outputs=["`reports/figures/01_laboratorio/`"],
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Parte A · Um sistema contínuo de feedback umidade–vegetação

    $$
    \dot m = P + \alpha v - \beta m, \qquad
    \dot v = v\left[r(1-v)\frac{m}{h+m} - d\right]
    $$

    - $m(t)$ é um índice adimensional de disponibilidade de umidade, e $v(t)$, de condição da
      vegetação;
    - $P$ é a entrada externa de umidade; $\alpha v$, a realimentação positiva da vegetação
      sobre a umidade; $\beta m$, a perda;
    - $r$ é a resposta máxima da vegetação, $h$ a escala de saturação e $d$ a perda efetiva.
      O termo $m/(h+m)$ satura: mais umidade ajuda muito quando $m$ é pequeno, e cada vez
      menos depois.

    O equilíbrio sem vegetação $E_0 = (P/\beta,\,0)$ sempre existe. Na Jacobiana em $E_0$, um
    autovalor é $-\beta<0$ e o outro é $\lambda_v = r\,\frac{P/\beta}{h+P/\beta} - d$. A
    estabilidade troca quando $\lambda_v = 0$:

    $$
    \boxed{P_c = \frac{\beta d h}{r - d}}
    $$

    Num sistema contínuo, o equilíbrio é estável se todos os autovalores têm
    $\operatorname{Re}(\lambda) < 0$.
    """)
    return


@app.cell
def _():
    p_slider = mo.ui.slider(0.02, 0.40, value=0.25, step=0.01, label="Entrada de umidade P",
                            show_value=True)
    return (p_slider,)


@app.function
def plot_flow(p):
    t, y = FLOW.simulate(p)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.2), layout="constrained")
    ax1.plot(t, y[0], color=COLORS["precip"], label="m(t): umidade")
    ax1.plot(t, y[1], color=COLORS["q"], label="v(t): vegetação")
    ax1.set(xlabel="tempo", ylabel="estado adimensional", title=f"Trajetória · P = {p:.2f}")
    ax1.legend()
    for z0 in [(0.15, 0.1), (0.3, 0.7), (0.6, 0.2), (1.0, 0.8), (1.2, 0.45)]:
        _, y = FLOW.simulate(p, z0=z0, t_max=35)
        ax2.plot(y[0], y[1], lw=1.4)
        ax2.scatter(y[0, 0], y[1, 0], s=18)
    ax2.set(xlabel="m · umidade", ylabel="v · vegetação", title="Retrato de fase")
    return fig


@app.cell(hide_code=True)
def _(p_slider):
    _side = "acima" if p_slider.value > FLOW.critical_p else "abaixo"
    mo.vstack([
        mo.md(nb.pt(f"Limiar analítico: **P_c = {FLOW.critical_p:.4f}**. Mova o controle e "
                    "veja a vegetação desaparecer abaixo do limiar.")),
        p_slider,
        mo.as_html(plot_flow(p_slider.value)),
        mo.md(nb.pt(f"P = {p_slider.value:.2f} está **{_side}** do limiar.")),
    ])
    return


@app.function
def plot_stability():
    ps = np.linspace(0.015, 0.40, 280)
    bare, vegetated, stable = FLOW.equilibria(ps)
    fig, ax = plt.subplots(figsize=(9, 4.4), layout="constrained")
    ax.plot(ps[bare], np.zeros(bare.sum()), ".", ms=3, color=COLORS["ink"],
            label="E0 (sem vegetação) estável")
    ax.plot(ps[~bare], np.zeros((~bare).sum()), ".", ms=3, color=COLORS["muted"],
            label="E0 instável")
    ok = np.isfinite(vegetated) & stable
    ax.plot(ps[ok], vegetated[ok], ".", ms=3, color=COLORS["q"],
            label="equilíbrio vegetado estável")
    ax.axvline(FLOW.critical_p, ls="--", color=COLORS["t2m"],
               label=nb.pt(f"P_c = {FLOW.critical_p:.3f}"))
    ax.set(xlabel="P · entrada externa de umidade", ylabel="v* · vegetação no equilíbrio",
           title="Troca de estabilidade no modelo contínuo")
    ax.legend()
    return fig


@app.cell(hide_code=True)
def _():
    book.figure(plot_stability(), "troca_estabilidade",
                "Modelo umidade–vegetação: equilíbrios em função da entrada de umidade P. "
                "Abaixo de P_c = βdh/(r − d) só o estado sem vegetação é estável; acima, o "
                "equilíbrio vegetado assume (bifurcação transcrítica).")
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Parte B · Um mapa discreto com memória

    $$
    x_{n+1} = S\!\left[b + \mu x_n(1-x_n) - \kappa x_{n-1}\right],
    \qquad S(q) = \frac{1}{1+e^{-aq}}
    $$

    $x_n$ é um índice agregado do estado floresta–atmosfera; $\mu x_n(1-x_n)$, a
    realimentação não linear; $-\kappa x_{n-1}$, a memória do passo anterior; $b$, o
    forçamento basal; $S$ mantém o índice entre 0 e 1. Embora observemos só $x_n$, o estado
    completo é bidimensional, $\mathbf z_n = (x_n, x_{n-1})$: é a ponte para reconstruir o
    espaço de fases a partir de uma série.

    Um ponto fixo é estável se os autovalores da Jacobiana ficam **dentro do círculo
    unitário**, $|\lambda_i| < 1$: a versão multidimensional do critério $|f'(x^*)| < 1$.
    Quando ele perde estabilidade, a trajetória não diverge, porque a sigmoide a limita:
    surgem ciclos, bandas aperiódicas e outros atratores.
    """)
    return


@app.cell(hide_code=True)
def _():
    _rows = []
    for _mu in [7.0, 8.0, 10.0, 11.5, 12.5, 14.0]:
        _x, _eig = MAP.fixed_point(_mu)
        _rows.append({"μ": _mu, "x*": round(_x, 4), "|λ| máximo": round(np.abs(_eig).max(), 4),
                      "ponto fixo estável": bool(np.abs(_eig).max() < 1),
                      "λ₁ (Lyapunov, Jacobiana)": round(MAP.lyapunov(_mu), 4)})
    book.table(pd.DataFrame(_rows), "pontos_fixos",
               "Mapa com memória: ponto fixo, raio espectral da Jacobiana e maior expoente de "
               "Lyapunov pela dinâmica tangente, para alguns valores de μ.", selection=None)
    return


@app.cell
def _():
    mu_slider = mo.ui.slider(6.0, 16.0, value=11.5, step=0.1, label="Realimentação μ",
                             show_value=True)
    return (mu_slider,)


@app.function
def plot_map(mu):
    tr = MAP.simulate(mu, n=5000, discard=1000)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4), layout="constrained")
    ax1.plot(tr[:220, 0], lw=1, color=COLORS["ink"])
    ax1.set(xlabel="iteração", ylabel="x_n", title=f"Série · μ = {mu:.1f}")
    ax2.scatter(tr[:, 0], tr[:, 1], s=2, alpha=0.45, color=COLORS["t2m"])
    ax2.set(xlabel="x_n", ylabel="x_{n−1}", title="Espaço de estados")
    return fig


@app.cell(hide_code=True)
def _(mu_slider):
    _lam = MAP.lyapunov(mu_slider.value)
    mo.vstack([mu_slider, mo.as_html(plot_map(mu_slider.value)),
               mo.md(nb.pt(f"λ₁ = **{_lam:+.3f}** por iteração: "
                           + ("expansão de perturbações, dependência sensível às condições "
                              "iniciais." if _lam > 0 else "perturbações se contraem."))) ])
    return


@app.function
def plot_bifurcation():
    mus = np.linspace(6.0, 16.0, 750)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7.5), sharex=True, layout="constrained")
    for mu in mus:
        values = MAP.simulate(mu, n=1400, discard=1260)[:, 0]
        ax1.plot(np.full(len(values), mu), values, ",k", alpha=0.3)
    ax1.set(ylabel="valores assintóticos de x", title="Diagrama de bifurcação")
    grid = np.linspace(6.0, 16.0, 260)
    lyap = np.array([MAP.lyapunov(mu, n=4200, transient=700) for mu in grid])
    ax2.plot(grid, lyap, lw=1, color=COLORS["t2m"])
    ax2.axhline(0, ls="--", color=COLORS["ink"])
    ax2.set(xlabel="μ · intensidade da realimentação", ylabel="λ₁",
            title="Maior expoente de Lyapunov (dinâmica tangente)")
    return fig


@app.cell(hide_code=True)
def _():
    mo.vstack([
        mo.md("### Bifurcação e espectro de Lyapunov\n\nPara cada μ, iteramos, descartamos o "
              "transiente e marcamos os valores assintóticos. Uma linha é um ponto fixo; duas, "
              "um ciclo de período 2; uma nuvem, um regime aperiódico. Embaixo, λ₁ calculado "
              "pela equação."),
        book.figure(plot_bifurcation(), "bifurcacao_lyapunov",
                    "Mapa com memória: diagrama de bifurcação em μ e maior expoente de Lyapunov "
                    "pela dinâmica tangente (Benettin). λ₁ > 0 coincide com as bandas "
                    "aperiódicas."),
    ])
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Parte C · Lyapunov: primeiro pela equação, depois pelos dados

    Com a equação, uma perturbação pequena evolui como $\delta\mathbf z_{n+1} \approx
    J(\mathbf z_n)\,\delta\mathbf z_n$, e

    $$
    \lambda_{\max} = \lim_{n\to\infty}\frac1n\ln\frac{\|\delta\mathbf z_n\|}{\|\delta\mathbf z_0\|}.
    $$

    Normalizamos o vetor tangente a cada passo e acumulamos os logaritmos (Benettin).
    $\lambda_{\max} > 0$ significa expansão exponencial média de perturbações.

    **Sem a equação** (o caso dos dados), o método de Rosenstein reconstrói o estado com
    atrasos, acha para cada ponto o vizinho mais próximo **fora da janela de Theiler** e
    acompanha $\langle \ln d(k)\rangle$: num sistema caótico, a curva sobe linearmente até
    saturar, e a inclinação estima $\lambda_1$.
    """)
    return


@app.function
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
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2), layout="constrained")
    axes[0].plot(x1, color=COLORS["ink"], label="trajetória A")
    axes[0].plot(x2, "--", color=COLORS["t2m"], label="trajetória B (Δx₀ = 10⁻⁸)")
    axes[0].set(xlabel="iteração", ylabel="x_n", title="Duas condições iniciais quase iguais")
    axes[0].legend(fontsize=8)
    axes[1].semilogy(np.maximum(d, 1e-16), color=COLORS["ink"])
    axes[1].set(xlabel="iteração", ylabel="distância (log)", title="Separação das trajetórias")
    k = np.arange(len(result.divergence))
    axes[2].plot(k, result.divergence, "o-", ms=3, color=COLORS["ink"], label="⟨ln d(k)⟩")
    fit = np.arange(result.fit[0], result.fit[1] + 1)
    axes[2].plot(fit, result.intercept + result.exponent * fit, lw=2.5, color=COLORS["t2m"],
                 label=nb.pt(f"ajuste: λ = {result.exponent:.3f}"))
    axes[2].set(xlabel="k · passos no futuro", ylabel="⟨ln d(k)⟩",
                title="Rosenstein, só com a série")
    axes[2].legend(fontsize=8)
    return fig, result.exponent


@app.cell(hide_code=True)
def _():
    _fig, _estimate = plot_sensitivity_and_rosenstein()
    _exact = MAP.lyapunov(MU_CHAOS)
    mo.vstack([
        book.figure(_fig, "sensibilidade_rosenstein",
                    f"Mapa com memória (μ = {MU_CHAOS}): separação exponencial de trajetórias "
                    "próximas e estimativa de Rosenstein a partir apenas da série reconstruída "
                    "(m = 3, τ = 1, Theiler 20, ajuste nos passos 1–8)."),
        mo.md(nb.pt(f"λ₁ pela equação: **{_exact:.3f}** por iteração · pela série (Rosenstein): "
                    f"**{_estimate:.3f}**. Não precisam coincidir: um usa a dinâmica exata; o "
                    "outro, uma série finita, uma reconstrução escolhida por nós e uma janela "
                    "de ajuste.")),
    ])
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Parte D · Quando a série parece "ambiental"

    Dados reais têm sazonalidade, ruído, lacunas, tendências e autocorrelação. Contaminamos a
    série caótica com $A\sin(2\pi n/T) + \eta_n$ e criamos uma série **AR(1)**, estocástica e
    fortemente autocorrelacionada. O AR(1) é o alerta central do projeto: **uma série
    irregular não é automaticamente caótica**, e Rosenstein também devolve uma inclinação
    positiva para ela.
    """)
    return


@app.cell
def _():
    noise_slider = mo.ui.slider(0.0, 0.3, value=0.05, step=0.01,
                                label="Ruído de observação (desvios-padrão)", show_value=True)
    return (noise_slider,)


@app.function
def contaminated(noise, n=3500, seed=2026):
    rng = np.random.default_rng(seed)
    clean = MAP.simulate(MU_CHAOS, n=n + 1000, discard=1000)[:, 0]
    t = np.arange(n)
    observed = clean + 0.07 * np.sin(2 * np.pi * t / 60) + noise * clean.std() * rng.normal(size=n)
    noise_ar = ar1(phi=0.92, n=n + 500, seed=seed)[500:]
    noise_ar = clean.mean() + noise_ar / noise_ar.std() * clean.std()
    return {"determinístico limpo": clean, "com sazonalidade + ruído": observed,
            "AR(1) estocástico": noise_ar}


@app.function
def plot_contamination(series):
    fig, axes = plt.subplots(2, 3, figsize=(15, 7), layout="constrained")
    for col, (name, s) in enumerate(series.items()):
        axes[0, col].plot(s[:300], lw=0.9, color=COLORS["ink"])
        axes[0, col].set_title(name)
        result = rosenstein(s, 3, 1, theiler=25, fit=(1, 8), max_steps=30)
        axes[1, col].plot(result.divergence, "o-", ms=3, color=COLORS["ink"])
        fit = np.arange(1, 9)
        axes[1, col].plot(fit, result.intercept + result.exponent * fit, lw=2.5,
                          color=COLORS["t2m"])
        axes[1, col].set(xlabel="k", ylabel="⟨ln d(k)⟩",
                         title=nb.pt(f"λ = {result.exponent:.3f} · R² = {result.r2:.2f}"))
    return fig


@app.cell(hide_code=True)
def _(noise_slider):
    mo.vstack([noise_slider, mo.as_html(plot_contamination(contaminated(noise_slider.value)))])
    return


@app.cell(hide_code=True)
def _():
    book.figure(plot_contamination(contaminated(0.05)), "contaminacao",
                "Rosenstein em três séries: dinâmica determinística limpa, a mesma com "
                "sazonalidade e 5% de ruído, e um AR(1) estocástico. O AR(1) também produz "
                "inclinação positiva, mas sem trecho linear (R² baixo): λ positivo não prova "
                "caos.")
    return


@app.function
def plot_surrogate_and_recurrence(series):
    clean = series["determinístico limpo"]
    sur = next(surrogates(clean, 1, method="FT", seed=7))
    examples = {"determinístico": clean, "substituta FT do determinístico": sur,
                "AR(1)": series["AR(1) estocástico"]}
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8), layout="constrained")
    for ax, (name, s) in zip(axes, examples.items(), strict=True):
        vectors = delay_embedding(s, 3, 1)[:550]
        eps = recurrence_threshold(vectors, 0.08, theiler=0)
        d = np.linalg.norm(vectors[:, None] - vectors[None, :], axis=2)
        ax.imshow(d <= eps, origin="lower", cmap="binary", interpolation="nearest")
        lam = rosenstein(s, 3, 1, theiler=25, fit=(1, 8)).exponent
        ax.set(title=nb.pt(f"{name}\nλ (Rosenstein) = {lam:.3f}"), xlabel="j", ylabel="i")
        ax.grid(False)
    return fig


@app.cell(hide_code=True)
def _():
    mo.vstack([
        mo.md(r"""
        ### Substitutas e gráficos de recorrência

        Uma **substituta** preserva propriedades lineares do sinal (aqui, o espectro: FT) e
        destrói a estrutura de fases. Se uma estatística não linear do dado não difere da
        mesma estatística em muitas substitutas, nada indica dinâmica não linear. Num teste de
        verdade, gera-se um conjunto de substitutas e uma estatística definida antes de olhar
        o resultado (cadernos 05 e 06).

        O **gráfico de recorrência** marca $R_{ij}=1$ quando o estado reconstruído no instante
        $j$ volta para perto do estado em $i$ (taxa de recorrência fixa de 8%). Diagonais
        longas indicam trechos de evolução parecida, típicos de determinismo.
        """),
        book.figure(plot_surrogate_and_recurrence(contaminated(0.05)), "recorrencia",
                    "Gráficos de recorrência (m = 3, τ = 1, taxa de recorrência de 8%) da série "
                    "determinística, de uma substituta FT dela e de um AR(1). A substituta "
                    "mantém o espectro, mas perde as diagonais longas."),
    ])
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Parte E · Do laboratório aos dados do TCC

    1. **Variável e escala:** anomalias diárias de temperatura e VPD, 2001–2024 (pré-registro,
       `configs/analysis/descriptors.yaml`).
    2. **Qualidade:** completude e calendário (caderno 03).
    3. **Sazonalidade e tendência:** análise sobre anomalias; nenhuma remoção automática de
       tendência.
    4. **τ e m por regra fixa:** informação mútua e falsos vizinhos, não defaults de biblioteca.
    5. **Vários descritores** (Lyapunov, RQA, D2, entropia de permutação, assimetria,
       previsão), todos **contra substitutas**.
    6. **Validação em controles** com a resposta conhecida antes dos dados reais: o gate do
       caderno 05.
    7. **Comparação entre células** com níveis diferentes de perturbação, com controles
       espaciais (caderno 08).
    8. **Interpretação cautelosa:** nenhum número isolado vira "caos" ou "tipping point".

    **Síntese.** Contínuo: equilíbrio estável se $\operatorname{Re}\lambda_i < 0$. Discreto:
    se $|\lambda_i| < 1$. Bifurcação: mudança qualitativa ao cruzar um valor crítico.
    $\lambda_{\max} > 0$: separação exponencial média de trajetórias próximas. Reconstrução:
    $\mathbf X_n = [x_n, x_{n-\tau}, \dots, x_{n-(m-1)\tau}]$.

    **Referências de estudo:** Cipolli (2012), *Sistemas dinâmicos discretos: análise de
    estabilidade* (UNESP); Proto (2013), *Estudo de estabilidade e bifurcações em sistemas
    não lineares*; Kantz e Schreiber (2004); Rosenstein et al. (1993); Marwan et al. (2007).
    """)
    return


if __name__ == "__main__":
    app.run()
