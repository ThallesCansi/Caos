# Protocolo de dados substitutos — notebook 06

## Integração e auditoria local

Foram inspecionados README, RESEARCH_PLAN, notebooks regionais 04/05, laboratório,
gerador regional, módulos de leitura ERA5 CDS/EDH, agregação diária, anomalias,
resumos regionais, dependências e testes. A estrutura local corresponde ao projeto.
Os notebooks regionais e o laboratório não foram modificados.

No clone em 13/10/2026, `data/` contém somente `README.md` e `.gitkeep` nas cinco
subpastas. Não há NetCDF, série climática processada nem máscara espacial local.
Não foi feita aquisição de ERA5. O inventário produzido pelo notebook lista os
70 diários anuais esperados (35 por recorte), dois resumos opcionais e dois
arquivos espaciais do Xingu, com os caminhos exatos.

`regional.summarize` lê os diários anuais, pesa por área e grava os resumos.
`regional_frame` fornece nomes curtos: `t2m`, `precip`, umidade, VPD, vento,
pressão e outras variáveis. Temperatura é média em °C; chuva é total diário em
mm. `daily_statistics` exige 24 horas finitas e atribui precipitação acumulada
à hora/dia correto, usando dias locais UTC−3. A chuva regional é a média espacial
de totais diários, não a soma espacial de milímetros. Somar no tempo e ponderar
no espaço são operações físicas diferentes.

O adaptador reutiliza esse pipeline. Um resumo transferido sem os diários é
aceito com proveniência não verificável. A média ponderada existente renormaliza
pesos sobre células disponíveis: o resumo sozinho não permite certificar suporte
espacial constante. As interpretações climáticas permanecem exploratórias.
Não há um segundo pipeline de leitura/ETL ou aquisição.

## Hipóteses e escolhas pré-definidas

FT: processo linear gaussiano estacionário condicionado ao espectro observado.
IAAFT: transformação estática monotônica de processo linear gaussiano estacionário;
marginal exata e espectro aproximado. São hipóteses diferentes. Rejeitar nenhuma
delas demonstra caos determinístico.

Configuração padrão: diário, 2001–2024, normal climatológica 1991–2020, 199
substitutas, α=0,05 e semente 20261013. A família primária tem quatro hipóteses:
temperatura em anomalias × dois recortes × dois métodos, usando assimetria
temporal no atraso 1, com escore absoluto. A direção e os parâmetros antecedem
os resultados. Holm controla a família primária; testes bloqueados contam como
p=1 na correção, mantendo o p bruto ausente.

Chuva, versões originais, previsão por vizinhos, atrasos 7/30 e janelas
2001–2012/2013–2024 são exploratórios. BH é aplicado conjuntamente à família
climática exploratória; exemplos sintéticos e sensibilidade sintética recebem
correções em famílias separadas. A calibração por repetições mede o tamanho de
um teste individual, usando p bruto e intervalos binomiais exatos.

A previsão usa imersão 3, atraso 1, horizonte 1, cinco vizinhos e primeiros 60%
para treino. A exclusão de Theiler é 14 amostras, com separação adicional da
extensão do vetor e horizonte. Nenhum alvo de avaliação entra no treino.

O p inclusivo usa a correção +1; resolução mínima 0,005 com M=199. Comparação
absoluta da assimetria usa zero definido previamente. A biblioteca oferece
caudas superior/inferior e duas caudas por dobro do menor posto inclusivo.
Não se supõe distribuição normal das estatísticas.

FT conserva DC, Nyquist com sinal e o periodograma até arredondamento. IAAFT
retorna os postos exatos e informa erro relativo das amplitudes espectrais sem
DC, histórico de erro, iterações, tolerância e motivo de parada. Postos fixos
não significam erro zero. O alerta espectral 0,02 é heurístico; não valida a
calibração nem seleciona substitutas pelo resultado da estatística.

## Qualidade e estacionariedade

Índices incompletos, duplicados ou irregulares, valores não finitos, séries
constantes, unidades incompatíveis e precipitação negativa bloqueiam o teste.
Não se preenchem lacunas com zero. A normal precisa de uma referência completa.
Reutiliza-se `regional.anomalies`: suavização circular de 31 dias e dia ordinal
do ano (deslocamento bissexto após fevereiro, documentado como limitação).
Não se remove tendência automaticamente.

Diagnósticos combinam ADF, KPSS, tendência HAC, CUSUM descritivo, média, desvio
e ACF(1) em quatro blocos e momentos móveis. Os alertas de heterogeneidade são
heurísticos e não certificam estacionariedade. Sazonalidade de variância e
rupturas podem invalidar surrogates estacionários mesmo após retirar a média
sazonal. A opção semanal usa sete dias completos, somando chuva e tomando a
média da temperatura; descarta somente o bloco final incompleto. Meses de
duração desigual não são tratados como amostras físicas equidistantes.

## Reprodução

```bash
uv sync --frozen --dev
uv run --frozen pytest
uv run --frozen python scripts/build_surrogate_notebook.py --execute
uv run --frozen python scripts/build_surrogate_notebook.py --execute --quick --output reports/tmp/surrogates_quick.ipynb
```

O kernel é iniciado com o mesmo Python do uv. O caderno padrão na raiz guarda
saídas executadas. O gerador escreve apenas o notebook escolhido. A configuração,
versões, revisão Git, checksums do código/configurações/resumos disponíveis,
inventário, p brutos/ajustados, distribuições nulas e diagnósticos ficam em
`experiments/surrogates/<modo_hash>/`; as figuras ficam em
`reports/figures/surrogates/<modo_hash>/`. Reexecutar a mesma configuração
substitui seus derivados. O hash identifica a configuração; checksums permitem
detectar mudanças de código/dados. Para execução em ambiente isolado, copie o
diretório de resultados antes de atualizar código ou dados.

Sem dados locais, o ramo climático registra “não executado”. Não se produzem
figuras ou valores-p climáticos fictícios. O ramo de leitura foi exercitado
por fixtures sintéticas nos testes, sem apresentá-las como dados reais.

Controles padrão: branco gaussiano, AR(1) com φ=0,8 e descarte de transiente,
mapa logístico r=4 e exemplo fora da nula com ciclo/tendência/variância sazonal.
A calibração usa 40 repetições por controle estacionário e método, com 512
amostras. Sensibilidade usa 256/1024 amostras, ruído 0/0,3 e atrasos 1/7/30.
Isso evidencia limites de poder, sem exigir significância em toda simulação.

## Dados reais pendentes

Prefira transferir os diários/resumos já calculados no HPC, conforme
[HPC_EDH.md](HPC_EDH.md), seção 3. Para brutos já disponíveis, processe por ano:

```bash
uv run python -m amazon_chaos.pilot_cli process 2001-01-01 2001-12-31 --config configs/xingu_1990_2024.yaml --source edh
uv run python -m amazon_chaos.pilot_cli process 2001-01-01 2001-12-31 --config configs/tapajos_1990_2024.yaml --source edh
```

Nova aquisição é explícita e separada, documentada em HPC_EDH.md e na CLI
`edh-download`. Nenhum desses comandos de aquisição foi executado nesta tarefa.

## Validação executada em 13/10/2026

O notebook padrão `full_e57802a1f7` foi executado do início ao fim: 11 células
de código, nenhuma saída de erro, 199 substitutas por protocolo, 28 figuras e
95 CSVs. O modo rápido também executou todas as células sem erro em
`reports/tmp/surrogates_quick.ipynb`, com resultados separados em
`experiments/surrogates/quick_78bebeb64b/`. Essa pasta temporária é ignorada no Git.

Na calibração padrão (40 repetições por controle/método, 512 pontos):

| Controle | FT | IAAFT | Interpretação restrita às simulações |
|---|---:|---:|---|
| Branco gaussiano | 3/40 (7,5%) | 2/40 (5%) | IC95% inclui 5% em ambos |
| AR(1), φ=0,8 | 2/40 (5%) | 2/40 (5%) | IC95% inclui 5% em ambos |
| Logístico, r=4 | 40/40 | 40/40 | Poder observado; IC95% aproximadamente [91,2%, 100%] |

Os intervalos são largos: compatibilidade com 5% não prova calibração exata.
A sensibilidade ao atraso mostrou não rejeições no controle logístico em
atrasos 7/30; séries curtas também produziram alertas de erro espectral IAAFT.
Os resíduos ficaram registrados, sem descartar substitutas pelo valor-p.

`uv run --frozen pytest`: **57 testes passaram**, com sete avisos preexistentes
sobre metadados consolidados Zarr v3 nos testes ERA5. Ruff passou nos cinco
arquivos Python criados/modificados. `git diff --check` passou. Foram verificados
programaticamente o formato nbformat, a execução de todas as células, a ausência
de erros, os checksums dos arquivos e a ausência de valores-p nos 32 protocolos
climáticos não executados. As figuras de calibração e preservação foram inspecionadas.

Os testes cobrem FFT par/ímpar, DC, Nyquist, ACF circular, marginal e resíduos
IAAFT, empates, sementes, postos Monte Carlo, entradas inválidas, previsão
cronológica, agregação semanal física, cache regional, climatologia e sintaxe
de todas as células. A execução ERA5 e as figuras climáticas **não foram validadas
com dados reais**, porque os arquivos locais faltam. Fixtures de integração
permanecem estritamente sintéticas.

Além dos comandos de reprodução acima, foi executado:

```bash
uv run --frozen pytest tests/test_surrogates.py tests/test_surrogate_protocol.py
uv run --frozen ruff check src/amazon_chaos/nonlinear/surrogates.py src/amazon_chaos/nonlinear/statistics.py src/amazon_chaos/nonlinear/surrogate_study.py scripts/build_surrogate_notebook.py tests/test_surrogate_protocol.py
git diff --check
```

Arquivos de implementação: `nonlinear/surrogates.py` (ampliado),
`nonlinear/statistics.py`, `nonlinear/surrogate_study.py`,
`scripts/build_surrogate_notebook.py`, `tests/test_surrogate_protocol.py`,
notebook 06 e este documento. README foi atualizado; dependências e `uv.lock`
foram preservados. Não foram modificados dados brutos ou notebooks anteriores.

## Referências

- [Theiler et al. (1992)](https://doi.org/10.1016/0167-2789(92)90102-S).
- [Schreiber (1999)](https://doi.org/10.1016/S0370-1573(98)00035-0).
- [Schreiber e Schmitz (2000)](https://doi.org/10.1016/S0167-2789(00)00043-9).
- [Improved surrogate data](https://arxiv.org/abs/chao-dyn/9909041).
- [Surrogates não estacionários](https://arxiv.org/abs/chao-dyn/9904023).
- [Sivakumar (2000)](https://doi.org/10.1016/S0022-1694(99)00186-9).
- [Sivakumar et al. (2001)](https://doi.org/10.1080/02626660109492805).
