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

**Status:** aceito em 30/09/2026 para Xingu e Baixo Tapajós 1990–2024, com precisão reduzida conhecida. Reavaliar a aquisição direta pelo CDS para as análises finais.

**Motivo:** a fila do CDS (20–60 min por requisição mensal de poucos MB) tornava o arquivo 1990–2024 inviável. O espelho Zarr do Earth Data Hub é lido ano a ano, sem fila. Os arquivos mensais mantêm dias, horas UTC, grade e validação do fluxo CDS, e exigem ausência total de valores faltantes.

**Precisão:** o EDH não é bit a bit igual ao CDS. Guarda o float32 com a mantissa arredondada a ~10 bits (CDS: 17–21), erro relativo ≤ 2⁻¹¹ ≈ 4,9e-4 e sem viés. Medido contra os meses CDS de jan/1990 e jan/2024 (1.288 células): diferença horária máxima de 0,125 K em t2m/d2m, 36 Pa em sp, 0,002 m/s no vento e 0,009 mm em tp. Nas séries diárias de jan/1990, RMS de 0,015 °C na temperatura média, 0,072 °C na máxima, 0,10 °C na amplitude térmica (~5% do desvio-padrão do campo), 0,11 p.p. na umidade relativa e 0,0009 mm na chuva. Irrelevante para médias e climatologia; **para descritores não lineares sensíveis a ruído (Lyapunov, recorrência), testar a sensibilidade contra meses CDS antes de concluir.** Cada NetCDF registra isso no atributo `edh_precision`.

**Trava:** o download integral só prossegue se os meses CDS já validados coincidirem com o EDH com tolerância relativa 2⁻¹⁰, o dobro do arredondamento, que ainda rejeita hora, grade ou convenção trocadas (um deslocamento de 1 h é rejeitado). Execução: [HPC_EDH.md](HPC_EDH.md).

**CDS direto (para depois):** o CDS recusa por custo pedidos de 6 variáveis × 6 meses e aceita 6 variáveis × 4 meses (testado em 30/09/2026), ou seja, ~106 requisições por região contra 842.
