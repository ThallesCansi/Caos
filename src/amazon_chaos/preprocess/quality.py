from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr


def qc_table(point: xr.Dataset, time_name: str) -> pd.DataFrame:
    df = point.to_dataframe().reset_index()
    rows = []
    for col in point.data_vars:
        s = df[col]
        rows.append(
            {
                "variable": col,
                "n": int(s.notna().sum()),
                "n_nan": int(s.isna().sum()),
                "missing_fraction": float(s.isna().mean()),
                "min": float(s.min()) if s.notna().any() else np.nan,
                "mean": float(s.mean()) if s.notna().any() else np.nan,
                "max": float(s.max()) if s.notna().any() else np.nan,
                "std": float(s.std()) if s.notna().any() else np.nan,
                "n_unique": int(s.nunique(dropna=True)),
            }
        )
    return pd.DataFrame(rows)


def time_regularity(point: xr.Dataset, time_name: str, expected: str = "1h") -> dict[str, object]:
    idx = pd.DatetimeIndex(point[time_name].values)
    diffs = idx.to_series().diff().dropna()
    expected_delta = pd.Timedelta(expected)
    return {
        "n_timestamps": len(idx),
        "monotonic_increasing": bool(idx.is_monotonic_increasing),
        "duplicates": int(idx.duplicated().sum()),
        "unexpected_steps": int((diffs != expected_delta).sum()),
        "modal_step": diffs.mode().iloc[0] if len(diffs) else None,
    }
