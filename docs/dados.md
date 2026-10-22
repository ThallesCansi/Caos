# Dados

Este documento reúne o catálogo de fontes, a cobertura real de cada uma, a organização em disco e os contratos entre etapas. O método de uso está em [metodologia.md](metodologia.md), e as decisões com data em [decisoes.md](decisoes.md).

## 1. Catálogo

| Fonte | Papel | Acesso | Cobertura e restrições | Estado |
|---|---|---|---|---|
| **ERA5** horário, single levels (ECMWF/C3S) | séries climáticas | CDS (`cdsapi`) ou espelho Zarr do **Earth Data Hub** (D-007) | 1940–hoje; 0,25° interpolado de cerca de 31 km nativos; reanálise com **vegetação fixa** (D-011) | Xingu e Tapajós 1990–2024 baixados e processados |
| **BHB250** (IBGE/ANA, 2021) | limites das bacias | geoftp do IBGE | nível 3. Xingu: `cod_otto=642`, 508.627 km², 93% Amazônia e 7% Cerrado. Tapajós: `cod_otto=644`, 493.153 km², 80% Amazônia e 20% Cerrado | Xingu (642) e Tapajós (644) prontos (D-009) |
| **PRODES** (INPE/TerraBrasilis) | desmatamento, fonte principal | download dos vetores e da máscara | incrementos de 1988–2007 **agregados**; anuais de 2008 em diante; ano agosto–julho | agregado por célula nas duas bacias (caderno 04) |
| **DETER** (INPE/TerraBrasilis) | degradação e alertas recentes | WFS (`io/terrabrasilis.py`) | alertas desde 2016 na Amazônia; data de detecção ≠ data de ocorrência; não é taxa oficial | corte raso e degradação 2016–2024 por célula (caderno 04) |
| **BDQueimadas** (INPE) | fogo ativo, fonte principal | CSVs anuais de dados abertos | usar o satélite de referência (AQUA tarde); foco ≠ incêndio ≠ área queimada; auditar trocas de plataforma | focos 2003–2024 por célula (caderno 04) |
| **MapBiomas Cobertura**, col. 11 | fração de floresta, uso, água; complementar | COGs públicos (sem GEE, D-012) | anual de 1985 a 2024, 30 m; mudança de classe ≠ desmatamento PRODES | frações por célula em 1990, 2000, 2012 e 2024, lidas dos COGs (caderno 04) |
| **MapBiomas Fogo**, col. 5.1 | área queimada, frequência e último fogo; complementar | COGs públicos | anual de 1985 a 2024; recorrência anual não conta eventos dentro de um ano | área queimada e frequência por célula (caderno 04) |
| **MODIS LST** MOD11A2 | checagem do ERA5 (D-011) | NASA AppEEARS (conta Earthdata) | 8 dias, 1 km, de 2000 em diante; lacunas de nuvens | 2001–2024 por célula nas duas bacias (D-018) |
| **CHIRPS** v3.0 diário "sat" (CHC/UCSB) | chuva diária observada; checagem da chuva do ERA5 (D-021) | NetCDF anual global, um por vez, recortado (`amazon-chaos chirps fetch`); o servidor bane leituras parciais em paralelo | pêntadas de infravermelho + estações repartidas em dias pelo IMERG; 0,05°; de 1998 em diante; dia UTC. A versão "rnl" reparte pelo ERA5 e não serve | 2001–2024 a baixar |
| **Relevo** (geopotencial do ERA5) | covariável | Earth Data Hub (`amazon-chaos era5 static`) | estático, na grade do modelo; substitui o MDE de 30 m (D-014) | pronto |
| **Contexto cartográfico** | mapas | IBGE (biomas, municípios), FUNAI (TIs), ICMBio/INDE (UCs), Natural Earth (rios, cidades) | limites atuais, não históricos; o servidor da FUNAI omite o certificado intermediário, que é obtido pelo endereço AIA (`regions.MISSING_INTERMEDIATE`) | prontos para as duas bacias |

Classes MapBiomas usadas: floresta {3, 6}; agropecuária {9, 14, 15, 18, 19, 20, 21, 35, 36, 39, 40, 41, 46, 47, 48, 62}; água {31, 33}. As versões exatas das coleções são fixadas no manifesto de cada download.

## 2. ERA5

**Variáveis baixadas:**
- instantâneas: `2m_temperature`, `2m_dewpoint_temperature`, `surface_pressure`, `10m_u_component_of_wind`, `10m_v_component_of_wind`;
- acumulada: `total_precipitation`.

As variáveis derivadas estão em [`configs/variables.yaml`](../configs/variables.yaml).

- **Earth Data Hub:** precisão reduzida conhecida (mantissa de cerca de 10 bits, até 0,125 K na temperatura horária). O download só segue se coincidir com os meses CDS dentro de uma tolerância relativa de 2⁻¹⁰. Os números estão em D-007.
- **Volume:** Xingu 1990–2024 ocupa cerca de 2,4 GB brutos e 2,5 GB processados (1.288 pontos pedidos, 779 na bacia). Tapajós (bacia) 1990–2024, baixado em 20/10/2026 em 35 min no HPC: 2,6 GB brutos (ficam no HPC) e 1,2 GB processados, 762 células sem nenhuma célula-ano incompleta.
- **Organização:** um NetCDF por mês, com manifesto e SHA-256. Os diários são gravados ano a ano e mascarados pela bacia.

## 3. Organização em disco

```
data/                          fora do Git; pode morar em outro lugar via AMAZON_CHAOS_DATA_DIR
  external/<região>/           limites, grade, cartografia de contexto (sources.json com URL, data, SHA-256)
  raw/<experiment_id>/         brutos imutáveis por fonte (era5/, edh/, prodes/, ...) com manifest.json
  processed/<experiment_id>/   daily_<ano>.nc, summary_1990_2024.nc, basin_grid.geojson,
                               disturbance.parquet, descriptors.parquet, runs/<hash>/
  processed/surrogates/runs/   execuções do protocolo de substitutas (config, p, distribuições nulas)
  cache/                       descartável
reports/
  figures/<caderno>/<região>/  figuras PNG (300 dpi) e PDF
  tables/<caderno>/            CSV e .tex
  overleaf/                    cópia com nomes estáveis para a monografia
  registro_experimentos.csv    uma linha por execução relevante
```

Experimentos: `xingu-era5-1990-2024` e `tapajos-bacia-era5-1990-2024`.

## 4. Contratos

**Grade** (`basin_grid.geojson`): `cell_id` estável, `latitude`, `longitude`, polígono de integração recortado, `cell_km2`, `basin_km2` (área efetiva) e `fraction`.

**Diário** (`daily_<ano>.nc`): dimensões `time` (dia local), `latitude`, `longitude`. Para cada variável há estatísticas diárias com as respectivas **contagens de horas válidas**. Atributos de proveniência incluem `edh_precision` e `dewpoint_tolerance_k`.

**Perturbação** (`disturbance.parquet`, um registro por `cell_id` × período):
- área terrestre válida;
- floresta no início;
- desmatamento acumulado e recente (PRODES);
- área DETER;
- focos por km² por ano, anos com foco e recência (BDQueimadas), com indicador de censura;
- frações MapBiomas;
- elevação.

A fonte e a versão ficam registradas por coluna.

**Descritores** (`descriptors.parquet`, um registro por `cell_id` × variável × transformação × janela × parâmetros):
- valor;
- média e desvio das substitutas;
- z-score e p;
- número de amostras;
- percentual ausente;
- hash da configuração pré-registrada;
- commit.

**Série para dinâmica não linear:** `series_id`, `cell_id`, variável, transformação (`original` ou `anomalia`), período, frequência, número de amostras, percentual ausente e a configuração, o commit e os manifestos de origem.
