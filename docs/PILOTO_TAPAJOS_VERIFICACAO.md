# Registro de verificação — piloto do Baixo Tapajós

Data: 2026-09-08. Período climático processado: janeiro de 2024, dias locais UTC−03 fixo. Este registro descreve a primeira entrega técnica, não o piloto anual ou a análise histórica concluídos.

## Entrega

- Notebook `03_Piloto_Tapajos_2024.ipynb`: 24 células, sendo 12 de código e 12 de Markdown; 12 células de código executadas, zero saídas de erro e nenhuma definição de função auxiliar no notebook.
- Configuração `configs/tapajos_2024.yaml`: retângulo [-2.25, -56.0, -3.75, -54.25].
- Grade: 56 pontos (7 latitudes × 8 longitudes), com polígonos de integração recortados à caixa e áreas em EPSG:6933.
- Aquisição: quatro NetCDF validados, aproximadamente 0,728 MiB, para janeiro completo e 1/fevereiro UTC de apoio. A medida corresponde aos NetCDF, excluindo cartografia, manifestos, figuras e derivados.
- Cubo bruto: 768 horas × 7 latitudes × 8 longitudes por variável. Cubo diário: 31 dias × 7 × 8.
- Completude: zero células/dias incompletos em todas as dez variáveis com contagem horária. Cada estatística diária usou 24 valores finitos.
- Retomada: reexecução da aquisição reconheceu os quatro arquivos como cache validado, sem novas requisições CDS.
- Seis figuras diferentes; mapa regional, séries diárias e mapas climáticos também exportados em PDF.

Os dados são reais do ERA5. As entradas sintéticas usadas em testes automatizados não integram o notebook.

## Cartografia

As malhas municipais pedidas como edição 2024 retornaram HTTP 500 no IBGE. A edição explícita 2022 foi consultada com sucesso para Santarém, Belterra e Mojuí dos Campos. A hidrografia de contexto contém os rios Amazonas e Tapajós, em escala generalizada Natural Earth 1:50 milhões.

O WFS oficial do ICMBio/INDE disponibilizou a camada `ICMBio:limiteucsfederais_a` (catálogo indicando agosto/2026). A consulta abrange a caixa e um entorno; algumas UCs listadas na tabela de contexto podem estar apenas nesse entorno. A Flona do Tapajós e a Resex Tapajós-Arapiuns aparecem no mapa do recorte. Esses limites atuais não foram utilizados para inferir proteção ou cobertura florestal histórica.

URLs, datas e hashes das respostas cartográficas estão nos arquivos JSON em `data/external/tapajos`. As requisições climáticas e checksums estão nos `manifest.json` de cada diretório de aquisição.

## Verificações executadas

- Suíte padrão: 14 testes passaram. Cobertura inclui os testes anteriores, calendário bissexto, virada de ano, chuva na fronteira local, ausência de horas, umidade, unidades, cobertura da grade, integridade de arquivos e retomada.
- Lint: passou para os sete módulos/arquivos de testes novos indicados no guia de execução.
- Notebook: execução integral via nbclient, validação nbformat e inspeção visual do mapa e dos mapas climáticos.
- CLI: planejamento sem download, aquisição real, reutilização do cache e processamento diário executados.

### Aviso de dependência

O pytest emite um `RuntimeWarning` de tamanho de `numpy.ndarray` ao importar a extensão binária `netCDF4._netCDF4` através do xarray. Ambiente observado: NumPy 2.4.6, netCDF4 1.7.4, xarray 2026.7.0, pandas 3.0.5. Transformar esse aviso em erro com `-W error::RuntimeWarning` interrompe os dois testes de NetCDF na importação. A suíte padrão, a leitura/validação dos quatro arquivos reais, a escrita dos derivados e a execução integral do notebook passaram.

O aviso permanece registrado; não foi suprimido por filtro no projeto nem tratado como incompatibilidade resolvida. Antes de escalar o processamento, é recomendável verificar a combinação binária do ambiente. Não houve erro de valores identificado nos testes desta entrega.

## Ajustes de implementação e próximos passos

A interface do piloto foi implementada em `amazon_chaos.pilot_cli`, executável com `uv run python -m amazon_chaos.pilot_cli`, para preservar o CLI anterior ERA5/DETER. Isso substitui os nomes de comandos inicialmente sugeridos no plano, sem alterar a separação entre planejamento, aquisição e processamento.

Os métodos não lineares e os conectores de MapBiomas/PRODES/focos não fazem parte deste primeiro teste climático. A próxima etapa é o piloto anual com integração das perturbações e máscara terrestre; só então avançar para comparações históricas e métodos dinâmicos.

O planejamento e os testes orientaram a separação das operações com rede, das transformações científicas e da visualização. A pasta não disponibiliza um repositório Git utilizável nesta sessão; não foram criados commits ou worktrees.
