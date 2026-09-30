"""Cria caderno leve para inspecionar a bacia e anos processados do Xingu."""

from pathlib import Path

import nbformat as nbf

cells = [
    nbf.v4.new_markdown_cell("""# Bacia do Xingu · ERA5 histórico

A bacia é o polígono BHB250/IBGE de código Otto 642. A aquisição ERA5 cobre o seu
retângulo envolvente; os derivados diários fora da bacia são mascarados. A janela
principal de comparação é 2001–2024 e o arquivo de apoio começa em 1990.
Este caderno lê arquivos locais e **não inicia downloads**.
"""),
    nbf.v4.new_code_cell("""from pathlib import Path
import json
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from IPython.display import display, Markdown
from amazon_chaos.config import load_config
from amazon_chaos.io.era5_monthly import plan_requests, job_directory

cfg = load_config('configs/xingu_1990_2024.yaml')
source = Path(cfg['spatial']['basin_source'])
cells_path = Path('data/processed') / cfg['experiment_id'] / 'basin_grid.geojson'
assert source.exists() and cells_path.exists(), 'Execute: uv run python scripts/prepare_xingu.py'
basin, cells = gpd.read_file(source), gpd.read_file(cells_path)
source_info = json.loads((source.parent / 'source.json').read_text())
display(Markdown(f"**Fonte:** {source_info['name']} · código Otto {source_info['cod_otto']} · "
                 f"{source_info['source_area_km2']:,.0f} km² · {len(cells)} células ERA5 "
                 'com interseção.'))
"""),
    nbf.v4.new_code_cell("""fig, ax = plt.subplots(figsize=(8, 11), layout='constrained')
basin.boundary.plot(ax=ax, color='#163f47', lw=1.4)
cells.boundary.plot(ax=ax, color='#889e9e', lw=.13)
ax.set(title='Bacia do Rio Xingu · BHB250/IBGE e grade ERA5 de 0,25°',
       xlabel='Longitude (°)', ylabel='Latitude (°)', aspect='equal')
plt.show()
display(cells[['cell_id', 'latitude', 'longitude', 'basin_fraction', 'basin_km2']].head(10))
"""),
    nbf.v4.new_markdown_cell("""## Plano e inventário de aquisição

Cada mês tem duas requisições: variáveis instantâneas e precipitação acumulada.
A primeira e a última borda temporal incluem horas UTC de apoio ao dia UTC−03.
O tamanho de 4 bytes por valor abaixo é apenas uma estimativa de dados numéricos;
compactação, metadados e derivados mudam o espaço real em disco.
"""),
    nbf.v4.new_code_cell("""jobs = plan_requests(cfg, '1990-01-01', '2024-12-31')
rows = []
for job in jobs:
    manifest = job_directory(cfg, job) / 'manifest.json'
    rows.append({'mês_UTC': job['month'], 'grupo': job['group'],
                 'situação': 'validado' if manifest.exists() else 'pendente',
                 'MiB': (sum(x['size_bytes'] for x in
                             json.loads(manifest.read_text())['files']) / 2**20)
                        if manifest.exists() else np.nan})
inventory = pd.DataFrame(rows)
display(inventory.groupby('situação').agg(requisições=('mês_UTC', 'size'), MiB=('MiB', 'sum')))
display(inventory.tail(8))
"""),
    nbf.v4.new_markdown_cell("""## Exploração de um ano processado

A série abaixo usa a média de temperatura ponderada pela área da bacia em cada célula.
Ela aparece após o teste de janeiro ou o processamento anual. Como a bacia percorre um
grande gradiente latitudinal e ecológico, a média deve ser acompanhada por mapas e
estratos Alto/Médio/Baixo Xingu antes de qualquer comparação causal.
"""),
    nbf.v4.new_code_cell("""year = 2024
base = Path('data/processed') / cfg['experiment_id']
path = base / f'daily_{year}-01-01_{year}-12-31.nc'
if not path.exists():
    path = base / f'daily_{year}-01-01_{year}-01-31.nc'
if not path.exists():
    display(Markdown(f'**Dados de {year} ainda não processados.** Veja `docs/XINGU.md`.'))
else:
    with xr.open_dataset(path) as ds:
        daily = ds.load()
    area = cells.pivot(index='latitude', columns='longitude', values='basin_km2')
    area = area.reindex(index=daily.latitude.values, columns=daily.longitude.values).fillna(0)
    weights = xr.DataArray(
        area.values, coords={'latitude': daily.latitude, 'longitude': daily.longitude},
        dims=('latitude', 'longitude'))
    regional = daily.t2m_c_mean.weighted(weights).mean(('latitude', 'longitude'))
    fig, ax = plt.subplots(figsize=(12, 3.5), layout='constrained')
    regional.plot(ax=ax, lw=.8)
    ax.set(title=f'Temperatura média diária na bacia · {path.stem}', xlabel='Dia local UTC−03',
           ylabel='Temperatura (°C)')
    fig.savefig('reports/figures/xingu_1990_2024/02_temperatura_diaria.png', dpi=170)
    plt.show()
    display(Markdown(f'**Dias disponíveis:** {int(regional.count())} de {regional.sizes["time"]}; '
                     f'**temperatura média da bacia:** {float(regional.mean()):.2f} °C.'))
"""),
    nbf.v4.new_markdown_cell("""## Contraste espacial no período disponível

Os mapas são resumos do intervalo carregado, ainda sem máscara detalhada de terra/água ou
histórico de perturbação. Um mês não define o clima médio da bacia.
"""),
    nbf.v4.new_code_cell("""if path.exists():
    summaries = [
        (daily.t2m_c_mean.mean('time'), 'Temperatura média (°C)', 'YlOrRd'),
        (daily.precip_mm_sum.sum('time', min_count=daily.sizes['time']),
         'Precipitação total (mm)', 'YlGnBu'),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(13, 10), layout='constrained')
    for ax, (field, title, cmap) in zip(axes, summaries):
        values = field.rename('value').to_dataframe().reset_index()
        mapped = cells.merge(values[['latitude', 'longitude', 'value']],
                             on=['latitude', 'longitude'])
        mapped.plot(column='value', ax=ax, cmap=cmap, legend=True, edgecolor='none',
                    legend_kwds={'shrink': .6})
        basin.boundary.plot(ax=ax, color='#163f47', lw=.7)
        ax.set(title=title, xlabel='Longitude (°)', ylabel='Latitude (°)', aspect='equal')
    fig.suptitle(f'Bacia do Xingu · {path.stem}', fontsize=14)
    fig.savefig('reports/figures/xingu_1990_2024/03_mapas_clima.png', dpi=170)
    plt.show()
"""),
]
notebook = nbf.v4.new_notebook(cells=cells, metadata={
    "kernelspec": {"display_name": "Python (TCC / uv)", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3.11"},
})
nbf.validate(notebook)
target = Path("04_Bacia_Xingu_1990_2024.ipynb")
nbf.write(notebook, target)
print(f"{target}: {len(cells)} células")
