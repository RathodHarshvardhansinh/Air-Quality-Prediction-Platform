"""
fix_database.py   -   run ONCE:   python backend/fix_database.py
=================================================================
Repairs backend/airsense.db  (a backup copy is made first).

What it fixes
  1. Duplicate rows       every hour of the imported Visnagar history was stored twice
                          (once as '2025-01-01T00:00', once as '2025-01-01 00:00:00').
  2. Mixed AQI standards  hour-aligned rows (CSV import + Open-Meteo backfill) stored the
                          US AQI inside the `aqi` column, live collector rows stored the
                          Indian NAQI.  Now:  aqi = Indian NAQI,  us_aqi = US AQI.
  3. Mixed units          CO is stored in ug/m3 everywhere (a few rows were mg/m3).
  4. Timestamps           one format 'YYYY-MM-DD HH:MM:SS' in Indian time (live rows were UTC).
  5. City spelling        Mahesāna -> Mehsana, Jūnāgadh -> Junagadh.

Safe to run again - it does nothing harmful on an already clean database.
"""

import os
import shutil
import sqlite3
import sys

import numpy as np
import pandas as pd

from aqi_history import compute_indices
from database import DATABASE, create_database, city_key

DISPLAY_NAMES = {"mehsana": "Mehsana", "junagadh": "Junagadh"}


def main():
    backup = DATABASE.replace(".db", "_backup_before_fix.db")
    if not os.path.exists(backup):
        shutil.copyfile(DATABASE, backup)
        print("Backup saved:", backup)

    create_database()
    conn = sqlite3.connect(DATABASE)
    df = pd.read_sql("SELECT * FROM environment_data", conn)
    before = len(df)
    print(f"Rows before: {before:,}")

    df["ts"] = pd.to_datetime(df["timestamp"], format="mixed")
    df["aligned"] = (df.ts.dt.minute == 0) & (df.ts.dt.second == 0)
    df["ckey"] = df["city"].map(city_key)
    already_fixed = df["us_aqi"].notna().any()

    # live-collector rows got SQLite's default timestamp = UTC; history is Indian time (IST)
    if not already_fixed:
        live = ~df["aligned"]
        df.loc[live, "ts"] = df.loc[live, "ts"] + pd.Timedelta(hours=5, minutes=30)
        print(f"Live rows shifted UTC -> IST (+5h30): {int(live.sum()):,}")

    # which standard did the OLD `aqi` column hold?  (hour-aligned rows = US AQI)
    # If us_aqi is already filled the database was fixed before: `aqi` is NAQI everywhere.
    df["old_is_us"] = df["aligned"] & (not already_fixed)

    # ---- 1. duplicates: same city + same timestamp -> keep the fullest row
    value_cols = ["aqi", "pm25", "pm10", "no2", "co", "o3", "so2", "temperature",
                  "humidity", "pressure", "wind_speed", "traffic_speed"]
    df["filled"] = df[value_cols].notna().sum(axis=1)
    df = df.sort_values(["ckey", "ts", "filled", "id"], ascending=[True, True, False, True])
    df = df.drop_duplicates(["ckey", "ts"], keep="first").copy()
    print(f"Duplicate rows removed: {before - len(df):,}")

    # ---- 3. CO unit: a value between 0 and 10 can only be mg/m3
    mg = df["co"].between(0, 10, inclusive="neither")
    df.loc[mg, "co"] = df.loc[mg, "co"] * 1000.0
    print(f"CO values converted mg/m3 -> ug/m3: {int(mg.sum())}")

    # ---- 2. recompute both indices from the hourly pollutant history
    df["naqi"] = np.nan
    df["us_new"] = np.nan
    for _, g in df.groupby("ckey"):
        cols = ["pm25", "pm10", "no2", "so2", "o3", "co"]
        hourly = g.set_index("ts").sort_index()[cols]
        hourly = hourly.groupby(hourly.index.floor("h")).last()
        full = hourly.reindex(pd.date_range(hourly.index.min(), hourly.index.max(), freq="h"))
        idx = compute_indices(full)
        hours = g["ts"].dt.floor("h")
        df.loc[g.index, "naqi"] = idx["naqi"].reindex(hours).to_numpy()
        df.loc[g.index, "us_new"] = idx["us_aqi"].reindex(hours).to_numpy()

    old = df["aqi"].astype(float)
    # aligned rows:      old value was US AQI  ->  keep it only as fallback for us_aqi
    # non-aligned rows:  old value was NAQI (official station reading) -> keep as aqi
    df["aqi_new"] = np.where(df["old_is_us"], df["naqi"], old.where(old.notna(), df["naqi"]))
    df["us_final"] = np.where(df["old_is_us"], df["us_new"].fillna(old), df["us_new"])

    # ---- 4/5. timestamps + names
    out = pd.DataFrame({
        "city": df["city"].map(lambda c: DISPLAY_NAMES.get(city_key(c), c)),
        "aqi": df["aqi_new"].round(),
        "us_aqi": pd.Series(df["us_final"]).round(),
        "pm25": df["pm25"], "pm10": df["pm10"], "no2": df["no2"], "co": df["co"],
        "o3": df["o3"], "so2": df["so2"], "temperature": df["temperature"],
        "humidity": df["humidity"], "pressure": df["pressure"], "wind_speed": df["wind_speed"],
        "traffic_speed": df["traffic_speed"], "free_flow_speed": df["free_flow_speed"],
        "timestamp": df["ts"].dt.strftime("%Y-%m-%d %H:%M:%S"),
    }).sort_values(["city", "timestamp"]).reset_index(drop=True)

    # ---- write back (swap table inside one transaction)
    out = out.astype(object).where(out.notna(), None)
    rows = list(out.itertuples(index=False, name=None))
    cur = conn.cursor()
    cur.execute("DROP INDEX IF EXISTS uq_env_city_ts")
    cur.execute("DELETE FROM environment_data")
    cur.executemany(
        "INSERT INTO environment_data(city, aqi, us_aqi, pm25, pm10, no2, co, o3, so2, temperature, "
        "humidity, pressure, wind_speed, traffic_speed, free_flow_speed, timestamp) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.execute("VACUUM")
    conn.close()
    create_database()          # re-creates the unique index

    conn = sqlite3.connect(DATABASE)
    print(f"\nRows after:  {len(rows):,}")
    for r in conn.execute("SELECT city, COUNT(*), MIN(timestamp), MAX(timestamp), "
                          "ROUND(AVG(aqi),1), ROUND(AVG(us_aqi),1) FROM environment_data "
                          "GROUP BY city ORDER BY 2 DESC LIMIT 8"):
        print("  ", r)
    conn.close()
    print("\nDone.  Database is clean.")


if __name__ == "__main__":
    sys.exit(main())
