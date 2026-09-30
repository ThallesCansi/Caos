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

## D-006 — Bacia do Xingu e arquivo ERA5 desde 1990

**Status:** aceito para a nova região.

**Recorte:** BHB250/IBGE-ANA, nível 3, bacia `cod_otto=642`; fração efetiva de célula ERA5 para integração espacial. O retângulo é somente a área de requisição CDS.

**Tempo:** 2001–2024 continua a janela principal; 1990–2000 é arquivo anterior para sensibilidade temporal e condições antecedentes. O corte em 1990 é operacional. Não presumir cobertura equivalente em PRODES, DETER ou focos. Detalhes e custos: [XINGU.md](XINGU.md).

## D-007 — ERA5 horário pelo Earth Data Hub

**Status:** aceito, condicionado à conferência automática com o CDS.

**Motivo:** a fila do CDS (20–60 min por requisição mensal de poucos MB) tornava o arquivo 1990–2024 inviável. O espelho Zarr do Earth Data Hub é lido ano a ano sem fila. Os arquivos mensais mantêm dias, horas UTC, grade e validação do fluxo CDS, e exigem ausência total de valores faltantes. O download integral só prossegue se os meses CDS já validados coincidirem com o EDH até arredondamento de float32. Execução: [HPC_EDH.md](HPC_EDH.md).
