"""Os dados dos clipes, preparados uma vez e guardados em `reports/animacoes/dados/`.

Cada bacia vira um pacote pequeno: as células recortadas, o limite e os rios (GeoJSON) e os
campos animados (NetCDF, tempo × latitude × longitude). Assim a renderização, local ou no HPC,
não precisa dos dados diários nem das tabelas de perturbação.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import xarray as xr

from amazon_chaos import regional, regions
from amazon_chaos.config import load_region

DADOS = Path("reports/animacoes/dados")
BACIAS = {"tapajos": "Tapajós", "xingu": "Xingu"}  # de oeste para leste
NORMAL = ("1991-01-01", "2020-12-31")


@dataclass
class Bacia:
    slug: str
    nome: str
    celulas: gpd.GeoDataFrame  # polígonos recortados no limite, com latitude e longitude
    limite: gpd.GeoDataFrame
    rios: gpd.GeoDataFrame | None
    pesos: xr.DataArray  # km² de cada célula dentro da bacia (latitude × longitude)


def _geo(slug: str, nome: str, build) -> gpd.GeoDataFrame:
    path = DADOS / slug / f"{nome}.geojson"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        build().to_file(path, driver="GeoJSON")
    return gpd.read_file(path)


def bacia(slug: str) -> Bacia:
    """Geometria e pesos da bacia, do pacote (ou da região, na primeira vez)."""
    cfg = None

    def region():
        nonlocal cfg
        cfg = cfg or load_region(slug)
        return cfg

    celulas = _geo(slug, "celulas", lambda: regions.cells(region())[
        ["cell_id", "latitude", "longitude", "weight_km2", "geometry"]])
    limite = _geo(slug, "limite", lambda: regions.boundary(region())[["geometry"]])
    rios = _geo(slug, "rios", lambda: regions.load_context(region())["rios"][["geometry"]])
    pesos = (celulas.set_index(["latitude", "longitude"]).weight_km2.to_xarray()
             .fillna(0).rename("weight_km2"))
    return Bacia(slug, BACIAS[slug], celulas, limite, rios, pesos)


def _campo(slug: str, nome: str, build) -> xr.DataArray:
    path = DADOS / slug / f"{nome}.nc"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        provisorio = path.with_suffix(".tmp")  # um erro no meio não deixa arquivo pela metade
        build().to_netcdf(provisorio)
        provisorio.rename(path)
    with xr.open_dataarray(path) as cached:
        return cached.load()


def anomalia_mensal(campo: xr.DataArray, base=NORMAL) -> xr.DataArray:
    """Anomalia de cada mês em relação à média do mesmo mês do calendário no período base."""
    meses = campo.time.dt.month
    normal = campo.sel(time=slice(*base)).groupby("time.month").mean()
    return (campo.groupby(meses) - normal).drop_vars("month")


def anomalia(slug: str, variavel: str = "t2m") -> xr.DataArray:
    """Anomalia mensal por célula (ERA5, 1990–2024), do resumo regional."""
    def build():
        resumo = regional.summarize(load_region(slug), 1990, 2024)
        campo = resumo[f"cell_{variavel}"].rename(month="time")
        return anomalia_mensal(campo).rename(f"anomalia_{variavel}").astype("float32")

    return _campo(slug, f"anomalia_{variavel}", build)


def media(campo: xr.DataArray, pesos: xr.DataArray) -> np.ndarray:
    """Média da bacia, ponderada pela área de cada célula dentro dela."""
    pesos = pesos.reindex_like(campo.isel(time=0), fill_value=0).fillna(0)
    return campo.weighted(pesos).mean(("latitude", "longitude")).values


def _perturbacao(slug: str, nome: str):
    import pandas as pd

    from amazon_chaos.features.disturbance import out_dir

    return pd.read_parquet(out_dir(load_region(slug)) / f"{nome}.parquet")


def _grade(slug: str, tabela, tempos) -> xr.DataArray:
    """Tabela célula × tempo (índice cell_id) como campo tempo × latitude × longitude."""
    posicao = bacia(slug).celulas.set_index("cell_id")[["latitude", "longitude"]]
    longa = (tabela.set_axis(range(len(tempos)), axis=1).join(posicao)
             .set_index(["latitude", "longitude"]).stack().rename("v")
             .rename_axis(["latitude", "longitude", "time"]))
    campo = longa.to_xarray().transpose("time", "latitude", "longitude").astype("float32")
    return campo.assign_coords(time=np.asarray(tempos)[campo.time.values.astype(int)])


def terra(slug: str) -> xr.DataArray:
    """Área terrestre de cada célula em 2000 (km², MapBiomas), o denominador das frações."""
    def build():
        celulas = _perturbacao(slug, "celulas")
        return _grade(slug, celulas[["terra_km2_2000"]], [0]).isel(time=0, drop=True).rename(
            "terra_km2")

    return _campo(slug, "terra_km2", build)


def nao_floresta(slug: str) -> xr.DataArray:
    """Fração da terra que o PRODES classifica como não floresta (no Tapajós, o Cerrado)."""
    def build():
        celulas = _perturbacao(slug, "celulas")
        return _grade(slug, celulas[["prodes_nao_floresta_frac"]], [0]).isel(
            time=0, drop=True).rename("nao_floresta_frac")

    return _campo(slug, "nao_floresta_frac", build)


def focos(slug: str) -> xr.DataArray:
    """Focos de fogo por 100 km² de terra, em cada célula e mês (BDQueimadas, 2003–2024)."""
    import pandas as pd

    def build():
        tabela = _perturbacao(slug, "focos_mensais")
        contagem = _grade(slug, tabela, pd.to_datetime(tabela.columns))
        return (100 * contagem / terra(slug)).rename("focos_100km2")

    return _campo(slug, "focos_100km2", build)


def desmatamento(slug: str) -> xr.DataArray:
    """Fração da terra desmatada até cada ano (PRODES): o bloco até 2007 mais os anuais.

    O bloco de 1988–2007 não é repartido por ano (é como o PRODES o entrega), então a série
    começa em 2007. O ano do PRODES vai de agosto a julho e leva o nome do ano em que termina.
    """
    import pandas as pd

    def build():
        anual = _perturbacao(slug, "prodes_anual")
        anual.columns = anual.columns.astype(int)
        anual = anual.loc[:, 2008:2024]
        ate_2007 = _perturbacao(slug, "prodes_acumulado_2007")["km2"]
        acumulado = pd.concat([ate_2007.rename(2007), anual], axis=1).cumsum(axis=1)
        tempos = pd.to_datetime([f"{a}-07-31" for a in acumulado.columns])
        return (_grade(slug, acumulado, tempos) / terra(slug)).clip(max=1).rename(
            "desmatamento_frac")

    return _campo(slug, "desmatamento_frac", build)


def climatologia(slug: str, variavel: str = "precip", base=NORMAL, janela: int = 31):
    """O ano médio de cada célula: média de cada dia do calendário na normal, suavizada por
    uma média móvel circular de `janela` dias (como em `regional.anomalies`). 365 dias, com o
    eixo do tempo num ano não bissexto qualquer (2001), só para dar nome aos dias."""
    import pandas as pd

    nome, _ = regional.VARIABLES[variavel]

    def build():
        primeiro, ultimo = int(base[0][:4]), int(base[1][:4])
        soma, n = 0, 0
        for path in regional.daily_files(load_region(slug), primeiro, ultimo):
            with xr.open_dataset(path) as ds:
                ano = ds[nome].load()
            ano = ano.sel(time=~((ano.time.dt.month == 2) & (ano.time.dt.day == 29)))
            soma = soma + ano.values
            n += 1
        media_dia = soma / n
        estendido = np.concatenate([media_dia[-janela:], media_dia, media_dia[:janela]])
        suave = (pd.DataFrame(estendido.reshape(len(estendido), -1))
                 .rolling(janela, center=True).mean().values[janela:-janela])
        return xr.DataArray(
            suave.reshape(media_dia.shape).astype("float32"),
            coords={"time": pd.date_range("2001-01-01", periods=365),
                    "latitude": ano.latitude.values, "longitude": ano.longitude.values},
            dims=("time", "latitude", "longitude"), name=f"climatologia_{variavel}",
        ).where(bacia(slug).pesos.reindex_like(ano.isel(time=0), fill_value=0) > 0)

    return _campo(slug, f"climatologia_{variavel}", build)


def takens(slug: str = "xingu", variavel: str = "t2m") -> Path:
    """A série da bacia (anomalia padronizada, 2001–2024) e uma substituta IAAFT dela, em .npz,
    para a cena do Manim, que roda num ambiente sem as dependências de dados do projeto."""
    path = DADOS / slug / f"takens_{variavel}.npz"
    if not path.exists():
        from amazon_chaos.nonlinear import basin_test
        from amazon_chaos.nonlinear.suite import load_spec
        from amazon_chaos.nonlinear.surrogates import iaaft_surrogate

        x = basin_test.basin_series(load_region(slug), variavel, load_spec()).to_numpy()
        substituta = iaaft_surrogate(x, np.random.default_rng(0), max_iter=200).values
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(path, serie=x, substituta=substituta)
    return path
