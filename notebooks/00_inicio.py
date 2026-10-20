import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium", app_title="00 · Início")

with app.setup:
    from datetime import date
    from pathlib import Path

    import marimo as mo
    import pandas as pd

    from amazon_chaos import nb
    from amazon_chaos.config import list_regions, load_region

    book = nb.notebook("00_inicio")

    NOTEBOOKS = [
        ("00_inicio", "Visão geral", "—"),
        ("01_laboratorio", "Sistemas dinâmicos conhecidos: estabilidade, bifurcação, Lyapunov",
         "F4"),
        ("02_regioes", "Bacias, grade ERA5 e contexto territorial", "F1"),
        ("03_clima", "Atlas climático 1990–2024 por região", "F2"),
        ("04_perturbacao", "PRODES, DETER, BDQueimadas e MapBiomas por célula; MODIS", "F3"),
        ("05_validacao_metodos", "Gate: descritores em controles sintéticos", "F4"),
        ("06_surrogates", "Testes de hipótese FT/IAAFT", "F5"),
        ("07_descritores", "Lyapunov, RQA, D2, entropia de permutação e EWS por célula", "F6"),
        ("08_gradiente", "Perturbação × dinâmica, com controles espaciais", "F7"),
    ]
    MILESTONES = [
        ("Arrumação e fundação (regiões, CLI, HPC)", date(2026, 10, 27)),
        ("Métodos validados, perturbação por célula, pré-registro", date(2026, 11, 2)),
        ("Lote de descritores nas duas bacias", date(2026, 11, 9)),
        ("Gradiente e figuras finais", date(2026, 11, 14)),
        ("Texto completo na Overleaf", date(2026, 11, 24)),
        ("Defesa (início de dezembro; data a confirmar)", date(2026, 12, 4)),
    ]


@app.cell(hide_code=True)
def _():
    nb.header(
        "Caos na floresta–atmosfera amazônica",
        "As células ERA5 com mais desmatamento e fogo antecedentes têm dinâmica climática "
        "diária diferente da das células comparáveis preservadas, depois de controlar "
        "sazonalidade, ruído, autocorrelação e geografia?",
        stage="mapa do projeto",
        inputs=["`configs/`", "`notebooks/`", "`data/processed/`"],
        outputs=["nenhuma (só leitura)"],
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    TCC de **Caio Ruas** e **Thalles Cansi** (Ilum/CNPEM, 2026), com orientação de
    Vinicius Wasques. Esta parte do repositório cuida da computação; a interpretação
    socioespacial é escrita pela dupla.

    ## Como o projeto funciona

    Os downloads e os cálculos pesados rodam pelo CLI `amazon-chaos` (local ou no HPC) e
    gravam arquivos com manifesto. Os cadernos só **leem** esses arquivos, contam a
    história de cada etapa e gravam as figuras e tabelas da monografia.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.mermaid("""
    flowchart LR
      A[Fontes<br/>ERA5 · BHB250 · PRODES<br/>DETER · BDQueimadas · MapBiomas · MODIS]
        -->|amazon-chaos · manifesto SHA-256| B[(data/raw)]
      B -->|era5 process · zonal| C[(data/processed<br/>diários · perturbação)]
      C -->|lote no HPC| D[(descritores<br/>e substitutas)]
      C --> E[notebooks Marimo]
      D --> E
      E --> F[reports/figures · tables]
      F -->|make overleaf| G[Monografia]
    """)
    return


@app.function
def notebook_status(name):
    path = Path("notebooks") / f"{name}.py"
    if not path.exists():
        return "a fazer"
    outputs = list(Path("reports/figures", name).rglob("*.png")) + list(
        Path("reports/tables", name).rglob("*.csv"))
    return f"pronto · {len(outputs)} saídas" if outputs else "pronto"


@app.cell(hide_code=True)
def _():
    _table = pd.DataFrame(
        [{"Caderno": n, "Fase": f, "Conteúdo": c, "Estado": notebook_status(n)}
         for n, c, f in NOTEBOOKS])
    mo.vstack([mo.md("## Cadernos"),
               mo.ui.table(_table, selection=None, show_download=False, page_size=12),
               mo.md("<small>Abrir: `uv run marimo edit notebooks/<caderno>.py`. "
                     "Versões em HTML: `make notebooks` (em `reports/html/`).</small>")])
    return


@app.function
def data_status(slug):
    cfg = load_region(slug)
    exp = cfg["experiment_id"]
    months = len(list(Path("data/raw", exp, "edh").glob("*/manifest.json")))
    daily = len(list(Path("data/processed", exp).glob("daily_*-01-01_*-12-31.nc")))
    grid = Path("data/processed", exp, "basin_grid.geojson").exists() or (
        cfg["boundary"]["source"] == "bbox")
    return {"Região": cfg["name"], "slug": slug, "Grade": "✅" if grid else "—",
            "ERA5 (meses)": f"{months}/421", "Diários (anos)": f"{daily}/35"}


@app.cell(hide_code=True)
def _():
    mo.vstack([
        mo.md("## Dados locais"),
        mo.ui.table(pd.DataFrame([data_status(s) for s in list_regions()]), selection=None,
                    show_download=False),
        mo.md("<small>`tapajos_caixa` é o recorte antigo (plano B). Para trazer o que o HPC "
              "processou: `make pull REGION=<slug>`.</small>"),
    ])
    return


@app.cell(hide_code=True)
def _():
    _today = date.today()
    _rows = [{"Marco": m, "Data": d.strftime("%d/%m"),
              "Faltam (dias)": (d - _today).days if d >= _today else "—"}
             for m, d in MILESTONES]
    mo.vstack([mo.md("## Cronograma"),
               mo.ui.table(pd.DataFrame(_rows), selection=None, show_download=False)])
    return


@app.cell(hide_code=True)
def _():
    nb.caveat(
        "**Regra de leitura.** `λ_max > 0` não é prova isolada de caos, e caos não é tipping "
        "point. O ERA5 é uma reanálise com vegetação fixa: não vê o desmatamento ano a ano "
        "(D-011). Toda conclusão passa por controles sintéticos, substitutas, sensibilidade "
        "aos parâmetros e consistência espacial; resultados negativos são relatados. "
        "Detalhes em `docs/metodologia.md`.")
    return


if __name__ == "__main__":
    app.run()
