import marimo

__generated_with = "0.23.16"
app = marimo.App(width="full", app_title="TCC — QC das séries")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md("""
    # Qualificação das séries temporais

    Para cada `series_id`, comparar:

    1. série bruta;
    2. anomalia do ciclo diurno;
    3. anomalia sazonal;
    4. lacunas/regularidade;
    5. tendência e autocorrelação;
    6. estabilidade ao variar a janela temporal.

    A saída deste estágio é uma tabela de **elegibilidade para análise não linear**, não ainda um resultado de caos.
    """)
    return


if __name__ == "__main__":
    app.run()
