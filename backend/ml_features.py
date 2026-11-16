"""
ml_features.py
==============
ONE place that turns an hourly history into model features.
Used by BOTH ml/train_models.py (training) and prediction.py (live use), so the model
always sees exactly the same kind of input it was trained on.
"""

import numpy as np
import pandas as pd

from aqi_history import compute_indices
from database import city_key

BASE_COLS = ["pm25", "pm10", "no2", "so2", "o3", "co",
             "temperature", "humidity", "pressure", "wind_speed"]


def build_hourly(rows):
    """
    DataFrame with a `timestamp` column (+ BASE_COLS)  ->  regular hourly frame
    with naqi + us_aqi computed from the pollutants (same rules as the dashboard).
    """
    df = rows.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="mixed")
    df = df.set_index("timestamp").sort_index()
    for c in BASE_COLS:
        if c not in df:
            df[c] = np.nan
    hourly = df[BASE_COLS].astype(float).groupby(df.index.floor("h")).last()
    if hourly.empty:
        return hourly
    full = hourly.reindex(pd.date_range(hourly.index.min(), hourly.index.max(), freq="h"))
    full = full.interpolate(limit=3, limit_area="inside")          # bridge gaps of up to 3 hours
    idx = compute_indices(full)
    full["naqi"], full["us_aqi"] = idx["naqi"], idx["us_aqi"]
    return full


def _cyc(values, period):
    ang = 2 * np.pi * values / period
    return np.sin(ang), np.cos(ang)


def make_features(h):
    """h = hourly frame from build_hourly().  Row t only uses information up to time t."""
    f = pd.DataFrame(index=h.index)
    for c in BASE_COLS + ["naqi", "us_aqi"]:
        f[c] = h[c]

    for name in ("naqi", "us_aqi", "pm25"):
        for lag in (1, 2, 3, 6, 12, 24):
            f[f"{name}_lag{lag}"] = h[name].shift(lag)

    f["pm25_m3"] = h["pm25"].rolling(3, min_periods=2).mean()
    f["pm25_m6"] = h["pm25"].rolling(6, min_periods=4).mean()
    f["pm25_m24"] = h["pm25"].rolling(24, min_periods=16).mean()
    f["pm25_std6"] = h["pm25"].rolling(6, min_periods=4).std()
    f["pm10_m6"] = h["pm10"].rolling(6, min_periods=4).mean()
    f["pm10_m24"] = h["pm10"].rolling(24, min_periods=16).mean()
    f["o3_m8"] = h["o3"].rolling(8, min_periods=6).mean()

    f["naqi_d1"] = h["naqi"] - h["naqi"].shift(1)
    f["naqi_d3"] = h["naqi"] - h["naqi"].shift(3)
    f["us_aqi_d3"] = h["us_aqi"] - h["us_aqi"].shift(3)
    f["pm25_d3"] = h["pm25"] - h["pm25"].shift(3)
    f["pressure_d3"] = h["pressure"] - h["pressure"].shift(3)
    f["temperature_d3"] = h["temperature"] - h["temperature"].shift(3)
    f["humidity_d3"] = h["humidity"] - h["humidity"].shift(3)

    idx = h.index
    f["hour_sin"], f["hour_cos"] = _cyc(idx.hour.to_numpy(), 24)
    f["dow_sin"], f["dow_cos"] = _cyc(idx.dayofweek.to_numpy(), 7)
    f["month_sin"], f["month_cos"] = _cyc(idx.month.to_numpy() - 1, 12)
    return f


FEATURES = list(make_features(pd.DataFrame(
    {c: [1.0] * 30 for c in BASE_COLS + ["naqi", "us_aqi"]},
    index=pd.date_range("2025-01-01", periods=30, freq="h"))).columns)

# (standard, hours ahead) -> (index column, how many hours ahead)
TARGETS = {("naqi", 1): ("naqi", 1), ("naqi", 6): ("naqi", 6),
           ("us", 1): ("us_aqi", 1), ("us", 6): ("us_aqi", 6)}


def city_frames(db_rows):
    """db_rows: all rows of the table.  -> {city_name: hourly frame}  (names merged by city_key)."""
    frames = {}
    db_rows = db_rows.copy()
    db_rows["_key"] = db_rows["city"].map(city_key)
    for key, g in db_rows.groupby("_key"):
        name = g["city"].value_counts().idxmax()
        frames[name] = build_hourly(g)
    return frames
