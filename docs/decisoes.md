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

**Leitura:** confirma, com observação independente do modelo, a limitação de D-011 e a interpretação de D-014 e D-015: o resultado longitudinal nulo do caderno 08 não indica ausência de efeito do desmatamento, e sim que o ERA5 não o registra. O LST não entra na análise não linear: as lacunas de nuvem impedem séries diárias. É análise complementar, prevista no plano mas não no pré-registro dos descritores.

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

## D-025 — Pergunta secundária: o tempo antes do início dos episódios de fogo

**Status:** aceito em 23/10/2026 (`features/fire_weather.py`, caderno 10).

**Desenho:**
- evento: o início de um episódio de fogo, isto é, um dia com foco do BDQueimadas (satélite de referência, 2003–2024, dia local UTC−03:00) numa célula sem foco nos 30 dias anteriores. A primeira versão, que usava o primeiro foco do ano civil, foi descartada antes de qualquer análise, porque punha muitos eventos em janeiro, em queimas da temporada anterior;
- medidas até a véspera: anomalia do VPD e da temperatura do ERA5 nos 7 e nos 30 dias anteriores, chuva dos 30 dias anteriores no CHIRPS e no ERA5 e dias seguidos com menos de 1 mm no CHIRPS;
- controle: os dias a até ±15 dias do calendário, na mesma célula, nos anos sem foco nessa janela. Cada evento é resumido pelo percentil entre os seus controles (0,5 é um dia típico). A diferença para a média dos controles foi descartada porque seria negativa sem efeito nenhum em medidas assimétricas, como a chuva acumulada;
- incerteza: bootstrap reamostrando anos inteiros, porque um mesmo episódio de tempo seco atinge muitas células;
- estratificação por estação (seca: junho a outubro) e por terço de perda antecedente, só nas células elegíveis.

**Natureza:** descritiva, sobre a associação entre o tempo e o início do fogo; não separa ignição humana de propagação.

## D-026 — O território: Terras Indígenas e Unidades de Conservação como chave de leitura

**Status:** aceito em 23/10/2026 (`features/territory.py`, caderno 11), como ponte com a parte socioespacial.

**Desenho:** a fração de cada célula, dentro da bacia, em Terras Indígenas (FUNAI), em Unidades de Conservação federais (ICMBio) e na união das duas, com os limites atuais das camadas de contexto. A classe da célula é: TI ou UC se a categoria cobre pelo menos metade dela; fora se menos de 10% é protegido; mista nos demais casos. Comparação por classe (medianas) e correlação parcial com a fração protegida (controles: latitude, água e altitude; IC por blocos de 1°) para a perturbação, os focos de fogo, o LST do MODIS e a máxima do ERA5 na estação seca, a entropia da chuva do CHIRPS e, a partir do caderno 10, o percentil do tempo antes do início dos episódios de fogo na estação seca.

**Limites:** os limites são os atuais, e muitas áreas foram criadas ou homologadas durante o período; a localização das áreas protegidas não é aleatória (tendem a estar em áreas mais remotas), então a comparação é uma associação e não mede o efeito da proteção. Rodovias, como a BR-163, não entram por falta de uma camada no projeto.
