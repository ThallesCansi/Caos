# Desenho do estudo floresta–atmosfera: 2001–2024

Documento de consolidação da discussão metodológica, em 8 de setembro de 2026. Reúne decisões aprovadas e explicita propostas operacionais para o futuro caderno. Não representa análise executada nem autoriza automaticamente novos downloads. Complementa RESEARCH_PLAN.md e METHODOLOGY_GUARDRAILS.md; a configuração e o piloto existentes ainda precisam ser adaptados na etapa de implementação.

## 1. Perguntas e alcance

Pergunta principal aprovada: como o histórico de desmatamento e fogo se associa à dinâmica climática diária em células comparáveis do Baixo Tapajós?

Pergunta secundária aprovada: quais condições meteorológicas antecedem detecções de fogo nessas células?

A direção perturbação → clima organiza a hipótese principal e a ordenação temporal. A análise estima associações, cuja interpretação depende da resolução das bases, da representação da superfície na reanálise e dos fatores de confusão. Antecedência temporal, sozinha, não identifica causalidade. A análise secundária também não demonstra um mecanismo de retroalimentação por si só.

## 2. Decisões aprovadas

| Dimensão | Decisão |
| --- | --- |
| Região de referência | Baixo Tapajós, entorno de Santarém, Belterra e Mojuí dos Campos, com contexto da BR-163 e da Flona do Tapajós |
| Período principal | 2001–2024, todos os meses do ano |
| Expansão futura | 1985–2024, respeitando a disponibilidade de cada fonte |
| Dados climáticos originais | ERA5 horário, preservado |
| Resolução analítica principal | Diária; sínteses mensais e anuais |
| Unidade espacial | Grade de distribuição do ERA5; limites administrativos como contexto |
| Comparação principal | Gradiente espacial de perturbação, com comparação entre células semelhantes |
| Perturbação | Métricas contínuas; classes apenas para comunicação e comparações visuais |
| Variáveis dinâmicas principais | Temperatura, VPD e velocidade do vento; umidade explicitada no conjunto de análises |
| Estado multivariado proposto anteriormente | Temperatura, umidade específica e componentes u/v do vento, em anomalias padronizadas |
| Precipitação | Contexto hidrológico, acumulados, estiagens e condições antecedentes |
| Caderno | Jupyter com explicações em Markdown, gráficos e operações legíveis; funções auxiliares em módulos Python |

O retângulo proposto na conversa é [N, W, S, E] = [-2.25, -56.00, -3.75, -54.25]. Sua delimitação deve aparecer no primeiro mapa para revisão cartográfica antes da aquisição. Não equivale ao limite municipal ou à delimitação completa da Flona. A contagem final de células depende da convenção de seleção e de borda.

## 3. Fontes e correções de cobertura

| Fonte | Função no estudo | Restrição a registrar |
| --- | --- | --- |
| ERA5 | Séries meteorológicas horárias e derivados diários | Reanálise: combinação de modelo e observações; não é medição de campo em cada célula |
| PRODES | Referência de desmatamento anual, onde há discriminação espacial por ano | No TerraBrasilis, incrementos anteriores a 2008 estão agregados em 1988–2007 |
| MapBiomas Cobertura | Fração de floresta, usos da terra e transições anuais | Mudança de classe e perda de floresta não são automaticamente equivalentes à definição PRODES |
| MapBiomas Fogo | Área queimada e histórico de anos com queima | Recorrência anual não conta todos os incêndios ocorridos dentro de um ano |
| BDQueimadas | Datas e localização de detecções de fogo ativo | Foco não equivale a incêndio individual nem mede área queimada |
| DETER | Alertas e contexto de degradação recente | Data de detecção pode diferir da ocorrência; não substituir a série consolidada de desmatamento |

**Correção à discussão anterior sobre PRODES:** a existência de taxas desde 1988 não significa disponibilidade de polígonos anuais desde aquele ano. O INPE informa que a base geográfica anterior a 2008 está agregada. Portanto, não construir uma falsa série anual PRODES por célula para 2001–2007, nem distribuir o acumulado entre esses anos. Fonte: [FAQ TerraBrasilis](https://terrabrasilis.dpi.inpe.br/faq/).

Consequência operacional: preservar a análise climática, de cobertura e fogo em 2001–2024; realizar as comparações que exigem incrementos anuais PRODES no subperíodo disponível. Eventuais transições do MapBiomas serão uma medida separada em toda a série, sem emendar as duas fontes como se fossem uma variável homogênea. As versões exatas de todas as coleções serão fixadas e registradas antes da aquisição.

**Limitação central para a hipótese principal:** o ERA5 prescreve uso do solo e tipos/frações de vegetação sem evolução temporal, embora haja variação sazonal do índice de área foliar. Assim, não se deve assumir que a reanálise incorporou diretamente a substituição local de floresta em cada ano. A hipótese continua investigável como associação nas séries representadas pelo ERA5; afirmar efeito biofísico local exige avaliação adicional com observações adequadas. Fonte: [ECMWF — descrição do ERA5 no centro de reanálises da OMM](https://confluence.ecmwf.int/spaces/GCR/pages/473842427/ECMWF%2BERA5).

O uso de um satélite de referência no BDQueimadas melhora a consistência, mas não elimina detecções repetidas do mesmo evento. A disponibilidade e as mudanças de plataforma devem ser auditadas; períodos incompatíveis serão identificados ou analisados separadamente.

## 4. Métricas e representação dos dados

Proposta operacional para a primeira versão do caderno:

| Variável | Derivados diários | Visualização principal |
| --- | --- | --- |
| Temperatura a 2 m | Média, mínimo, máximo e amplitude das amostras horárias | Série temporal e distribuição por mês |
| VPD | Média e máximo dos valores calculados hora a hora | Série temporal e mapa de anomalias |
| Umidade relativa | Média e mínimo dos valores horários derivados | Ciclo anual e relação com temperatura/VPD |
| Umidade específica | Média diária, derivada de ponto de orvalho e pressão | Estado multivariado e anomalias |
| Vento a 10 m | Média e máximo da velocidade horária; médias de u e v | Série e mapa vetorial de síntese |
| Precipitação | Total diário; acumulados antecedentes de 7, 30 e 90 dias | Barras, acumulados mensais e sequências secas |

Os extremos acima são os extremos das amostras horárias disponíveis, não necessariamente os extremos instantâneos reais. O máximo horário de velocidade do vento não será chamado de rajada. A média das velocidades é diferente da velocidade calculada a partir das componentes médias. VPD e umidades serão calculados antes da agregação diária; não se presume equivalência entre transformar médias e fazer a média dos valores transformados.

Temperatura, ponto de orvalho, umidade relativa e VPD compartilham informação. Os gráficos podem mostrar todas essas grandezas, mas os modelos não tratarão suas associações como evidências independentes. Pressão integra o cálculo de umidade específica e não precisa se tornar outra resposta principal.

Para anomalias, a proposta é estimar um ciclo sazonal suave por célula usando 2001–2024 como referência interna, explicitamente identificada como climatologia do estudo. Preservar a série original e sua tendência; remoção de tendência, se utilizada, será uma variante separada. A futura extensão manterá uma versão calculada sobre a mesma referência para permitir comparação. Métodos de previsão, caso venham a existir, devem estimar transformações somente no conjunto de treinamento.

A regra para dia seco será precipitação diária inferior a 1 mm como convenção operacional proposta, acompanhada de análise de sensibilidade. Dias ausentes interrompem a classificação de uma sequência; não contam como secos. Acumulados anteriores a um foco excluem o próprio dia do foco. O limiar não será interpretado como limiar físico universal de incêndio.

## 5. Integração espacial e temporal

Cada ponto da grade terá um identificador estável e um polígono de agregação definido pelos pontos médios entre coordenadas vizinhas. A borda será recortada ao retângulo do estudo, registrando sua área efetiva. Esse polígono é uma convenção de integração espacial; não representa uma estação meteorológica nem precisão climática de 30 m. A grade distribuída em 0,25° é interpolada a partir de um modelo com resolução nativa aproximada de 31 km. Fonte: [ECMWF — ERA5](https://www.ecmwf.int/en/forecasts/dataset/ecmwf-reanalysis-v5).

Manter área total, área terrestre e área válida de cada célula. Frações terrestres usarão denominador terrestre válido explicitado. Água e ausência de classificação não serão contabilizadas como desmatamento. Para células de borda e com grandes rios, apresentar sensibilidades à cobertura terrestre e ao recorte. Pixels finos e polígonos serão ponderados pela área efetivamente intersectada, usando cálculo de área adequado.

Métricas de perturbação: cobertura florestal no início da janela, desmatamento acumulado e recente, fração anual queimada, recorrência e recência do fogo. Recorrência e tempo desde a última queima serão calculados na resolução do produto de fogo antes de serem resumidos na célula climática. Não confundir uma queima em qualquer ponto da célula com a queima de toda a célula. Locais sem fogo observado terão indicador próprio; seu tempo desde o último fogo será desconhecido/censurado, não zero.

A interseção desmatamento–fogo exigirá sobreposição espacial e ordem temporal identificável. Eventos datados apenas pelo ano não permitirão resolver a ordem dentro daquele ano. O histórico acumulado sempre terá uma data inicial declarada; não será chamado de histórico completo da paisagem.

O clima será apresentado em anos civis completos. O ano PRODES será preservado com seu intervalo agosto–julho e nunca convertido em desmatamento diário por interpolação. Para a pergunta principal, somente informação referente a intervalos encerrados antes da janela de resposta poderá definir sua perturbação antecedente. O gradiente final observado em 2024 poderá ilustrar a paisagem, mas não representar exposição antecedente de 2001.

Proposta para o dia meteorológico: 00h–24h em UTC−03:00 fixo, identificado nos gráficos, preservando UTC nos dados originais. Incluir as horas adicionais necessárias nas bordas do período e verificar o intervalo representado pela precipitação acumulada. Cada estatística diária registrará a contagem de horas válidas; dias incompletos serão sinalizados, sem preencher totais de chuva com zero.

## 6. Sequência didática do caderno

1. **Pergunta, região e período:** mapa de localização Brasil → Pará → Baixo Tapajós, com caixa de estudo, grade, rios, municípios e áreas protegidas disponíveis.
2. **O que cada base mede:** catálogo com unidades, resolução, calendário, versão e cobertura real; explicação do cubo tempo × latitude × longitude.
3. **Plano de aquisição:** inventário do que já existe, estimativa de volume e requisições mensais; aquisição habilitada explicitamente na futura implementação.
4. **Qualidade:** calendário de disponibilidade, duplicações, lacunas, unidades e contagens; diferenças entre dado ausente e valor zero.
5. **Da hora ao dia:** exemplo curto com os valores horários e o resumo diário da mesma célula, incluindo cálculos de VPD, vento e chuva.
6. **Séries de 2001–2024:** painéis alinhados de temperatura, VPD, umidade, vento e precipitação; seleção identificada de célula e média regional ponderada pela área.
7. **Sazonalidade e anomalias:** ciclo dos 12 meses e matriz ano × mês; médias para variáveis de estado e totais para precipitação.
8. **Paisagem e perturbação:** mapas comparáveis e séries anuais de cobertura, desmatamento e área queimada, respeitando os períodos próprios.
9. **Comparações exploratórias:** dispersões de perturbação antecedente × descritor climático, com célula, janela e tamanho amostral identificados.
10. **Contexto dos focos:** meteorologia anterior às detecções, com dias de comparação da mesma célula e época; dependência entre focos explicitada.
11. **Interpretação em Markdown:** o que cada figura mostra, quais comparações permite e quais limitações afetam a conclusão.

Os gráficos científicos serão exportáveis. Funções de download, validação e integração ficarão nos módulos Python; o notebook mostrará parâmetros, chamadas legíveis, transformações didáticas e figuras. O laboratório sintético continuará como referência instrumental; descritores não lineares dos dados reais constituem uma etapa posterior à exploração e aos testes de adequação.

## 7. Comparabilidade e métodos posteriores

Não usar os resultados climáticos para definir as classes de perturbação. A seleção de comparáveis considerará localização, relevo, água e condições de fundo justificadas; evitar ajustar por respostas climáticas posteriores que possam fazer parte do efeito investigado. Células vizinhas e dias consecutivos não serão tratados como réplicas independentes. Reportar número de células e blocos, além do número de linhas da tabela.

Descritores iniciais: nível médio, extremos amostrados, dispersão e persistência nas séries diárias. Análises de recorrência, Lyapunov e dimensão de correlação exigem validação prévia com sistemas sintéticos e séries substitutas. A duração mínima de janela será definida por experimentos de convergência e sensibilidade, antes de procurar relações com perturbação. Não fixar uma janela apenas porque produz a associação esperada.

Fragmentação e modelos mais extensos ficam para a fase seguinte. A disponibilidade de apenas algumas dezenas de células pode limitar a comparação espacial; a auditoria deve verificar se há diversidade de perturbação e comparáveis suficientes antes de prometer inferência estatística.

## 8. Escala e verificação antes da aquisição

O primeiro ciclo de implementação deverá gerar o mapa do retângulo proposto e um inventário das fontes, sem solicitar automaticamente a série histórica. Um teste técnico curto servirá para medir volume real, validar unidades/tempo e testar a retomada por mês antes de escalar para 2001–2024.

A extensão para 1985–2024 reutilizará identificadores de células, interfaces e referência climática. Não pressupõe que PRODES anual por célula, focos ou DETER existam em todo o intervalo. Métricas de história anterior exigem anos de apoio: por exemplo, o estado inicial de 2001 requer cobertura anterior, e chuva antecedente de 90 dias exige dados meteorológicos anteriores ao primeiro dia analisado. Quando faltar esse apoio, a métrica será marcada como indisponível.

Downloads futuros terão manifestos com fonte, produto/coleção, período, área, parâmetros, tamanho e checksum. Dados brutos serão preservados e derivados terão proveniência. Validar coordenadas, unidades, calendário, área, disponibilidade e reexecução do notebook antes da entrega. O plano de aquisição deverá distinguir tamanho em disco, memória de processamento e número de requisições.

## 9. Referências institucionais complementares

- [MapBiomas — Cobertura e Uso da Terra](https://brasil.mapbiomas.org/iniciativas-e-produtos/cobertura-e-uso-da-terra/cobertura-30m/cobertura/): série anual de cobertura e documentação do produto.
- [MapBiomas Fogo — Coleção 4](https://brasil.mapbiomas.org/event/lancamento-mapbiomas-fogo-colecao-4/): cobertura 1985–2024 discutida no projeto.
- [INPE — DETER](https://www.gov.br/inpe/pt-br/area-conhecimento/unidade-amazonia/projetos-e-pesquisas/deter/deter): finalidade dos alertas e diferença entre detecção e ocorrência.
- [INPE — Programa Queimadas, dados abertos](https://terrabrasilis.dpi.inpe.br/queimadas/portal/dados-abertos/): acesso aos registros de focos.

## 10. Estado da consolidação

As decisões da seção 2 e a hierarquia das perguntas foram aprovadas na conversa. Regras operacionais, sequência de figuras e tratamento das limitações foram concretizados neste documento para orientar a implementação e a discussão com o professor. Nenhum resultado empírico foi produzido nesta etapa. A configuração atual ainda declara resolução horária principal e deverá ser alinhada à decisão diária quando começar a implementação.
