# Caos na floresta–atmosfera amazônica

Código do TCC **"Uma Análise do Sistema Floresta-Atmosfera Amazônica sob a ótica da Teoria do Caos"** (Ilum/CNPEM, 2026), de Caio Ruas e Thalles Cansi, com orientação de Vinicius Wasques.

> As células ERA5 com mais desmatamento e fogo antecedentes têm dinâmica climática diária diferente da das células comparáveis preservadas, depois de controlar sazonalidade, ruído, autocorrelação e geografia?

Regiões: bacias do **Xingu** (779 células ERA5) e do **Tapajós** (762). Período: 2001–2024, com o arquivo 1990–2000 para sensibilidade. Método: reconstrução do espaço de fases, Lyapunov, RQA, D2, entropia de permutação e sinais precoces, sempre contra controles sintéticos e séries substitutas. Os detalhes estão em [docs/metodologia.md](docs/metodologia.md).

## Cadernos (Marimo)

Cada etapa é um caderno Marimo em `notebooks/`, que lê dados já produzidos e gera as figuras da monografia. Os cadernos que servem a mais de uma região recebem `--region`.

| Caderno | Etapa | Estado |
|---|---|---|
| `00_inicio` | visão geral e mapa do projeto | a fazer |
| `01_laboratorio` | sistemas dinâmicos conhecidos (teoria) | a migrar |
| `02_regioes` | limites, grade ERA5, contexto territorial | a fazer |
| `03_clima` | atlas climático de 1990–2024 | a migrar (antigos 04 e 05) |
| `04_perturbacao` | PRODES, DETER, BDQueimadas, MapBiomas por célula e checagem MODIS | a fazer |
| `05_validacao_metodos` | gate dos descritores em sistemas sintéticos | a fazer |
| `06_surrogates` | testes FT/IAAFT | a migrar (antigo 06) |
| `07_descritores` | descritores por célula, robustez, EWS | a fazer |
| `08_gradiente` | perturbação × dinâmica | a fazer |

Os cadernos Jupyter anteriores estão em [`legacy/`](legacy/README.md) e na tag `v0-jupyter`.

```bash
uv run marimo edit notebooks/03_clima.py                                  # editar
uv run marimo export html notebooks/03_clima.py -o reports/html/03_clima_xingu.html -- --region xingu
```

## Começo rápido

```bash
uv sync --dev                    # ambiente (uv.lock versionado)
uv run pytest                    # testes
uv run ruff check .              # estilo
```

Os dados não estão no Git (veja [docs/dados.md](docs/dados.md)). Para obtê-los:
- ERA5 pelo Earth Data Hub no HPC, conforme [docs/hpc.md](docs/hpc.md);
- uma região nova se cria com um YAML em `configs/regions/`.

Downloads **nunca** rodam dentro de um caderno; são comandos explícitos de CLI, com manifesto e SHA-256.

## Estrutura

```text
configs/      regiões, variáveis e análise pré-registrada (YAML)
data/         dados locais, fora do Git
docs/         metodologia, dados, decisões, HPC; entregas/ (projeto aprovado, relatório parcial)
legacy/       fluxo Jupyter anterior, só para auditoria
notebooks/    cadernos Marimo
reports/      figuras e tabelas finais; registro de experimentos
scripts/hpc/  jobs Slurm
src/          biblioteca amazon_chaos (io, preprocess, features, nonlinear)
tests/        testes das transformações e dos métodos
```

## Regra interpretativa

`λ_max > 0` **não é prova isolada de caos**, e muito menos de tipping point. A conclusão depende da qualidade da série, dos controles sintéticos, das substitutas, da sensibilidade aos parâmetros e da consistência espacial. Resultados negativos são relatados ([guardrails](docs/metodologia.md#3-guardrails)).

## Licença

Código sob licença MIT. As bases de terceiros seguem os termos das instituições responsáveis.
