import marimo

__generated_with = "0.23.16"
app = marimo.App(width="full", app_title="TCC — análise não linear")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md("""
    # Análise não linear

    **Não preencher com resultados finais antes de F0–F4 estarem concluídas.**

    Este estágio receberá séries já qualificadas e registrará:

    - método/grade para `tau`;
    - método/grade para `m`;
    - reconstrução do espaço de fases;
    - maior expoente de Lyapunov e sensibilidade de parâmetros;
    - recurrence plots/RQA;
    - séries substitutas;
    - intervalos/bootstrap quando apropriado;
    - configuração e `experiment_id` associados.
    """)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
