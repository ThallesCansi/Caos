import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium", app_title="TCC — visão geral")


@app.cell
def _():
    import marimo as mo
    from amazon_chaos.config import load_config

    return load_config, mo


@app.cell
def _(load_config):
    study = load_config("configs/study.yaml")
    return (study,)


@app.cell
def _(mo, study):
    mo.md(f"""
    # TCC — Dinâmica não linear floresta–atmosfera

    **Objetivo:** {study['project']['objective']}

    ## Fluxo de trabalho

    **perturbação independente → séries climáticas → QC → controles sintéticos → embedding → descritores → surrogates → comparação espacial → interpretação socioespacial**

    O projeto não tratará um expoente de Lyapunov positivo isolado como prova de caos ou tipping point.
    """)
    return


if __name__ == "__main__":
    app.run()
