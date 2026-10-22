# Caos na floresta–atmosfera amazônica

Código do TCC **"Uma Análise do Sistema Floresta-Atmosfera Amazônica sob a ótica da Teoria do Caos"** (Ilum/CNPEM, 2026), de Caio Ruas e Thalles Cansi, com orientação de Vinicius Wasques.

> As células ERA5 com mais desmatamento e fogo antecedentes têm dinâmica climática diária diferente da das células comparáveis preservadas, depois de controlar sazonalidade, ruído, autocorrelação e geografia?

Regiões: bacias do **Xingu** (779 células ERA5) e do **Tapajós** (762). Período: 2001–2024, com o arquivo 1990–2000 para sensibilidade. Método: reconstrução do espaço de fases, Lyapunov, RQA, D2, entropia de permutação e sinais precoces, sempre contra controles sintéticos e séries substitutas. Os detalhes estão em [docs/metodologia.md](docs/metodologia.md).

## Cadernos (Marimo)

Cada capítulo é um caderno Marimo em `notebooks/`, que lê dados já produzidos e gera as figuras da monografia. Os mapas mostram as duas bacias juntas; as figuras de uma só série têm um seletor de bacia, e as versões impressas das duas são gravadas.

| Caderno | Capítulo | Estado |
|---|---|---|
| `00_inicio` | apresentação, percurso, legenda das caixas e resumo dos resultados | pronto |
| `01_laboratorio` | sistemas dinâmicos conhecidos (teoria, interativo) | pronto |
| `02_regioes` | as bacias, a grade ERA5 e as células da comparação | pronto |
| `03_clima` | o clima de 1990–2024 e a anomalia padronizada | pronto |
| `04_perturbacao` | desmatamento e fogo por célula, concordância entre fontes, MODIS | pronto |
| `05_validacao_metodos` | o portão: descritores em controles sintéticos | pronto |
| `06_surrogates` | substitutas FT/IAAFT nas séries das bacias (D-016) | pronto |
| `07_descritores` | descritores por célula, robustez, EWS | pronto |
| `08_gradiente` | perturbação × dinâmica e checagem MODIS (D-014, D-015, D-018) | pronto |

O fluxo anterior, em Jupyter, só existe no histórico do Git (tag `v0-jupyter`).

```bash
uv run marimo edit notebooks/03_clima.py                                  # editar
uv run marimo export html notebooks/03_clima.py -o reports/html/03_clima.html
```

## Começo rápido

```bash
make sync                        # ambiente exatamente como no uv.lock
make test && make check          # testes, ruff e marimo check
uv run marimo edit notebooks/    # abrir os cadernos
make notebooks                   # executar todos e exportar HTML (reports/html/)
make overleaf                    # figuras e tabelas finais em reports/overleaf/
```

Os dados não estão no Git (veja [docs/dados.md](docs/dados.md)). Toda aquisição passa pelo CLI, com manifesto e SHA-256; os cadernos **nunca** baixam nada:

```bash
uv run amazon-chaos region list                 # regiões em configs/regions/
uv run amazon-chaos region prepare tapajos      # limite, grade e cartografia
uv run amazon-chaos era5 --help                 # plan · download · edh · process · summarize
```

O ERA5 de 1990–2024 é baixado no HPC pelo Earth Data Hub (`sbatch --export=ALL,REGION=<slug> scripts/hpc/era5.sbatch`) e trazido com `make pull REGION=<slug>`. Uma região nova se cria com um YAML. Tudo isso está em [docs/hpc.md](docs/hpc.md).

## Estrutura

```text
configs/      regiões, variáveis e análise pré-registrada (YAML)
data/         dados locais, fora do Git
docs/         metodologia, dados, decisões, HPC; entregas/ (projeto aprovado, relatório parcial)
notebooks/    cadernos Marimo
reports/      figuras e tabelas finais; registro de experimentos
scripts/hpc/  jobs Slurm, setup e sincronização com o HPC
src/          biblioteca amazon_chaos (io, preprocess, features, nonlinear)
tests/        testes das transformações e dos métodos
```

## Regra interpretativa

`λ_max > 0` **não é prova isolada de caos**, e muito menos de tipping point. A conclusão depende da qualidade da série, dos controles sintéticos, das substitutas, da sensibilidade aos parâmetros e da consistência espacial. Resultados negativos são relatados ([guardrails](docs/metodologia.md#3-guardrails)).

## Licença

Código sob licença MIT. As bases de terceiros seguem os termos das instituições responsáveis.
