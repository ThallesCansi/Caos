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

## D-018 — Checagem MODIS: o satélite vê o desmatamento, o ERA5 não

**Status:** resultado registrado em 22/10/2026 (checagem prevista em D-011).

**Dados:** MOD11A2 coleção 6.1 pelo AppEEARS, 2001–2024, composições de 8 dias a 1 km, só pixels de boa qualidade (QC bits 0–1 ≤ 1 e erro de LST ≤ 2 K), agregados às células (`features/lst.py`, `gradient.surface_table`). O QC = 0, melhor qualidade, vem do AppEEARS marcado como "sem dado" e era decodificado como NaN; o filtro agora o trata explicitamente como 0. As datas vêm em `cftime`. Comparação no ERA5: máxima diária do ar a 2 m na estação seca (junho a setembro), a grandeza mais próxima do LST diurno das 10h30.

**Resultado (células elegíveis, controles latitude, água e altitude, IC por blocos de 1°):** entre células, a perda antecedente se associa ao LST diurno da estação seca com ρ parcial de +0,81 (Xingu) e +0,74 (Tapajós), de 6 a 7 °C entre o décimo menos e o mais desmatado; com a máxima do ERA5, −0,14 e −0,06, compatíveis com zero. Ao longo do tempo, a perda de 2001–2012 se associa ao aquecimento do LST entre as décadas com ρ de +0,72 e +0,77; no ERA5, −0,18 e +0,04.

**Checagem (23/10/2026):** só nas células com menos de 5% de vegetação natural não florestal em 2000, a associação entre perda antecedente e LST continua em +0,81 (Xingu) e +0,77 (Tapajós), com 5,6 °C entre o décimo mais e o menos convertido; com a conversão agropecuária, controlando a vegetação natural, +0,77 nas duas. A diferença não vem do Cerrado natural.

**Viés de céu limpo (23/10/2026):** na estação seca, a mediana das células tem cerca de 378 das 384 composições possíveis (16 por ano × 24 anos) com qualidade boa; o 10º percentil é 335 no Xingu e 371 no Tapajós. Com o número de composições válidas nos controles, a associação entre a perda antecedente e o LST fica em +0,80 e +0,71, e a longitudinal em +0,71 e +0,76; só na metade das células com mais composições válidas, +0,85 e +0,68.

**Comparativo F2e (29/10/2026, D-027):** a máxima diária do ar não é a grandeza do LST. Com a temperatura de pele (`skt`) do ERA5 interpolada para as 10h30 solares na estação seca (`features/lst.era5_overpass`, `amazon-chaos era5 overpass`), a associação entre células com a perda antecedente é de +0,25 [+0,05; +0,46] no Xingu e +0,29 [+0,09; +0,47] no Tapajós, com 2,4 e 1,2 °C entre o décimo mais e o menos perturbado, contra 6,7 e 6,4 °C no MODIS; só nos dias com `tcc` < 0,3, +0,29 e +0,32, com contrastes menores (1,7 e 0,8 °C). Com a vegetação alta e baixa do ERA5 nos controles, a do Xingu cai a +0,05 [−0,12; +0,25] e a do Tapajós fica em +0,29 [+0,10; +0,42]. Ao longo do tempo, −0,13 [−0,30; +0,05] e −0,43 [−0,53; −0,29]: no Tapajós, o ERA5 aquece mais a pele das células sem perda. Pela regra de leitura fixada, o resultado qualifica a leitura entre células (parte do contraste MODIS × ERA5 era diferença de grandeza; a superfície do ERA5 registra de um quarto a um terço do contraste em °C, e no Xingu só pelo mapa de vegetação fixo) e confirma a cegueira ao desmatamento posterior a 2000. Caderno 08, Figura 7 e Tabela 4, como comparativo complementar.

**Leitura:** evidencia, com observação independente do modelo, a limitação de D-011 e a interpretação de D-014 e D-015: o resultado longitudinal nulo do caderno 08 não indica ausência de efeito do desmatamento, e sim que o ERA5 não o registra. O LST não entra na análise não linear: as lacunas de nuvem impedem séries diárias. É análise complementar, prevista no plano mas não no pré-registro dos descritores.

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
- associação: a de D-018 (perda antecedente; latitude, água e altitude; blocos de 1°), entre células e ao longo do tempo (perda de 2001–2012 contra a mudança entre as metades), e o contraste em °C entre o décimo mais e o menos desmatado;
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
- *F2f, gate realista* (`gate/realista_bea8860a92`, 600 séries, sem erros; caderno 05, Figura 5 e Tabela 3): o AR(1) com memória sazonal faz o DET rejeitar em 81% das séries, a LAM em 86% e o par ordinal em 54–59% (90–100% com os ajustes do VPD); o AR-GARCH faz DET, LAM e Kantz rejeitarem em 98–100% e o Rosenstein em 81%; o erro de previsão rejeita em no máximo 16%; o D_E2 de Cao, em no máximo 8% (poder de 100% nos três caóticos, 0% no ruído branco e no AR(1)). Pela regra fixada (caderno 07, Tabela 5), as células se distinguem da nula mais permissiva no D2, na assimetria, no par ordinal do VPD (e da temperatura do Xingu, por pouco) e no S-map da temperatura; não no DET, na LAM nem no Lyapunov. Qualifica: a rejeição das substitutas não basta para falar em dinâmica determinística.
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
- n efetivo de Clifford, Richardson e Hémon (1989), a aproximação usual do teste de Dutilleul (1993): σ²(r) = Σ_k n_k ρ_x(k) ρ_y(k) / n², com classes de 0,5° até a maior distância e o termo de distância zero (n_0 = n, ρ = 1); n' = 1 + 1/σ², e p bilateral por t = r √((n' − 2)/(1 − r²)) com n' − 2 graus de liberdade. Holm sobre os 16 também nesse p.

**Bootstrap × permutação em blocos.** O pré-registro (`disturbance.inference.spatial_blocks_degrees`) fala em "permutação por blocos de 1° × 1°". O caderno 08 usa, desde o primeiro cálculo, o bootstrap em blocos de 1°, que dá o intervalo de confiança da correlação parcial e não só um p. Fica registrado como a implementação da inferência por blocos; o p desta decisão vem do mesmo bootstrap.

**Exposição-placebo.** A perda de 2013 a 2024 não pode ter causado a dinâmica de 2001 a 2012. Se ela se associar aos descritores dessa década tanto quanto a perda antecedente, a associação reflete a geografia de onde o desmatamento avança, e não um efeito.
- células: elegíveis com floresta ≥ 50% da área terrestre em 2000;
- exposição: `mb_perda_floresta_2013_2024` (MapBiomas); resposta: z dos 4 descritores primários na janela 2001–2012; controles e inferência da Tabela 1;
- referência: a perda antecedente contra o mesmo z, nas mesmas células;
- leitura: placebo perto de zero onde a principal aparece reforça que a associação não é só seleção geográfica; placebo do mesmo tamanho e sinal a enfraquece. Exploratório.

**Resultado (29/10/2026):** com Holm sobre os 16, 9 ficam abaixo de 0,05: o par ordinal do VPD e o DET da temperatura nas duas bacias, e no Xingu também o DET e a previsão do VPD e a previsão da temperatura. O Moran dos resíduos (0,39–0,76) tem p = 0,001 por permutação em todos. O correlograma dos resíduos se anula perto de 1° (Tapajós) e 2° (Xingu) na exposição e de 2 a 2,5° nos descritores. O n efetivo cai para 22–55 células no Xingu e 94–213 no Tapajós; com ele, 7 dos 16 ficam abaixo de 0,05 (os pares que se repetem nas duas bacias e a previsão do VPD no Xingu), e com Holm por cima só o DET da temperatura no Tapajós (0,017). Placebo: no Xingu, nada (|ρ| ≤ 0,11), enquanto a perda antecedente nas mesmas 593 células dá +0,47 e −0,46 no par ordinal do VPD e −0,25 e −0,30 no DET; no Tapajós (500 células), o placebo aparece nos padrões ordinais e na previsão da temperatura (+0,17, −0,18, −0,27), onde a exposição principal é nula, e fica perto de zero no VPD e no DET da temperatura. Leitura: a conclusão fica mais modesta, não muda de sinal; caderno 08, Tabela 1 (colunas novas), Figura 8 e Tabela 5.
