"""Polígonos de integração em torno de centros ERA5; não refinam o clima."""

import geopandas as gpd
import numpy as np
from shapely.geometry import box


def grid_coordinates(area, step=0.25):
    north, west, south, east = map(float, area)
    if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise ValueError("Área inválida: usar [N, W, S, E], sem cruzar o antimeridiano")
    if step != 0.25 or not np.allclose(np.asarray(area) / step, np.round(np.asarray(area) / step)):
        raise ValueError("Este piloto requer limites alinhados à grade ERA5 de 0,25°")
    return (
        np.round(np.arange(north, south - step / 2, -step), 6),
        np.round(np.arange(west, east + step / 2, step), 6),
    )


def build_grid(area, step=0.25):
    latitudes, longitudes = grid_coordinates(area, step)
    north, west, south, east = area
    mask = box(west, south, east, north)
    rows = []
    for lat in latitudes:
        for lon in longitudes:
            geom = box(lon - step / 2, lat - step / 2, lon + step / 2, lat + step / 2).intersection(
                mask
            )
            rows.append(
                {
                    "cell_id": f"ERA5_{lat:+07.2f}_{lon:+08.2f}",
                    "latitude": lat,
                    "longitude": lon,
                    "geometry": geom,
                    "edge_fraction": geom.area / step**2,
                }
            )
    out = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    out["area_km2"] = out.to_crs("EPSG:6933").area / 1e6
    return out
