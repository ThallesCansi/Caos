# Bacia do Xingu: recorte e aquisição histórica

## Recorte verificado

O objeto espacial é **toda a Bacia do Rio Xingu**, não a Região de Integração Xingu, o Parque Indígena do Xingu ou somente Altamira. Usamos a [BHB250 do IBGE/ANA](https://geoftp.ibge.gov.br/informacoes_ambientais/estudos_ambientais/bacias_e_divisoes_hidrograficas_do_brasil/2021/Bacias_Hidrograficas_do_Brasil_BHB250/vetores/), nível 3, `cod_otto=642`, edição 2021. O polígono oficial tem 508.626,96 km²; sua caixa é arredondada para a grade ERA5 em `[N,W,S,E]=[-1.25,-55.75,-15.00,-50.25]`. São 1.288 pontos no retângulo solicitado ao CDS; 779 células têm interseção positiva com a bacia. As interseções das células reproduzem 508.627 km² (arredondado). O código salva o polígono, a fração por célula, o arquivo original, hash SHA-256 e figura em `data/external/xingu`, `data/processed/xingu-era5-1990-2024` e `reports/figures/xingu_1990_2024`.

O CDS recebe uma caixa, portanto os arquivos brutos incluem células externas. Os derivados diários são mascarados pela bacia. Para médias regionais, pesar cada célula pela área efetiva `basin_km2`, jamais igualmente ou só pela fração sem considerar a área da célula.

## Por que 1990–2024?

A **análise principal permanece 2001–2024**, como decidido no [desenho do estudo](DESENHO_ESTUDO_2001_2024.md). O arquivo climático de **1990–2000** fornece onze anos completos anteriores à janela principal para testar dependência da climatologia, condições antecedentes e estabilidade dos descritores em janelas mais longas. 1990 é um corte operacional arredondado, não uma mudança ecológica demonstrada. A [cobertura anual do MapBiomas](https://brasil.mapbiomas.org/iniciativas-e-produtos/cobertura-e-uso-da-terra/cobertura-30m/cobertura/) começa em 1985, e o [ERA5 horário](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab=overview) cobre esse intervalo; assim, as fontes comportam a extensão. A escolha de 1990 reduz cinco anos de aquisição frente à expansão 1985–2024 já prevista, sem impedir essa expansão posterior. Não reclassificar 1990–2000 como período principal depois de ver resultados.

O histórico das demais fontes não terá a mesma cobertura: [PRODES/TerraBrasilis](https://terrabrasilis.dpi.inpe.br/faq/) agrega os incrementos geográficos de 1988–2007 e não permite uma série anual de polígonos por célula nesse trecho. MapBiomas, PRODES, fogo e DETER exigem versões, regras e aquisições próprias; este fluxo baixa apenas ERA5.

## Volume e limites

O plano de 1990-01-01 a 2024-12-31 gera **842 requisições CDS** (grupos de cinco variáveis instantâneas e precipitação, por mês, com dia UTC de apoio em 2025). São cerca de **2,371 bilhões de valores**, ou **8,83 GiB se cada valor usar 4 bytes**; isso não prediz o tamanho dos arquivos NetCDF, taxas de compressão, espaço temporário ou derivados. O processamento é anual para limitar memória. Antes de ampliar, confirme espaço local e throughput CDS com um mês completo. Cada requisição salva manifesto e SHA-256; reexecução reutiliza apenas cache validado.

## Executar

**Recomendado:** baixar pelo Earth Data Hub no HPC, sem a fila do CDS; ver [HPC_EDH.md](HPC_EDH.md). Os comandos abaixo usam o CDS.

Na raiz do projeto, com `.venv` sincronizado e termos do produto aceitos no CDS, a credencial colocada em `../.cdsapirc` é lida por `cdsapi` via `CDSAPI_RC` (sem copiá-la para o repositório):

```bash
export CDSAPI_RC=../.cdsapirc
uv run python scripts/prepare_xingu.py
uv run python scripts/build_xingu_notebook.py
uv run python -m amazon_chaos.pilot_cli plan 2024-01-01 2024-01-31 --config configs/xingu_1990_2024.yaml
uv run python -m amazon_chaos.pilot_cli download 2024-01-01 2024-01-31 --config configs/xingu_1990_2024.yaml
uv run python -m amazon_chaos.pilot_cli process 2024-01-01 2024-01-31 --config configs/xingu_1990_2024.yaml
```

Depois do mês de teste e da inspeção no `04_Bacia_Xingu_1990_2024.ipynb`:

```bash
uv run python -m amazon_chaos.pilot_cli download 1990-01-01 2024-12-31 --config configs/xingu_1990_2024.yaml
for year in $(seq 1990 2024); do
  uv run python -m amazon_chaos.pilot_cli process "$year-01-01" "$year-12-31" --config configs/xingu_1990_2024.yaml
done
```

O download integral é sequencial e retomável **entre requisições finalizadas**; a fila CDS de uma requisição interrompida não é persistida. Não executar o processamento de 35 anos em uma única chamada: o carregamento atual põe o intervalo solicitado na memória. O CLI existente não inclui MapBiomas, PRODES, fogo ou DETER.

## Próxima análise científica

A bacia atravessa um amplo gradiente norte–sul, de floresta úmida a cabeceiras no Cerrado. Médias da bacia inteira não são comparação entre áreas preservadas e perturbadas. Primeiro, classificar unidades espaciais independentemente da resposta climática, construir estratos Alto/Médio/Baixo Xingu ou comparáveis em clima de fundo e terreno, integrar as bases de perturbação e verificar completude. Só então comparar descritores dinâmicos, com autocorrelação espacial e temporal considerada. O notebook atual descreve mapa, aquisição e uma série regional quando houver dados; ainda não produz inferência sobre desmatamento ou caos.

## Execução iniciada em 29/09/2026

O teste de janeiro/2024 foi adquirido (4 NetCDF, 10,048 MiB), validado e processado. As 779 células intersectadas têm 31 dias completos para temperatura e precipitação. O caderno foi executado com o mapa, a série diária e os mapas de temperatura e chuva de janeiro. Essa análise é exploratória de um mês; não caracteriza a climatologia histórica.

A aquisição histórica continua em um processo iniciado no terminal do usuário com o comando integral acima. As duas unidades de serviço `amazon-chaos-xingu-early.service` e `amazon-chaos-xingu-late.service` foram paradas após a detecção desse processo, para evitar requisições e escrita duplicadas. Há também um teste isolado de uma requisição de dois dias com as seis variáveis juntas; ele usa a chave `all` e não altera o plano histórico até a validação dos dados recebidos.

Para verificar o processo ativo e os arquivos concluídos:

```bash
pgrep -af 'amazon_chaos.pilot_cli download'
find data/raw/xingu-era5-1990-2024/era5 -name manifest.json | wc -l
```

O plano histórico original tem 842 requisições; o teste de janeiro/2024 criou duas requisições parciais extras para o dia UTC de apoio. Se o terminal com o processo integral for encerrado ou a conexão cair, o comando integral na seção anterior retoma os manifestos validados. Para uma mudança futura ao plano combinado, primeiro validar todos os campos, horários e unidades contra os downloads separados já disponíveis e encerrar o processo antigo antes de reiniciar; não rodar duas instâncias históricas no mesmo diretório ao mesmo tempo.
