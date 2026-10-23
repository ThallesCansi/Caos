"""Fração de cada célula em Terras Indígenas e Unidades de Conservação federais (D-026).

As camadas são as de contexto do caderno 02 (FUNAI e ICMBio, limites atuais). A área é a
interseção com o polígono recortado da célula, em projeção de área igual, e a fração usa a
área da célula dentro da bacia; a união das duas camadas não conta duas vezes a sobreposição
entre TI e UC.
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd

from amazon_chaos import regions
from amazon_chaos.preprocess.zonal import polygon_areas

CLASSES = {"ti": "Terra Indígena", "uc": "Unidade de Conservação federal",
           "fora": "fora de áreas protegidas"}


def protection(cfg) -> pd.DataFrame:
    """Frações de TI, UC e da união das duas, por célula; e a classe dominante."""
    cells = regions.cells(cfg)
    context = regions.load_context(cfg)
    out = pd.DataFrame(index=pd.Index(cells.cell_id, name="cell_id"))
    shapes = {}
    for key, layer in (("ti", "tis"), ("uc", "ucs")):
        shapes[key] = context[layer][["geometry"]].to_crs("EPSG:4326")
        out[f"frac_{key}"] = polygon_areas(shapes[key], cells).km2.to_numpy()
    union = gpd.GeoDataFrame(geometry=[pd.concat(shapes.values()).union_all()], crs="EPSG:4326")
    out["frac_protegida"] = polygon_areas(union, cells).km2.to_numpy()
    area = cells.set_index("cell_id").weight_km2
    for column in ("frac_ti", "frac_uc", "frac_protegida"):
        out[column] = (out[column] / area).clip(upper=1)
    out["classe"] = "mista"
    out.loc[out.frac_protegida < 0.1, "classe"] = "fora"
    out.loc[(out.frac_ti >= 0.5) & (out.frac_ti >= out.frac_uc), "classe"] = "ti"
    out.loc[(out.frac_uc >= 0.5) & (out.frac_uc > out.frac_ti), "classe"] = "uc"
    return out
