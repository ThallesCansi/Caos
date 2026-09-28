# Registro de decisões

Use este arquivo para decisões arquiteturais/científicas estáveis. Para experimentos, use `experiments/registry.csv`.

## D-001 — Marimo como ambiente interativo principal

**Status:** aceito inicialmente.

**Motivo:** notebooks em Python puro, execução reativa/determinística e melhor integração com Git.

**Regra:** downloads e ETLs caros ficam fora dos notebooks reativos.

## D-002 — uv para ambiente Python

**Status:** aceito inicialmente.

**Motivo:** `pyproject.toml` + lockfile reproduzível e comandos consistentes.

## D-003 — Dados pesados fora do Git

**Status:** aceito.

**Motivo:** o projeto pode atingir centenas de GB/1 TB; Git é usado para código, manifests, configs e resultados pequenos.

## D-004 — GeoJSON/GeoParquet em vez de Shapefile no pipeline interno

**Status:** aceito.

**Motivo:** evitar truncamento de nomes de campos DBF e facilitar interoperabilidade moderna.

## D-005 — Unidade espacial inicial: célula ERA5

**Status:** proposta a validar.

**Motivo:** fornece grade comum para agregar perturbações e extrair séries climáticas. Comparar com alternativas antes de congelar.
