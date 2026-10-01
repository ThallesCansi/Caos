import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import xarray as xr  # noqa: E402

from amazon_chaos.config import load_config  # noqa: E402
from amazon_chaos.preprocess.grid import build_grid  # noqa: E402
from amazon_chaos.regional import (  # noqa: E402
    VARIABLES,
    anomalies,
    longest_run,
    regional_frame,
    summarize,
    theil_sen,
)
from amazon_chaos.viz import map_cells, pt  # noqa: E402


def test_longest_run_per_cell():
    mask = np.array([[1, 0], [1, 1], [0, 1], [1, 1]], dtype=bool)[:, :, None]
    assert longest_run(mask)[:, 0].tolist() == [2, 3]


def test_anomalies_remove_seasonal_cycle():
    days = pd.date_range("1991-01-01", "2020-12-31")
    cycle = 3 * np.sin(2 * np.pi * days.dayofyear / 365.25)
    anomaly, normal = anomalies(pd.Series(cycle + 25, index=days))
    assert abs(anomaly).max() < 0.05
    assert len(normal) == 366


def test_theil_sen_per_decade():
    years = np.arange(1990, 2025, dtype=float)
    slope, p = theil_sen(0.03 * years + np.sin(years), years)
    assert abs(slope - 0.3) < 0.1 and p < 0.05
    assert np.isnan(theil_sen(np.full(5, np.nan), years[:5])[0])


def test_pt_numbers_keep_dates():
    assert pt("508,627 km² · +1.01 °C · 01/01/1990 · 1991–2020") == \
        "508.627 km² · +1,01 °C · 01/01/1990 · 1991–2020"


def test_map_colors_follow_vmin_vmax():
    cells = build_grid([-2.25, -56, -2.5, -55.75])
    field = xr.DataArray([[10.0, 20.0], [30.0, 40.0]], dims=("latitude", "longitude"),
                         coords={"latitude": [-2.25, -2.5], "longitude": [-56.0, -55.75]})
    fig, ax = plt.subplots()
    map_cells(ax, cells, field, "viridis", "x", vmin=0, vmax=100)
    collection = ax.collections[0]
    assert (collection.norm.vmin, collection.norm.vmax) == (0, 100)
    plt.close(fig)


def test_summarize_weights_and_cache(tmp_path):
    cfg = load_config("configs/tapajos_1990_2024.yaml")
    cfg["spatial"]["area"] = [-2.25, -56, -2.5, -55.75]
    base = tmp_path / cfg["experiment_id"]
    base.mkdir()
    for year in [2000, 2001]:
        days = pd.date_range(f"{year}-01-01", f"{year}-12-31")
        shape = (len(days), 2, 2)
        data = {var: (("time", "latitude", "longitude"), np.full(shape, 2.0, "float32"))
                for var, _ in VARIABLES.values()}
        data["precip_mm_sum"][1][:, 0, 0] = 0.0  # célula sempre seca
        xr.Dataset(data, coords={"time": days, "latitude": [-2.25, -2.5],
                                 "longitude": [-56.0, -55.75]}).to_netcdf(
            base / f"daily_{year}-01-01_{year}-12-31.nc")
    summary = summarize(cfg, 2000, 2001, root=tmp_path)
    frame = regional_frame(summary)
    assert len(frame) == 731 and np.allclose(frame.t2m, 2)
    assert int(summary.longest_dry_spell.sel(year=2000, latitude=-2.25, longitude=-56)) == 366
    assert float(summary.cell_precip.sel(latitude=-2.5, longitude=-55.75).isel(month=0)) == 62
    assert summarize(cfg, 2000, 2001, root=tmp_path).identical(summary)
