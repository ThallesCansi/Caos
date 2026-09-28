# TCC — Dinâmica não linear do sistema floresta–atmosfera amazônico

## Piloto Jupyter do Baixo Tapajós

Comece por [03_Piloto_Tapajos_2024.ipynb](03_Piloto_Tapajos_2024.ipynb): mapa do recorte, aquisição documentada, qualidade e séries diárias de janeiro de 2024. O notebook lê os dados locais; as funções auxiliares ficam nos módulos Python.

Configuração: `configs/tapajos_2024.yaml`. Consulte [como executar o piloto](docs/PILOTO_TAPAJOS_COMO_EXECUTAR.md) e o [desenho metodológico](docs/DESENHO_ESTUDO_2001_2024.md). O roteiro abaixo descreve a infraestrutura anterior ERA5/DETER e marimo, preservada para reprodução.

---

Projeto computacional do TCC **“Uma Análise do Sistema Floresta-Atmosfera Amazônica sob a ótica da Teoria do Caos”**.

## Objetivo científico

> Investigar a dinâmica não linear do sistema floresta-atmosfera amazônico, utilizando conceitos e métodos da Teoria do Caos e dos sistemas dinâmicos complexos para analisar possíveis sinais de instabilidade associados a perturbações na cobertura vegetal, como desmatamento, queimadas e degradação florestal.

A hipótese de trabalho do projeto original é que séries temporais climáticas e ambientais associadas ao sistema floresta-atmosfera amazônico possam apresentar padrões de dinâmica não linear detectáveis por reconstrução do espaço de fases e descritores como o maior expoente de Lyapunov.

## Pergunta operacional

A versão computacional do objetivo será tratada como uma sequência de testes:

1. É possível construir séries climáticas comparáveis, suficientemente longas, regulares e bem documentadas para diferentes regiões amazônicas?
2. É possível classificar essas regiões por **níveis independentes de perturbação florestal** usando PRODES/MapBiomas/fogo/DETER sem olhar previamente para os descritores não lineares?
3. Depois de controlar sazonalidade, tendência, autocorrelação, ruído e tamanho da amostra, aparecem estruturas não lineares robustas nas séries?
4. Os descritores não lineares diferem sistematicamente entre gradientes de preservação e perturbação?
5. Os padrões encontrados permanecem robustos a escolhas de atraso, dimensão de imersão, janelas temporais, variáveis e hipóteses nulas por séries substitutas?
6. Como os resultados se relacionam ao contexto territorial e socioambiental sem transformar um descritor matemático isolado em alegação causal ou em “prova de tipping point”?

## Princípio de arquitetura

O repositório separa **efeitos colaterais caros** (download/ETL) de **análise interativa**.

```text
Fontes institucionais
      │
      ▼
[ acquisition / src/amazon_chaos/io ]
      │
      ▼
data/raw  ── imutável, não versionado
      │
      ▼
[ preprocess + provenance ]
      │
      ▼
data/interim
      │
      ▼
[ harmonização espacial/temporal + features ]
      │
      ▼
data/processed
      │
      ├────────► apps/ (marimo: exploração/QC/resultados)
      │
      └────────► nonlinear/ (embedding, Lyapunov, surrogates, recurrence)
                         │
                         ▼
                 experiments/registry.csv
                         │
                         ▼
                 reports/figures + tables
```

**Downloads não devem ocorrer automaticamente em um notebook reativo.** Aquisição é chamada explicitamente por CLI. Marimo é usado para inspeção e análise reprodutível.

## Começo rápido

### 1. Instale o `uv`

Consulte a documentação oficial do uv para o método adequado ao seu sistema.

### 2. Crie/sincronize o ambiente

```bash
uv sync --dev
```

Na primeira execução, o uv criará `uv.lock`. **Commitar `uv.lock` no Git é recomendado** para congelar o ambiente computacional do TCC.

### 3. Configure o CDS

Crie/valide `~/.cdsapirc` com sua credencial do Climate Data Store. Nunca versione credenciais.

### 4. Inicialize as pastas locais

```bash
uv run amazon-chaos init-dirs
```

### 5. Baixe o piloto ERA5 + DETER

```bash
uv run amazon-chaos pilot --config configs/pilot.yaml
```

### 6. Gere/atualize o manifesto dos arquivos

```bash
uv run amazon-chaos manifest data/raw --output metadata/manifests/raw_files.csv
```

### 7. Abra o projeto no marimo

```bash
uv run marimo edit apps/
```

Comece por:

```bash
uv run marimo edit apps/00_project_overview.py
uv run marimo edit apps/01_pilot_qc.py
```

## Estrutura

```text
tcc-amazonia-caos/
├── apps/                    # notebooks marimo (análise, sem downloads implícitos)
├── configs/                 # configurações versionadas de pilotos/experimentos
├── data/                    # dados locais; conteúdo pesado ignorado pelo Git
├── docs/                    # arquitetura, plano científico e guardrails
├── experiments/             # registro de experimentos e resultados por configuração
├── legacy/                  # notebook Jupyter do piloto inicial, preservado para auditoria
├── metadata/                # catálogo, variáveis, manifests e proveniência
├── reports/                 # figuras e tabelas derivadas
├── src/amazon_chaos/        # biblioteca reutilizável do projeto
├── tests/                   # testes unitários de transformações críticas
├── .github/workflows/       # CI
├── pyproject.toml
└── README.md
```

## Os dados não vão para o Git

O projeto prevê volumes muito maiores que um repositório de código. `data/raw`, `data/interim` e `data/processed` ficam fora do Git; versionamos **código, configuração, manifestos, metadados, pequenas tabelas derivadas e figuras finais**. Se futuramente for necessário distribuir algum artefato binário grande, decidir entre armazenamento institucional, release, object storage ou Git LFS será uma decisão separada.

## Fases científicas

| Fase | Entrega principal | Gate para avançar |
|---|---|---|
| F0 | infraestrutura e catálogo | downloads reproduzíveis + manifests |
| F1 | unidade espacial e gradiente de perturbação | classificação independente da resposta climática |
| F2 | séries climáticas longas | QC, lacunas e regularidade documentados |
| F3 | validação sintética | método distingue controles caóticos e nulos |
| F4 | reconstrução e descritores | robustez a `tau`, `m`, janela e preprocessing |
| F5 | hipóteses nulas | comparação com séries substitutas |
| F6 | comparação espacial | efeito consistente entre regiões/estratos |
| F7 | interpretação socioespacial | conclusão proporcional à evidência |

Detalhes: [`docs/RESEARCH_PLAN.md`](docs/RESEARCH_PLAN.md).

## Regra interpretativa central

`lambda_max > 0` **não será tratado como prova isolada de caos**, e muito menos como prova de tipping point. A interpretação final depende da qualidade da série, controles sintéticos, sazonalidade, tendências, autocorrelação, ruído, sensibilidade dos parâmetros, séries substitutas e consistência espacial.

## Licença

Código sob licença MIT. Bases de terceiros permanecem submetidas aos termos e licenças de suas instituições responsáveis.
