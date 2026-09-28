from __future__ import annotations

import geopandas as gpd
import pandas as pd

from amazon_chaos.preprocess.spatial import add_area_km2


def summarize_deter(
    clipped: gpd.GeoDataFrame,
    class_column: str = "classname",
    equal_area_crs: str = "EPSG:6933",
) -> pd.DataFrame:
    """Summarize DETER by class using clipped polygon area, not polygon count alone."""
    if clipped.empty:
        return pd.DataFrame(columns=[class_column, "n_alerts", "area_km2"])
    gdf = add_area_km2(clipped, equal_area_crs)
    if class_column not in gdf.columns:
        candidates = [c for c in gdf.columns if "class" in c.lower()]
        if len(candidates) != 1:
            raise KeyError(f"Could not infer DETER class column. Candidates: {candidates}")
        class_column = candidates[0]
    return (
        gdf.groupby(class_column, dropna=False)
        .agg(n_alerts=(class_column, "size"), area_km2=("area_km2", "sum"))
        .reset_index()
        .sort_values("area_km2", ascending=False)
    )
