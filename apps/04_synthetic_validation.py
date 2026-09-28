import marimo

__generated_with = "0.23.16"
app = marimo.App(width="full", app_title="TCC — validação sintética")


@app.cell
def _():
    import marimo as mo
    import numpy as np
    from amazon_chaos.nonlinear.synthetic import ar1, logistic_map, lorenz, periodic_signal

    return ar1, logistic_map, lorenz, mo, periodic_signal


@app.cell
def _(ar1, logistic_map, lorenz, periodic_signal):
    controls = {
        "logistic_chaotic": logistic_map(n=5000),
        "lorenz_x": lorenz(n=5000)[:, 0],
        "periodic": periodic_signal(n=5000, period=24, noise=0.0),
        "periodic_noise": periodic_signal(n=5000, period=24, noise=0.2),
        "ar1": ar1(n=5000),
    }
    return (controls,)


@app.cell
def _(controls, mo):
    rows = [{"control": name, "n": len(values), "mean": float(values.mean()), "std": float(values.std())} for name, values in controls.items()]
    mo.vstack([
        mo.md("# Controles antes dos dados climáticos\nO pipeline de dinâmica não linear deve ser calibrado nestes casos antes de qualquer conclusão sobre a Amazônia."),
        mo.ui.table(rows),
    ])
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
