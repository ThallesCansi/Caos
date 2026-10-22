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

- **τ** pelo primeiro mínimo da informação mútua média (AMI); **m** por falsos vizinhos mais próximos (FNN). Ambos sobre as anomalias.
- Avaliar uma grade pré-registrada em torno dos valores estimados, nunca um único par escolhido a dedo.
- Janela de Theiler para excluir vizinhos temporais.

### 8.3 Descritores

| Descritor | O que mede | Cuidados |
|---|---|---|
| Maior expoente de Lyapunov (Rosenstein) | divergência de trajetórias próximas | a região de ajuste é pré-registrada; AR(1) também produz inclinação positiva (laboratório), por isso a comparação é contra substitutas |
| RQA (DET, LAM, ENTR) | estrutura de recorrência | taxa de recorrência fixa, não limiar fixo |
| Dimensão de correlação D2 | complexidade geométrica | pouco confiável com cerca de 9 mil pontos e ruído; procurar platô, com relato honesto |
| Entropia de permutação e complexidade estatística | plano complexidade–entropia (Bandt–Pompe; Rosso et al., 2007) | ordem e atraso pré-registrados |
| Assimetria temporal e erro de previsão não linear | irreversibilidade e previsibilidade | já usados no protocolo de substitutas (§8.4) |
| EWS: variância e AR(1) em janela móvel | *critical slowing down* | tendência por Kendall τ contra substitutas (Dakos et al., 2012); **não** é evidência de caos |

O resultado de cada descritor é uma distribuição, com robustez na grade e posição em relação às substitutas, não um número isolado.

### 8.4 Substitutas (protocolo do caderno 06)

- **FT:** processo linear gaussiano estacionário condicionado ao espectro. **IAAFT:** transformação estática monotônica de um processo linear gaussiano estacionário, com marginal exata e espectro aproximado. São hipóteses diferentes. Rejeitar qualquer uma delas **não demonstra caos determinístico**.
- **Configuração padrão:** diário, 2001–2024, normal 1991–2020, 199 substitutas, α=0,05, semente 20261013.
- **Família primária:** quatro hipóteses (anomalia de temperatura × duas regiões × dois métodos), com assimetria temporal no atraso 1 e escore absoluto, corrigidas por **Holm**. Testes bloqueados contam como p=1 na correção.
- **Família exploratória:** chuva, séries originais, previsão por vizinhos, atrasos de 7 e 30 dias e as janelas 2001–2012 e 2013–2024, corrigidas por **Benjamini–Hochberg**.
- **p de Monte Carlo** inclusivo, com correção +1 (resolução de 0,005 com M=199).
- **Previsão não linear:** imersão 3, atraso 1, horizonte 1, cinco vizinhos, primeiros 60% para treino, exclusão de Theiler de 14 amostras. Nenhum alvo de avaliação entra no treino.
- **Bloqueios de qualidade:** índice incompleto, duplicado ou irregular; valores não finitos; série constante; unidade incompatível; chuva negativa. Diagnósticos de estacionariedade (ADF, KPSS, tendência HAC, CUSUM, momentos em blocos) são **heurísticos** e não certificam estacionariedade.
- **Calibração medida** (40 repetições, 512 pontos): branco gaussiano com 7,5% (FT) e 5% (IAAFT) de rejeição; AR(1) com φ=0,8, 5% em ambos; logístico, 40 de 40 em ambos. Os intervalos são largos, e compatibilidade com 5% não prova calibração exata.
- **No lote por célula** (caderno 07) usam-se 39 substitutas IAAFT por célula. Isso é o bastante para um teste unilateral com α=0,05, e os resultados são resumidos pela fração de células que rejeitam e pelos z-scores, com correção para múltiplos testes espaciais.

## 9. Comparação espacial (F7)

- **Transversal:** regressão dos descritores contra a perturbação antecedente, com latitude, elevação e fração de água como controles. A inferência é feita por blocos espaciais, com o I de Moran dos resíduos.
- **Longitudinal:** a mudança do descritor entre 2001–2012 e 2013–2024 contra a mudança da perturbação, na mesma célula. Isso elimina a geografia fixa.
- **Checagem MODIS:** se o gradiente de LST observado aparece no t2m do ERA5 (D-011).
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
