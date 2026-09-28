import marimo

__generated_with = "0.23.16"
app = marimo.App(width="full", app_title="TCC — seleção de regiões")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md("""
    # Seleção de regiões / células

    **Status: próxima fase.**

    Este notebook será responsável por unir a grade climática a métricas independentes de perturbação:

    - PRODES: desmatamento consolidado;
    - MapBiomas: cobertura/fração florestal e histórico de uso;
    - BDQueimadas: pressão por fogo;
    - DETER: perturbação recente.

    A seleção das regiões deve acontecer **antes** de calcular Lyapunov/RQA, evitando escolha circular.
    """)
    return


if __name__ == "__main__":
    app.run()
