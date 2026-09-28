# Plano de implementação: piloto do Baixo Tapajós

**Objetivo:** produzir mapa revisável, aquisição ERA5 mensal retomável e notebook Jupyter executado para o teste de janeiro de 2024.

**Arquitetura:** configuração própria preserva o piloto anterior. Módulos Python cuidam de aquisição, grade, qualidade e agregação; o notebook contém narrativa, parâmetros, chamadas e gráficos. Execução nesta sessão pelo agente principal, conforme preferência já estabelecida.

**Tecnologias:** Python, xarray, pandas, geopandas, matplotlib, cdsapi, nbformat, nbclient e pytest.

**Especificação:** `docs/DESENHO_ESTUDO_2001_2024.md`. Este ciclo implementa a preparação espacial e o teste climático; o piloto anual e a integração das perturbações são as etapas seguintes.

## Restrições

- Recorte [N,W,S,E] = [-2.25,-56.00,-3.75,-54.25], grade 0,25°.
- Estudo 2001–2024, expansão futura 1985–2024; teste atual janeiro/2024.
- Dados horários originais em UTC; dia derivado UTC−03 fixo.
- Precipitação representa a hora terminada no timestamp; horas de borda incluídas.
- Aquisição explícita; reexecutar o notebook não solicita dados remotos.
- Arquivos antigos preservados; cache novo identifica requisição e valida arquivo antes de reutilizar.
- Sem Git disponível nesta pasta: sem commits ou worktrees neste ciclo.

## Tarefas e verificação

- [x] Configuração e grade: criar `configs/tapajos_2024.yaml` e `src/amazon_chaos/preprocess/grid.py`. Testar cobertura exata da caixa, área positiva, 56 células e bordas parciais em `tests/test_tapajos.py`.
- [x] Aquisição: criar `src/amazon_chaos/io/era5_monthly.py`. Interface `plan_requests(config, start, end)` gera requisições mensais com apoio temporal; `download_plan(config, start, end)` valida coordenadas, variáveis, tempo, unidades e checksum. Testar fevereiro bissexto, virada de ano, cache, truncamento e rejeição de produto/região incompatíveis.
- [x] Transformações: criar `src/amazon_chaos/preprocess/daily.py`. Interface `derive_hourly(ds)` calcula umidades/VPD/vento; `daily_statistics(ds, start, end, utc_offset_hours=-3)` devolve estatísticas e contagem de horas por variável. Testar fronteira local, 24 mm de chuva para 24 horas de 1 mm, dia incompleto NaN, extremos e umidade saturada.
- [x] Interface: acrescentar comandos `era5-plan`, `era5-download`, `era5-process` e `tapajos-map` ao CLI. Planejamento deve funcionar sem credencial e não realizar rede; download deve exigir período explícito.
- [x] Cartografia: criar `src/amazon_chaos/pilot_maps.py`, com fontes/cache identificados, mapa Brasil/Pará/recorte e grade exportada. Limites simplificados servem ao contexto, não a cálculo de cobertura terrestre.
- [x] Teste real: obter somente janeiro/2024 e horas de apoio, registrar volume e cobertura, executar retomada para comprovar reutilização. Em falha externa, registrar exatamente o bloqueio e entregar mapa e caderno utilizáveis com diagnóstico.
- [x] Notebook: criar `03_Piloto_Tapajos_2024.ipynb` com Markdown em português, mapa, inventário, cubo, controle de qualidade, exemplo hora→dia, séries e mapas; exportar PNG/PDF. Acrescentar dependências Jupyter ao projeto e instruções reproduzíveis.
- [x] Verificação: executar `uv run pytest`, lint dos arquivos alterados e execução integral do notebook; inspecionar os mapas e registrar resultados reais.

## Casos de teste independentes

```python
# Datas exatas: janeiro local requer também 1 de fevereiro UTC.
jobs = plan_requests(config, "2024-01-01", "2024-01-31")
assert len(jobs) == 4  # dois grupos, janeiro e dia de apoio em fevereiro
# A célula na borda norte/oeste tem um quarto da área angular de uma interior.
assert len(build_grid([-2.25, -56, -3.75, -54.25])) == 56
# Chuva de 1 mm/h entre 04 UTC e 03 UTC do dia seguinte soma 24 mm no dia local.
# Remover uma dessas horas torna o total diário indisponível e sua contagem 23.
```

As verificações usarão NetCDF sintético apenas nos testes, explicitamente separado dos dados reais no notebook. Aquisição e processamento serão testados antes da requisição externa.
