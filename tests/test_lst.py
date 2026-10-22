import cftime
import numpy as np
import xarray as xr

from amazon_chaos.features.lst import good_quality


def test_quality_filter_keeps_best_pixels_decoded_as_nan():
    # 0 (melhor qualidade, decodificado como NaN), 1 (outra qualidade), 2 (nuvem),
    # 0b01000001 (erro ≤ 2 K) e 0b11000000 (erro > 3 K)
    qc = np.array([np.nan, 0, 1, 2, 0b01000001, 0b11000000])
    assert good_quality(qc).tolist() == [True, True, True, False, True, False]


def test_cftime_step_gives_month_and_year():
    times = [cftime.DatetimeJulian(2007, 7, 20)]
    ds = xr.Dataset(coords={"time": times})
    when = ds.isel(time=0).time.values.item()
    assert (when.month, when.year) == (7, 2007)
