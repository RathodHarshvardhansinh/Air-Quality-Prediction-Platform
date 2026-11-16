"""
aqi_history.py
==============
Computes Indian NAQI and US AQI for a whole hourly history at once (fast, vectorised),
using EXACTLY the same rules as the live dashboard (aqi.py):

    NAQI : 24-hour average for PM2.5 / PM10 / NO2 / SO2,
           latest 8-hour average for CO / O3
    US   : NowCast for PM2.5 / PM10, 8-hour average for CO / O3, 1-hour for NO2 / SO2

Input : DataFrame with a regular HOURLY DatetimeIndex and columns
        pm25, pm10, no2, so2, o3 (ug/m3) and co (ug/m3)
Output: same index with columns  naqi  and  us_aqi   (NaN where it cannot be computed)

This module is used by fix_database.py, fetch_city_history.py and ml/train_models.py,
so the model is trained on the same definition the dashboard shows.
"""

import numpy as np
import pandas as pd

from aqi import (
    PM25_BREAKPOINTS, PM10_BREAKPOINTS, NO2_BREAKPOINTS, SO2_BREAKPOINTS,
    CO_BREAKPOINTS, O3_BREAKPOINTS,
    US_PM25, US_PM10, US_O3_PPB, US_CO_PPM, US_SO2_PPB, US_NO2_PPB,
)


def _sub_index(values, table, truncate_decimals=None):
    """Vectorised version of the scalar sub-index (first matching segment wins)."""
    c = np.asarray(values, dtype=float)
    if truncate_decimals is not None:
        f = 10 ** truncate_decimals
        c = np.floor(c * f) / f
    out = np.full(c.shape, np.nan)
    # reversed so that the FIRST segment ends up winning on shared boundaries
    for lo, hi, i_lo, i_hi in reversed(table):
        m = (c >= lo) & (c <= hi)
        out[m] = (i_hi - i_lo) / (hi - lo) * (c[m] - lo) + i_lo
    lo, hi, i_lo, i_hi = table[-1]
    above = c > hi
    out[above] = np.minimum(500.0, (i_hi - i_lo) / (hi - lo) * (c[above] - lo) + i_lo) \
        if table is US_PM25 or table in (US_PM10, US_O3_PPB, US_CO_PPM, US_SO2_PPB, US_NO2_PPB) \
        else (i_hi - i_lo) / (hi - lo) * (c[above] - lo) + i_lo
    out[c < 0] = 0.0
    return np.round(out, 2)


def _nowcast(series):
    """EPA NowCast, vectorised over a regular hourly series."""
    v = series.to_numpy(dtype=float)
    n = len(v)
    out = np.full(n, np.nan)
    for t in range(n):
        window = v[max(0, t - 11): t + 1][::-1]            # most recent first, up to 12 h
        if len(window) < 3 or np.isnan(window[:3]).sum() > 1:
            continue
        ok = ~np.isnan(window)
        c_max, c_min = np.nanmax(window), np.nanmin(window)
        w = max((c_min / c_max) if c_max > 0 else 1.0, 0.5)
        weights = w ** np.arange(len(window))
        out[t] = (window[ok] * weights[ok]).sum() / weights[ok].sum()
    return pd.Series(out, index=series.index)


def compute_indices(df):
    d = df.copy()
    for col in ("pm25", "pm10", "no2", "so2", "o3", "co"):
        if col not in d:
            d[col] = np.nan
    co_mg = d["co"] / 1000.0

    # ---------- NAQI ----------
    pm25_24 = d["pm25"].rolling(24, min_periods=16).mean()
    pm10_24 = d["pm10"].rolling(24, min_periods=16).mean()
    no2_24 = d["no2"].rolling(24, min_periods=16).mean()
    so2_24 = d["so2"].rolling(24, min_periods=16).mean()
    co_8 = co_mg.rolling(8, min_periods=6).mean()
    o3_8 = d["o3"].rolling(8, min_periods=6).mean()

    subs = pd.DataFrame({
        "pm25": _sub_index(pm25_24, PM25_BREAKPOINTS),
        "pm10": _sub_index(pm10_24, PM10_BREAKPOINTS),
        "no2": _sub_index(no2_24, NO2_BREAKPOINTS),
        "so2": _sub_index(so2_24, SO2_BREAKPOINTS),
        "co": _sub_index(co_8, CO_BREAKPOINTS),
        "o3": _sub_index(o3_8, O3_BREAKPOINTS),
    }, index=d.index)
    valid = (subs.notna().sum(axis=1) >= 3) & (subs["pm25"].notna() | subs["pm10"].notna())
    naqi = subs.max(axis=1).where(valid)

    # ---------- US AQI ----------
    us = pd.DataFrame({
        "pm25": _sub_index(_nowcast(d["pm25"]), US_PM25, 1),
        "pm10": _sub_index(_nowcast(d["pm10"]), US_PM10, 0),
        "no2": _sub_index(d["no2"] * 0.5314, US_NO2_PPB, 0),
        "so2": _sub_index(d["so2"] * 0.3816, US_SO2_PPB, 0),
        "o3": _sub_index(d["o3"].rolling(8, min_periods=6).mean() * 0.5094, US_O3_PPB, 0),
        "co": _sub_index(co_mg.rolling(8, min_periods=6).mean() * 0.8729, US_CO_PPM, 1),
    }, index=d.index)
    # like NAQI, an AQI without any particulate reading would be misleading (gases alone are tiny)
    us_aqi = us.max(axis=1, skipna=True).where(us["pm25"].notna() | us["pm10"].notna())

    out = pd.DataFrame(index=d.index)
    out["naqi"] = naqi.round()
    out["us_aqi"] = us_aqi.round()
    return out
