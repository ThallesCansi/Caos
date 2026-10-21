import json
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import box
from typer.testing import CliRunner

from amazon_chaos.cli import app
from amazon_chaos.config import list_regions, load_region, merge
from amazon_chaos.regions import envelope, intersect_grid

CAIXA = Path(__file__).parent / "fixtures" / "regiao_caixa.yaml"


def test_merge_is_recursive_and_replaces_lists():
    base = {"a": {"x": 1, "y": [1, 2]}, "b": 1}
    out = merge(base, {"a": {"y": [3]}, "c": 2})
    assert out == {"a": {"x": 1, "y": [3]}, "b": 1, "c": 2}
    assert base["a"]["y"] == [1, 2]


def test_every_region_config_is_complete():
    regions = list_regions()
    assert {"xingu", "tapajos"} <= set(regions)
    for slug in regions:
        cfg = load_region(slug)
        assert cfg["slug"] == slug
        assert cfg["era5"]["variables"]["accum"] == ["total_precipitation"]
        assert cfg["time"]["science_start"].year == 2001
        assert "context_dir" in cfg["spatial"]


def test_region_defaults_and_overrides():
    tapajos = load_region("tapajos")
    assert tapajos["spatial"]["basin_source"] == "data/external/tapajos/limite.geojson"
    xingu = load_region("xingu")
    assert xingu["spatial"]["basin_source"].endswith("bacia_ibge_bhb250_2021.geojson")
    caixa = load_region(CAIXA)
    assert "basin_source" not in caixa["spatial"]
    assert caixa["context"]["layers"] == ["rios", "ucs"]
    with pytest.raises(FileNotFoundError, match="Disponíveis"):
        load_region("inexistente")


def test_envelope_snaps_outwards_and_grid_conserves_area():
    shape = box(-55.1, -3.9, -54.6, -3.3)
    assert envelope(shape) == [-3.25, -55.25, -4.0, -54.5]
    cfg = {"spatial": {"area": envelope(shape), "grid_degrees": 0.25}}
    limit = gpd.GeoDataFrame(geometry=[shape], crs="EPSG:4326")
    cells = intersect_grid(cfg, limit)
    assert cells.basin_fraction.between(0, 1).all()
    assert cells.basin_km2.sum() == pytest.approx(limit.to_crs("EPSG:6933").area.sum() / 1e6)


def test_cli_lists_regions_and_plans_without_network():
    runner = CliRunner()
    listed = runner.invoke(app, ["region", "list"])
    assert listed.exit_code == 0 and "xingu" in listed.stdout
    planned = runner.invoke(app, ["era5", "plan", str(CAIXA), "2024-01-01", "2024-01-31"])
    assert planned.exit_code == 0
    jobs = json.loads(planned.stdout)
    assert len(jobs) == 4 and jobs[-1]["request"]["month"] == ["02"]
