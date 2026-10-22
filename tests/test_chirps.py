from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from amazon_chaos.config import load_region
from amazon_chaos.features.chirps import cell_precip, full_cells
from amazon_chaos.io.chirps import fetch, snapped_bounds, year_file

CAIXA = Path(__file__).parent / "fixtures" / "regiao_caixa.yaml"


def _global_year(path, year=2003):
    """NetCDF no formato do CHIRPS: latitude crescente, `precip`, oceano negativo."""
    lat = np.round(np.arange(-5.975, -0.975, 0.05), 3)
    lon = np.round(np.arange(-57.975, -52.975, 0.05), 3)
    days = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
    field = np.broadcast_to(lon[None, None, :] + 60.0, (len(days), len(lat), len(lon))).copy()
    field[:, :, :3] = -9999.0  # "oceano" a oeste
    field[10] = 0.0  # um dia seco em toda parte
    xr.Dataset({"precip": (("time", "latitude", "longitude"), field.astype("float32"))},
               coords={"time": days, "latitude": lat, "longitude": lon}).to_netcdf(path)
    return path


def test_snapped_bounds_contain_the_box_on_the_grid():
    west, south, east, north = snapped_bounds((-56.125, -3.875, -54.125, -2.125))
    assert (west, south, east, north) == (-56.2, -3.95, -54.05, -2.05)


def test_fetch_clips_flips_and_records_the_source(tmp_path, monkeypatch):
    import amazon_chaos.io.chirps as chirps

    source = _global_year(tmp_path / "global.nc")
    monkeypatch.setattr(chirps, "url", lambda year: str(source))
    root = tmp_path / "chirps"
    fetch((-56.125, -3.875, -54.125, -2.125), 2003, 2003, root=root, pause=0)
    with xr.open_dataset(year_file(2003, root)) as ds:
        lat = ds.latitude.values
        assert lat[0] > lat[-1]  # gravado de norte para sul
        assert ds.longitude.min() >= -56.2 and ds.longitude.max() <= -54.05
        assert ds.sizes["time"] == 365 and float(ds.precip_mm.isel(time=10).max()) == 0.0
        assert len(ds.attrs["source_sha256"]) == 64
    manifest = pd.read_csv(root / "manifest.csv")
    assert manifest.relative_path.tolist() == ["chirps-v3.0.sat.2003.nc"]
    assert source.exists()  # um arquivo local de origem não é apagado


def test_incomplete_year_is_not_written(tmp_path):
    from amazon_chaos.io.chirps import fetch_year

    source = _global_year(tmp_path / "global.nc", year=2003)
    with pytest.raises(RuntimeError, match="dias"):
        fetch_year(2004, (-56.2, -3.95, -54.05, -2.05), root=tmp_path, source=str(source))
    assert not year_file(2004, tmp_path).exists()


def test_cell_mean_covers_the_whole_cell_and_weights_by_area(tmp_path, monkeypatch):
    import amazon_chaos.io.chirps as chirps

    cfg = load_region(CAIXA)
    cells = full_cells(cfg)
    assert np.allclose((cells.bounds.maxx - cells.bounds.minx), 0.25)
    source = _global_year(tmp_path / "global.nc")
    monkeypatch.setattr(chirps, "url", lambda year: str(source))
    root = tmp_path / "chirps"
    fetch(cells.total_bounds, 2003, 2003, root=root, pause=0)
    table = cell_precip(cfg, 2003, 2003, root=root)
    assert table.shape == (365, len(cells))
    # o campo é linear na longitude: a média da célula inteira é o valor no centro
    expected = cells.set_index("cell_id").longitude + 60.0
    assert np.allclose(table.iloc[0], expected.loc[table.columns], atol=1e-4)
    assert (table.iloc[10] == 0).all()


def test_dither_breaks_ties_but_keeps_distinct_order():
    from amazon_chaos.nonlinear.precip import dither

    x = np.array([0.0, 0.0, 0.0, 2.5, 0.0, 7.1, 7.1, 0.3])
    y = dither(x, seed=1)
    assert len(np.unique(y)) == len(y)
    distinct = np.abs(x[:, None] - x[None, :]) > 1e-6
    assert (np.sign(y[:, None] - y[None, :]) == np.sign(x[:, None] - x[None, :]))[distinct].all()
    assert np.array_equal(dither(x, seed=1), y)


def test_precip_cell_task_gives_ordinal_rows_per_source_and_window():
    from amazon_chaos.nonlinear.precip import DESCRIPTORS, cell_task
    from amazon_chaos.nonlinear.suite import load_spec

    spec = load_spec()
    spec["surrogates"] = {**spec["surrogates"], "per_cell": 3, "max_iter": 5}
    days = pd.date_range("2001-01-01", "2024-12-31", freq="D")
    rng = np.random.default_rng(0)
    rain = np.where(rng.random(len(days)) < 0.6, 0.0, rng.gamma(0.8, 8.0, len(days)))
    table = cell_task(spec, "ERA5_-003.00_-055.00", {"precip_chirps": pd.Series(rain, days)})
    assert set(table.descriptor) == set(DESCRIPTORS)
    assert set(table.window) == {"2001_2024", "2001_2012", "2013_2024"}
    assert table.zero_fraction.between(0.55, 0.65).all() and table.n_null.eq(3).all()
