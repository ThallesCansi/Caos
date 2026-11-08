# Caos na floresta–atmosfera amazônica

Código do TCC **"Uma Análise do Sistema Floresta-Atmosfera Amazônica sob a ótica da Teoria do Caos"** (Ilum/CNPEM, 2026), de Caio Ruas e Thalles Cansi, com orientação de Vinicius Wasques.

> A perturbação da floresta amazônica, por desmatamento e fogo, deixa marca na dinâmica do clima local, isto é, na forma como ele evolui de um dia para o outro? E as ferramentas da teoria do caos conseguem revelá-la?

A pergunta se desdobra em três: que tipo de dinâmica o clima diário local tem (natureza), se ela difere entre lugares mais e menos perturbados e muda onde a floresta é perdida (relação), e que tipo de registro é preciso para que essa marca apareça (detectabilidade). A reanálise ERA5 é o instrumento principal; a temperatura da superfície medida pelo MODIS e a chuva diária do CHIRPS são as checagens observacionais (D-019, D-021).

Regiões: bacias do **Xingu** (779 células ERA5) e do **Tapajós** (762). Período: 2001–2024, com o arquivo 1990–2000 para sensibilidade. Método: reconstrução do espaço de fases, Lyapunov, RQA, D2, entropia de permutação e sinais precoces, sempre contra controles sintéticos e séries substitutas. Os detalhes estão em [docs/metodologia.md](docs/metodologia.md).

O pré-registro (D-010), o gate congelado `1c2fb37657` e o lote `81333bb007` são o resultado principal. As extensões da revisão crítica de 29/10/2026 (D-027: grade de atrasos, mínima e máxima, temperatura + umidade, Wolf e Kantz, temperatura de pele do ERA5, gate com nulas realistas, S-map, Cao e dither da chuva) são comparativos, apresentados ao lado do resultado principal nos capítulos em que cabem, sem substituí-lo. A reanálise de 30/10/2026 corrigiu a leitura das nulas realistas, que passa a ser por variável (D-029), e acrescentou a sazonalidade como explicação alternativa, blocos espaciais maiores, nulas ajustadas nas células, a auditoria dos comparativos e a separação entre ocorrência e intensidade da chuva (D-030).

A metodologia de 31/10/2026 (D-031) acrescenta a floresta como variável dinâmica: a vegetação do MODIS (LAI e NDMI, composições de 8 dias) sozinha, junto com a atmosfera e depois do fogo, com o seu próprio portão e pré-registro (`configs/analysis/vegetation.yaml`). A D-032 (07/11/2026) amplia a comparação com a atmosfera para horizontes de 8 a 64 dias, estados compactos com atrasos escolhidos no treino, modelos lineares e não lineares e a direção inversa, com validação em blocos cronológicos e anos permutados como controle.

### O que os resultados dizem

Em quatro níveis, como no resumo do caderno `00_inicio` (Tabela 1, "o que resiste a quê"):

1. **Validade dos métodos.** Os descritores reconhecem caos em sistemas conhecidos, mas DET, LAM e Lyapunov também rejeitam a hipótese linear em processos estocásticos com memória sazonal ou variância condicional; só o teste de Cao separa caos de ruído (cadernos 05 e 07).
2. **Estrutura.** O clima diário das bacias é um processo estocástico com memória sazonal e não linearidade fraca, sem caos de baixa dimensão. A temperatura guarda uma não linearidade que nenhuma nula realista reproduz (assimetria e D2); no VPD, a rejeição vem em boa parte da memória sazonal (cadernos 06 e 07).
3. **Paisagem.** Entre células, a perda antecedente se associa a recorrências mais curtas (DET) na temperatura e a padrões ordinais do VPD mais próximos do aleatório. A evidência confirmatória mais firme é a do DET da temperatura; a associação ordinal é em boa parte geografia da sazonalidade. Ao longo do tempo, nada (caderno 08).
4. **Detectabilidade.** O MODIS vê a superfície de 6 a 7 °C mais quente nas células convertidas; o ar do ERA5 não vê, e a sua superfície vê só uma fração do contraste entre lugares e nada da mudança no tempo. A chuva do CHIRPS mostra intensidades organizadas de outro modo nas células convertidas (cadernos 08 e 09).

E na própria floresta (caderno 12): a vegetação do MODIS em 8 dias não tem estrutura não linear nem se deixa prever pela atmosfera; o fogo derruba o LAI e o NDMI, deixa um déficit que reaparece em cada estação seca por pelo menos 3 anos e torna a floresta queimada mais sensível à chuva e ao VPD.

## Cadernos (Marimo)

Cada capítulo é um caderno Marimo em `notebooks/`, que lê dados já produzidos e gera as figuras da monografia. Os mapas mostram as duas bacias juntas; as figuras de uma só série têm um seletor de bacia, e as versões impressas das duas são gravadas.

| Caderno | Capítulo | Estado |
|---|---|---|
| `00_inicio` | apresentação, percurso, legenda das caixas e resumo dos resultados | pronto |
| `01_laboratorio` | sistemas dinâmicos conhecidos (teoria, interativo) | pronto |
| `02_regioes` | as bacias, a grade ERA5 e as células da comparação | pronto |
| `03_clima` | o clima de 1990–2024 e a anomalia padronizada | pronto |
| `04_perturbacao` | desmatamento e fogo por célula, concordância entre fontes, MODIS | pronto |
| `05_validacao_metodos` | o portão: descritores em controles sintéticos, e o portão mais exigente com nulas realistas, Wolf, Kantz, Cao e S-map (D-027) | pronto |
| `06_surrogates` | substitutas FT/IAAFT nas séries das bacias, Wolf, Kantz e Cao, e temperatura + umidade contra substitutas multivariadas (D-016, D-027, D-030) | pronto |
| `07_descritores` | descritores por célula, robustez, EWS, a grade de atrasos e a natureza diante das nulas realistas, por variável (D-024, D-027, D-029) | pronto |
| `08_gradiente` | perturbação × dinâmica, multiplicidade, inferência espacial (blocos de 1° a 2,5°, n efetivo) e placebo, robustez, checagem MODIS com a temperatura de pele do ERA5 no horário do satélite, comparativos e a sazonalidade como explicação alternativa (D-014, D-015, D-018, D-022, D-027, D-028, D-030) | pronto |
| `09_chuva` | a chuva do ERA5 e do CHIRPS diante da perturbação, o dither das substitutas e a ocorrência × intensidade (D-021, D-023, D-027, D-030) | pronto |
| `10_fogo` | o tempo antes do início dos episódios de fogo, com o contraste direto entre paisagens e bootstrap de anos × blocos (pergunta secundária, D-025, D-030) | pronto |
| `11_territorio` | Terras Indígenas e Unidades de Conservação diante do clima e do fogo (D-026) | pronto |
| `12_floresta_atmosfera` | a vegetação do MODIS (LAI e NDMI, 8 dias) como sistema dinâmico: portão de 8 dias, descritores, previsão e CCM com a atmosfera, horizontes de 8 a 64 dias com estado compacto e direção inversa (D-032), associação com a perda e a floresta depois do fogo (D-031) | pronto |

O fluxo anterior, em Jupyter, só existe no histórico do Git (tag `v0-jupyter`).

```bash
uv run marimo edit notebooks/03_clima.py                                  # editar
uv run marimo export html notebooks/03_clima.py -o reports/html/03_clima.html
```

## Ver e rodar sem os dados brutos

- **Ler:** a galeria em <https://thallescansi.github.io/Caos/> traz cada capítulo com todas as figuras.
- **Rodar no molab:** cada cartão tem um botão "Abrir no molab"; escolha o modo **Server**. O cabeçalho de cada caderno instala a biblioteca direto deste repositório, e, fora dele, a biblioteca baixa sozinha o pacote de visualização (configurações e dados processados, 59 MB).
- **Rodar localmente sem clonar os dados:** `uvx marimo edit --sandbox notebooks/03_clima.py`.
- **Atualizar a galeria:** `make notebooks && make publicar` (refaz capas, pacote de dados e página no ramo `gh-pages`).

O modo WebAssembly do molab não funciona com estes cadernos: várias dependências (rasterio, geopandas com GDAL) não existem no navegador.

## Animações

Clipes curtos e mudos, em 1920×1080, para a defesa e as palestras, gravados em `reports/animacoes/` (fora do Git) por `make animacoes CLIPES="…" QUALIDADE=final`; `make animacoes` sem nomes lista os clipes. São timelapses de mapa das duas bacias (anomalia mensal da temperatura, fogo mês a mês, desmatamento do PRODES, o ano médio da chuva), a máquina de substitutas em matplotlib e três peças em Manim (duas trajetórias, a bifurcação, de Lorenz ao Xingu). O código está em `src/amazon_chaos/animacoes/` e depende do grupo opcional `animacao` (`uv sync --group animacao`). O Manim roda num ambiente conda do conda-forge, porque o `pycairo` não tem wheel para Linux; a CLI chama esse Python sozinha (`MANIM_PYTHON`, por padrão `~/miniconda3/envs/manim/bin/python`).

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
