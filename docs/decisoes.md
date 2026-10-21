# Registro de decisões

Decisões arquiteturais e científicas estáveis. Execuções de análise ficam em `reports/registro_experimentos.csv`.

## D-001 — Marimo como ambiente interativo principal

**Status:** aceito; consolidado em D-008.

**Motivo:** notebooks em Python puro, execução reativa/determinística e melhor integração com Git.

**Regra:** downloads e ETLs caros ficam fora dos notebooks reativos.

## D-002 — uv para ambiente Python

**Status:** aceito.

**Motivo:** `pyproject.toml` + lockfile reproduzível e comandos consistentes.

## D-003 — Dados pesados fora do Git

**Status:** aceito.

**Motivo:** o projeto pode atingir centenas de GB/1 TB; Git é usado para código, manifests, configs e resultados pequenos.

## D-004 — GeoJSON/GeoParquet em vez de Shapefile no pipeline interno

**Status:** aceito.

**Motivo:** evitar truncamento de nomes de campos DBF e facilitar interoperabilidade moderna.

## D-005 — Unidade espacial: célula ERA5

**Status:** aceito em 20/10/2026.

**Motivo:** grade comum para agregar perturbações e extrair séries climáticas. Cada célula é recortada pelo limite da região e ponderada pela área efetiva. Regiões maiores servem apenas para síntese e comunicação.

## D-006 — Bacia do Xingu e arquivo ERA5 desde 1990

**Status:** aceito para a nova região.

**Recorte:** BHB250/IBGE-ANA, nível 3, bacia `cod_otto=642`; fração efetiva de célula ERA5 para integração espacial. O retângulo é somente a área de requisição CDS.

**Tempo:** 2001–2024 continua a janela principal; 1990–2000 é arquivo anterior para sensibilidade temporal e condições antecedentes. O corte em 1990 é operacional. Não presumir cobertura equivalente em PRODES, DETER ou focos. Detalhes e custos: [dados.md](dados.md).

## D-007 — ERA5 horário pelo Earth Data Hub

**Status:** aceito em 30/09/2026 para Xingu e Baixo Tapajós 1990–2024, com precisão reduzida conhecida. Reavaliar a aquisição direta pelo CDS para as análises finais.

**Motivo:** a fila do CDS (20–60 min por requisição mensal de poucos MB) tornava o arquivo 1990–2024 inviável. O espelho Zarr do Earth Data Hub é lido ano a ano, sem fila. Os arquivos mensais mantêm dias, horas UTC, grade e validação do fluxo CDS, e exigem ausência total de valores faltantes.

**Precisão:** o EDH não é bit a bit igual ao CDS. Guarda o float32 com a mantissa arredondada a ~10 bits (CDS: 17–21), erro relativo ≤ 2⁻¹¹ ≈ 4,9e-4 e sem viés. Medido contra os meses CDS de jan/1990 e jan/2024 (1.288 células): diferença horária máxima de 0,125 K em t2m/d2m, 36 Pa em sp, 0,002 m/s no vento e 0,009 mm em tp. Nas séries diárias de jan/1990, RMS de 0,015 °C na temperatura média, 0,072 °C na máxima, 0,10 °C na amplitude térmica (~5% do desvio-padrão do campo), 0,11 p.p. na umidade relativa e 0,0009 mm na chuva. Irrelevante para médias e climatologia; **para descritores não lineares sensíveis a ruído (Lyapunov, recorrência), testar a sensibilidade contra meses CDS antes de concluir.** Cada NetCDF registra isso no atributo `edh_precision`.

**Umidade:** o arredondamento faz o ponto de orvalho passar da temperatura em até 0,25 K (no CDS, no máximo 0,003 K), e a margem de 0,05 K anulava 1.493 horas no Xingu e 70 no Tapajós (1990–2024). Com EDH, a margem é 0,05 + 2 × 0,125 = 0,30 K: nenhuma hora anulada, e a umidade relativa dessas horas vale 100%. Atributo `dewpoint_tolerance_k` nas séries diárias.

**Trava:** o download integral só prossegue se os meses CDS já validados coincidirem com o EDH com tolerância relativa 2⁻¹⁰, o dobro do arredondamento, que ainda rejeita hora, grade ou convenção trocadas (um deslocamento de 1 h é rejeitado). Execução: [hpc.md](hpc.md).

**CDS direto (para depois):** o CDS recusa por custo pedidos de 6 variáveis × 6 meses e aceita 6 variáveis × 4 meses (testado em 30/09/2026), ou seja, ~106 requisições por região contra 842.

## D-008 — Marimo substitui os cadernos Jupyter

**Status:** aceito em 20/10/2026.

**Motivo:** os cadernos 03–06 eram gerados por scripts de 400 a 850 linhas, e os demais tinham lógica inline duplicada. Em Marimo, cada caderno é um arquivo Python versionável. Um mesmo caderno serve a todas as regiões (`-- --region <slug>`), e a lógica científica vive em `src/amazon_chaos`.

**Regra:** os cadernos não baixam dados nem fazem cálculo pesado; leem o que o CLI e os jobs em lote produziram. Os Jupyter ficam em `legacy/jupyter/` e na tag `v0-jupyter`, só para auditoria.

## D-009 — Tapajós pela bacia inteira (BHB250)

**Status:** aceito em 20/10/2026.

**Recorte:** BHB250/IBGE-ANA, nível 3, `cod_otto=644` (Bacia do Rio Tapajós): 493.153 km², 762 células ERA5 com interseção e 1.431 pontos pedidos ao EDH, com caixa `[N,W,S,E]=[-2.0,-60.25,-15.0,-53.75]`. A bacia é 80% Amazônia e 20% Cerrado; 35% da área está em TIs ou UCs federais (sem dupla contagem).

**Motivo:** a caixa de 56 células usada até aqui tinha muita água (Tapajós e Amazonas) e pouco contraste de perturbação. A bacia inteira segue a lógica hidrográfica do Xingu, tem tamanho quase igual (779 × 762 células) e cobre o gradiente completo: a soja do Teles Pires em MT, o Jamanxim e a BR-163, e o baixo Tapajós com a Flona e as TIs Munduruku. Também foi avaliado o recorte "644 sem Teles Pires, Arinos e Sangue" (450 células), descartado porque deixa uma faixa estreita ao longo do Juruena. O nível 4 da BHB250 só traz as sub-bacias afluentes, não o trecho do eixo principal.

A caixa antiga (`configs/regions/tapajos_caixa.yaml`, `tapajos-era5-1990-2024`) fica como plano B e como registro da execução `full_e57802a1f7` das substitutas.

## D-010 — Pré-registro dos descritores não lineares

**Status:** aceito em 20/10/2026.

**Regra:** variáveis, transformações, grades de τ e m, janela de Theiler, região de ajuste do Rosenstein, limiar da RQA, parâmetros da entropia de permutação, janela dos EWS, número de substitutas e sementes ficam em `configs/analysis/descriptors.yaml`. Esse arquivo é congelado num commit **antes** de qualquer cálculo nos dados reais. Mudanças posteriores geram uma nova versão, e ambas são relatadas.

**Gate:** um descritor só é interpretado nos dados reais depois de separar os controles positivos (Lorenz, logístico) dos negativos (AR(1), ruído, seno com ruído) contra substitutas, no caderno `05_validacao_metodos`.

**Versão 1, congelada em 20/10/2026** (gate `1c2fb37657`). Os 8 descritores passaram no critério, mas no AR(1) com variância sazonal e tendência Lyapunov e RQA·DET rejeitaram H0 em 100% e 80% das repetições. Padronizar a anomalia pelo desvio-padrão sazonal levou o DET a 0% sem perder poder no Lorenz; o Lyapunov ficou em 60%. Decisões aprovadas:
- séries em **anomalia padronizada**, sem remover tendência;
- família primária: entropia de permutação, complexidade, erro de previsão e RQA·DET;
- secundária: D2, LAM e assimetria;
- **Lyapunov apenas exploratório**, com ressalva explícita;
- exposição principal: 1 − floresta em 2000 (MapBiomas), com PRODES como sensibilidade (o PRODES não vê o Cerrado);
- células com menos de 50% de terra observada ficam fora da comparação.

**Versão 2, 20/10/2026**, antes de qualquer análise de perturbação × dinâmica. Na comparação entre células, só entram as que têm pelo menos 50% da área dentro da bacia. Motivo: o ERA5 dá uma única série para a célula inteira, mas a perturbação de uma célula de borda é medida só na parte dentro da bacia; e 80 células cortadas pelo divisor entre Xingu e Tapajós entrariam nas duas regiões. Ficam 668 células no Xingu e 654 no Tapajós, sem repetição. A mudança não altera nenhum cálculo por célula: o lote é identificado só pelas seções que o afetam (`batch_hash`).

## D-011 — Checagem do ERA5 com MODIS LST

**Status:** aceito em 20/10/2026.

**Motivo:** o ERA5 usa um mapa de vegetação fixo e não "vê" o desmatamento diretamente. A temperatura de superfície do MODIS (MOD11A2, 2001–2024) mostra se o gradiente de perturbação aparece num dado observado. O MODIS serve só para essa checagem e não entra na análise não linear, por causa das lacunas de nuvens.

## D-012 — INPE como fonte principal de perturbação; MapBiomas complementar; sem GEE no caminho crítico

**Status:** aceito em 20/10/2026.

**Motivo:** o projeto aprovado (`docs/entregas/projeto_aprovado.pdf`) define PRODES e DETER (TerraBrasilis) e BDQueimadas como bases de distúrbio, com o MapBiomas como complemento. O Google Earth Engine tem cota mensal de computação, por isso todas as fontes são baixadas uma vez pelo CLI, com manifesto, e agregadas por célula localmente ou no HPC. O MapBiomas é lido dos COGs públicos. O `earthengine-api` fica num grupo opcional (`gee`), só para reproduzir as séries regionais antigas.


## D-013 — Resolução das substitutas e análise complementar da rejeição

**Status:** aceito em 21/10/2026, depois do lote por célula e antes de qualquer análise de perturbação × dinâmica.

**Problema:** com 39 substitutas por célula, o menor p de Monte Carlo é 1/40 = 0,025 (unilateral) e 2/40 = 0,05 (bilateral). Na correção de Benjamini–Hochberg pré-registrada, um p no piso só sobrevive se ao menos metade das células também estiver no piso (unilateral) ou se todas estiverem (bilateral). O resultado pré-registrado passa a depender de quantas células atingem o piso, e não da força da evidência: a complexidade da temperatura no Tapajós dá 0% de rejeição com 10% das células com z > 9; a laminaridade do VPD dá 100% no Xingu e 0% no Tapajós por uma única célula.

**Decisão:** o resultado pré-registrado (BH) é relatado como está, com essa limitação explicada. Ao lado dele, **marcados como análise complementar, não pré-registrada**: (1) a fração de células com p ≤ 0,05, comparada a α, com IC 95% por bootstrap em blocos espaciais de 1° × 1° (`nonlinear.results.global_rejection`); (2) a distribuição dos z-scores. A comparação q ≤ α usa tolerância numérica de 1e-9, porque 2/40 × n/n = 0,05000000001 por arredondamento. Repetir o lote com 199 substitutas resolveria a resolução, mas custaria cerca de 95 h de HPC.

## D-014 — Controle do relevo e análises complementares do gradiente

**Status:** aceito em 21/10/2026, durante a análise do caderno 08.

**Relevo (previsto no pré-registro):** a altitude do relevo do modelo ERA5 (geopotencial `z` / g, Earth Data Hub, comando `amazon-chaos era5 static`) entra como controle ao lado da latitude e da fração de água, como o pré-registro previa ("elevação entra quando o MDE estiver agregado"). Usar o relevo do próprio ERA5 evita a mistura de escalas de um modelo digital de elevação de 30 m.

**Análises complementares, não pré-registradas, motivadas pelos resultados:**
1. A exposição principal, 1 − floresta em 2000, conta como "perda" também a vegetação naturalmente não florestal (savanas e campos do Cerrado, ρ ≈ 0,7–0,8 com a exposição). Como sensibilidade, usamos a fração agropecuária em 2000 (conversão de fato) e controlamos a vegetação natural não florestal.
2. A fração de vegetação alta fixa do ERA5 (`cvh`) acompanha a floresta de 2000 (ρ = 0,51 e 0,65), mas não a perda posterior. Controlá-la mostra quanto da associação entre perturbação e descritores passa pelo mapa de vegetação do próprio modelo.

Ambas são relatadas como complementares, ao lado do resultado pré-registrado, que permanece o principal.
