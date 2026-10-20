"""Local-data adapter and diagnostics for notebook 06 (no acquisition)."""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import xarray as xr
from statsmodels.stats.diagnostic import breaks_cusumolsresid
from statsmodels.stats.multitest import multipletests
from statsmodels.tsa.stattools import acf, adfuller, kpss

from amazon_chaos.config import load_region
from amazon_chaos.nonlinear.surrogates import validate_series
from amazon_chaos.regional import anomalies, regional_frame, summarize

# Nome usado nas tabelas do protocolo → configs/regions/<slug>.yaml. A execução
# full_e57802a1f7 usou a caixa do Tapajós; a bacia (D-009) entra na migração do caderno 06.
REGIONS = {"xingu": "xingu", "tapajos": "tapajos_caixa"}
UNITS = {"t2m": "degC", "precip": "mm"}
NULLS = {
    "FT": "Processo estocástico linear gaussiano estacionário (espectro condicionado)",
    "IAAFT": "Transformação estática monotônica de processo linear gaussiano estacionário",
}


def local_inventory(root, regions=("xingu", "tapajos"), first=1990, last=2024):
    """List every required annual file, cache, and spatial dependency exactly."""
    root = Path(root)
    rows = []
    for region in regions:
        cfg = load_region(REGIONS[region], root=root)
        base = root / "data/processed" / cfg["experiment_id"]
        required = [("daily", base / f"daily_{y}-01-01_{y}-12-31.nc")
                    for y in range(first, last + 1)]
        required.append(("summary", base / f"summary_{first}_{last}.nc"))
        if "basin_source" in cfg["spatial"]:
            required += [("spatial", root / cfg["spatial"]["basin_source"]),
                         ("spatial", base / "basin_grid.geojson")]
        for kind, path in required:
            rows.append({"region": region, "kind": kind, "path": str(path.relative_to(root)),
                         "available": path.exists(),
                         "bytes": path.stat().st_size if path.exists() else 0})
    return pd.DataFrame(rows)


def load_local_region(root, region, first=1990, last=2024):
    """Reuse existing regional pipeline; allow a transferred standalone cache.

    Standalone caches cannot have fingerprints revalidated without daily inputs;
    their provenance is recorded as unverified and interpretation exploratory.
    """
    root = Path(root)
    cfg = load_region(REGIONS[region], root=root)
    inventory = local_inventory(root, (region,), first, last)
    prerequisites = inventory[inventory.kind.isin(["daily", "spatial"])]
    target = root / "data/processed" / cfg["experiment_id"] / f"summary_{first}_{last}.nc"
    if prerequisites.available.all():
        summary = summarize(cfg, first, last, root=root / "data/processed")
        provenance = "cache validado pelos diários (tamanho/mtime; não SHA-256)"
    elif target.exists():
        with xr.open_dataset(target) as ds:
            summary = ds.load()
        provenance = "cache isolado: fontes diárias/máscara não verificáveis localmente"
    else:
        raise FileNotFoundError("ERA5 regional ausente; veja inventory.csv para caminhos exatos")
    frame = regional_frame(summary)
    metadata = {v: summary[f"region_{v}"].attrs.get("units", "") for v in frame}
    return frame, metadata, provenance


def quality_report(series, variable, expected_start, expected_end):
    """Audit dates, missing days, finite values, quantiles and physical limits."""
    idx = series.index
    expected = pd.date_range(expected_start, expected_end, freq="D")
    finite = series[np.isfinite(series)]
    return {
        "n": len(series), "start": str(idx.min()), "end": str(idx.max()),
        "duplicates": int(idx.duplicated().sum()), "ordered": idx.is_monotonic_increasing,
        "missing_dates": len(expected.difference(idx)),
        "missing_values": int((~np.isfinite(series)).sum()),
        "off_daily_grid": int((idx != idx.normalize()).sum()),
        "minimum": finite.min(), "maximum": finite.max(),
        "q01": finite.quantile(.01), "q99": finite.quantile(.99),
        "negative_rain": int((finite < 0).sum()) if variable == "precip" else 0,
        "extreme_temperature": int(((finite < -20) | (finite > 60)).sum())
        if variable == "t2m" else 0,
        "zero_fraction": float((finite == 0).mean()),
    }


def prepare_climate_series(series, *, variable="t2m", period=("2001-01-01", "2024-12-31"),
                           base=("1991-01-01", "2020-12-31"), version="anomaly",
                           resolution="D", climatology_window=31):
    """Reuse project daily climatology; never fill signal gaps or detrend.

    The project uses day-of-year (leap-day offset) and smooths a 366-day normal.
    Require a complete baseline, preventing climatology interpolation over absent
    years. Smoothing the climatology is distinct from interpolating the signal.
    Weekly precipitation is summed only for seven complete days, temperature
    averaged. Incomplete edge weeks are excluded and documented by the caller.
    """
    if variable not in UNITS or version not in {"original", "anomaly"}:
        raise ValueError("Variável/versão não suportada")
    if resolution not in {"D", "7D"}:
        raise ValueError("Use D ou 7D: meses têm duração física desigual para Fourier")
    if (not isinstance(series.index, pd.DatetimeIndex) or series.index.has_duplicates
            or not series.index.is_monotonic_increasing):
        raise ValueError("Índice diário inválido")
    selected = series.loc[period[0]:period[1]]
    if not selected.index.equals(pd.date_range(*period, freq="D")):
        raise ValueError("Período diário incompleto ou fora da grade")
    validate_series(selected)
    if variable == "precip" and (selected < 0).any():
        raise ValueError("Precipitação negativa")
    if version == "anomaly":
        reference = series.loc[base[0]:base[1]]
        if not reference.index.equals(pd.date_range(*base, freq="D")):
            raise ValueError("Referência climatológica incompleta; não mudar o período")
        validate_series(reference)
        if variable == "precip" and (reference < 0).any():
            raise ValueError("Precipitação negativa na referência climatológica")
        selected = anomalies(series, base, window=climatology_window)[0].loc[period[0]:period[1]]
    if resolution == "7D":
        grouped = selected.resample("7D")
        count = grouped.count()
        selected = grouped.sum(min_count=7) if variable == "precip" else grouped.mean()
        selected = selected[count == 7]
    validate_series(selected)
    return selected


def stationarity_diagnostics(series, blocks=4, hac_lags=14):
    """Complementary diagnostics, never a certificate of stationarity.

    ADF fixed lag 14 and KPSS automatic bandwidth; trend HAC and CUSUM are
    descriptive with serial-dependence caveats. Thresholds are protocol flags,
    not calibrated stationarity tests. No detrending follows these diagnostics.
    """
    x = validate_series(series, min_length=64)
    chunks = np.array_split(x, blocks)
    block = pd.DataFrame([{"block": i + 1, "n": len(y), "mean": y.mean(),
                           "std": y.std(), "acf1": acf(y, nlags=1, fft=True)[1]}
                          for i, y in enumerate(chunks)])
    # Scale time to the whole record; slope is total change in original units.
    trend = sm.OLS(x, sm.add_constant(np.linspace(0, 1, len(x)))).fit(
        cov_type="HAC", cov_kwds={"maxlags": hac_lags})
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        adf_p = adfuller(x, maxlag=min(hac_lags, len(x) // 4), autolag=None)[1]
        kpss_p = kpss(x, regression="c", nlags="auto")[1]
    # CUSUM around a constant mean, not around an automatically detrended signal.
    cusum_p = breaks_cusumolsresid(x - x.mean(), ddof=1)[1]
    variance_ratio = float(block["std"].max() / max(block["std"].min(), 1e-15))
    mean_range = float(np.ptp(block["mean"]) / x.std())
    acf_range = float(np.ptp(block["acf1"]))
    flags = []
    if trend.pvalues[1] < .05:
        flags.append("tendência HAC")
    if kpss_p < .05:
        flags.append("KPSS rejeita nível estacionário")
    if adf_p >= .05:
        flags.append("ADF não rejeita raiz unitária")
    if variance_ratio > 1.5:
        flags.append("heterogeneidade de variância")
    if mean_range > .5:
        flags.append("heterogeneidade de média")
    if acf_range > .25:
        flags.append("heterogeneidade de ACF")
    return {"adf_p": adf_p, "kpss_p": kpss_p, "trend_hac_p": trend.pvalues[1],
            "trend_total": trend.params[1], "cusum_p_descriptive": cusum_p,
            "block_std_ratio": variance_ratio, "block_mean_range_sigma": mean_range,
            "block_acf1_range": acf_range, "flags": "; ".join(flags),
            "status": "exploratório" if flags else "sem alerta; premissas não comprovadas",
            "warnings": "; ".join(str(w.message) for w in caught)}, block


def adjust_results(frame, alpha=.05):
    """Holm on a frozen primary family; BH separately on exploratory tests.

    Missing/blocked planned primary tests count as p=1 so the multiplicity
    family cannot shrink opportunistically. Call only once after all protocols.
    """
    frame = frame.copy()
    frame["p_adjusted"] = np.nan
    for family, method in [("primary", "holm"), ("exploratory", "fdr_bh")]:
        mask = frame.family == family
        if mask.any():
            frame.loc[mask, "p_adjusted"] = multipletests(
                frame.loc[mask, "p_raw"].fillna(1), alpha=alpha, method=method)[1]
    frame["decision"] = np.where(frame.p_adjusted <= alpha,
                                 "rejeitamos a hipótese nula", "não rejeitamos a hipótese nula")
    frame.loc[frame.p_raw.isna(), "decision"] = "não executado"
    return frame
