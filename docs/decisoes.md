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

**Versão 2, 20/10/2026**, antes de qualquer análise de perturbação × dinâmica. Na comparação entre células, só entram as que têm pelo menos 50% da área dentro da bacia. Motivo: o ERA5 dá uma única série para a célula inteira, mas a perturbação de uma célula de borda é medida só na parte dentro da bacia; e 80 células cortadas pelo divisor entre Xingu e Tapajós entrariam nas duas regiões. Ficam 668 células no Xingu e 654 no Tapajós, sem repetição; somada a regra de terra observada (≥ 50%), o Tapajós perde mais 2 células dominadas pelo rio e a comparação usa 652. A mudança não altera nenhum cálculo por célula: o lote é identificado só pelas seções que o afetam (`batch_hash`).

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

## D-015 — Mudança da dimensão de imersão entre as metades do período

**Status:** aceito em 21/10/2026, durante a análise longitudinal do caderno 08.

**Problema:** o pré-registro escolhe m pelo critério dos falsos vizinhos em cada janela. Entre 2001–2012 e 2013–2024, m muda em 20% a 33% das células (t2m e VPD, Xingu). Os descritores que dependem do espaço de fases (DET, LAM, D2, Lyapunov) saltam junto com m: a mudança de DET fica em três faixas (cerca de −0,03, +0,01 e +0,04 para m −1, igual e +1), e esse salto é maior que a mudança climática que se quer medir. A entropia e a complexidade de permutação têm ordem fixa e não dependem de m; o erro de previsão quase não reage.

**Decisão:** o resultado longitudinal pré-registrado é relatado como está. Como sensibilidade complementar, repetimos a análise só nas células em que m é o mesmo nas duas metades (`dm_{var} == 0` em `gradient.cell_table`). As conclusões não mudam: nenhuma associação longitudinal se destaca. As frações de células em que DET e LAM aumentam (caderno 07) também misturam esse efeito e devem ser lidas com essa ressalva.

## D-016 — Teste de substitutas na série média de cada bacia

**Status:** aceito em 21/10/2026, para o caderno 06.

**Decisão:** o caderno 06 aplica os oito descritores pré-registrados à série média diária de cada bacia (ponderada pela área; anomalia padronizada; 2001–2024), com a mesma regra de (τ, m, w) do lote por célula, mas com 199 substitutas em vez de 39 e com três variantes: FT, IAAFT (a nula do pré-registro) e IAAFT depois de retirar a tendência linear (`amazon-chaos descriptors basin`, módulo `nonlinear.basin_test`). A correção de Holm é feita sobre os descritores primários das duas variáveis, separadamente por bacia e variante.

**Motivo:** a série da bacia é uma só, então cabe uma resolução de Monte Carlo maior (p mínimo de 0,005, unilateral), que evita a limitação de D-013. A comparação FT × IAAFT separa a assimetria da distribuição (que a FT confunde com dinâmica) de estrutura temporal. A variante sem tendência é necessária porque as séries sobem de 0,8 a 1,1 desvio-padrão em 24 anos (o KPSS rejeita a estacionariedade em todas), e uma tendência é uma não estacionariedade que nenhuma das duas nulas contempla.

**Natureza:** análise complementar, não pré-registrada. Não substitui o resultado por célula (caderno 07), que segue o pré-registro.

## D-017 — Limpeza final do repositório e cadernos com as duas bacias juntas

**Status:** aceito em 21/10/2026.

**Decisão:** saem do repositório a pasta `legacy/` (cadernos Jupyter e seus geradores), as figuras e tabelas do fluxo antigo em `reports/` (`mapbiomas`, `surrogates`, `*_1990_2024`), o módulo `nonlinear/surrogate_study.py` (o diagnóstico de estacionariedade passou para `nonlinear/basin_test.py`), a função `surrogate_test`, os auxiliares de cabeçalho e aviso de `nb.py` e o grupo opcional `gee` do `pyproject.toml`. A caixa antiga do Tapajós deixa de ser uma região e vira um arquivo de teste (`tests/fixtures/regiao_caixa.yaml`), o único exemplo de limite por caixa. Tudo continua recuperável pela tag `v0-jupyter` e pelo histórico do Git.

Os cadernos 03 e 04 deixam de ter um seletor de região que trocava o capítulo inteiro: os mapas mostram as duas bacias juntas, os gráficos de linhas as sobrepõem e só as figuras de uma única série têm um seletor próprio, com as versões impressas das duas bacias gravadas. Com isso, o HTML estático mostra o trabalho inteiro, e o `--region` deixou de existir. As figuras passam a ser exibidas em resolução de tela (110 dpi), e os arquivos da monografia continuam em 300 dpi, o que mantém cada célula abaixo do limite de saída do Marimo.

Substitui, nesses pontos, D-008 (`-- --region <slug>` e `legacy/jupyter/`), D-009 (caixa como plano B) e D-012 (grupo `gee`).

## D-018 — Checagem MODIS: o satélite vê o desmatamento; o ar do ERA5 não, a superfície vê uma fração

**Status:** resultado registrado em 22/10/2026 (checagem prevista em D-011).

**Dados:** MOD11A2 coleção 6.1 pelo AppEEARS, 2001–2024, composições de 8 dias a 1 km, só pixels de boa qualidade (QC bits 0–1 ≤ 1 e erro de LST ≤ 2 K), agregados às células (`features/lst.py`, `gradient.surface_table`). O QC = 0, melhor qualidade, vem do AppEEARS marcado como "sem dado" e era decodificado como NaN; o filtro agora o trata explicitamente como 0. As datas vêm em `cftime`. Comparação no ERA5: máxima diária do ar a 2 m na estação seca (junho a setembro), a grandeza mais próxima do LST diurno das 10h30.

**Resultado (células elegíveis, controles latitude, água e altitude, IC por blocos de 1°):** entre células, a perda antecedente se associa ao LST diurno da estação seca com ρ parcial de +0,81 (Xingu) e +0,74 (Tapajós), de 6 a 7 °C entre o décimo menos e o mais perturbado (perda antecedente); com a máxima do ERA5, −0,14 e −0,06, compatíveis com zero. Ao longo do tempo, a perda de 2001–2012 se associa ao aquecimento do LST entre as décadas com ρ de +0,72 e +0,77; no ERA5, −0,18 e +0,04.

**Checagem (23/10/2026):** só nas células com menos de 5% de vegetação natural não florestal em 2000, a associação entre perda antecedente e LST continua em +0,81 (Xingu) e +0,77 (Tapajós), com 5,6 °C entre o décimo mais e o menos convertido; com a conversão agropecuária, controlando a vegetação natural, +0,77 nas duas. A diferença não vem do Cerrado natural.

**Viés de céu limpo (23/10/2026):** na estação seca, a mediana das células tem cerca de 378 das 384 composições possíveis (16 por ano × 24 anos) com qualidade boa; o 10º percentil é 335 no Xingu e 371 no Tapajós. Com o número de composições válidas nos controles, a associação entre a perda antecedente e o LST fica em +0,80 e +0,71, e a longitudinal em +0,71 e +0,76; só na metade das células com mais composições válidas, +0,85 e +0,68.

**Comparativo F2e (29/10/2026, D-027):** a máxima diária do ar não é a grandeza do LST. Com a temperatura de pele (`skt`) do ERA5 interpolada para as 10h30 solares na estação seca (`features/lst.era5_overpass`, `amazon-chaos era5 overpass`), a associação entre células com a perda antecedente é de +0,25 [+0,05; +0,46] no Xingu e +0,29 [+0,09; +0,47] no Tapajós, com 2,4 e 1,2 °C entre o décimo mais e o menos perturbado, contra 6,7 e 6,4 °C no MODIS; só nos dias com `tcc` < 0,3, +0,29 e +0,32, com contrastes menores (1,7 e 0,8 °C). Com a vegetação alta e baixa do ERA5 nos controles, a do Xingu cai a +0,05 [−0,12; +0,25] e a do Tapajós fica em +0,29 [+0,10; +0,42]. Ao longo do tempo, −0,13 [−0,30; +0,05] e −0,43 [−0,53; −0,29]: no Tapajós, o ERA5 aquece mais a pele das células sem perda. Pela regra de leitura fixada, o resultado qualifica a leitura entre células (parte do contraste MODIS × ERA5 era diferença de grandeza; a superfície do ERA5 registra cerca de um terço do contraste em °C no Xingu, e ali só pelo mapa de vegetação fixo, e cerca de um quinto no Tapajós) e confirma que o ERA5 não registra o desmatamento posterior a 2000. Caderno 08, Figura 7 e Tabela 4, como comparativo complementar.

**Leitura (corrigida em 30/10/2026 com o F2e):** evidencia, com observação independente do modelo, a limitação de D-011 e a interpretação de D-014 e D-015: o resultado longitudinal nulo do caderno 08 não indica ausência de efeito do desmatamento, e sim que o ERA5 não o registra. O ERA5 não é cego, é míope: entre lugares, a sua superfície vê uma fração do contraste, em parte pelo próprio mapa de vegetação; ao longo do tempo, nada. Isso explica por que o contraste entre células aparece na reanálise e a mudança não. O LST não entra na análise não linear: as lacunas de nuvem impedem séries diárias. É análise complementar, prevista no plano mas não no pré-registro dos descritores.

## D-019 — A pergunta no nível do sistema, não da base de dados

**Status:** aceito em 22/10/2026, depois de duas avaliações do projeto.

**Decisão:** a pergunta de pesquisa volta ao nível do objetivo geral do projeto aprovado e deixa de citar a fonte dos dados: a perturbação da floresta amazônica (desmatamento e fogo) deixa marca na dinâmica do clima local, isto é, na forma como ele evolui de um dia para o outro, e as ferramentas da teoria do caos conseguem revelá-la? Ela se desdobra em três subperguntas: natureza (que tipo de dinâmica o clima diário local tem), relação (se essa dinâmica difere entre lugares mais e menos perturbados e muda onde a floresta é perdida) e detectabilidade (que escala, grandeza e tipo de registro são necessários para que a marca apareça). A pergunta sobre as células ERA5 continua como operacionalização. O ERA5 e o MODIS passam a ser instrumentos, e a limitação de D-011 e D-018 responde à terceira subpergunta.

**Natureza:** muda o enquadramento, não a análise. Descritores, transformações, famílias, exposição e regras de seleção do pré-registro (D-010) ficam como estão.

## D-020 — Benjamini–Hochberg dentro de cada família, como no pré-registro

**Status:** aceito em 22/10/2026.

**Problema:** o pré-registro (`descriptors.yaml`, seção `families`) manda corrigir "dentro de cada família, sobre as células, separadamente por região × variável × janela", mas `nonlinear.results.load` corrigia dentro de cada descritor.

**Decisão:** o resultado principal passa a ser a correção por família, a leitura literal do arquivo congelado; a correção por descritor fica ao lado como sensibilidade (Tabela 1 do caderno 07). As duas coincidem em todos os casos menos dois, ambos efeito do piso de p de D-013: o determinismo da temperatura no Tapajós e a laminaridade do VPD no Xingu passam de 100% para 0% das células. Nenhuma conclusão depende dessa diferença: a fração de células com p ≤ 0,05 e os z-scores (D-013) não mudam.

**Também revisto:** o I de Moran de `gradient.moran_i` usa os 4 vizinhos ortogonais, e não os 8 adjacentes que a documentação dizia (a diagonal fica a 0,354°, fora do raio de 0,26°). Com os 8, o I cai cerca de 0,05 (por exemplo, de 0,65 para 0,60 na entropia do VPD no Xingu), sem mudar a leitura.

## D-021 — Chuva: CHIRPS v3 "sat" e ERA5 pelos descritores ordinais

**Status:** aceito em 22/10/2026, antes de qualquer cálculo dos descritores da chuva.

**Motivo:** o pré-registro previa a chuva como variável exploratória, só com métodos ordinais, e o lote não a calculou (só t2m e VPD). A subpergunta de detectabilidade (D-019) pede uma série diária observada que não dependa da vegetação fixa da reanálise.

**Fonte:** CHIRPS v3.0, produto diário final "sat" (CHC/UCSB; Funk et al., 2026). O CHIRPS é um produto de pêntadas, com infravermelho e estações; o valor diário é a pêntada repartida em dias. Na versão "sat" a repartição segue o IMERG Late V07, de 1998 em diante. Ficam de fora a "rnl", que reparte pelos dias do próprio ERA5, e a v2.0, que reparte pelo CFSv2: nas duas, a dinâmica dia a dia viria de um modelo. A média é tomada sobre o quadrado inteiro de cada célula de 0,25°, o mesmo que a série do ERA5 representa, com a fração exata de cada pixel de 0,05° (as bordas das células caem nos centros dos pixels). O dia é o dia UTC do produto. Aquisição: `amazon-chaos chirps fetch`, um NetCDF anual por vez, recortado na caixa das regiões e com o SHA-256 do arquivo global de origem.

**Análise** (`nonlinear/precip.py`, fixada antes de calcular):
- série: chuva diária bruta (mm), sem anomalia. Os padrões ordinais não mudam com transformações monotônicas, e a anomalia padronizada ordenaria os dias secos pela climatologia;
- empates: ruído uniforme de até 10⁻⁶ mm, com semente fixa por célula, fonte e janela, antes das substitutas;
- descritores: entropia de permutação e complexidade estatística com os parâmetros pré-registrados (ordem 5, atraso 1, alternativas `less` e `greater`), contra 39 substitutas IAAFT, nas janelas 2001–2024, 2001–2012 e 2013–2024;
- as mesmas regras para a chuva do ERA5 (`precip_mm_sum`) e do CHIRPS, em todas as células;
- correção de Benjamini–Hochberg dentro da família exploratória (os dois descritores), por região × fonte × janela; associação com a perturbação pelo mesmo modelo do caderno 08 (Spearman parcial, latitude, água e altitude, IC por blocos de 1°).

**Natureza:** exploratória. Os descritores ordinais passaram no gate F4 em séries contínuas, mas não foram validados em séries intermitentes; o resultado é lido como comparação entre as duas fontes, não como evidência isolada.

## D-022 — Robustez do resultado entre células: blocos maiores, valor observado e perda de 1990 a 2000

**Status:** aceito em 22/10/2026, depois da revisão externa do projeto (caderno 08, Tabela 2).

**Análises complementares, não pré-registradas:**
1. IC por bootstrap em blocos de 3° além dos de 1° (`gradient.associate(..., block=)`). As associações do VPD nas duas bacias e a do determinismo da temperatura se mantêm; no Xingu, a entropia e o erro de previsão da temperatura passam a tocar o zero.
2. O valor observado do descritor como resposta, no lugar do z, e a decomposição do z em média das substitutas (a parte linear) e excesso (observado − média). As associações dos padrões ordinais somem no valor observado, porque a parte linear e o excesso variam em sentidos opostos com a perturbação. A associação do z é praticamente a do excesso, e não vem do desvio das substitutas. Leitura: nas células mais perturbadas, a organização das séries vem mais da parte linear (persistência, ciclo anual) e menos da estrutura não linear além dela. O erro de previsão é menor nessas células também no valor observado (no Xingu nas duas variáveis; no Tapajós só no VPD).
3. A perda de floresta de 1990 a 2000 (MapBiomas), que é desmatamento de fato, sem a vegetação aberta natural, como exposição. As associações do VPD no Xingu se repetem com metade do tamanho; as demais ficam compatíveis com zero, salvo o determinismo do VPD no Tapajós, com sinal oposto.

4. Só as células com menos de 5% de vegetação natural não florestal em 2000 (521 no Xingu, 437 no Tapajós): todas as associações se repetem com o mesmo tamanho; o contraste não vem do Cerrado natural.

O resultado pré-registrado (Tabela 1 do caderno 08) permanece o principal.

## D-023 — A secura como explicação alternativa da associação na chuva do CHIRPS

**Status:** aceito em 23/10/2026, depois de ver o primeiro resultado do lote da chuva (caderno 09).

**Resultado que motivou:** com os controles do pré-registro (latitude, água e altitude), a entropia de permutação da chuva do CHIRPS é menor nas células com mais perda antecedente (ρ parcial de −0,38 no Xingu e −0,21 no Tapajós, no valor observado), e a do ERA5 não acompanha a perturbação.

**Análises complementares, não pré-registradas:** a mesma associação com controles da climatologia do próprio CHIRPS em 2001–2024 (chuva anual, fração de dias com menos de 0,1 mm e número de meses com menos de 100 mm na média), separadamente e juntos; com a conversão agropecuária em 2000 como exposição, controlando a vegetação natural não florestal; e só nas células com menos de 5% de vegetação natural não florestal. A secura da fronteira agrícola é o confundidor mais plausível, porque a perda antecedente se correlaciona com a chuva anual (−0,39 e −0,72) e com os meses secos (+0,20 e +0,68).

**Leitura fixada antes de escrever o caderno:** a associação só é tratada como robusta numa bacia se sobreviver aos três controles juntos e ao recorte das células de floresta.

## D-024 — Sensibilidade do lote: 199 substitutas, τ = 2 e ruído do Earth Data Hub

**Status:** aceito em 23/10/2026, antes do cálculo (`nonlinear/sensitivity.py`).

**Motivo:** três perguntas que o lote por célula deixou abertas: a resolução das 39 substitutas (D-013), a dependência do atraso de imersão (a regra deu τ = 1 em quase todas as células, e o determinismo muda muito com τ) e o arredondamento do Earth Data Hub, que D-007 mandava testar antes de concluir.

**Desenho:** cerca de 60 células elegíveis por bacia (eram 100; reduzidas antes de qualquer resultado, para caber antes de uma manutenção do HPC), sorteadas em partes iguais nos 9 estratos de terços de latitude × terços de perda antecedente (semente 20261023); só os descritores primários e a janela 2001–2024; três variantes da regra, cada uma com a mesma semente das substitutas do lote original: (1) 199 substitutas; (2) τ = 2, com m pelos falsos vizinhos nesse atraso e Theiler recalculado; (3) ruído gaussiano somado à série diária antes da anomalia, com o dobro da diferença RMS diária medida entre o EDH e o CDS (0,030 °C na temperatura; 0,010 kPa no VPD, propagado da umidade relativa), com 39 substitutas.

**Leitura:** comparação, nas mesmas células, com o lote original: a fração que rejeita a hipótese linear, a correlação célula a célula dos z e a correlação parcial com a perturbação. Análise complementar.

**Resultado (23/10/2026; 60 células no Xingu e 62 no Tapajós; caderno 07, Tabela 2):** as três variantes reproduzem o lote. A correlação de postos entre o z da variante e o do lote fica acima de 0,9 na maior parte dos casos (mínimos: 0,66 no DET da temperatura com τ = 2 no Tapajós e 0,69 no erro de previsão do VPD com 199 substitutas); a fração de células que rejeitam muda no máximo alguns pontos percentuais; a correlação parcial com a perturbação muda da ordem de 0,1, dentro dos intervalos. Os resultados não dependem da resolução das substitutas, do atraso nem do arredondamento do EDH.

## D-025 — Pergunta secundária: o tempo antes do início dos episódios de fogo

**Status:** aceito em 23/10/2026 (`features/fire_weather.py`, caderno 10).

**Desenho:**
- evento: o início de um episódio de fogo, isto é, um dia com foco do BDQueimadas (satélite de referência, 2003–2024, dia local UTC−03:00) numa célula sem foco nos 30 dias anteriores. A primeira versão, que usava o primeiro foco do ano civil, foi descartada antes de qualquer análise, porque punha muitos eventos em janeiro, em queimas da temporada anterior;
- medidas até a véspera: anomalia do VPD e da temperatura do ERA5 nos 7 e nos 30 dias anteriores, chuva dos 30 dias anteriores no CHIRPS e no ERA5 e dias seguidos com menos de 1 mm no CHIRPS;
- controle: os dias a até ±15 dias do calendário, na mesma célula, nos anos sem foco nessa janela. Cada evento é resumido pelo percentil entre os seus controles (0,5 é um dia típico). A diferença para a média dos controles foi descartada porque seria negativa sem efeito nenhum em medidas assimétricas, como a chuva acumulada;
- incerteza: bootstrap reamostrando anos inteiros, porque um mesmo episódio de tempo seco atinge muitas células;
- estratificação por estação (seca: junho a outubro) e por terço de perda antecedente, só nas células elegíveis.

**Natureza:** descritiva, sobre a associação entre o tempo e o início do fogo; não separa ignição humana de propagação.

**Correção (29/10/2026):** os terços de perda antecedente eram cortados sobre a tabela de eventos, de modo que as células com muitos episódios (as perturbadas) deslocavam os cortes e empurravam células preservadas para o terço do meio. Os cortes passam a ser feitos nas células elegíveis, e cada evento herda o terço da sua célula (`fire_weather.cell_thirds`). Mudaram de terço 47% dos eventos no Xingu e 30% no Tapajós. A leitura principal se mantém e fica mais nítida (na estação seca, percentil perto de 0,59–0,61 nas preservadas e perto de 0,5 nas perturbadas); as intermediárias do Xingu passam a ficar entre as duas.

**Correção e complementos (29/10/2026, F1):** os controles eram tomados no dia do ano, com a janela de ±15 dias dando a volta dentro do mesmo ano civil (um evento de 5 de janeiro tinha controles no fim de dezembro do mesmo ano) e com o dia do ano deslocado em anos bissextos. Passam a ser datas reais: em cada outro ano, a mesma data (29/2 vira 28/2) e ±15 dias corridos, atravessando a virada do ano (`fire_weather.same_dates`, `composite`). A anomalia de temperatura de 30 dias prometida acima passa a ser calculada (`t2m_30d`), e a diferença entre preservadas e perturbadas é testada diretamente (`fire_weather.contrast`, IC por bootstrap dos mesmos anos nos dois grupos; caderno 10, Tabela 2). Os percentis mudam no terceiro decimal. Na estação seca, a diferença preservadas − perturbadas exclui zero nas duas bacias no VPD de 7 e de 30 dias (+0,08 a +0,10), nos dias secos (+0,09) e na chuva do mês (−0,08 a −0,10, CHIRPS e ERA5); na temperatura, nas duas escalas no Tapajós e só na de 7 dias no Xingu. A estação seca do fogo continua de junho a outubro, como fixado; com junho a setembro, as diferenças ficam iguais ou até 0,012 maiores.

## D-026 — O território: Terras Indígenas e Unidades de Conservação como chave de leitura

**Status:** aceito em 23/10/2026 (`features/territory.py`, caderno 11), como ponte com a parte socioespacial.

**Desenho:** a fração de cada célula, dentro da bacia, em Terras Indígenas (FUNAI), em Unidades de Conservação federais (ICMBio) e na união das duas, com os limites atuais das camadas de contexto. A classe da célula é: TI ou UC se a categoria cobre pelo menos metade dela; fora se menos de 10% é protegido; mista nos demais casos. Comparação por classe (medianas) e correlação parcial com a fração protegida (controles: latitude, água e altitude; IC por blocos de 1°) para a perturbação, os focos de fogo, o LST do MODIS e a máxima do ERA5 na estação seca, a entropia da chuva do CHIRPS e, a partir do caderno 10, o percentil do tempo antes do início dos episódios de fogo na estação seca.

**Limites:** os limites são os atuais, e muitas áreas foram criadas ou homologadas durante o período; a localização das áreas protegidas não é aleatória (tendem a estar em áreas mais remotas), então a comparação é uma associação e não mede o efeito da proteção. Rodovias, como a BR-163, não entram por falta de uma camada no projeto.

## D-027 — Extensões complementares da revisão crítica (comparativos)

**Status:** aceito em 29/10/2026, antes de qualquer cálculo; regras fixadas aqui para não serem escolhidas depois de ver os resultados.

**Natureza:** nove análises complementares, não pré-registradas, motivadas pela revisão crítica de 29/10 (quatro sugestões recebidas e cinco recomendações). São **comparativos**: nenhuma recalcula, refaz ou substitui o pré-registro (D-010), o gate congelado (`1c2fb37657`) ou o lote `81333bb007`, que seguem como resultado principal. Cada uma é relatada ao lado do resultado principal correspondente, identificada como complementar.

**Regras comuns:**
- células: as elegíveis do caderno 08 (v2 do pré-registro); "subamostra" é a de D-024 (`sensitivity.subsample`, semente 20261023; 60 células no Xingu e 62 no Tapajós);
- séries: anomalia padronizada (`regional.standardized_anomalies`, normal 1991–2020), sem remover tendência; janela 2001–2024, salvo menção;
- (τ, m, w): pela regra do pré-registro (`suite.embedding_parameters`), salvo quando a própria extensão varia o parâmetro;
- sementes: `batch._seed(spec, célula, variável, janela, <rótulo da extensão>)` para tudo o que é novo; quando a extensão muda só um parâmetro, as substitutas usam a **mesma** semente do lote (`batch._seed(spec, célula, variável, janela)`), para que a diferença venha só do parâmetro, e a variante que coincide com a regra original tem de reproduzir o lote (verificação de código, não resultado);
- p de Monte Carlo como no pré-registro; a fração de células com p ≤ 0,05 (D-013) e a correção de Benjamini–Hochberg dentro da família de cada extensão, por região × variável × janela;
- associação com a perturbação: `gradient.associate` com a perda antecedente (1 − floresta em 2000), controles latitude, água e altitude, IC por bootstrap em blocos de 1°;
- leitura: um comparativo **confirma** o resultado principal quando o sinal é o mesmo e o IC contém a estimativa principal nas mesmas células; caso contrário, **qualifica-o**, e o texto diz em que direção. Um achado que só exista num comparativo é destacado apenas se aparecer nas duas bacias, e é sempre rotulado como exploratório;
- cada extensão grava as suas regras num dicionário `RULES` com hash próprio no nome da pasta de saída, com manifesto e commit (`execucao.json`), como em `nonlinear/precip.py`.

**F2a — Atrasos de imersão e atrasos ordinais.** Subamostra; t2m e VPD; descritores primários; 39 substitutas IAAFT com a semente do lote.
- grade de imersão τ ∈ {1, 2, 3, 5, 7}: em cada τ, m pelos falsos vizinhos nesse atraso (máximo 8, limiar 0,05, Theiler max(10, τ) na busca) e w = max(10, τ·m); afeta RQA·DET e erro de previsão;
- atraso ordinal L ∈ {1, 2, 4, 7} na entropia e na complexidade (ordem 5, isto é, padrões de 4L dias);
- o primeiro mínimo local da AMI (até 60 dias, sem a regra 1/e) é registrado em cada célula; quando existe, entra como mais uma variante de τ ("τ = mínimo da AMI");
- τ = 1 e L = 1 reproduzem o lote;
- leitura: por descritor e parâmetro, a fração de células que rejeitam, a mediana do z, a correlação de postos do z com o lote e a correlação parcial com a perturbação. A associação principal "resiste ao atraso" se, em todos os pontos da grade, o sinal for o mesmo e o IC contiver o valor do lote nas mesmas células. O descritor "se estabiliza" a partir do menor τ (ou L) depois do qual a mediana do z muda menos de 10% entre pontos vizinhos da grade.

**Resultado F2a (29/10/2026):** τ = 1 e L = 1 reproduzem o lote. O primeiro mínimo da AMI fica em 10 a 12 dias na mediana das células; a regra escolhe τ = 1 porque a AMI cai abaixo de 1/e no primeiro dia. Em todos os τ, o DET rejeita em 98–100% das células e o erro de previsão em nenhuma. A associação do DET da temperatura com a perda antecedente resiste no Tapajós (−0,31 no lote; −0,34 a −0,42 na grade) e, no Xingu, mantém o sinal mas enfraquece (−0,54 para −0,20 a −0,39), fora do IC: qualifica. Nos ordinais, L = 2 e 4 derrubam a rejeição do VPD de ~90% para 30–50%, e a associação do par do VPD no Xingu (+0,39/−0,43) cai para cerca de ±0,25 e some em L = 7 (qualifica: a marca está na escala diária); no Tapajós o par do VPD resiste. Caderno 07, Tabelas 3 e 4.

**F2b — Mínima, máxima e amplitude térmica.** Variáveis `t2m_c_min`, `t2m_c_max` e `t2m_c_range` dos `daily_*.nc` (extremos das 24 amostras horárias), cada uma em anomalia padronizada própria.
- todas as células, as três janelas: entropia e complexidade (ordem 5, atraso 1) com 39 IAAFT, no molde de `nonlinear/precip.py`; família exploratória (os dois descritores), BH por região × variável × janela;
- subamostra, janela 2001–2024: RQA·DET e erro de previsão, (τ, m, w) pela regra, 39 IAAFT;
- associação: o modelo pré-registrado do caderno 08 no z, no valor observado e no excesso (observado − média nula, D-022); longitudinal com a perda de 2001–2012 (MapBiomas), como no caderno 08;
- leitura: lado a lado com a temperatura média do lote. Como o ERA5 tem vegetação fixa (D-011), o resultado esperado é nulo; uma associação na máxima ou na amplitude que não exista na média é relatada como indício de que o ciclo diurno carrega um sinal que a média dilui, e só é destacada se aparecer nas duas bacias.

**F2c — Multivariado temperatura + umidade específica.** Série média de cada bacia (como D-016), t2m e `q_gkg_mean` em anomalia padronizada.
- espaço de estados: cada canal com o seu (τ, m) pela regra, na própria série da bacia; o vetor conjunto concatena os dois atrasos;
- alvos: t2m e q, horizonte 1; para cada alvo, quatro previsores: só o próprio canal, só o outro canal, os dois juntos e um VAR linear com os mesmos atrasos; cada um por vizinhos (5 vizinhos, 60% de treino, Theiler w, como `statistics.nonlinear_prediction_error`) e por S-map (regras de F2g);
- estatística: o erro do previsor conjunto e o ganho (erro do melhor previsor de um canal − erro do conjunto);
- nula: 199 substitutas FT multivariadas (Prichard e Theiler, 1994: a mesma fase aleatória somada aos dois canais, que preserva os espectros e o espectro cruzado) e, como segunda nula, 199 IAAFT multivariadas (Schreiber e Schmitz, 2000); p unilateral (erro menor, ganho maior); Holm sobre 2 bacias × 2 alvos, separadamente por nula;
- depois, na subamostra, com 39 substitutas: fração de células com p ≤ 0,05 e associação do ganho com a perturbação;
- leitura: rejeitar a nula multivariada indica estrutura conjunta não linear além da correlação cruzada linear; substitutas independentes por canal não são usadas, porque destruiriam a correlação cruzada e rejeitariam por construção.

*Nota de implementação (29/10/2026, antes de qualquer resultado):* o S-map com validação deixando um de fora em todos os pontos do treino custa cerca de 180 s por série, o que levaria o F2c a dezenas de horas. No F2c, θ passa a ser escolhido deixando um de fora em 1 de cada 4 pontos do treino (com a mesma exclusão de Theiler; a previsão do teste usa a biblioteca inteira), cerca de 60 s por série; e a subamostra usa só a nula IAAFT multivariada (39). Medido na série do Xingu, os erros do teste mudam na quarta casa decimal.

**F2d — Wolf e Kantz ao lado de Rosenstein** (`nonlinear/lyapunov.py`). Mesmo (τ, m, w) da regra.
- Rosenstein: como no pré-registro (passos 0–5);
- Kantz (1994): S(k) = ⟨ln da distância média, após k passos, entre um ponto e os vizinhos dentro do raio ε⟩, para ε nos quantis 1%, 2%, 5% e 10% das distâncias entre pares (fora da janela de Theiler), com no mínimo 5 vizinhos; λ = inclinação em k ∈ [0, 5] no raio de 2%; as curvas dos outros raios são relatadas;
- Wolf et al. (1985): tempo de evolução de 3 passos; substituição quando a distância passa de 10% do diâmetro do atrator reconstruído; candidatos a substituto acima de 0,1% do diâmetro e com ângulo menor que 0,3 rad (relaxado em degraus de 0,3 rad até 1,2 rad se não houver candidato);
- onde: os sete controles do gate (mesmas séries, sementes, comprimentos e ruídos de `gate.tasks`) e as nulas de F2f, com 39 IAAFT; as séries das bacias com 199 IAAFT (D-016); a subamostra com 39;
- leitura: (1) viés contra o λ conhecido nos controles sem ruído (Lorenz ≈ 0,091 por passo com Δt = 0,1; Hénon 0,419; logístico ln 2); (2) se cada estimador separa caos de ruído contra substitutas pelo critério do gate (poder ≥ 0,8 em 2 positivos e falso positivo ≤ 0,2 no ruído branco e no AR(1)) e nas nulas de F2f. A concordância entre os três estimadores **não** é evidência de caos; o Lyapunov continua exploratório.

**F2e — Temperatura de pele do ERA5 contra o MODIS LST.**
- dados: `skt`, `t2m` e `tcc` (cobertura total de nuvens) do Earth Data Hub, às 13, 14 e 15 UTC, de junho a setembro (estação seca de `features/lst.py`), 2001–2024, na grade das duas bacias;
- horário: em cada célula, interpolação linear entre as horas UTC vizinhas para as 10h30 solares locais, isto é, 10,5 − longitude/15 h UTC (de 13,8 a 14,5 UTC nas bacias), o horário nominal de passagem do Terra; o horário de cada composição do MOD11A2 não foi baixado;
- medidas por célula: médias da estação seca de `skt` e de `t2m` às 10h30 em 2001–2024 e em cada metade; e a média de `skt` só nas horas com `tcc` < 0,3 (céu quase limpo, aproximando a amostragem do MODIS);
- associação: a de D-018 (perda antecedente; latitude, água e altitude; blocos de 1°), entre células e ao longo do tempo (perda de 2001–2012 contra a mudança entre as metades), e o contraste em °C entre o décimo mais e o menos perturbado;
- leitura: se a associação com o `skt` às 10h30 ficar perto de zero, como a da máxima do ar, a cegueira do ERA5 se confirma com uma grandeza homogênea ao LST; se ela aparecer, parte do contraste MODIS × ERA5 de D-018 era diferença de grandeza e de horário, e o texto é corrigido nesse ponto.

**F2f — Gate com nulas realistas** (`synthetic.py`, `gate.py`). Relatado ao lado do gate congelado, sem substituí-lo.
- quatro nulas sem caos, simuladas em 1990–2024 com calendário diário, passadas pela mesma anomalia padronizada dos dados e cortadas em 2001–2024 (8.766 dias):
  1. AR(1) com φ por dia do ano e variância sazonal;
  2. AR(1) com φ fixo, variância sazonal e tendência linear;
  3. SETAR de dois regimes (limiar em zero no dia anterior);
  4. AR(1) com inovações GARCH(1,1) (α = 0,1, β = 0,85, ω pela variância incondicional);
- parâmetros: estimados por um procedimento fixo na série média de cada bacia × variável (t2m, VPD) em 1991–2020, o que dá quatro ajustes por nula: φ(dia do ano) é a autocorrelação de passo 1 da anomalia padronizada numa janela circular de 31 dias; a variância sazonal é a da anomalia bruta; a tendência é a inclinação por mínimos quadrados de 2001–2024; o SETAR é ajustado por mínimos quadrados em cada regime;
- 20 repetições por nula × ajuste (80 por nula), sem ruído de observação; os oito descritores pré-registrados com 39 IAAFT e as mesmas regras, mais Wolf, Kantz (F2d), Cao (F2h) e o ganho do S-map (F2g); sementes por `gate._seed` com o nome da nula;
- leitura: a taxa de rejeição de cada descritor em cada nula, com IC de Clopper–Pearson, é a taxa de falso positivo realista. A fração de células que rejeitam no lote (D-013) é lida contra ela, e não contra 5%: se a fração das células não passar do limite superior do IC da nula mais permissiva, a rejeição nas células não se distingue de um processo estocástico sazonal ou não linear.

**F2g — S-map em todas as células** (Sugihara, 1994; numpy, sem pyEDM).
- séries: t2m e VPD, todas as células, janela 2001–2024; (τ, m, w) pela regra;
- θ ∈ {0; 0,25; 0,5; 1; 2; 4; 8}; θ = 0 é um AR(m) linear ajustado localmente com pesos iguais;
- treino nos primeiros 60% e teste nos últimos 40%, como o erro de previsão; θ escolhido só no treino, por validação deixando um de fora com exclusão de Theiler; empate fica com o menor θ; nenhum alvo do teste entra na biblioteca;
- horizontes de 1, 3 e 7 dias; referências também da persistência e da climatologia (anomalia zero);
- índice: ganho G = 1 − RMSE(θ escolhido)/RMSE(θ = 0) no teste; significância pelo teste de Diebold–Mariano unilateral (variância HAC com h − 1 defasagens) e BH sobre as células por região × variável × horizonte;
- calibração: o mesmo índice nos controles do gate e nas nulas de F2f;
- leitura: G > 0 com DM significativo indica não linearidade dependente do estado **sem depender da nula IAAFT**. O G de horizonte 1 entra no `gradient.associate` como descritor exploratório, com os horizontes 3 e 7 ao lado.

**F2h — Cao (1997), E1 e E2.** m de 1 a 10, τ pela regra, vizinho mais próximo fora da janela de Theiler.
- onde: séries das bacias (com 199 IAAFT), controles do gate e nulas de F2f, subamostra (com 39 IAAFT);
- índices: a dimensão de saturação, menor m com E1(m) ≥ 0,9 e |E1(m+1) − E1(m)| < 0,05; e o afastamento D_E2 = max_m |1 − E2(m)|;
- leitura: E2 perto de 1 em todo m é o sinal de processo estocástico; o limiar entre "perto" e "longe" não é fixado a priori, mas lido na distribuição de D_E2 dos controles positivos, das nulas lineares e das nulas de F2f, e nas substitutas de cada série.

**F2i — Chuva: dither em cada substituta e erro espectral do IAAFT.**
- dither repetido: a série original recebe o dither de D-021 com a mesma semente; as substitutas IAAFT são geradas da série **sem** dither e cada uma recebe o seu próprio dither (semente derivada da substituta), de modo que original e nula tenham o mesmo tratamento dos empates. Todas as células, as duas fontes, janela 2001–2024, entropia e complexidade, 39 substitutas com a semente do lote da chuva; comparado ao lote do caderno 09 nas mesmas células (fração que rejeita, z e associação, com os controles de secura de D-023);
- erro espectral: o erro relativo final de cada substituta IAAFT (`IAAFTResult.spectral_error`), na subamostra, para a chuva das duas fontes e para t2m e VPD; resumido por mediana e máximo por célula;
- leitura: se o dither repetido mantiver a rejeição e a associação do caderno 09, o tratamento dos empates não era a origem do resultado; o erro espectral mostra quanto a nula IAAFT da chuva se afasta do espectro observado em comparação com as variáveis contínuas.

**Resultados (30/10/2026):**
- *F2f, gate realista* (`gate/realista_bea8860a92`, 600 séries, sem erros; caderno 05, Figura 5 e Tabela 3): o AR(1) com memória sazonal faz o DET rejeitar em 81% das séries, a LAM em 86% e o par ordinal em 54–59% (90–100% com os ajustes do VPD); o AR-GARCH faz DET, LAM e Kantz rejeitarem em 98–100% e o Rosenstein em 81%; o erro de previsão rejeita em no máximo 16%; o D_E2 de Cao, em no máximo 8% (poder de 100% nos três caóticos, 0% no ruído branco e no AR(1)). Pela regra fixada, lida na primeira versão com o limite das quatro séries juntas, as células se distinguiam da nula mais permissiva no D2, na assimetria, no par ordinal do VPD e no S-map da temperatura. **Essa leitura estava errada** e foi refeita por variável na D-029: o VPD não se distingue das nulas nos ordinais nem na D2, e a temperatura se distingue na assimetria, na D2 e, pontualmente, nos ordinais. Qualifica: a rejeição das substitutas não basta para falar em dinâmica determinística.
- *F2d, Wolf e Kantz*: recuperam o λ do Hénon e do logístico; o Kantz rejeita nas nulas quase como o Rosenstein, e o Wolf fica abaixo das substitutas nos dados. Não acrescentam evidência (caderno 06, Tabela 3; caderno 07, Tabela 5).
- *F2h, Cao*: nas células, D_E2 mediano ≈ 0,02, igual ao das substitutas e das nulas (percentil 95 de 0,03), contra 0,08–0,32 nos caóticos; saturação em m = 8–9. Nas bacias, o VPD fica um pouco acima das substitutas (p = 0,04 e 0,005). Confirma a leitura de processo estocástico com não linearidade fraca. Exploratório: o z do D_E2 do VPD se associa negativamente à perda antecedente nas duas bacias (−0,33 e −0,36).
- *F2g, S-map*: nas nulas, o DM rejeita em até 49% (SETAR), mas o ganho fica abaixo de 0,3% no percentil 99; nos caóticos, 37–57%. Nas células, o DM (1 dia) rejeita em 69–86% na temperatura e 42–69% no VPD, com ganho mediano de 0,2–0,6%. Exploratório, nas duas bacias: o ganho na temperatura (1 dia) cresce com a perda antecedente (+0,29 e +0,24), e o do VPD a 3 e 7 dias também (caderno 08, Tabela 6).
- *F2b, extremas*: a máxima repete a média (associação ordinal só no Xingu); a mínima tem pouca estrutura e nenhuma associação; o DET da amplitude se associa à perda (−0,38 e −0,44, subamostra) como o da média. Confirma; nenhum sinal exclusivo do ciclo diurno (caderno 08, Tabela 6).
- *F2c, T + q (bacias)*: o erro conjunto é maior nos dados que nas substitutas; o ganho de juntar as duas no S-map é de 0,2–1% e, com Holm, só se sustenta no Tapajós contra a FT multivariada. Um VAR quase empata com o S-map conjunto (caderno 06, Tabela 4). *F2c, T + q (subamostra; 60 células no Xingu, 62 no Tapajós; 39 IAAFT multivariadas)*: o erro conjunto nunca fica abaixo do das substitutas. O ganho do S-map conjunto passa de p ≤ 0,05 em 13% (Xingu) e 23% (Tapajós) das células para a temperatura, nenhuma depois de BH; para a umidade específica, em 73% e 50%, e BH mantém 57% no Xingu e nenhuma no Tapajós (ganho mediano de 0,6% e 1,2% do erro). O ganho não se associa à perda antecedente em nenhuma bacia (caderno 08, Tabela 6). Leitura: um pouco de estrutura conjunta não linear na umidade, mais clara no Xingu, sem relação com a perturbação.
- *F2i, dither da chuva*: observado idêntico ao lote; rejeição de 100% mantida; z um pouco maior; associação com a perda no mesmo lugar. O erro espectral do IAAFT é de cerca de 2% na chuva, contra 0,04% em t2m e VPD (caderno 09).

**Custos previstos:** F2e é só download (minutos a poucas horas no HPC); F2a, F2b e F2i, de 1 a 4 h no HPC cada; F2f com F2d e F2h, algumas horas no HPC; F2g, menos de 1 h por bacia; F2c, minutos nas bacias e cerca de 1 h na subamostra.

## D-028 — Gradiente: multiplicidade, inferência espacial e exposição-placebo

**Status:** fixado em 29/10/2026, antes do cálculo (F1 da revisão crítica). Complementa a Tabela 1 do caderno 08 sem mudar as estimativas: ρ parcial, IC por blocos e Moran dos resíduos continuam os mesmos.

**Multiplicidade.** A família confirmatória são os 16 testes pré-registrados (2 bacias × 2 variáveis × 4 descritores primários, perda antecedente, controles latitude, água e altitude). O p-valor de cada um vem do mesmo bootstrap em blocos de 1° que dá o IC (999 reamostras, semente 20261021): p = 2 · (min(#{ρ* ≤ 0}, #{ρ* ≥ 0}) + 1) / (999 + 1), limitado a 1, o teste que corresponde ao IC percentil. Sobre os 16, Holm (controle do erro da família) e Benjamini–Hochberg. Todo o resto do caderno 08 (outras exposições, modelos de sensibilidade, longitudinal, MODIS) é rotulado como exploratório.

**Inferência espacial** (`gradient.spatial_inference`), nos resíduos dos postos usados na correlação parcial:
- I de Moran com teste de permutação dos resíduos entre células (999 permutações, semente 20261029), com a vizinhança atual (4 ortogonais);
- correlograma: I de Moran em classes de distância de 0,25° até 5° (largura 0,25°), para mostrar o alcance da autocorrelação diante do bloco de 1°;
- n efetivo de Clifford, Richardson e Hémon (1989), a aproximação usual do teste de Dutilleul (1993): σ²(r) = Σ_k n_k ρ_x(k) ρ_y(k) / n², com classes de 0,5° até a maior distância e o termo de distância zero (n_0 = n, ρ = 1); n' = 1 + 1/σ², e p bilateral por t = r √((n' − 2)/(1 − r²)) com n' − 2 graus de liberdade (desde a D-030, n' − 5, descontando os três controles). Holm sobre os 16 também nesse p.

**Bootstrap × permutação em blocos.** O pré-registro (`disturbance.inference.spatial_blocks_degrees`) fala em "permutação por blocos de 1° × 1°". O caderno 08 usa, desde o primeiro cálculo, o bootstrap em blocos de 1°, que dá o intervalo de confiança da correlação parcial e não só um p. Fica registrado como a implementação da inferência por blocos; o p desta decisão vem do mesmo bootstrap.

**Exposição-placebo.** A perda de 2013 a 2024 não pode ter causado a dinâmica de 2001 a 2012. Se ela se associar aos descritores dessa década tanto quanto a perda antecedente, a associação reflete a geografia de onde o desmatamento avança, e não um efeito.
- células: elegíveis com floresta ≥ 50% da área terrestre em 2000;
- exposição: `mb_perda_floresta_2013_2024` (MapBiomas); resposta: z dos 4 descritores primários na janela 2001–2012; controles e inferência da Tabela 1;
- referência: a perda antecedente contra o mesmo z, nas mesmas células;
- leitura: placebo perto de zero onde a principal aparece reforça que a associação não é só seleção geográfica; placebo do mesmo tamanho e sinal a enfraquece. Exploratório.

**Resultado (29/10/2026):** com Holm sobre os 16, 9 ficam abaixo de 0,05: o par ordinal do VPD e o DET da temperatura nas duas bacias, e no Xingu também o DET e a previsão do VPD e a previsão da temperatura. O Moran dos resíduos (0,39–0,76) tem p = 0,001 por permutação em todos. O correlograma dos resíduos se anula perto de 1° (Tapajós) e 2° (Xingu) na exposição e de 2 a 2,5° nos descritores. O n efetivo cai para 22–55 células no Xingu e 94–213 no Tapajós; com ele, 7 dos 16 ficam abaixo de 0,05 (os pares que se repetem nas duas bacias e a previsão do VPD no Xingu), e com Holm por cima só o DET da temperatura no Tapajós (0,017). Placebo: no Xingu, nada (|ρ| ≤ 0,11), enquanto a perda antecedente nas mesmas 593 células dá +0,47 e −0,46 no par ordinal do VPD e −0,25 e −0,30 no DET; no Tapajós (500 células), o placebo aparece nos padrões ordinais e na previsão da temperatura (+0,17, −0,18, −0,27), onde a exposição principal é nula, e fica perto de zero no VPD e no DET da temperatura. Leitura: a conclusão fica mais modesta, não muda de sinal; caderno 08, Tabela 1 (colunas novas), Figura 8 e Tabela 5.

## D-029 — Emenda: a regra das nulas realistas por variável, com margem

**Status:** emenda de 30/10/2026, depois dos resultados da D-027 (reanálise de `ANALISE4.md`, bloco G1). Não muda o pré-registro, o gate congelado nem o lote; muda a leitura da Tabela 5 do caderno 07 e do resultado F2f.

**O erro.** A regra da D-027 comparava a fração de células que rejeitam com o limite superior do IC 95% da nula realista mais permissiva, mas não dizia como combinar os quatro ajustes (2 bacias × 2 variáveis). A primeira implementação (`realistic.null_rates`) juntou as 80 séries de cada nula. O limite da temperatura passou a refletir as nulas ajustadas ao VPD, cuja memória sazonal faz os ordinais e a D2 rejeitarem em 92–98% das séries, e vice-versa. A comparação deixava de ser com o clima estocástico da própria variável.

**A regra emendada** (`realistic.null_rates(by=("variable",))`, `permissive`, `compare` e `cell_comparison`):
- limite por variável: as 40 séries de cada nula ajustadas à variável (duas bacias); como sensibilidade, só as 20 da própria bacia;
- saturação: se o limite da nula mais permissiva passa de 95%, a leitura é "indistinguível", porque a nula já rejeita quase sempre;
- margem: a leitura é "acima" quando o limite inferior do IC 95% de Clopper–Pearson da fração das células, calculado com o n efetivo da fração, passa do limite da nula; "dentro", no caso contrário. O n efetivo da fração (`gradient.effective_n_mean`) é n² / Σᵢⱼ ρ(dᵢⱼ), com ρ a autocorrelação espacial do campo de z das células (do ganho, no S-map) por classe de 0,5°, somada até a primeira classe não positiva;
- a comparação pontual (fração acima do limite, sem margem) é relatada ao lado, porque a margem foi definida depois de ver os números agregados.

**Resultado (30/10/2026):**
- *temperatura*: a assimetria temporal (100% das células contra limites de 46,5%) e a D2 (100% contra 63,9%) ficam acima com a margem nas duas bacias. Os padrões ordinais ficam acima pontualmente (74% e 52% na entropia, contra 35,6%), mas não com a margem, porque o campo do z é muito liso (n efetivo de 3 a 4). O S-map fica acima só pontualmente nas duas bacias (69% e 86% contra 56,7%);
- *VPD*: os ordinais, a D2, o DET, a LAM e os Lyapunov de Rosenstein e Kantz ficam indistinguíveis, porque a nula de memória sazonal (ou o GARCH) já rejeita em mais de 95%. A assimetria fica acima só pontualmente. O S-map fica dentro;
- *as duas*: DET e LAM indistinguíveis; Cao e previsão dentro; Wolf dentro, salvo a temperatura do Xingu, que passa do limite por 2 pontos, sem margem;
- leitura: a temperatura tem uma não linearidade fraca que nenhuma das quatro nulas reproduz, sobretudo na assimetria e na D2; no VPD, o que parecia estrutura é, em boa parte, memória sazonal. Caderno 07, Tabela 5. As nulas ajustadas em cada célula da subamostra (D-030, G2b) testam essa leitura com nulas do tamanho certo.

## D-030 — Reanálise de 30/10: sazonalidade, inferência espacial e auditoria dos comparativos

**Status:** fixado em 30/10/2026, antes dos cálculos de cada item (bloco G do plano, a partir de `ANALISE4.md`). Comparativos, como na D-027: nada aqui refaz o pré-registro, o gate congelado ou o lote.

**G2a — memória sazonal como explicação alternativa** (`features/seasonality.py`, `amazon-chaos era5 seasonality`). Por célula e variável, na normal 1991–2020, com o procedimento de `synthetic.fit_realistic`: média e amplitude de φ(dia do ano), razão entre o maior e o menor desvio sazonal e fração da variância explicada pelo ciclo médio. As quatro entram, junto com latitude, água e altitude, como controles da correlação parcial dos 16 testes. Leitura: se a associação some, a "marca" da perturbação nos descritores é a geografia da sazonalidade. Ressalva fixada antes: a sazonalidade pode ser mediadora (a conversão alongando a estação seca), e então controlar por ela remove parte do efeito; o resultado não separa as duas leituras.

**G2b — nulas ajustadas nas células** (`nonlinear/realistic_cells.py`, `amazon-chaos gate cells`). As quatro nulas ajustadas na série bruta de cada célula da subamostra de D-024 (60 por bacia), com o GARCH por máxima verossimilhança (`synthetic.fit_garch`, alvo de variância) no lugar de α = 0,10 e β = 0,85; uma realização por célula × variável × nula; oito descritores com 39 IAAFT e o S-map. Os limites por variável, das células das duas bacias, substituem os da série da bacia na regra da D-029 como sensibilidade.

**G4 — inferência espacial.** (i) Bootstrap em blocos de 2° e 2,5°, além de 1°, nos 16 testes (`gradient.block_sensitivity`), porque o correlograma vai a 2–2,5°; (ii) graus de liberdade de Clifford n' − 2 − k, com k = 3 controles; (iii) placebo com a perda antecedente como controle, e a principal com o placebo como controle.

**G5 — auditoria dos comparativos.**
- IAAFT multivariada: diagnóstico do erro espectral por canal e da razão entre as correlações cruzadas (atrasos −30 a 30) das substitutas e dos dados (`multivariate.cross_diagnostics`); a subamostra do F2c lida também contra 39 FT multivariadas, que preservam o espectro cruzado exatamente (`amazon-chaos descriptors multivariate-ft`);
- Kantz nos raios dos quantis de 1%, 2%, 5% e 10%, com o número de pontos com 5 vizinhos (`lyapunov.kantz_profile`), e Wolf com o número de substituições, as falhas e o ângulo médio (`estimator_checks.py`, `amazon-chaos descriptors checks`), nas séries das bacias (199 IAAFT) e na subamostra (39);
- fogo: o contraste preservadas − perturbadas também com bootstrap cruzado de anos e blocos de 1° (`fire_weather.contrast(blocks=...)`);
- S-map: o DM com HAC de h − 1 não foi refeito. A simulação da `ANALISE4.md` (AR-GARCH e SETAR) deu razão Newey–West/simples entre 0,73 e 1,21, e o ponto que importa é outro: o ganho é minúsculo. Convenção registrada: o θ daqui multiplica a distância média uma vez nos pesos, que entram em XᵀWX; equivale a 2θ do pyEDM.

**G6 — chuva: ocorrência × intensidade** (`nonlinear/precip_split.py`, `amazon-chaos descriptors rain-split`). Por célula e fonte, 2001–2024, dia chuvoso ≥ 1 mm: entropia das palavras binárias de 5 dias e fração de dias chuvosos (descritivas); entropia e complexidade ordinais da série inteira contra 39 nulas que mantêm a ocorrência e permutam as quantidades entre os dias chuvosos; as mesmas medidas só nos dias chuvosos contra 39 permutações. Leitura: se o z contra a nula de ocorrência se associa à perda e a ocorrência não, a mudança é na organização das intensidades, e não no número de dias secos.

**Resultados (30/10/2026):**
- *G2a*: a amplitude de φ cai com a perda antecedente (ρ de −0,65 a −0,77) e se correlaciona com o z ordinal em ±0,85 a ±0,91. Com as quatro medidas como controle, o par ordinal some no Tapajós (−0,02/+0,02) e na temperatura do Xingu; no VPD do Xingu cai para +0,22 [0,00; 0,39] e −0,20 [−0,38; +0,02]. Resistem o DET da temperatura (−0,28 no Xingu, −0,15 no Tapajós), o DET do VPD (−0,22) e a previsão do VPD (−0,26) no Xingu. Leitura: a associação ordinal é, em grande parte, a geografia da memória sazonal; a do DET da temperatura não (caderno 08, Tabela 7).
- *G4*: com Holm, 9 dos 16 resistem com blocos de 1°, 5 com blocos de 2° e de 2,5° (o DET da temperatura nas duas bacias e o par ordinal e a previsão do VPD no Xingu); com o n efetivo e n' − 5 graus de liberdade, 7 de 16 ficam abaixo de 0,05 e, com Holm, só o DET da temperatura no Tapajós (0,020). No placebo com controle mútuo, a perda antecedente mantém o par ordinal do VPD (+0,49/−0,49 no Xingu; +0,21/−0,20 no Tapajós) e o DET (−0,28 e −0,11); o placebo segue nulo no Xingu (salvo o par ordinal do VPD, com sinal oposto, ±0,18) e presente nos ordinais e na previsão da temperatura do Tapajós (caderno 08, Tabelas 1 e 5).
- *G5, fogo*: o contraste da estação seca mantém o sinal e a exclusão do zero em todas as medidas com o bootstrap de anos × blocos (caderno 10, Tabela 2).
- *G6*: no ERA5, a ordem das intensidades tem estrutura além da ocorrência em todas as células (z ≈ −11 e −9), e nos dias chuvosos em 95–97%; no CHIRPS, em cerca de um terço das células (z ≈ −1) e quase nada nos dias chuvosos (16–19%). No CHIRPS, o excesso de organização das intensidades se associa à perda antecedente nas duas bacias (−0,40 [−0,50; −0,25] e −0,19 [−0,38; −0,01]), e a ocorrência não; no ERA5, é o contrário: menos dias chuvosos nas células mais perturbadas (−0,32 e −0,25) e nada na intensidade. Leitura: a associação da chuva do CHIRPS (D-021) vem da organização das intensidades, e não de haver mais dias secos (caderno 09, Tabela 5).
- *G5, Kantz nos quatro raios* (`estimadores_checagem/`, jobs 22573 e 22574): a rejeição depende do raio. Na temperatura, 97–100% das células da subamostra rejeitam com os raios de 1% a 5% e 63–78% com 10%; no VPD, 55–72% com os raios pequenos e 19–72% com 10%. Nas séries das bacias, o z cai de 3,6–6,2 (1%) para −1,5–2,5 (10%), e o VPD do Tapajós deixa de rejeitar a partir de 5%. O número de pontos com 5 vizinhos fica acima de 7.300 em todos os raios, um pouco menor nos dados que nas substitutas. Leitura: o Kantz rejeita mais onde o raio é pequeno e o ruído domina, como nas nulas com GARCH; não acrescenta evidência de divergência determinística.
- *G5, Wolf*: substituições quase sempre encontradas (0,1–0,3% sem candidato; ângulo médio de 0,24–0,26 rad), mas a implementação encerra a trajetória quando o vizinho chega ao fim da série: na série da bacia do Xingu, o λ usa 5.202 dos 8.760 passos na temperatura e 1.758 no VPD (Tapajós: 8.760 e 5.175). O defeito não foi corrigido nem recalculado, porque o Wolf não sustenta nenhuma leitura do trabalho; ele fica registrado como limitação e reforça que o Wolf das Tabelas 3 do caderno 06 e 5 do 07 não deve ser lido como estimativa do expoente.
- *G2b (nulas ajustadas por célula)*: as quatro nulas ajustadas a cada célula da subamostra de D-024 (uma simulação por célula, 39 IAAFT por série; jobs 22571 e 22572) entram como sensibilidade da Tabela 5 do caderno 07 (`realistic.cell_comparison(..., rates=realistic_cells.null_rates(...))`). A assimetria e o D2 da temperatura continuam acima com folga nas duas bacias. Os padrões ordinais da temperatura: a nula de memória sazonal por célula rejeita em ~48% das séries (contra ~20% ajustada à bacia), e o Tapajós (52%) cai para dentro do limite; o Xingu (74%) segue só pontual. No VPD a nula deixa de saturar, mas os ordinais ficam dentro e o D2 só pontual. O S-map da temperatura no Tapajós passa a ter folga. Ressalva: 39 substitutas contra 99 nas células, o que baixa um pouco o limite.
- *G5 (FT multivariada)*: diagnóstico em 5 substitutas por célula (jobs 22575 e 22576): erro espectral < 0,1% nas duas nulas e razão média da correlação cruzada (atrasos ±30 dias, |r| > 0,1) de 0,999 (IAAFT) e 0,999 (FT) — a IAAFT multivariada não enfraquece a dependência T–q nestas séries, e a dúvida do F2f fica respondida. Subamostra contra 39 FT: ganho do S-map conjunto com p ≤ 0,05 na umidade em 72% (Xingu) e 57% (Tapajós) das células, contra 73% e 50% com a IAAFT; na temperatura 23% e 32%, contra 13% e 23%, nenhuma depois de BH. Com o piso de p = 0,025, o BH na umidade fica na fronteira (FT 65% e 52%; IAAFT 57% e 0%). Leitura inalterada (caderno 06).


## D-031 — A floresta como variável dinâmica: vegetação, sistema conjunto e fogo (bloco H)

**Status:** fixado em 30/10/2026, antes de qualquer download ou cálculo (proposta metodológica do usuário, revisada). Extensão complementar, como D-027 e D-030: não muda o pré-registro, o gate congelado nem o lote. Motivação: até aqui a floresta entrou só como atributo das células (perda, fogo, mapa de vegetação); o título fala do sistema floresta–atmosfera.

**Dados (NASA AppEEARS, 2001–2024).**
- MOD15A2H.061 (8 dias, 500 m): `Lai_500m`, `FparLai_QC`;
- MOD09A1.061 (8 dias, 500 m): `sur_refl_b02` (NIR), `sur_refl_b06` (SWIR), `sur_refl_state_500m`, `sur_refl_qc_500m`, `sur_refl_vzen`, `sur_refl_day_of_year`; NDMI = (b02 − b06)/(b02 + b06);
- MCD64A1.061 (mensal, 500 m): `Burn_Date` (dia do ano da queima), `QA`;
- máscara de floresta: MapBiomas Cobertura (coleção 11, 30 m, classes 3 e 6), lida dos COGs públicos e resumida como fração de floresta em cada pixel de 500 m.

**Filtros de qualidade.**
- LAI: `FparLai_QC` com nuvem ausente (bits 3–4 = 00) e algoritmo principal (bits 5–7 ∈ {0, 1}); o algoritmo de reserva, usado sob nuvem, é descartado;
- NDMI: `state` sem nuvem (bits 0–1 = 00), sem sombra (bit 2 = 0), aerossol não alto (bits 6–7 ≠ 11), sem nuvem interna (bit 10 = 0); `qc_500m` com qualidade ideal nas bandas 2 e 6; ângulo de visada ≤ 35°, para reduzir o artefato de geometria sol–sensor (Morton et al., 2014);
- MCD64A1: `Burn_Date` entre 1 e 366 e `QA` com bit 0 = 1 (dado válido).

**Etapa 1 — dinâmica da vegetação isolada.**
- células: a subamostra de D-024 (60 por bacia);
- pixels: floresta persistente (fração MapBiomas ≥ 0,9 em 2000 e em 2024) e nunca queimada no MCD64A1; média dos pixels válidos em cada composição, com mínimo de 20% dos pixels da máscara; o dia de cada composição é a mediana do dia de observação do MOD09A1;
- anomalia padronizada por composição do ano (46 por ano), climatologia 2001–2024;
- lacunas: interpolação linear em sequências de até 2 composições; mais longas, preenchidas com a climatologia (anomalia 0); células com mais de 20% de composições originalmente vazias são excluídas. As substitutas recebem o mesmo tratamento nas mesmas posições;
- parâmetros: a regra do pré-registro (AMI e FNN) nas séries de 8 dias; padrões ordinais de ordem 4 (24 padrões para cerca de 1.100 pontos);
- descritores principais: D_E2 de Cao, ganho do S-map (Diebold–Mariano), entropia e complexidade ordinais, assimetria temporal, erro de previsão; exploratórios: DET, LAM, D2, Lyapunov de Rosenstein e de Kantz;
- nula: 99 substitutas IAAFT por célula e variável;
- portão novo, antes dos dados: os controles do gate (caóticos e lineares) e as quatro nulas realistas, estas ajustadas às séries de vegetação, com cerca de 1.100 pontos a 8 dias; leitura pela regra da D-029.

**Etapa 2 — dinâmica conjunta.**
- mesmas células e pixels; a atmosfera alinhada ao dia de observação de cada composição: VPD e temperatura do ERA5, média dos 8 dias que terminam nesse dia; chuva do CHIRPS acumulada em 32 e 96 dias; todas em anomalia padronizada por composição do ano;
- previsão de V(t+1) (V = LAI ou NDMI) por três conjuntos de preditores: só V (atrasos pela regra), só a atmosfera (H32, H96, D e os seus atrasos) e o conjunto; cada um por modelo linear, vizinhos e S-map (regras de F2g); treino nos primeiros 60%, teste no restante; RMSE, ganho do conjunto sobre V isolada e teste de Diebold–Mariano;
- convergent cross mapping (Sugihara et al., 2012): V mapeando D, H32 e H96 (a atmosfera forçando a vegetação) e o inverso, com a dimensão de V pela regra; o forçante é mapeado com defasagem de 0, −1 ou −2 composições, a de maior ρ (Ye et al., 2015), escolhida do mesmo modo em cada substituta (acrescentado em 30/10, antes dos dados, depois de o teste sintético mostrar que um forçante defasado não aparece no mapeamento simultâneo); habilidade ρ em bibliotecas de 10% a 100% da série; convergência = ρ(100%) − ρ(10%) > 0; significância contra 99 substitutas sazonais do forçante (Deyle et al., 2016: ciclo anual mantido, anomalias sorteadas em blocos de um ano);
- dependência do estado: no S-map conjunto, a correlação entre o coeficiente ∂V/∂H (ou ∂V/∂D) e o próprio V;
- substitutas multivariadas (FT e IAAFT, como F2c) para o ganho do conjunto;
- relação com a perturbação (exploratória): as medidas de acoplamento contra a perda antecedente, com os controles e a inferência do caderno 08 (blocos e n efetivo).

**Etapa 3 — fogo.**
- episódios: pixel de floresta (fração MapBiomas ≥ 0,9 no ano anterior) com primeira queima no MCD64A1 depois de ao menos 2 anos sem queima (episódios de 2003 a 2022); excluídos os que perdem floresta (fração < 0,9) até 2 anos depois do fogo, que mediriam desmatamento, e os que queimam de novo nesse intervalo (relatados à parte);
- controles: 3 por episódio, pixels de floresta persistente nunca queimados na mesma célula ERA5, pareados pelo vizinho mais próximo na média e na amplitude sazonal de LAI e NDMI nos 2 anos anteriores;
- amostra: até 300 episódios por bacia, sorteio estratificado por ano com semente 20261031;
- alteração e recuperação: Δ(k) = [Vq(k) − Vq(pré)] − [Vc(k) − Vc(pré)], com pré = média das 46 composições anteriores e k de −46 a +138 composições (um ano antes, três depois); a composição da queima é excluída; IC 95% por bootstrap de episódios agrupados por célula ERA5; recuperação = primeiro k a partir do qual o IC inclui zero por 6 composições seguidas;
- mudança na resposta: V(t+1) = a·V(t) + b·H(t) + c·D(t) com interações com queimado × depois, efeitos fixos de pixel e erro agrupado por célula ERA5; e o erro do S-map treinado antes do fogo, aplicado depois, em queimados e controles;
- confirmação: as cicatrizes do MapBiomas Fogo, quando disponíveis, nos episódios sorteados.

**Emenda de 30/10/2026, antes dos dados.** Na etapa 3, a floresta de cada ano em cada pixel vem do MCD12Q1.061 (`LC_Type1` = 2, floresta perene, IGBP), pedido pelo AppEEARS na mesma grade de 500 m: ler o MapBiomas de 30 m ano a ano na bacia inteira seria caro, e os COGs públicos passaram a responder com erro 403 nesse dia. O MapBiomas fica como confirmação nos episódios sorteados. Nas etapas 1 e 2, a máscara continua sendo a do MapBiomas (2000 e 2024); se os COGs seguirem inacessíveis, o MCD12Q1 (primeiro e último ano) a substitui, e a troca é registrada no resultado. Os controles da etapa 3 são sorteados (10 candidatos por episódio, na mesma célula ERA5) antes de qualquer vegetação; o pareamento escolhe 3 deles pelos 2 anos anteriores.

**Emenda de 31/10/2026, pela disponibilidade, antes de qualquer resultado das etapas 1 e 2.** A primeira execução no Tapajós tinha um defeito: as composições vazias nas duas variáveis sumiam da série em vez de virar lacuna (corrigido em `vegetation_dynamics.full_grid`, com teste), e os resultados foram descartados sem leitura; o Xingu foi cancelado. Com as lacunas contadas corretamente, a regra original excluiria quase tudo: com 20% dos pixels válidos por composição, a mediana das lacunas nas células é de 29% no LAI e 44% no NDMI, e nenhuma célula de NDMI fica abaixo de 20%. Num diagnóstico de 1.500 pixels do Tapajós, o critério de nuvem do MOD09A1 deixa passar ~30% dos pixels em janeiro–março e ~94% em julho–agosto; o ângulo de visada ≤ 35° tira mais ~16%, e afrouxá-lo para 50° recuperaria pouco, com ruído de geometria de visada, e por isso o filtro de qualidade não muda. Mudam duas regras: (i) a cobertura mínima por composição cai de 20% para 5% dos pixels da máscara (~100 pixels numa célula típica); (ii) entram na análise as células com até 35% de lacunas, e a leitura principal fica nas células com até 20% (a regra original), com as demais como sensibilidade. A coluna `lacunas` de cada linha do resultado permite a separação. As séries são remontadas com a média sempre que há pixel válido, e a cobertura é aplicada na análise (`vegetation.with_coverage`). Hash da execução: versão 2 das regras.

**Resultado do portão de 8 dias (31/10, `gate/vegetacao_cb50fc216c`, 1.104 pontos, 99 IAAFT).** Os padrões ordinais, a previsão não linear e o $D_{E2}$ de Cao rejeitam em quase todas as séries caóticas (Hénon, logístico, Lorenz) e em no máximo 8% das estocásticas (AR(1), ruído branco, senoide com ruído, sazonalidade com tendência). O Kantz, o Lyapunov e o DET rejeitam também em 60% a 100% das séries com sazonalidade e tendência, e não servem como evidência na vegetação; a assimetria não vê o Lorenz; o D2 tem poder de 55% a 65%. O S-map tem ganho mediano de 25% a 35% no Hénon e no Lorenz e nulo nos estocásticos. A etapa 1 lê, portanto, os padrões ordinais, a previsão e o Cao.

**Resultado das etapas 1 e 2 (31/10, `vegetacao/8cbbd4c044`, regras v2, máscara MCD12Q1).** Células analisadas: LAI 56 (Xingu) e 62 (Tapajós), das quais 43 e 59 com até 20% de lacunas (leitura principal); NDMI 29 e 39, quase todas entre 20% e 35% de lacunas (só sensibilidade; uma célula principal). *Etapa 1:* nos descritores que o portão valida (padrões ordinais, previsão, Cao, S-map), a rejeição das 99 IAAFT fica no nível do acaso ou abaixo (0% a 9%) no LAI; no NDMI (só sensibilidade), os padrões ordinais e a previsão também, mas a assimetria rejeita em 18% das células do Tapajós (7 de 39; binomial p = 0,003) e 14% das do Xingu, e Cao e S-map em 13% no Tapajós, sem relação com a fração de lacunas; a leitura mais simples é a contaminação residual por nuvem e aerossol, que só baixa o índice (quedas rápidas, voltas lentas), e não estrutura dinâmica (correção de 02/11, ao montar o caderno 12). A entropia de permutação dos dados é ligeiramente maior que a das substitutas (z mediano +1,3 no LAI, também nas células com menos de 12% de lacunas; +3,2 no NDMI): a anomalia de 8 dias é mais irregular que o processo linear de mesmo espectro, o que indica ruído de recuperação, não determinismo. As rejeições do Kantz e do Lyapunov no NDMI (79% a 97%) acompanham a fração de lacunas (ρ ≈ −0,4 a −0,6) e são descritores que o portão desqualifica. As nulas realistas para a vegetação (H1) ficam dispensadas: os dados não rejeitam nem as substitutas lineares. *Etapa 2:* a anomalia do LAI é praticamente imprevisível um passo à frente (RMSE relativo de 0,96 a 1,06); a do NDMI um pouco (0,77 a 0,87). Juntar VPD e chuva piora a previsão fora da amostra (ganho mediano de −0,01 com S-map e linear) e a atmosfera sozinha é pior que a persistência. O CCM do VPD sobre a vegetação passa as substitutas sazonais em 52% (Tapajós) e 72% (Xingu) das células de LAI e em 56% a 68% das de NDMI, mas com ρ mediano de 0,08 a 0,11 (nula ≈ 0,02); o da chuva, em 9% a 35%; o sentido inverso também aparece (27% a 47% no VPD). Como a previsão não melhora, o acoplamento é um sinal comum fraco, e parte dele pode vir de contaminação residual da recuperação pela atmosfera (nuvem fina, aerossol da estação seca), que o filtro não elimina e que também correlaciona VPD e LAI. A dependência do estado é nula (|ρ| ≤ 0,03 nas células principais). Nenhuma medida (CCM, ganho conjunto, z de ordinais, previsão e Cao) se associa à perda antecedente: 24 de 24 intervalos por blocos de 1° incluem zero.

**Emenda da etapa 3 (02/11, regra do fogo v2).** Os pedidos de pontos ao AppEEARS (14 tarefas, uma por grupo de anos de queima) ficaram mais de 40 h em fila ou processamento sem terminar. Decidido só pela disponibilidade, antes de qualquer resultado da etapa 3: a leitura do TCC usa episódios e controles sorteados apenas nas células da subamostra das etapas 1 e 2 (60 no Xingu, 62 no Tapajós), com as mesmas regras de episódio, pareamento, Δ(k) e painel, e a vegetação de cada ponto lida nos cubos de área do MOD15A2H e do MOD09A1 já baixados (`vegetation episodes --local`, `vegetation fire --local`; saída em `vegetacao/fogo_subamostra/`). As três etapas passam a ter a mesma moldura amostral; o custo é um número menor de grupos no bootstrap (as células ERA5 da subamostra). A versão na bacia inteira continua esperando a fila e, se terminar a tempo, entra como complemento.

**Resultado da etapa 3 na subamostra (02/11, `vegetacao/fogo_subamostra`, regra do fogo v2).** Pareados 284 de 285 episódios no Xingu e 282 de 285 no Tapajós, em 38 e 39 células ERA5 (os grupos do bootstrap); as queimas caem quase todas entre julho e outubro. *Δ(k):* nas seis composições depois da queima, o LAI cai 1,31 (Xingu) e 1,17 (Tapajós) e o NDMI 0,13, com o IC excluindo zero em todas; entre 2 e 6 meses a queda é de 0,70 e 0,37 no LAI; de 6 a 12 meses, 0,29 e 0,26; de 1 a 3 anos fica um resíduo de 0,15 a 0,20 no LAI e de cerca de 0,02 no NDMI, com o IC excluindo zero em 30% a 57% das composições. O critério automático de recuperação (IC cobrindo zero por seis composições seguidas) dá k = 67 e 55 no LAI e 59 e 58 no NDMI (cerca de 1,2 a 1,5 ano), mas o resíduo volta a ficar negativo depois: a leitura é de recuperação parcial, não completa, em três anos. No período de referência, o IC exclui zero em 20% a 52% das composições, com médias de no máximo 0,035 no LAI e 0,004 no NDMI, uma ordem de grandeza abaixo do efeito. *Painel:* depois da queima, a floresta queimada fica abaixo dos controles (−0,17 a −0,24 desvios da anomalia), mais persistente (+0,23 e +0,14 no LAI; +0,15 e +0,13 no NDMI; p < 0,001) e mais sensível à chuva acumulada de 96 dias (+0,05 no Tapajós, p ≤ 0,001; +0,03 no Xingu, p 0,05 e 0,10) e ao VPD (−0,05 no Xingu, p ≤ 0,001; −0,01 a −0,02 no Tapajós, p 0,08 e 0,18). Os sinais concordam nas duas bacias. Parte do ganho de persistência pode ser a própria recuperação lenta, que deixa a anomalia correlacionada no tempo; o painel não separa as duas coisas.

**Leitura.** Rejeitar substitutas na vegetação não demonstra caos (D-027, D-029). Previsibilidade maior com a atmosfera e CCM significativo indicam acoplamento dinâmico, não caos; mudança na resposta depois do fogo indica alteração do acoplamento, não causalidade da perturbação sobre o clima.

## D-032 — Escalas de tempo e estado compacto do acoplamento floresta–atmosfera (ampliação da etapa 2 da D-031)

**Status:** fixado em 07/11/2026, antes de qualquer resultado real (proposta do usuário, "Ampliação da investigação do acoplamento floresta-atmosfera", com os ajustes de método abaixo). Comparativo, como D-027 a D-031: não muda o pré-registro, o gate congelado, o lote nem as etapas da D-031. Código em `nonlinear/vegetation_scales.py` (`amazon-chaos vegetation scales`), testes em `tests/test_vegetation_scales.py`. Motivação: a etapa 2 da D-031 comparou os preditores só em V(t+1), com o mesmo número de atrasos para as quatro variáveis (um estado de 4m dimensões), e a ausência de ganho nessa configuração não basta para dizer que não há relação dinâmica identificável.

**Dados e células.** Os da etapa 2 da D-031 (regras v2): LAI e NDMI da subamostra, máscara MCD12Q1, cobertura mínima de 5%; VPD do ERA5 (média dos 8 dias até o dia de observação) e chuva do CHIRPS acumulada em 32 (H32) e 96 dias (H96), em valores brutos (`vegetacao/conjunto.parquet`). Leitura principal: LAI nas células com até 20% de lacunas; LAI com 20–35% e NDMI (até 35%) como consistência.

**Validação cronológica em blocos.** Três dobras com janela de treino crescente: teste em 2013–16, 2017–20 e 2021–24, treino com todos os anos anteriores ao bloco. Dentro de cada dobra, os três últimos anos do treino são a validação interna, onde se escolhem os parâmetros; o modelo escolhido é reajustado no treino inteiro e avaliado no bloco. Em cada estágio, a climatologia da anomalia (média e desvio por posição da composição no ano) é estimada só com os anos de ajuste, e a anomalia de todos os anos é calculada com ela. O RMSE de cada célula junta os erros das três dobras.

**Lacunas (ajuste ao proposto).** A interpolação da D-031 usa as composições seguintes: um preditor V(t) interpolado entre t − 1 e t + 1 carrega parte do alvo V(t+1). Na leitura principal (variante "estrita"), os preditores são preenchidos só com o passado (o último valor válido por até duas composições; depois a climatologia, 0) e só os alvos efetivamente observados entram no ajuste e no erro. A proposta tinha o preenchimento como principal e os alvos válidos como versão restritiva; a ordem foi invertida porque medir o erro contra um valor interpolado, ou contra o zero da climatologia, mede o preenchimento e não a vegetação. A variante "d031" repete o tratamento da D-031 (interpolação e alvos preenchidos) como comparação.

**1. Horizontes.** h = 1, 2, 4 e 8 composições (≈ 8, 16, 32 e 64 dias). Para cada h, os mesmos tempos t (de t = 8, o maior atraso, até n − h) e os mesmos alvos para todos os modelos. Vegetação isolada: X = [V(t), V(t−1)]. Sistema conjunto: X = [V(t), V(t−1), H(t−k_H), D(t−k_D)]. Ganho G(h) = 1 − RMSE_conjunto(h) / RMSE_vegetação(h). Variante "media" (acrescentada, sensibilidade): o alvo é a média de V nas h composições seguintes (com pelo menos metade observadas), que reduz o ruído de recuperação de cada composição; só h ≥ 2.

**2. Atrasos e estado compacto.** H é H32 ou H96 (uma das duas, nunca as duas, pela redundância), k_H e k_D ∈ {0, 2, 4, 8} composições: 32 configurações conjuntas, todas com 4 coordenadas. A escolha (chuva, k_H, k_D) é feita na validação interna de cada dobra, separadamente para cada modelo. Descritivo, sem seleção: o ganho linear no teste de cada uma das 32 configurações fixas ("perfil") e a frequência das escolhas entre células e dobras.

**3. Linear e não linear.** Três modelos para cada conjunto: regressão linear (S-map com θ = 0, mínimos quadrados), vizinhos próximos (5 vizinhos, média simples) e S-map com θ ∈ {0; 0,25; 0,5; 1; 2; 4; 8}, (configuração, θ) escolhidos juntos na validação interna. A evidência de não linearidade é G_NL = 1 − RMSE_S-map(θ escolhido) / RMSE_S-map(θ = 0) com a mesma configuração, para o conjunto e para a vegetação isolada, com o teste de Diebold–Mariano (HAC com h − 1 defasagens). O G(h) principal é o do modelo linear; S-map e vizinhos são lidos ao lado.

**4. Direção inversa.** Alvo D(t+h) (VPD). Atmosfera isolada: [D(t), D(t−1)]; atmosfera e vegetação: [D(t), D(t−1), V(t−k)], k ∈ {0, 2, 4, 8} escolhido na validação interna; mesmos modelos, dobras e variantes. Leitura com cautela: ganho preditivo não demonstra retroalimentação, e o ERA5 usa vegetação climatológica, sem o LAI observado de cada ano, de modo que um efeito local da vegetação sobre o VPD só apareceria pelo que as observações assimiladas carregam.

**5. Controle e inferência.** Para cada célula, 39 permutações dos anos inteiros (2001–2024, sem nenhum ano no lugar) do bloco que não é o alvo: a atmosfera (VPD, H32 e H96 com a mesma permutação) no sentido direto, a vegetação no inverso. A permutação é feita nos valores brutos, por (ano, posição no ano), e mantém o ciclo anual, a memória dentro do ano e as relações entre as variáveis atmosféricas; destrói só o alinhamento entre os blocos. A climatologia, a escolha dos parâmetros e o ajuste são refeitos em cada uma. As 39 permutações são as mesmas em todas as células de uma bacia (semente 20261107 + s), e por isso a nula da mediana entre células preserva a dependência espacial. Estatística por bacia: a mediana de G(h) entre as células, contra as 39 medianas das permutações (p = (1 + #{nula ≥ observado}) / 40); e a fração de células acima do 95º percentil das suas próprias permutações, contra a mesma fração calculada em cada permutação. Família principal: LAI, sentido direto, variante estrita, modelo linear, células com até 20% de lacunas, 4 horizontes × 2 bacias = 8 testes, com Holm. Todo o resto é secundário e lido pelo tamanho do efeito. O IC da mediana vem do bootstrap de blocos de 1° (D-028). As variantes "estrita" e "media" recebem permutações; a "d031" só o valor observado.

**Checagem antes dos dados reais.** O procedimento inteiro roda em células sintéticas montadas sobre a atmosfera real e as lacunas reais do LAI de 10 células do Tapajós: V = u + ruído, u(t+1) = 0,8 u(t) + β D(t−4) + ε, com β = 0 (sem acoplamento), 0,15 e 0,3, e 19 permutações (`synthetic_frame`). Exige-se que, com β = 0, o ganho mediano fique perto de zero e a fração de células acima do 95º percentil perto de 5%; e que, com β > 0, o ganho apareça e cresça com β. *Resultado (07/11, h = 1, 4 e 8, variante estrita):* com β = 0, ganho mediano linear de −0,005 a −0,009, igual ao das permutações (p da bacia de 0,45 a 1,0) e 0% a 20% das células acima do 95º percentil; com β = 0,15, ganho de 0,014 a 0,021 (p = 0,05, o mínimo com 19 permutações) em 70% a 90% das células; com β = 0,3, de 0,05 a 0,08 em 90% a 100%. S-map e vizinhos acompanham com ganhos um pouco menores. A defasagem escolhida concentra-se em k_D = 2–4 quando há acoplamento e se espalha sem ele. Um ganho linear de cerca de 0,02 é, portanto, detectável com 10 células. Ressalva para o item 3: com acoplamento linear nos dados e não nas permutações, o G_NL dos dados fica um pouco acima do das permutações mesmo sem não linearidade (p da bacia de 0,05 em 2 de 6 casos com G_NL negativo); por isso a não linearidade é lida pelo G_NL e pelo teste de Diebold–Mariano por célula, nunca pelas permutações.

**Interpretação, fixada antes.** (i) Ganho do conjunto só em alguns horizontes ou atrasos: a relação depende da escala de tempo. (ii) S-map melhor que o linear com os mesmos preditores: a resposta depende do estado. (iii) Nenhum ganho acima das permutações: conclusão negativa mais robusta que a da D-031, porque cobre horizontes, atrasos, representações e modelos sem aumentar a dimensão do estado. Nenhum dos três é evidência de caos; a busca por assinaturas caóticas no estado multivariado fica para depois e não deve confundir previsibilidade, dependência não linear e determinismo caótico.

**Resultado (07/11, `vegetacao/escalas_a531f9f155`, 39 permutações).** Células: LAI 56 no Xingu e 62 no Tapajós (43 e 59 na leitura principal); NDMI 29 e 39, só consistência. *Família principal (LAI, sentido direto, estrita, linear, até 20% de lacunas):* o ganho mediano é negativo nos quatro horizontes e nas duas bacias (−0,004 a −0,007), no nível das permutações ou um pouco abaixo delas (mediana das nulas de −0,003 a −0,004; no Xingu, o linear fica abaixo do 5º percentil das permutações nos quatro horizontes), com p da bacia de 0,62 a 1,0 e p de Holm = 1 nos 8 testes; a fração de células acima do 95º percentil das suas permutações fica entre 5% e 16%, dentro do acaso. Na checagem sintética, um ganho de 0,02 seria detectado. *Horizontes e alvo médio:* a vegetação isolada também não prevê o LAI melhor que a climatologia (RMSE relativo de 0,98 a 1,00 em todos os h, e de 0,98 a 0,99 com o alvo médio); a média de h composições reduz o ruído, mas não revela memória nem resposta à atmosfera. *Atrasos:* as escolhas se espalham pelas 32 configurações (a mais frequente em cada horizonte fica com 5% a 10% das células × dobras, contra 3% de uma escolha ao acaso), sem defasagem preferida; no perfil, a melhor configuração fixa tem ganho mediano de −0,002 a +0,0001. *Linear × não linear:* G_NL negativo em todos os casos (−0,007 a −0,016 no conjunto; ~0 na vegetação isolada), com Diebold–Mariano abaixo de 0,05 em no máximo 7% das células: o S-map escolhe θ > 0 no treino e perde no teste, sem sinal de dependência do estado. *Direção inversa:* o LAI não acrescenta nada à previsão do VPD (ganho de −0,002 a 0,000, p de 0,05 a 0,97, sem padrão). *NDMI (consistência):* ganhos de −0,005 a +0,004, alguns acima das permutações (p 0,03 a 0,05, frações de 20% a 49%), nos dois sentidos e também com o VPD como alvo, sempre abaixo de 0,5% do erro; como as permutações têm mediana negativa (um preditor sem informação custa um pouco no teste), o NDMI fica "menos prejudicado que o ruído", o que é compatível com a contaminação atmosférica residual já apontada na D-031, e não com uma resposta fisiológica. *Variante d031:* os mesmos números (−0,006 a −0,003 no LAI); o tratamento das lacunas não muda a leitura.

**Leitura.** Cenário (iii) da interpretação fixada: horizontes de 8 a 64 dias, estados compactos com chuva de 32 ou 96 dias e VPD com atrasos de até 64 dias, modelos lineares e não lineares e as duas direções não acrescentam informação preditiva sobre a anomalia de 8 dias da vegetação além do acaso, num desenho capaz de ver um ganho de 2%. A conclusão negativa da D-031 deixa de depender do horizonte de um passo e da dimensão do estado. O limite é o instrumento: a anomalia do LAI do MODIS sob nuvem não tem memória mensurável nem em relação a si mesma, e a resposta da floresta, se existe nessa escala, fica abaixo do ruído de recuperação; escalas mais longas (sazonal, interanual) e o fogo (etapa 3 da D-031, onde a resposta aparece) são o caminho.

## D-033 — Memória e sensibilidade da floresta depois do fogo (ampliação da etapa 3 da D-031)

**Status:** fixado em 07/11/2026, antes de qualquer resultado com as correções (proposta do usuário, "Ampliação da investigação da resposta da floresta ao fogo", com os ajustes abaixo). Comparativo: os resultados de 02/11 da D-031 ficam gravados e são relidos com as correções. Moldura: a variante da subamostra (regra do fogo v2; 285 episódios por bacia, 3 controles pareados entre 10 candidatos da mesma célula ERA5, pontos lidos nos cubos de área). Código em `features/fire_episodes.py`, `nonlinear/coupling.py` e `nonlinear/fire_response.py` (`amazon-chaos vegetation fire-memory`); execução no HPC (`vegetacao_fogo_memoria.sbatch`, com avisos no Telegram).

**1. Correções.** (a) *Data da queima:* o `Burn_Date` do MCD64A1 no pixel e no mês do episódio dá o dia da queima; k passa a ser o número de composições MODIS desde a que contém esse dia (k = 0), e não desde a primeira que começa no mês. Diagnóstico antes de qualquer resultado: na regra antiga, a composição da queima caía em k = −1 em 11% (Xingu) e 16% (Tapajós) dos episódios e em k = 1 a 3 em 60% e 62%; havia composições depois do fogo contadas como antes e composições antes contadas como depois. A composição k = 0 é sempre excluída; na sensibilidade "margem", também k = −1 e k = 1 (incerteza do dia da queima e composição do LAI pelo melhor dia de 8). (b) *Transições:* `v_next` só existe entre composições consecutivas do mesmo lado da queima (k e k + 1 ambos < 0 ou ambos ≥ 1); antes, ele era tomado antes de retirar k = 0, e a transição de k = −1 carregava a própria queima como resposta de um período "antes". O painel da D-031 é refeito com (a) e (b), e os dois resultados ficam lado a lado. (c) *Tendências anteriores:* placebo de data (a queima posta 92 composições, dois anos, antes da verdadeira; janela de −46 a +46 em relação à data fictícia, toda anterior ao fogo) e placebo de unidade (o controle mais próximo vira o "queimado" e os outros dois, os controles, na mesma data); nos dois, nada deve aparecer. (d) *Qualidade estrita:* LAI só do algoritmo principal sem saturação (bits 5–7 = 0) e NDMI com aerossol baixo ou climatológico e visada ≤ 20°, extraídos de novo dos cubos.

**2. Recuperação e memória.** δₑ(t) = V do queimado − média dos controles com valor (pelo menos 2 dos 3), em LAI ou NDMI brutos. Δₑ(k) = δₑ(k) − média de δₑ em k ∈ [−46, −1] (a linha de base da D-031). Ajuste: linha de base sazonal, δₑ(k) − média de δₑ no mesmo mês do calendário nos dois anos antes do fogo (k ∈ [−92, −1]), porque queimados e controles podem diferir no ciclo do ano antes do fogo, e então o déficit que "volta nas estações secas" seria anterior à queima. Por episódio: déficit acumulado Aₑ = −Δt Σ min[Δₑ(k), 0] em k = 1…138, com Δt = 8/365,25 ano (unidade: LAI·ano), calculado como −Δt · 138 · média dos k válidos, com pelo menos metade válidos; o déficit líquido A_net (sem o min); o do primeiro ano A₁ (k = 1…46); e a diferença residual Rₑ = média de Δₑ em k = 47…138 (anos 2 e 3), com pelo menos 30% válidos. Ajuste: o min[·, 0] faz o ruído sozinho dar Aₑ > 0; por isso o piso de ruído é o mesmo Aₑ no placebo de unidade, e o efeito do fogo é a diferença entre os dois. Médias com IC 95% por bootstrap das células ERA5 (999), por bacia e por grupo de anos de queima (2003–09, 2010–15, 2016–21).

**3. Mudança da sensibilidade (análise principal).** Painel por episódio, nas transições válidas com k de −92 a 138: δₑ(t+1) = αₑ + φδₑ(t) + βH(t) + γD(t) + φ_P P·δₑ(t) + θ_H P·H(t) + θ_D P·D(t) + f(k) + s(mês) + s_P(mês)·P + ε. H: anomalia padronizada (por célula e posição no ano, 2001–2024) da chuva do CHIRPS em 96 dias; D: a do VPD do ERA5 (média de 8 dias), ambas na célula do episódio, que é a dos controles, e no meio da composição; P = 1 depois do fogo; f(k): indicadores das janelas 1–6, 7–23, 24–46, 47–92 e 93–138; s(mês) e s_P(mês)·P: o ciclo do ano antes e depois do fogo, de modo que θ mede a resposta às anomalias, e não o déficit típico da estação seca; efeitos fixos de episódio (dentro de cada episódio). Acrescentado à proposta: φ_P, porque a D-031 encontrou persistência maior depois do fogo, e deixá-la de fora poderia passar para θ. Inferência: bootstrap de células ERA5 (499 reamostras, episódios repetidos tratados como distintos), p bilateral do percentil; o erro agrupado por célula ao lado. Família principal: θ_D e θ_H no LAI, nas duas bacias (4 testes, Holm). NDMI e as variantes são secundários. Variantes: depois do primeiro ano (só k ≥ 47 no período depois, P = 1 a partir daí); chuva de 32 dias; margem; qualidade estrita; 3 candidatos sorteados em vez dos pareados; regra antiga de tempo; placebo de data e placebo de unidade (θ ≈ 0 esperado).

**4. Seca antes do fogo.** Sₑ = média da anomalia padronizada diária do VPD (por célula e mês do calendário, 2001–2024) nos 60 dias antes da queima; alternativa: anomalia da chuva do CHIRPS acumulada nos 96 dias antes, padronizada da mesma forma. Modelo: Aₑ = α + βSₑ + bacia + ano da queima + estação seca (julho a outubro) + V médio do queimado no ano anterior + ε, com S padronizado entre os episódios; também com Rₑ e A₁. Bacias juntas (principal: β com Aₑ no LAI) e separadas; IC por bootstrap de células ERA5. Um teste principal.

**Emenda de 07/11, pela disponibilidade, antes de qualquer resultado.** Nos pixels, as lacunas são maiores que nas médias por célula: depois do fogo, a mediana das composições válidas (com pelo menos 2 controles) é de 41% a 42% no LAI e de 38% a 39% no NDMI. Com o mínimo de metade, A e A₁ ficariam com 23% a 25% dos episódios de LAI e 8% a 24% dos de NDMI. Passa a valer o mínimo de 30% para A e A₁, o mesmo de R, que mantém 85% a 90% dos episódios de LAI e 70% a 74% dos de NDMI. Como A usa a média dos k válidos vezes o número de composições, o mínimo menor aumenta a variância, não o viés.

**5. Limites, fixados antes.** A amostra exclui episódios que perdem floresta em 2 anos ou queimam de novo em 3, e sorteia 15 por ano: as conclusões valem para queimadas de sub-bosque em floresta que segue floresta. O pareamento pela média e pela amplitude sazonal não garante tendências paralelas; os placebos dizem quanto isso pesa. A seca antecedente também se associa à intensidade da queima, que o MCD64A1 não mede.

**Interpretação, fixada antes.** (i) Redução temporária sem mudança de sensibilidade: Δ volta a zero e θ ≈ 0. (ii) Diferença persistente de estado sem mudança de sensibilidade: R < 0 além do placebo e θ ≈ 0. (iii) Resposta diferente às mesmas anomalias: θ_D < 0 (VPD alto aprofunda o déficit do queimado) ou θ_H > 0, além dos placebos, e de preferência mantido depois do primeiro ano. Nenhum dos três demonstra caos, histerese ou troca de atrator; (iii) indica memória da perturbação nas relações dinâmicas da vegetação.
