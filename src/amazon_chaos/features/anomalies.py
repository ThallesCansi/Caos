from __future__ import annotations

import pandas as pd


def diurnal_anomaly(series: pd.Series) -> pd.Series:
    """Remove mean UTC hour-of-day cycle from a regular time-indexed series."""
    if not isinstance(series.index, pd.DatetimeIndex):
        raise TypeError("series must use DatetimeIndex")
    climatology = series.groupby(series.index.hour).transform("mean")
    return series - climatology


def monthly_anomaly(series: pd.Series) -> pd.Series:
    """Remove monthly climatological mean; initial coarse seasonal control."""
    if not isinstance(series.index, pd.DatetimeIndex):
        raise TypeError("series must use DatetimeIndex")
    climatology = series.groupby(series.index.month).transform("mean")
    return series - climatology
