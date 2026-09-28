# Piloto do Baixo Tapajós: como executar

O ponto de entrada didático é `03_Piloto_Tapajos_2024.ipynb`, na raiz do projeto. Selecione no VS Code o interpretador `.venv/bin/python` (ambiente do projeto). O notebook usa somente dados locais; reexecutá-lo não inicia downloads.

## Preparação

```bash
uv sync --dev
```

Configuração: `configs/tapajos_2024.yaml`. O período anual planejado é 2024; `test_start` e `test_end` definem janeiro/2024, usado na primeira execução do notebook. O antigo `configs/pilot.yaml` permanece para reproduzir o piloto anterior.

## Mapa antes da aquisição climática

```bash
uv run python -m amazon_chaos.pilot_cli map --download-context
```

A opção `--download-context` obtém explicitamente malhas municipais IBGE (2022), rios generalizados Natural Earth e limites atuais ICMBio/INDE. URLs, datas de acesso e checksums ficam em `data/external/tapajos`. Os estados brasileiros são reutilizados de `data/external/ibge_estados_minima.geojson`, já existente no projeto. Para redesenhar offline, execute o mesmo comando sem a opção.

Os nomes dos municípios aparecem dentro de suas geometrias e não indicam a posição das sedes urbanas. Verde identifica unidades de conservação federais, não uma classificação de floresta. Os limites atuais não representam automaticamente a configuração territorial histórica. Rios são linhas cartográficas, não uma máscara para calcular água/terra.

Mapa exportado em PNG e PDF: `reports/figures/tapajos_2024/01_regiao_grade.*`. Grade em GeoJSON: `data/processed/tapajos-era5-2024/grid.geojson`.

## Planejar e baixar janeiro/2024

```bash
uv run python -m amazon_chaos.pilot_cli plan 2024-01-01 2024-01-31
uv run python -m amazon_chaos.pilot_cli download 2024-01-01 2024-01-31
```

`plan` não usa rede nem credenciais. `download` usa a credencial CDS local; os termos do produto ERA5 precisam estar aceitos na conta do usuário. O programa não modifica credenciais nem aceita termos automaticamente.

São quatro requisições: janeiro instantâneo, janeiro precipitação, 1/fevereiro instantâneo e 1/fevereiro precipitação. O dia de apoio fecha a agregação local UTC−03. Os arquivos incluem horas adicionais, que não entram nas estatísticas de janeiro. O ano 2024 da configuração não é baixado automaticamente: o intervalo vem dos dois argumentos explícitos.

Os dados ficam em `data/raw/tapajos-era5-2024/era5`. Cada requisição tem um identificador calculado de produto, variáveis, área, dias e horários. Seu manifesto registra tamanho, SHA-256 e cobertura validada. Repetir o comando verifica e reutiliza o cache sem solicitar novamente os arquivos completos. Um checksum inválido interrompe a execução para inspeção; dados brutos existentes não são apagados automaticamente. Transferências interrompidas são preservadas como `.part` e não contam como arquivos válidos. Retomada de requisição ainda na fila do CDS não é persistida: reexecutar após encerrar o processo pode submeter essa requisição novamente.

## Processar e visualizar

```bash
uv run python -m amazon_chaos.pilot_cli process 2024-01-01 2024-01-31
```

Abra o notebook e execute as células. Os derivados possuem 31 dias × 7 latitudes × 8 longitudes. Médias, mínimos, máximos e contagens de horas são calculados em cada célula. Um dia com menos de 24 amostras finitas resulta em estatística ausente. O notebook exporta figuras, tabela da célula de demonstração e tabela de qualidade.

Para reconstruir o notebook a partir do roteiro Python, preservando uma cópia se tiver editado manualmente o `.ipynb`:

```bash
uv run python scripts/build_tapajos_notebook.py
```

Esse comando recria o notebook e remove suas saídas anteriores. A execução normal para explorar dados deve ser feita diretamente no Jupyter/VS Code.

## Escalar depois do teste

```bash
# Estes comandos ampliam a aquisição: executar na etapa do piloto anual.
uv run python -m amazon_chaos.pilot_cli plan 2024-01-01 2024-12-31
uv run python -m amazon_chaos.pilot_cli download 2024-01-01 2024-12-31
uv run python -m amazon_chaos.pilot_cli process 2024-01-01 2024-12-31
```

Janeiro completo é reutilizado. Requisições parciais e mensais completas têm identificadores diferentes; o dia de apoio de fevereiro não substitui uma requisição de fevereiro inteiro. O processamento carrega o intervalo solicitado na memória: para a série longa, processar por ano ou acrescentar uma etapa de combinação particionada antes de solicitar processamento de todos os anos de uma vez.

Os comandos não integram automaticamente MapBiomas, PRODES, BDQueimadas ou DETER. A aquisição dessas bases e a construção do gradiente espacial são a próxima entrega. A extensão temporal e os parâmetros do notebook devem ser atualizados conscientemente; janeiro não produz climatologia ou anomalias históricas.

## Verificação

```bash
uv run pytest
uv run ruff check src/amazon_chaos/io/era5_monthly.py src/amazon_chaos/preprocess/daily.py src/amazon_chaos/preprocess/grid.py src/amazon_chaos/pilot_maps.py src/amazon_chaos/pilot_cli.py tests/test_tapajos.py tests/test_era5_monthly.py
```

Testes usam dados sintéticos controlados para conferir calendário bissexto, virada de ano, chuva na fronteira do dia, lacunas, unidades, área e cache. Eles não são usados como dados reais no notebook. A execução integral do notebook verifica separadamente a integração com os arquivos adquiridos.
