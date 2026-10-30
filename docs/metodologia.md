# Metodologia

Documento único de método do projeto. Ele funde o plano de pesquisa, o desenho do estudo, os guardrails, a arquitetura e o protocolo de substitutas, que antes ficavam em arquivos separados (histórico na tag `v0-jupyter`). As decisões estáveis e suas datas estão em [decisoes.md](decisoes.md); as fontes e os contratos de dados, em [dados.md](dados.md).

## 1. Pergunta

**Objetivo geral** (projeto aprovado): investigar a dinâmica não linear do sistema floresta–atmosfera amazônico, com métodos da Teoria do Caos e dos sistemas dinâmicos complexos, para analisar possíveis sinais de instabilidade associados a desmatamento, queimadas e degradação florestal. A interpretação inclui a dimensão socioespacial, que é responsabilidade da parte de humanidades do TCC.

**Pergunta de pesquisa** (D-019): a perturbação da floresta amazônica, por desmatamento e fogo, deixa marca na dinâmica do clima local, isto é, na forma como ele evolui de um dia para o outro? E as ferramentas da teoria do caos conseguem revelá-la?

1. **Natureza:** que tipo de dinâmica o clima diário local tem: caos de baixa dimensão, ruído ou não linearidade de alta dimensão? (cadernos 01, 05, 06 e 07)
2. **Relação:** essa dinâmica difere entre lugares mais e menos perturbados, e muda onde a floresta é perdida? (caderno 08)
3. **Detectabilidade:** que escala, grandeza e tipo de registro são necessários para que essa marca apareça? (checagem MODIS, D-018; condições meteorológicas antes do fogo)

**Operacionalização:** depois de controlar sazonalidade, tendência, autocorrelação, ruído, tamanho da amostra e geografia, as células ERA5 com mais perturbação florestal antecedente apresentam descritores dinâmicos sistematicamente diferentes das células comparáveis mais preservadas? O ERA5 é o instrumento principal porque é a única série diária, sem falhas, de 35 anos nessa grade; o MODIS é a checagem observacional.

**Pergunta secundária:** quais condições meteorológicas antecedem as detecções de fogo nessas células?

A direção perturbação → clima organiza a hipótese e a ordenação temporal. O estudo estima **associações**. Antecedência temporal, sozinha, não identifica causalidade.

## 2. Recortes e período

| Dimensão | Decisão |
|---|---|
| Regiões | Bacias do Xingu (BHB250, `cod_otto=642`, 779 células) e do Tapajós (`cod_otto=644`, 762 células; D-009) |
| Unidade espacial | célula ERA5 de 0,25°, recortada pelo limite e ponderada pela área efetiva (D-005) |
| Período principal | 2001–2024, anos civis completos |
| Arquivo anterior | 1990–2000, para sensibilidade e condições antecedentes, nunca reclassificado como período principal depois de ver resultados |
| Normal climatológica | 1991–2020 (normal da OMM), usada nas anomalias |
| Resolução analítica | diária (dia local UTC−03:00 fixo), com sínteses mensais e anuais; o horário original é preservado |

## 3. Guardrails

1. **Lyapunov positivo não é prova de caos.**
2. **Caos não é tipping point.** Sensibilidade a condições iniciais não demonstra aproximação de transição crítica. Os EWS são tratados separadamente.
3. **Reanálise não é observação.** O ERA5 combina modelo e assimilação e usa um mapa de vegetação **fixo**: não incorpora o desmatamento ano a ano (D-011).
4. **A sazonalidade cria geometria aparente.** As análises usam a série original e as anomalias.
5. **Não otimizar τ, m ou o pré-processamento** para obter o sinal desejado: pré-registro (D-010).
6. **DETER não é taxa oficial de desmatamento**, e foco não é incêndio nem área queimada.
7. **Contagem de polígonos não é área.** Áreas são calculadas após o recorte, em projeção equal-area (EPSG:6933).
8. **Comparação espacial não é causalidade.** Clima de fundo, latitude, relevo e história territorial confundem o efeito.
9. **Sem pseudorreplicação.** Células vizinhas e dias consecutivos não são réplicas independentes; reportar o número de células e de blocos, não só o de linhas.
10. **Resultados negativos são resultados.** Não rejeitar uma substituta ou ter uma estimativa instável é algo a relatar, não a "corrigir".
11. **Dados brutos são imutáveis.** Cada correção gera um novo derivado com proveniência.
12. **Reprodutível a partir de configuração + manifesto + commit.**

## 4. Etapas e cadernos

| Fase | Pergunta | Caderno (`notebooks/`) | Gate |
|---|---|---|---|
| F0 | a infraestrutura é reprodutível? | — | downloads retomáveis com manifesto |
| F1 | onde estamos? | `02_regioes` | mapa e grade aprovados antes do download |
| F2 | as séries são boas? | `03_clima` | completude, unidades e calendário documentados |
| F3 | qual a perturbação de cada célula? | `04_perturbacao` | métricas definidas **sem olhar a resposta climática** |
| F4 | os métodos funcionam em sistemas conhecidos? | `01_laboratorio`, `05_validacao_metodos` | o descritor separa controles positivos de negativos |
| F5 | há estrutura não linear? | `06_surrogates` | hipóteses FT/IAAFT com correção múltipla |
| F6 | como os descritores variam no espaço? | `07_descritores` | robustez a τ, m e janela |
| F7 | a dinâmica acompanha a perturbação? | `08_gradiente` | controles espaciais e checagem MODIS |
| F8 | o que isso significa no território? | texto da dupla | conclusão proporcional à evidência |

## 5. Da hora ao dia

- O **dia local** vai das 00h às 24h em UTC−03:00 fixo. A hora UTC de apoio necessária nas bordas é baixada; o UTC é preservado nos brutos.
- VPD, umidade relativa e umidade específica são calculados **hora a hora, antes da agregação**. A média de transformações não é a transformação da média.
- Temperatura: média, mínimo, máximo e amplitude **das amostras horárias** (não são extremos instantâneos). Vento: média e máximo da velocidade horária, médias de u e v; o máximo horário não é rajada.
- **Precipitação** é acumulada na hora que termina em `valid_time` e somada respeitando esse intervalo. É variável intermitente e tem tratamento próprio: totais, acumulados de 7, 30 e 90 dias, sequências secas. Dia seco é < 1 mm (convenção operacional, com análise de sensibilidade).
- Cada estatística diária registra quantas horas válidas teve. **Dia incompleto não é preenchido**, e chuva ausente não vira zero. Dias ausentes interrompem sequências secas.
- Com dados do Earth Data Hub, a tolerância do ponto de orvalho é de 0,30 K (D-007).
- Temperatura, ponto de orvalho, umidade e VPD compartilham informação: não são evidências independentes.

## 6. Integração espacial

- Cada célula tem `cell_id` estável e um polígono de integração (pontos médios entre coordenadas vizinhas), recortado pelo limite da região. São mantidas área total, área terrestre e área válida.
- Médias regionais são ponderadas pela área efetiva da célula. A chuva regional é a média espacial dos totais diários, não a soma de milímetros.
- Água e "não classificado" não contam como desmatamento. As frações usam o denominador terrestre válido, declarado.
- Pixels e polígonos são ponderados pela área de interseção.

## 7. Perturbação (independente da resposta)

As métricas por célula são definidas antes de olhar os descritores: floresta no início da janela, desmatamento acumulado e recente, fogo (densidade de focos, anos com foco, recência), degradação recente e, como complemento, frações MapBiomas. Fontes e coberturas estão em [dados.md](dados.md).

- **PRODES:** os incrementos de 1988–2007 são um bloco agregado. Não se constrói uma série anual falsa para 2001–2007, nem se reparte esse acumulado. O ano PRODES (agosto a julho) é preservado e nunca interpolado para dias.
- **Antecedência:** só intervalos encerrados antes da janela de resposta definem a perturbação antecedente. O gradiente de 2024 ilustra a paisagem, mas não é exposição de 2001.
- **Fogo:** recorrência e recência são calculadas na resolução do produto e só depois resumidas na célula. Uma queima em parte da célula não é a queima da célula inteira. Sem fogo observado, o tempo desde o último fogo é **censurado**, não zero.
- **Fontes heterogêneas não são emendadas** como se fossem uma única variável homogênea.
- O índice de perturbação é contínuo. Classes (preservada, intermediária, perturbada) servem só para comunicação.

## 8. Análise não linear

### 8.1 Pré-registro e gate

Tudo o que pode ser escolhido fica em `configs/analysis/descriptors.yaml`, **versão 1 congelada em 20/10/2026**, antes do cálculo nos dados reais (D-010), e **versão 2** no mesmo dia, antes de qualquer análise de perturbação × dinâmica: na comparação, só células com pelo menos 50% da área dentro da bacia (668 no Xingu e 652 no Tapajós com a regra de terra). As variáveis primárias são as **anomalias padronizadas** (divididas pelo desvio-padrão sazonal) de temperatura e de VPD; a tendência não é removida. A chuva é exploratória, analisada por métodos ordinais. As conclusões vêm só da família primária (entropia de permutação, complexidade, erro de previsão, RQA·DET), com Benjamini–Hochberg sobre as células, dentro de cada família, por região × variável × janela (D-020). D2, LAM e assimetria são secundários, e o Lyapunov é exploratório.

Antes dos dados reais, cada descritor passa pelo **gate F4**: controles positivos (Lorenz, logístico r=4) e negativos (AR(1), ruído branco, seno com ruído, seno com tendência e variância sazonal), variando o comprimento e o ruído. Se o descritor não separar os dois grupos contra substitutas, ele não entra na interpretação. Isso é relatado como resultado metodológico.

### 8.2 Reconstrução

- **τ** pelo menor valor entre o primeiro mínimo local da informação mútua média (AMI) e o primeiro τ com AMI < AMI(0)/e; nas anomalias diárias o critério de 1/e prevalece e dá τ = 1, enquanto o primeiro mínimo fica em 10 a 12 dias (F2a, D-027). **m** pelo menor m com fração de falsos vizinhos (FNN) abaixo de 0,05, até 8. Ambos sobre as anomalias padronizadas, escolhidos na série observada e mantidos nas substitutas.
- Janela de Theiler w = max(10, τ·m).
- Robustez: τ·{0,5; 2} e m ± 1 em todos os descritores (caderno 07), τ = 2 na subamostra (D-024) e a grade τ ∈ {1, 2, 3, 5, 7}, mínimo da AMI e atraso ordinal L ∈ {1, 2, 4, 7} (F2a, D-027).

### 8.3 Descritores

| Descritor | O que mede | Cuidados |
|---|---|---|
| Maior expoente de Lyapunov (Rosenstein) | divergência de trajetórias próximas | a região de ajuste é pré-registrada; AR(1) também produz inclinação positiva (laboratório), por isso a comparação é contra substitutas |
| RQA (DET, LAM) | estrutura de recorrência | taxa de recorrência fixa (5%), não limiar fixo; a entropia das diagonais (ENTR) não foi calculada |
| Dimensão de correlação D2 | complexidade geométrica | pouco confiável com cerca de 9 mil pontos e ruído; procurar platô, com relato honesto |
| Entropia de permutação e complexidade estatística | plano complexidade–entropia (Bandt–Pompe; Rosso et al., 2007) | ordem e atraso pré-registrados |
| Assimetria temporal e erro de previsão não linear | irreversibilidade e previsibilidade | já usados no protocolo de substitutas (§8.4) |
| EWS: variância e AR(1) em janela móvel | *critical slowing down* | tendência por Kendall τ contra substitutas (Dakos et al., 2012); **não** é evidência de caos |

O resultado de cada descritor é uma distribuição, com robustez na grade e posição em relação às substitutas, não um número isolado.

### 8.4 Substitutas

- **FT:** processo linear gaussiano estacionário condicionado ao espectro. **IAAFT:** transformação estática monotônica de um processo linear gaussiano estacionário, com marginal exata e espectro aproximado. São hipóteses diferentes. Rejeitar qualquer uma delas **não demonstra caos determinístico**.
- **p de Monte Carlo** inclusivo, com correção +1; a alternativa de cada descritor (unilateral, bilateral ou absoluta) está no pré-registro.
- **Lote por célula (D-010, caderno 07):** 39 substitutas IAAFT (até 200 iterações) por célula, variável e janela, com semente própria derivada por SHA-256 da semente do pré-registro (20261020), da célula, da variável e da janela (`batch._seed`). Famílias do pré-registro: primária (entropia e complexidade de permutação, erro de previsão e RQA·DET), secundária (D2, LAM, assimetria) e exploratória (Lyapunov); Benjamini–Hochberg dentro de cada família, sobre as células, por região × variável × janela (D-020). Com 39 substitutas o menor p unilateral é 0,025, e os resultados são lidos também pela fração de células com p ≤ 0,05 e pelo z (D-013).
- **Erro de previsão:** previsor de vizinhos (média dos 5 mais próximos), horizonte 1, treino nos primeiros 60%, com o (τ, m, w) da regra; nenhum alvo do teste entra no treino. Os padrões m = 3 e Theiler 14 de `statistics.nonlinear_prediction_error` são só valores-padrão da função e não são usados no lote.
- **Séries das bacias (D-016, caderno 06):** 199 substitutas FT e IAAFT, e IAAFT depois de retirar a tendência, com Holm sobre os descritores primários de cada bacia × método.
- **Bloqueios de qualidade:** índice incompleto, duplicado ou irregular; valores não finitos; série constante; unidade incompatível; chuva negativa. Diagnósticos de estacionariedade (ADF, KPSS, tendência HAC, CUSUM, momentos em blocos) são **heurísticos** e não certificam estacionariedade.
- **Validação:** o gate congelado (`1c2fb37657`, caderno 05) mede poder e falso positivo dos descritores em controles caóticos e lineares; o gate com nulas realistas (F2f, D-027) mede o falso positivo em processos estocásticos sazonais e não lineares sem caos.

## 9. Comparação espacial (F7)

- **Transversal:** correlação parcial de Spearman entre os descritores e a perturbação antecedente, com latitude, altitude e fração de água como controles. A inferência é feita por bootstrap em blocos espaciais de 1° (IC percentil, 999 reamostras); o pré-registro dizia "permutação por blocos", e o bootstrap em blocos, que dá intervalo e não só p, foi o implementado desde o primeiro cálculo do caderno 08 (D-028). O I de Moran dos resíduos acompanha cada associação. Os 16 testes pré-registrados (2 bacias × 2 variáveis × 4 descritores primários) têm p-valor do mesmo bootstrap em blocos, corrigido por Holm e por Benjamini–Hochberg; ao lado, o I de Moran por permutação, o correlograma dos resíduos e o n efetivo de Clifford et al. (1989), com o p-valor correspondente (D-028). O resto do caderno 08 é exploratório.
- **Exposição-placebo (D-028):** a perda de 2013–2024 contra os descritores de 2001–2012, nas células com ao menos metade de floresta em 2000, para separar efeito de seleção geográfica.
- **Longitudinal:** a mudança do descritor entre 2001–2012 e 2013–2024 contra a mudança da perturbação, na mesma célula. Isso elimina a geografia fixa.
- **Checagem MODIS:** se o gradiente de LST observado aparece no t2m do ERA5 (D-011).
  Comparativo (D-027, F2e): a temperatura de pele do ERA5 às 10h30 solares, a mesma grandeza e o mesmo horário do LST, registra um quarto a um terço do contraste entre células e nada do aquecimento ao longo do tempo (D-018).
- **Tempo antes do fogo (D-025, caderno 10):** cada início de episódio (foco depois de 30 dias sem foco na célula) é comparado com controles da mesma célula, na mesma data dos outros anos sem foco a ±15 dias corridos. O resultado é o percentil do evento entre os controles, com IC por bootstrap de anos. Preservadas × perturbadas (terços de perda antecedente cortados nas células) são comparadas diretamente pela diferença dos percentis médios, reamostrando os mesmos anos. A estação seca do fogo é junho a outubro, e não junho a setembro como no resto do trabalho.
- **Comparáveis:** localização, relevo, água e condições de fundo justificadas. Não ajustar por respostas climáticas posteriores que façam parte do efeito.
- Antes de prometer inferência, verificar se há diversidade de perturbação e comparáveis suficientes.

## 10. Critérios de parada

O projeto aceita resultados negativos. Exemplos: o ERA5 pode não ter resolução para a hipótese local; a série pode ser dominada por sazonalidade e ruído; o Lyapunov pode ser instável ao variar os parâmetros; as substitutas podem não permitir rejeitar a hipótese linear; as diferenças espaciais podem desaparecer com os controles. Cada um desses resultados é informativo e é relatado.

## 11. Arquitetura

```
fontes ─► CLI amazon-chaos (download explícito, manifesto SHA-256)
          ─► data/raw/<exp>          imutável, fora do Git
          ─► data/processed/<exp>    diários, resumos, perturbação, descritores
               ├─► jobs em lote (HPC)  descritores e substitutas por célula
               └─► notebooks/ (Marimo) narrativa, figuras e tabelas
                     └─► reports/figures, reports/tables ─► Overleaf
```

- Downloads e cálculos caros **nunca** rodam dentro de um caderno reativo.
- A mesma biblioteca roda localmente e no HPC ([hpc.md](hpc.md)).
- Cada região é definida por um YAML em `configs/regions/`.

## Referências metodológicas

- Theiler et al. (1992), [doi:10.1016/0167-2789(92)90102-S](https://doi.org/10.1016/0167-2789(92)90102-S); Schreiber e Schmitz (2000), [doi:10.1016/S0167-2789(00)00043-9](https://doi.org/10.1016/S0167-2789(00)00043-9); Schreiber (1999), [doi:10.1016/S0370-1573(98)00035-0](https://doi.org/10.1016/S0370-1573(98)00035-0).
- Kantz e Schreiber (2004), *Nonlinear Time Series Analysis*; Rosenstein et al. (1993); Kennel et al. (1992) para FNN; Fraser e Swinney (1986) para AMI.
- Marwan et al. (2007) para RQA; Bandt e Pompe (2002); Rosso et al. (2007).
- Dakos et al. (2012) para EWS.
- Sivakumar (2000), [doi:10.1016/S0022-1694(99)00186-9](https://doi.org/10.1016/S0022-1694(99)00186-9).
- ERA5: Hersbach et al. (2020); [descrição no ECMWF](https://confluence.ecmwf.int/spaces/GCR/pages/473842427/ECMWF%2BERA5).
