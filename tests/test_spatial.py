import geopandas as gpd
from shapely.geometry import box

from amazon_chaos.preprocess.spatial import add_area_km2, clip_bbox


def test_clip_bbox_reduces_geometry():
    gdf = gpd.GeoDataFrame({"id": [1]}, geometry=[box(-56, -4, -53, -1)], crs="EPSG:4674")
    clipped = clip_bbox(gdf, [-2, -55, -3, -54])
    assert len(clipped) == 1
    areas = add_area_km2(clipped)
    assert float(areas["area_km2"].iloc[0]) > 0
