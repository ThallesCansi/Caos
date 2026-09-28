from __future__ import annotations

import geopandas as gpd
from shapely.geometry import box


def clip_bbox(gdf: gpd.GeoDataFrame, area_nwse: list[float]) -> gpd.GeoDataFrame:
    north, west, south, east = area_nwse
    if gdf.crs is None:
        raise ValueError("GeoDataFrame must have a CRS before clipping")
    geo = gdf.to_crs("EPSG:4674")
    geo.geometry = geo.geometry.make_valid()
    
    mask = gpd.GeoDataFrame(geometry=[box(west, south, east, north)], crs="EPSG:4674")
    return gpd.clip(geo, mask)


def add_area_km2(gdf: gpd.GeoDataFrame, equal_area_crs: str = "EPSG:6933") -> gpd.GeoDataFrame:
    out = gdf.copy()
    out["area_km2"] = out.to_crs(equal_area_crs).geometry.area / 1_000_000.0
    return out