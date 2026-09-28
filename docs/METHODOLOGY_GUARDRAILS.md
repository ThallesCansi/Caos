# Guardrails metodológicos

1. **Lyapunov positivo ≠ prova automática de caos.**
2. **Caos ≠ tipping point.** São conceitos relacionados a dinâmica não linear, mas uma estimativa de sensibilidade não demonstra por si só aproximação de transição crítica.
3. **Reanálise ≠ observação pura.** ERA5 combina modelo e assimilação; interpretar a dinâmica da série considerando essa natureza.
4. **Sazonalidade pode criar geometria aparente.** Analisar série bruta e versões dessazonalizadas.
5. **Não otimizar `tau`, `m` ou preprocessing para obter o sinal desejado.** Pré-especificar grades/critérios e registrar todas as variantes relevantes.
6. **DETER não é a taxa oficial consolidada de desmatamento.** Usar como alerta/perturbação recente; priorizar PRODES/MapBiomas para estrutura histórica.
7. **Contagem de polígonos ≠ área perturbada.** Calcular área após clipping e em projeção adequada/equal-area.
8. **Comparação espacial ≠ causalidade.** Clima de fundo, localização e história territorial podem confundir o efeito.
9. **Evitar pseudorreplicação espacial.** Células vizinhas são autocorrelacionadas; considerar matching, blocos ou distância.
10. **Preservar resultados negativos.** Falha em rejeitar um surrogate ou instabilidade de estimativa é resultado.
11. **Dados brutos são imutáveis.** Qualquer correção gera novo derivado com proveniência.
12. **Análise final deve ser reproduzível a partir de configuração + manifest + commit.**
