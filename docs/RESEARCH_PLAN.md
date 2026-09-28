# Plano científico e computacional

## Objetivo

Investigar a dinâmica não linear do sistema floresta-atmosfera amazônico e avaliar se descritores dinâmicos apresentam padrões robustamente associados a diferentes níveis de perturbação florestal.

## F0 — Infraestrutura e auditoria das bases

**Entregas**
- catálogo de fontes;
- pipeline de ERA5 e DETER funcionando;
- manifests/checksums;
- estrutura Git/uv/marimo;
- regras de unidades e tempo testadas.

**Gate**
Não escalar enquanto downloads, semântica temporal e proveniência não forem reproduzíveis.

## F1 — Definição da unidade espacial e da perturbação

Construir métricas de perturbação **sem usar os resultados climáticos**:

- fração de cobertura florestal histórica;
- perda acumulada de floresta;
- recência de desmatamento;
- frequência/intensidade de fogo;
- alertas recentes de degradação/desmatamento;
- fragmentação, se suportada por dados e tempo do projeto.

Produzir um gradiente ou classes (ex.: preservada/intermediária/fortemente perturbada) apenas depois de testar sensibilidade das métricas.

**Gate**
A classificação deve ser independente da variável-resposta dinâmica para evitar seleção circular.

## F2 — Seleção das regiões comparáveis

Não comparar aleatoriamente o oeste úmido com o sudeste seco e atribuir diferenças ao desmatamento. Construir pares/estratos comparáveis em clima médio, latitude/ecorregião ou outra variável de confusão disponível.

Saídas:
- mapa de células elegíveis;
- critérios de inclusão/exclusão;
- conjunto congelado de células para a primeira análise.

## F3 — Séries temporais climáticas

Para cada célula/região:

1. baixar ERA5 horário;
2. verificar regularidade e lacunas;
3. calcular variáveis derivadas;
4. guardar versões:
   - bruta;
   - anomalia do ciclo diurno;
   - anomalia sazonal;
5. documentar cada transformação.

A precipitação deve ser tratada como variável acumulada/intermitente e não assumir o mesmo pipeline de uma variável contínua.

## F4 — Validação dos métodos em sistemas conhecidos

Antes de interpretar a Amazônia:

### Controles positivos
- sistema de Lorenz em regime caótico;
- mapa logístico em regime caótico.

### Controles negativos / hipóteses nulas
- seno periódico;
- seno + ruído;
- AR(1)/red noise;
- ruído branco;
- série substituta preservando propriedades lineares relevantes.

O pipeline deve demonstrar onde funciona, onde falha e como depende de comprimento, ruído e amostragem.

## F5 — Reconstrução do espaço de fases

Para cada série elegível:

- estimar/candidatar atraso `tau`;
- estimar/candidatar dimensão `m`;
- reconstruir embedding;
- avaliar sensibilidade em uma grade de parâmetros;
- registrar parâmetros e critérios, nunca escolhê-los apenas porque produzem o resultado desejado.

## F6 — Descritores não lineares

Núcleo:
- maior expoente de Lyapunov;
- recurrence plots/RQA;
- dimensão de correlação quando a qualidade/comprimento permitirem;
- séries substitutas.

O resultado é uma distribuição/intervalo de descritores e sua robustez, não um único número mágico.

## F7 — Comparação entre gradientes de perturbação

Pergunta principal:

> Após controlar os principais fatores de confusão e o preprocessing, células/regiões mais perturbadas apresentam mudanças consistentes nos descritores dinâmicos em relação a áreas comparáveis mais preservadas?

Análises possíveis:
- comparação pareada;
- regressão dos descritores contra métricas contínuas de perturbação;
- análise por janelas temporais;
- sensibilidade espacial;
- bootstrap/intervalos de incerteza.

## F8 — Interpretação socioespacial

Relacionar os padrões ambientais a uso da terra, expansão agropecuária, infraestrutura, áreas protegidas, terras indígenas e demais dimensões previstas no TCC.

A camada socioespacial não deve ser usada apenas como “decoração de mapa”; ela serve para limitar e contextualizar a interpretação do mecanismo e da vulnerabilidade.

## Critérios de parada

O projeto deve aceitar resultados negativos. Exemplos:

- ERA5 pode não conter resolução adequada para determinada hipótese local;
- uma série pode ser dominada por sazonalidade/ruído;
- Lyapunov pode ser instável ao variar parâmetros;
- surrogates podem não permitir rejeitar uma hipótese linear estocástica;
- diferenças espaciais podem desaparecer após matching.

Um resultado desse tipo é cientificamente informativo e deve ser reportado, não “corrigido” até virar caos.
