import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import Point, box

from amazon_chaos.preprocess.grid import build_grid
from amazon_chaos.preprocess.zonal import class_areas, pixel_area_km2, point_counts, polygon_areas


def test_pixel_area_matches_equal_area_projection():
    transform = from_origin(-56.0, -3.0, 0.01, 0.01)
    rows = np.arange(25)
    total = pixel_area_km2(transform, rows).sum() * 25
    exact = gpd.GeoSeries([box(-56.0, -3.25, -55.75, -3.0)], crs=4326).to_crs(6933).area[0] / 1e6
    assert total == pytest.approx(exact, rel=1e-4)


def test_class_areas_split_raster_by_cell_and_class(tmp_path):
    # células de 0,25° recortadas pela caixa; raster de 0,005° (as bordas de 0,125° caem
    # entre pixels) cobrindo a caixa inteira, com classe 3 a oeste de −55,75° e 15 a leste
    cells = build_grid([-3.0, -56.0, -3.25, -55.5])
    data = np.where(np.arange(100)[None, :] < 50, 3, 15).astype("uint8").repeat(50, axis=0)
    path = tmp_path / "raster.tif"
    with rasterio.open(path, "w", driver="GTiff", width=100, height=50, count=1, dtype="uint8",
                       crs="EPSG:4326", transform=from_origin(-56.0, -3.0, 0.005, 0.005)) as dst:
        dst.write(data, 1)
    areas = class_areas(str(path), cells, block=16).join(cells.set_index("cell_id"))
    assert (areas[areas.longitude == -56.0][15] == 0).all()
    assert (areas[areas.longitude == -55.5][3] == 0).all()
    middle = areas[areas.longitude == -55.75]
    assert np.allclose(middle[3], middle[15], rtol=1e-3)  # metade de cada lado
    assert np.allclose(areas[3] + areas[15], areas.area_km2, rtol=1e-3)


def test_polygon_areas_and_point_counts():
    cells = build_grid([-3.0, -56.0, -3.25, -55.75])
    polygons = gpd.GeoDataFrame({"ano": [2010, 2020]},
                                geometry=[box(-56.05, -3.1, -55.95, -3.0),
                                          box(-55.85, -3.2, -55.80, -3.15)], crs=4326)
    areas = polygon_areas(polygons, cells, by="ano")
    assert set(areas.columns) == {2010, 2020} and (areas.to_numpy() >= 0).all()
    points = gpd.GeoDataFrame(geometry=[Point(-55.9, -3.1), Point(-55.9, -3.1), Point(0, 0)],
                              crs=4326)
    counts = point_counts(points, cells)
    assert counts["count"].sum() == 2 and isinstance(counts, pd.DataFrame)


def test_polygonal_handles_mixed_collections_and_invalid_polygons():
    from shapely.geometry import GeometryCollection, LineString, Polygon

    from amazon_chaos.preprocess.zonal import polygonal

    bowtie = Polygon([(0, 0), (1, 1), (1, 0), (0, 1)])
    mixed = GeometryCollection([box(2, 2, 3, 3), LineString([(0, 0), (5, 5)])])
    frame = gpd.GeoDataFrame({"k": [1, 2, 3]}, geometry=[bowtie, mixed, box(4, 4, 5, 5)],
                             crs=3857)
    out = polygonal(frame)
    assert set(out.geom_type) == {"Polygon"} and out.k.tolist() == [1, 1, 2, 3]
    assert out.area.sum() == pytest.approx(2.5)
