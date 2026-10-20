import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium", app_title="05 · Validação dos métodos (gate F4)")

with app.setup:
    import json
    from pathlib import Path

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
    NAMES = {"lyapunov": "Lyapunov (Rosenstein)", "rqa_det": "RQA · DET", "rqa_lam": "RQA · LAM",
             "d2": "Dimensão de correlação D2", "pe_entropy": "Entropia de permutação",
             "pe_complexity": "Complexidade estatística", "asymmetry": "Assimetria temporal",
             "prediction": "Erro de previsão não linear"}
    CONTROL_NAMES = {"logistic": "logístico", "henon": "Hénon", "lorenz": "Lorenz",
                     "white": "ruído branco", "ar1": "AR(1)", "sine_noise": "seno + ruído",
                     "seasonal_trend": "AR(1) sazonal + tendência"}


@app.cell(hide_code=True)
def _():
    nb.header(
        "05 · Validação dos métodos: o gate F4",
        "Os descritores pré-registrados distinguem dinâmica caótica conhecida de processos "
        "lineares estocásticos, com séries do tamanho e do ruído das nossas?",
        stage="F4 · gate: nenhum descritor é interpretado nos dados reais sem passar aqui",
        inputs=["`configs/analysis/descriptors.yaml` (pré-registro)",
                "`data/processed/gate/<hash>/` (gerado por `amazon-chaos gate run` no HPC)"],
        outputs=["`reports/figures/05_validacao_metodos/`",
                 "`reports/tables/05_validacao_metodos/`"],
        status=f"Pré-registro **v{SPEC['version']}**, estado **{SPEC['status']}**, hash "
               f"`{gate_hash(SPEC)}`.",
    )
    return


@app.cell(hide_code=True)
def _():
    _g, _c = SPEC["gate"], SPEC["gate"]["criterion"]
    _pos = ", ".join(CONTROL_NAMES[k] for k in _g["positive"])
    _neg = ", ".join(CONTROL_NAMES[k] for k in _g["negative"])
    mo.md(f"""
    ## O desenho do gate

    Cada controle é gerado {_g['repetitions']} vezes em cada comprimento
    ({', '.join(map(str, _g['lengths']))} pontos; 8.766 é o número de dias de 2001–2024) e
    nível de ruído de observação ({', '.join(f'{v:g}' for v in _g['noise'])} desvio-padrão).
    Em cada série, τ, m e a janela de Theiler saem **das mesmas regras** que serão usadas nos
    dados (AMI, falsos vizinhos, w = max(10, τ·m)), e cada descritor é comparado com
    {SPEC['surrogates']['per_cell']} substitutas IAAFT pelo p de Monte Carlo.

    | Grupo | Controles | O que se espera |
    |---|---|---|
    | positivo | {_pos} | rejeitar H0 (dinâmica determinística não linear) |
    | negativo | {_neg} | não rejeitar (processos lineares) |

    **Critério (pré-registrado)**, no maior comprimento e no maior ruído: o descritor passa se
    tiver poder ≥ {_c['power']:.0%} em pelo menos {_c['positives_required']} dos
    {len(_g['positive'])} controles positivos **e** taxa de rejeição ≤ {_c['size']:.0%} no
    ruído branco e no AR(1), onde a hipótese nula é verdadeira. O controle sazonal com
    tendência viola a estacionariedade, como os dados climáticos podem violar: a taxa de
    rejeição nele é um **alerta** de falso positivo por não estacionariedade.
    """)
    return


@app.function
def latest_run():
    """A execução completa do pré-registro atual; senão, a mais recente (avisando)."""
    target = GATE_DIR / gate_hash(SPEC)
    if (target / "descritores.csv").exists():
        return target, True
    runs = sorted(GATE_DIR.glob("*/descritores.csv"), key=lambda p: p.stat().st_mtime)
    return (runs[-1].parent, False) if runs else (None, False)


@app.cell
def _():
    run_dir, current = latest_run()
    mo.stop(run_dir is None, nb.missing(
        [GATE_DIR / gate_hash(SPEC)],
        "sbatch scripts/hpc/gate.sbatch   # no HPC; depois, localmente: make pull-gate"))
    results = pd.read_csv(run_dir / "descritores.csv")
    run_spec = json.loads((run_dir / "spec.json").read_text())
    execution = json.loads((run_dir / "execucao.json").read_text())
    ews = pd.read_csv(run_dir / "ews.csv")
    rates = rejection_rates(results, run_spec["surrogates"]["alpha"])
    gate = verdict(rates, run_spec)
    _notes = []
    if execution["quick"]:
        _notes.append(nb.caveat("**Execução rápida** (só testa o código): 9 substitutas não "
                                "permitem p ≤ 0,05. Nada aqui é resultado.", "danger"))
    if not current:
        _notes.append(nb.caveat(f"Esta execução (`{run_dir.name}`) não corresponde ao "
                                f"pré-registro atual (`{gate_hash(SPEC)}`).", "warn"))
    mo.vstack([*_notes, nb.stats({
        "Séries": execution["series"], "Linhas": len(results),
        "Erros": int((results.descriptor == "erro").sum()), "Commit": execution["commit"],
        "Concluída": execution["finished_utc"][:16].replace("T", " ")})])
    return ews, execution, gate, rates, results, run_spec


@app.cell(hide_code=True)
def _(execution, gate):
    _table = gate.copy()
    _table.insert(0, "Descritor", _table.pop("descriptor").map(NAMES))
    _table["passa"] = _table["passa"].map({True: "✅ passa", False: "❌ não passa"})
    _passed = [NAMES[d] for d in gate[gate.passa].descriptor]
    mo.vstack([
        mo.md("## Veredito"),
        book.table(_table.round(2), "veredito",
                   "Gate F4: poder nos controles positivos e taxa de rejeição nos negativos "
                   "(n máximo, ruído máximo), e o veredito pelo critério pré-registrado.",
                   selection=None, overleaf=not execution["quick"]),
        nb.caveat(("**Passam:** " + ", ".join(_passed) + ". Só estes são interpretados nos "
                   "dados reais; os demais entram na monografia como resultado metodológico.")
                  if _passed else "**Nenhum descritor passou.** Isso é um resultado: com "
                  "séries deste tamanho e ruído, os métodos não separam caos de nulos "
                  "lineares, e a análise real fica restrita ao que o gate sustentar.",
                  "success" if _passed else "warn"),
    ])
    return


@app.function
def plot_rates(rates, spec):
    n, noise = max(spec["gate"]["lengths"]), max(spec["gate"]["noise"])
    final = rates[(rates.n == n) & (rates.noise == noise)]
    order = [k for k in [*POSITIVE, *NEGATIVE] if k in set(final.control)]
    table = final.pivot(index="descriptor", columns="control", values="rate")[order]
    table.index = [NAMES[d] for d in table.index]
    fig, ax = plt.subplots(figsize=(11, 5.2), layout="constrained")
    im = ax.imshow(table.values, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(order)), [CONTROL_NAMES[k] for k in order], rotation=25, ha="right")
    ax.set_yticks(range(len(table)), table.index)
    for i in range(table.shape[0]):
        for j in range(table.shape[1]):
            ax.text(j, i, f"{table.values[i, j]:.0%}", ha="center", va="center", fontsize=9)
    ax.axvline(len(POSITIVE) - 0.5, color="black", lw=2)
    ax.set_title(f"Taxa de rejeição de H0 · n = {n} · ruído {noise:g} · à esquerda: "
                 "positivos (quer-se alta); à direita: negativos (quer-se baixa)")
    ax.grid(False)
    fig.colorbar(im, ax=ax, shrink=0.8, label="fração de repetições com p ≤ α")
    return fig


@app.function
def plot_conditions(rates, spec):
    names = list(NAMES)
    fig, axes = plt.subplots(2, 4, figsize=(16, 7.5), sharey=True, layout="constrained")
    for ax, name in zip(axes.flat, names, strict=True):
        part = rates[rates.descriptor == name]
        for (n, noise), group in part.groupby(["n", "noise"]):
            g = group.set_index("control").reindex([*POSITIVE, *NEGATIVE]).dropna(subset=["rate"])
            ax.plot(range(len(g)), g.rate, "o-", ms=4,
                    label=f"n={n}, ruído {noise:g}", alpha=0.85)
            ax.set_xticks(range(len(g)), [CONTROL_NAMES[k][:9] for k in g.index], rotation=60,
                          fontsize=7)
        ax.axhline(spec["gate"]["criterion"]["size"], color=COLORS["muted"], ls=":", lw=1)
        ax.set_title(NAMES[name], fontsize=10)
    axes[0, 0].legend(fontsize=7)
    axes[0, 0].set_ylabel("taxa de rejeição")
    axes[1, 0].set_ylabel("taxa de rejeição")
    fig.suptitle("Como o comprimento e o ruído mudam o poder e o tamanho de cada teste",
                 fontsize=13, x=0.02, ha="left")
    return fig


@app.cell(hide_code=True)
def _(execution, rates, run_spec):
    mo.vstack([
        mo.md("## Poder e tamanho"),
        book.figure(plot_rates(rates, run_spec), "taxas_rejeicao",
                    "Gate F4: fração de repetições que rejeitam a hipótese nula IAAFT, por "
                    "descritor e controle, no maior comprimento e ruído.",
                    overleaf=not execution["quick"]),
        book.figure(plot_conditions(rates, run_spec), "comprimento_ruido",
                    "Gate F4: taxa de rejeição por controle em cada combinação de comprimento "
                    "e ruído de observação; pontilhado: tamanho máximo aceito.",
                    overleaf=not execution["quick"]),
        mo.accordion({"Tabela completa com intervalos de Clopper–Pearson":
                      mo.ui.table(rates.round(3), selection=None, page_size=12)}),
    ])
    return


@app.cell(hide_code=True)
def _(results):
    _params = (results[results.descriptor == "lyapunov"]
               .groupby(["control", "n", "noise"])[["tau", "m", "theiler"]]
               .agg(lambda s: f"{s.min():g}–{s.max():g}" if s.min() != s.max() else f"{s.min():g}")
               .reset_index())
    _params["control"] = _params.control.map(CONTROL_NAMES)
    mo.vstack([
        mo.md("## Parâmetros escolhidos pelas regras\n\nτ, m e w não foram ajustados à mão: "
              "saem da AMI e dos falsos vizinhos em cada série. Com ruído, os falsos vizinhos "
              "não caem e m sobe, o que já é um sinal de dinâmica estocástica."),
        mo.ui.table(_params, selection=None, page_size=10),
    ])
    return


@app.function
def plot_diagnostics(n=4000, seed=11):
    kinds = [*POSITIVE, *NEGATIVE]
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8), layout="constrained")
    colors = plt.cm.tab10(np.arange(len(kinds)))
    for kind, color in zip(kinds, colors, strict=True):
        x = control(kind, n, seed=seed, noise=0.2)
        p = embedding_parameters(x, SPEC)
        r = rosenstein(x, p["m"], p["tau"], p["theiler"], fit=(0, 5), max_steps=30)
        style = "-" if kind in POSITIVE else "--"
        axes[0].plot(r.divergence - r.divergence[0], style, color=color, label=CONTROL_NAMES[kind])
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
                title="D2 × m: platô (caos) ou crescimento (ruído)")
    axes[2].legend(fontsize=8)
    fig.suptitle(f"Diagnósticos em controles com ruído 0,2 e n = {n}", fontsize=13, x=0.02,
                 ha="left")
    return fig


@app.cell(hide_code=True)
def _(execution):
    mo.vstack([
        mo.md("## Como os descritores enxergam os controles\n\nUma repetição de cada controle, "
              "com o ruído máximo do gate. Linhas cheias: positivos; tracejadas: negativos."),
        book.figure(plot_diagnostics(), "diagnosticos",
                    "Controles com ruído de observação 0,2: curvas de divergência de Rosenstein, "
                    "plano complexidade–entropia (Bandt–Pompe, d = 5) e D2 em função da "
                    "dimensão de imersão (Lorenz × AR(1)).", overleaf=not execution["quick"]),
    ])
    return


@app.cell(hide_code=True)
def _(ews, execution):
    _table = (ews.assign(reject=ews.pvalue <= SPEC["surrogates"]["alpha"])
              .groupby(["control", "indicator"])
              .agg(repetições=("reject", "size"), rejeições=("reject", "sum"),
                   tau_médio=("tau", "mean")).reset_index())
    _table["taxa"] = _table["rejeições"] / _table["repetições"]
    mo.vstack([
        mo.md("## Sinais precoces (EWS): calibração à parte\n\nOs EWS não são descritores de "
              "caos: testam *critical slowing down*, a subida da variância e do AR(1) perto de "
              "uma transição. Aqui, um AR(1) estacionário (nulo verdadeiro) e um AR(1) com φ "
              "subindo de 0,2 a 0,95 ao longo da série."),
        book.table(_table.round(3), "ews_calibracao",
                   "EWS: taxa de rejeição (τ de Kendall da variância e do AR(1) contra "
                   "substitutas IAAFT) num AR(1) estacionário e num AR(1) que se aproxima da "
                   "instabilidade.", selection=None, overleaf=not execution["quick"]),
        nb.caveat("O τ de Kendall sobre janelas sobrepostas é muito autocorrelacionado: num "
                  "AR(1) estacionário ele chega facilmente a ±0,6. Por isso o τ observado só "
                  "vale contra substitutas, nunca contra a tabela de Kendall.", "info"),
    ])
    return


@app.function
def plot_standardization(table):
    variants = ["anomalia", "padronizada", "padronizada+sem tendência"]
    names = ["lyapunov", "rqa_det", "d2", "pe_complexity"]
    fig, axes = plt.subplots(1, 4, figsize=(16, 4), sharey=True, layout="constrained")
    for ax, kind in zip(axes, ["seasonal_trend", "sine_noise", "ar1", "lorenz"], strict=True):
        part = table[table.controle == kind].pivot(index="descritor", columns="variante",
                                                    values="taxa").loc[names, variants]
        x = np.arange(len(names))
        for k, (variant, color) in enumerate(zip(variants, ["#b0523b", COLORS["ink"],
                                                             COLORS["muted"]], strict=True)):
            ax.bar(x + (k - 1) * 0.27, part[variant], 0.27, color=color, label=variant)
        ax.set_xticks(x, [NAMES[n].split(" (")[0] for n in names], rotation=30, ha="right",
                      fontsize=8)
        ax.set_title(CONTROL_NAMES[kind] + (" (poder)" if kind == "lorenz" else
                                            " (falso positivo)"), fontsize=10)
        ax.axhline(0.2, color=COLORS["muted"], ls=":", lw=1)
    axes[0].set_ylabel("taxa de rejeição")
    axes[0].legend(fontsize=8)
    fig.suptitle("Padronizar pela variância sazonal elimina o falso positivo da RQA; o Lyapunov "
                 "continua vulnerável", fontsize=12, x=0.02, ha="left")
    return fig


@app.cell(hide_code=True)
def _(execution):
    _run, _ = latest_run()
    _path = _run / "padronizacao.csv" if _run else None
    _out = [mo.md("## Variância sazonal: o alerta e a correção\n\nNo controle sazonal com "
                  "tendência, Lyapunov e RQA·DET rejeitam H0 sem haver caos. As anomalias "
                  "climáticas também têm variância sazonal (a estação seca é mais variável). "
                  "Testamos três tratamentos com 10 repetições, n = 8766 e ruído 0,2 "
                  "(`amazon_chaos.nonlinear.gate.standardization_check`).")]
    if _path is not None and _path.exists():
        _table = pd.read_csv(_path)
        _out.append(book.figure(plot_standardization(_table), "padronizacao",
                                "Taxa de rejeição de H0 com a anomalia simples, a anomalia "
                                "padronizada pelo desvio sazonal e a padronizada sem "
                                "tendência; pontilhado: tamanho máximo aceito.",
                                overleaf=not execution["quick"]))
    _f = SPEC.get("families", {})
    _out.append(mo.md(
        "**Decisão pré-registrada (D-010).** Séries em anomalia padronizada, sem remoção de "
        "tendência. Família primária: " + ", ".join(NAMES[n] for n in _f.get("primary", []))
        + ". Secundária: " + ", ".join(NAMES[n] for n in _f.get("secondary", []))
        + ". Exploratória: " + ", ".join(NAMES[n] for n in _f.get("exploratory", []))
        + " (falso positivo sob variância sazonal mesmo depois de padronizar)."))
    mo.vstack(_out)
    return


@app.cell(hide_code=True)
def _():
    nb.caveat(
        f"**Pré-registro {SPEC['status']}** (v{SPEC['version']}, "
        f"{SPEC.get('frozen_on', 'sem data')}). Toda mudança daqui em diante gera a versão 2, e "
        "as duas versões são relatadas (D-010).",
        "success" if SPEC["status"] == "congelado" else "neutral")
    return


@app.cell(hide_code=True)
def _():
    run_dir_, _ = latest_run()
    nb.provenance(files=[Path("configs/analysis/descriptors.yaml")]
                  + ([run_dir_ / "descritores.csv", run_dir_ / "ews.csv"] if run_dir_ else []))
    return


if __name__ == "__main__":
    app.run()
