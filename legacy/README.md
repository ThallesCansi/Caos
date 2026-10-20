# Legado: fluxo em Jupyter (até 20/10/2026)

Registro de auditoria do fluxo anterior. **Não é mantido.** Os cadernos podem depender de módulos e configurações que foram removidos. Para reproduzir exatamente esse estado, use a tag `v0-jupyter`:

```bash
git worktree add ../Caos-v0 v0-jupyter
```

## `jupyter/`

| Caderno | Conteúdo | O que virou |
|---|---|---|
| `01_ERA5_DETER.ipynb` | primeiro piloto ERA5 e DETER (agosto de 2024), com lógica inline e downloads | o pipeline ERA5 de `amazon_chaos.io` e `preprocess`, e o DETER em `io/terrabrasilis.py` |
| `02_Dados_Reais_ERA5_DETER_…ipynb` | versão didática do mesmo piloto | idem |
| `03_Piloto_Tapajos_2024.ipynb` | Baixo Tapajós em janeiro de 2024: passagem da hora ao dia | seção "da hora ao dia" do `notebooks/03_clima.py` |
| `04_Bacia_Xingu_1990_2024.ipynb`, `05_Baixo_Tapajos_1990_2024.ipynb` | atlas climático de 1990–2024 | `notebooks/03_clima.py`, um só caderno com o parâmetro `--region` |
| `06_Teste_Nao_Linearidade_Surrogates.ipynb` | protocolo FT/IAAFT (execução `full_e57802a1f7`) | `notebooks/06_surrogates.py` |
| `07_Fogo_Cobertura_Socioambiental_MapBiomas.ipynb` | séries regionais do MapBiomas exportadas pelo GEE | `notebooks/04_perturbacao.py`, com métricas por célula (D-012) |
| `Laboratorio_Sistemas_Dinamicos_…ipynb` | laboratório teórico | `notebooks/01_laboratorio.py` |
| `build_*_notebook.py` | geradores dos cadernos 03–06 | substituídos pelos cadernos Marimo |

## `figures/`

Figuras do piloto `tapajos_2024` e do laboratório, citadas no relatório parcial (`docs/entregas/relatorio_parcial.tex`).

As execuções antigas de substitutas (CSVs e figuras do modo rápido) foram movidas para `data/processed/surrogates/`, fora do Git. As figuras da execução principal continuam em `reports/figures/surrogates/full_e57802a1f7/`.
