"""
fetch_city_history.py
=====================
Downloads REAL hourly history (weather + air quality) for many cities from the free
Open-Meteo archive (no API key) and stores it in backend/airsense.db, so the AI models
can be trained on more than one city.

    python backend/fetch_city_history.py --all                     # every city in cities.py (~40)
    python backend/fetch_city_history.py --cities "Surat,Rajkot"   # only some
    python backend/fetch_city_history.py --all --start 2023-01-01  # shorter history
    python backend/fetch_city_history.py --list                    # show the city list

Then retrain the models:       python ml/train_models.py

Notes
  * Needs internet.  ~10 requests per city, polite pauses are built in (about 1 minute/city).
  * Safe to stop and run again: rows that already exist are skipped, nothing is duplicated.
  * Air-quality history exists from 2022-07-29.  The weather archive ends ~6 days ago,
    so the newest days are not included (the live collector fills those).
  * The AQI values are COMPUTED here from the pollutants with the same rules as the
    dashboard (aqi_history.py): aqi = Indian NAQI, us_aqi = US AQI.
  * Units stored: CO ug/m3, wind km/h, pressure hPa (see database.py).
"""

import argparse
import sqlite3
import sys
import time
from datetime import date, timedelta

import numpy as np
import pandas as pd
import requests

from aqi_history import compute_indices
from cities import HISTORY_CITIES
from database import DATABASE, create_database

WEATHER_URL = "https://archive-api.open-meteo.com/v1/archive"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WEATHER_VARS = "temperature_2m,relative_humidity_2m,pressure_msl,wind_speed_10m"
AIR_VARS = "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone"
AIR_START = date(2022, 8, 1)          # air-quality history starts 2022-07-29
PAUSE = 1.0                           # seconds between requests


def get_json(url, params, retries=5):
    """GET with retry/backoff (handles rate limits)."""
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=60)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                wait = 20 * (attempt + 1)
                print(f"      rate limited, waiting {wait}s ...")
                time.sleep(wait)
                continue
            print(f"      HTTP {r.status_code}: {r.text[:120]}")
        except requests.RequestException as error:
            print("      network error:", str(error)[:100])
        time.sleep(3 * (attempt + 1))
    return None


def year_chunks(start, end):
    """Split the date range into <= 1-year pieces (keeps each request small)."""
    cur = start
    while cur <= end:
        nxt = min(date(cur.year, 12, 31), end)
        yield cur, nxt
        cur = nxt + timedelta(days=1)


def frame_from(payload, columns):
    hourly = (payload or {}).get("hourly") or {}
    if not hourly.get("time"):
        return pd.DataFrame(columns=list(columns.values()))
    df = pd.DataFrame({new: hourly.get(old) for old, new in columns.items()},
                      index=pd.to_datetime(hourly["time"]))
    return df.astype(float)


def fetch_city(name, lat, lon, start, end):
    weather_cols = {"temperature_2m": "temperature", "relative_humidity_2m": "humidity",
                    "pressure_msl": "pressure", "wind_speed_10m": "wind_speed"}
    air_cols = {"pm10": "pm10", "pm2_5": "pm25", "carbon_monoxide": "co",
                "nitrogen_dioxide": "no2", "sulphur_dioxide": "so2", "ozone": "o3"}
    w_parts, a_parts = [], []
    for s, e in year_chunks(start, end):
        base = {"latitude": lat, "longitude": lon, "start_date": s.isoformat(),
                "end_date": e.isoformat(), "timezone": "Asia/Kolkata"}
        w = get_json(WEATHER_URL, {**base, "hourly": WEATHER_VARS})
        time.sleep(PAUSE)
        a = get_json(AIR_URL, {**base, "hourly": AIR_VARS})
        time.sleep(PAUSE)
        if w is None or a is None:
            print(f"    !! {name}: could not download {s} .. {e}")
            return None
        w_parts.append(frame_from(w, weather_cols))
        a_parts.append(frame_from(a, air_cols))

    air = pd.concat(a_parts) if a_parts else pd.DataFrame()
    weather = pd.concat(w_parts) if w_parts else pd.DataFrame()
    air = air[~air.index.duplicated()].sort_index()
    weather = weather[~weather.index.duplicated()].sort_index()
    if air.empty:
        return None

    full_index = pd.date_range(air.index.min(), air.index.max(), freq="h")
    df = air.reindex(full_index).join(weather.reindex(full_index))
    idx = compute_indices(df[["pm25", "pm10", "no2", "so2", "o3", "co"]])
    df["aqi"], df["us_aqi"] = idx["naqi"], idx["us_aqi"]
    # keep hours that have at least a particulate reading
    return df[df["pm25"].notna() | df["pm10"].notna()]


def save_frame(city, df):
    cols = ["aqi", "us_aqi", "pm25", "pm10", "no2", "co", "o3", "so2",
            "temperature", "humidity", "pressure", "wind_speed"]
    clean = df[cols].astype(object).where(df[cols].notna(), None)
    stamps = df.index.strftime("%Y-%m-%d %H:%M:%S")
    rows = [(city, *vals, ts) for vals, ts in zip(clean.itertuples(index=False, name=None), stamps)]

    conn = sqlite3.connect(DATABASE)
    before = conn.execute("SELECT COUNT(*) FROM environment_data WHERE LOWER(city)=LOWER(?)", (city,)).fetchone()[0]
    conn.executemany(
        "INSERT OR IGNORE INTO environment_data(city, aqi, us_aqi, pm25, pm10, no2, co, o3, so2, "
        "temperature, humidity, pressure, wind_speed, timestamp) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        rows)
    conn.commit()
    after = conn.execute("SELECT COUNT(*) FROM environment_data WHERE LOWER(city)=LOWER(?)", (city,)).fetchone()[0]
    conn.close()
    return after - before


def existing_hours(city):
    conn = sqlite3.connect(DATABASE)
    n = conn.execute("SELECT COUNT(DISTINCT substr(timestamp,1,13)) FROM environment_data "
                     "WHERE LOWER(city)=LOWER(?)", (city,)).fetchone()[0]
    conn.close()
    return n


def main():
    p = argparse.ArgumentParser(description="Download hourly city history from Open-Meteo")
    p.add_argument("--all", action="store_true", help="every city in cities.py (HISTORY_CITIES)")
    p.add_argument("--cities", help='comma separated, e.g. "Surat,Rajkot"')
    p.add_argument("--start", default=AIR_START.isoformat(), help="YYYY-MM-DD (default 2022-08-01)")
    p.add_argument("--end", default=(date.today() - timedelta(days=6)).isoformat(), help="YYYY-MM-DD")
    p.add_argument("--refresh", action="store_true", help="also fetch cities that already have history")
    p.add_argument("--list", action="store_true", help="print the available cities and exit")
    args = p.parse_args()

    known = {c[0].lower(): c for c in HISTORY_CITIES}
    if args.list:
        for c in HISTORY_CITIES:
            print(f"{c[0]:22s} {c[1]:8.4f} {c[2]:8.4f}")
        return 0
    if args.cities:
        wanted = []
        for n in [x.strip() for x in args.cities.split(",") if x.strip()]:
            if n.lower() not in known:
                print(f"'{n}' is not in cities.py - add it to HISTORY_CITIES (name, lat, lon).")
                return 1
            wanted.append(known[n.lower()])
    elif args.all:
        wanted = HISTORY_CITIES
    else:
        p.print_help()
        return 1

    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    create_database()
    total_new = 0
    for i, (name, lat, lon) in enumerate(wanted, 1):
        have = existing_hours(name)
        expected = (end - start).days * 24
        if have >= 0.9 * expected and not args.refresh:
            print(f"[{i}/{len(wanted)}] {name}: already has {have:,} hours - skipped")
            continue
        print(f"[{i}/{len(wanted)}] {name}: downloading {start} .. {end} ...")
        df = fetch_city(name, lat, lon, start, end)
        if df is None or df.empty:
            print(f"    {name}: nothing saved")
            continue
        new = save_frame(name, df)
        total_new += new
        print(f"    {name}: {len(df):,} hours downloaded, {new:,} new rows saved")

    print(f"\nFinished. {total_new:,} new rows saved.  Next step:  python ml/train_models.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
