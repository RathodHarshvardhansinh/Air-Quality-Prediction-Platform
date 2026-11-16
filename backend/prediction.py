"""
prediction.py  -  live AQI forecast (1 hour and 6 hours ahead)
==============================================================
Uses the XGBoost + CatBoost models trained by ml/train_models.py
(files in ml/models/).  The features come from ml_features.py - the SAME code the
models were trained with.

Where the recent history comes from
  1. the database (last 4 days of the city), if it is fresh (newest reading <= 3 h old)
  2. otherwise the last 3 days are downloaded live from Open-Meteo for the given
     latitude/longitude - so a brand-new place works immediately.
If neither is possible we say so.  (The old version silently predicted from a
months-old database row.)
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta

import pandas as pd
import requests

from database import DATABASE, resolve_db_city
from ml_features import BASE_COLS, FEATURES, TARGETS, build_hourly, make_features

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ml", "models")
MAX_AGE_HOURS = 3

_state = {"loaded": False, "models": {}, "meta": None}


class PredictionError(Exception):
    """A problem the user should be told about in plain words."""


# --------------------------------------------------------------------------------------
# models
# --------------------------------------------------------------------------------------

def _load_models():
    """
    Loads the saved models.  Never fails just because a package is missing:
      xgboost + catboost installed -> full model (average of both)
      only xgboost installed       -> XGBoost
      neither                      -> XGBoost evaluated by xgb_lite.py (numpy only)
    """
    if _state["loaded"]:
        return
    meta_path = os.path.join(MODEL_DIR, "model_meta.json")
    if not os.path.exists(meta_path):
        raise PredictionError("The AI models are not trained yet. Run:  python ml/train_models.py")

    with open(meta_path) as fh:
        meta = json.load(fh)
    if meta["features"] != FEATURES:
        raise PredictionError("The saved models do not match the current feature code. "
                              "Run:  python ml/train_models.py")

    try:
        import xgboost as xgb
    except ImportError:
        xgb = None
    try:
        from catboost import CatBoostRegressor
    except ImportError:
        CatBoostRegressor = None
    from xgb_lite import XGBLite

    models = {}
    for name in meta["targets"]:
        xgb_path = os.path.join(MODEL_DIR, f"{name}_xgb.json")
        if xgb is not None:
            mx = xgb.XGBRegressor()
            mx.load_model(xgb_path)
        else:
            mx = XGBLite(xgb_path)
        mc = None
        if CatBoostRegressor is not None:
            mc = CatBoostRegressor()
            mc.load_model(os.path.join(MODEL_DIR, f"{name}_cat.cbm"))
        choice = meta["targets"][name]["choice"]
        if mc is None and choice in ("cat", "avg"):
            choice = "xgb"                      # CatBoost not available on this computer
        models[name] = (mx, mc, choice)

    if xgb is not None and CatBoostRegressor is not None:
        label = "XGBoost + CatBoost"
    elif xgb is not None:
        label = "XGBoost"
    else:
        label = "XGBoost (built-in lite mode)"
    if label != "XGBoost + CatBoost":
        print(f"NOTE: forecast running as '{label}'. For the full model run: "
              "python -m pip install -r requirements.txt")
    _state.update(loaded=True, models=models, meta=meta, label=label)


def model_info():
    try:
        _load_models()
        m = _state["meta"]
        return {"algorithms": m["algorithms"], "running_as": _state["label"], "trained_at": m["trained_at"],
                "cities": list(m["cities"].keys()), "data_range": m["data_range"]}
    except PredictionError as error:
        return {"error": str(error)}


# --------------------------------------------------------------------------------------
# history sources
# --------------------------------------------------------------------------------------

def _now_local():
    return datetime.now()


def _now_ist():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)


def _db_frame(city, hours=96):
    now = _now_local()
    cutoff = (now - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    upto = now.strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DATABASE)
    rows = pd.read_sql(
        "SELECT timestamp, pm25, pm10, no2, so2, o3, co, temperature, humidity, pressure, wind_speed "
        "FROM environment_data WHERE LOWER(city) = LOWER(?) AND timestamp >= ? AND timestamp <= ? "
        "ORDER BY timestamp",
        conn, params=(city, cutoff, upto))
    last = conn.execute("SELECT MAX(timestamp) FROM environment_data WHERE LOWER(city)=LOWER(?)",
                        (city,)).fetchone()[0]
    conn.close()
    return (build_hourly(rows) if len(rows) else None), last


def _api_frame(lat, lon):
    """Last 3 days of hourly weather + air quality from Open-Meteo (free, no key)."""
    common = {"latitude": lat, "longitude": lon, "past_days": 3, "forecast_days": 1,
              "timezone": "Asia/Kolkata"}
    try:
        air = requests.get("https://air-quality-api.open-meteo.com/v1/air-quality", timeout=15, params={
            **common, "hourly": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone"})
        wx = requests.get("https://api.open-meteo.com/v1/forecast", timeout=15, params={
            **common, "hourly": "temperature_2m,relative_humidity_2m,pressure_msl,wind_speed_10m"})
        if air.status_code != 200 or wx.status_code != 200:
            return None
        a, w = air.json()["hourly"], wx.json()["hourly"]
    except Exception as error:
        print("Live history download failed:", error)
        return None

    df = pd.DataFrame({
        "timestamp": pd.to_datetime(a["time"]),
        "pm25": a["pm2_5"], "pm10": a["pm10"], "no2": a["nitrogen_dioxide"],
        "so2": a["sulphur_dioxide"], "o3": a["ozone"], "co": a["carbon_monoxide"],
    }).set_index("timestamp")
    wdf = pd.DataFrame({
        "timestamp": pd.to_datetime(w["time"]),
        "temperature": w["temperature_2m"], "humidity": w["relative_humidity_2m"],
        "pressure": w["pressure_msl"], "wind_speed": w["wind_speed_10m"],
    }).set_index("timestamp")
    df = df.join(wdf, how="left")
    df = df[df.index <= pd.Timestamp(_now_ist())]                 # drop future (forecast) hours
    df = df[df["pm25"].notna() | df["pm10"].notna()].reset_index()
    return build_hourly(df) if len(df) else None


# --------------------------------------------------------------------------------------
# prediction
# --------------------------------------------------------------------------------------

def predict_from_frame(frame):
    """frame = hourly frame from build_hourly().  Predicts from its newest usable hour."""
    _load_models()
    feats = make_features(frame)
    usable = frame.index[frame["naqi"].notna()]            # NAQI is the main index
    if len(usable) == 0:
        usable = frame.index[frame["us_aqi"].notna()]
    if len(usable) == 0:
        raise PredictionError("Not enough recent history yet (needs about 24 hours of readings).")
    t0 = usable[-1]
    x = feats.loc[[t0], FEATURES]

    out = {}
    for (std, hz), (col, _) in TARGETS.items():
        name = f"{std}_{hz}h"
        current = frame.loc[t0, col]
        if pd.isna(current):
            out[name] = None
            continue
        mx, mc, choice = _state["models"][name]
        dx = float(mx.predict(x)[0])
        dc = float(mc.predict(x)[0]) if mc is not None else dx
        delta = {"xgb": dx, "cat": dc, "avg": (dx + dc) / 2}[choice]
        out[name] = int(max(0, min(500, round(current + delta))))
    cur = {"naqi": None if pd.isna(frame.loc[t0, "naqi"]) else int(frame.loc[t0, "naqi"]),
           "us": None if pd.isna(frame.loc[t0, "us_aqi"]) else int(frame.loc[t0, "us_aqi"])}
    return t0, cur, out


def get_predictions(city, lat=None, lon=None):
    _load_models()
    db_city = resolve_db_city(city)

    frame, last_in_db = _db_frame(db_city)
    basis = "database"

    def is_fresh(fr):
        if fr is None:
            return False
        ok = fr.index[fr["naqi"].notna()]
        if len(ok) == 0:
            ok = fr.index[fr["us_aqi"].notna()]
        return len(ok) > 0 and _now_local() - ok[-1].to_pydatetime() <= timedelta(hours=MAX_AGE_HOURS)

    if not is_fresh(frame) and lat is not None and lon is not None:
        live = _api_frame(lat, lon)
        if live is not None and is_fresh(live):
            frame, basis = live, "live_download"

    if not is_fresh(frame):
        if last_in_db:
            raise PredictionError(f"The saved history for {city} ends on {last_in_db[:16]} - too old to "
                                  "forecast from, and a live download was not possible right now.")
        raise PredictionError(f"No history for {city} yet and a live download was not possible right now.")

    t0, cur, preds = predict_from_frame(frame)
    return {
        "city": city,
        "basis": basis,
        "based_on": t0.strftime("%Y-%m-%d %H:%M"),
        "model": _state["label"],
        "current": cur,
        "prediction_1h": preds["naqi_1h"],      # Indian NAQI (kept for the existing dashboard)
        "prediction_6h": preds["naqi_6h"],
        "us_prediction_1h": preds["us_1h"],     # US AQI
        "us_prediction_6h": preds["us_6h"],
    }
