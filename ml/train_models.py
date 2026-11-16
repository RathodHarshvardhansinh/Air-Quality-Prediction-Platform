"""
train_models.py   -   python ml/train_models.py
================================================
Trains XGBoost + CatBoost models that predict the AQI 1 hour and 6 hours ahead,
for BOTH standards (Indian NAQI and US AQI), from everything in backend/airsense.db.

    python backend/fix_database.py                 # once, cleans the database
    python backend/fetch_city_history.py --all     # optional: more cities = better model
    python ml/train_models.py                      # train  (add --fast for a quick test)

What it does
  * builds an hourly series per city, computes NAQI / US AQI from the pollutants
  * features: current values, lags up to 24 h, rolling means, trends, weather, time of day/year
  * time-ordered split PER CITY (first 70 % train, next 10 % validation, last 20 % test)
    -> the test period is always in the "future" of the training period (no leakage)
  * compares: persistence ("same as now"), Random Forest (your old approach), XGBoost, CatBoost
    and their average; the best one on the validation period is used
  * refits the winner on ALL data and saves it to ml/models/
"""

import argparse
import json
import os
import sys
import time
import warnings
from datetime import datetime

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backend"))
warnings.filterwarnings("ignore")

import sqlite3                                              # noqa: E402
import xgboost as xgb                                       # noqa: E402
from catboost import CatBoostRegressor                      # noqa: E402
from sklearn.ensemble import RandomForestRegressor          # noqa: E402
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score   # noqa: E402

import database                                             # noqa: E402
from ml_features import FEATURES, TARGETS, city_frames, make_features   # noqa: E402

MODEL_DIR = os.path.join(HERE, "models")


def load_rows(db_path):
    conn = sqlite3.connect(db_path)
    rows = pd.read_sql("SELECT city, timestamp, pm25, pm10, no2, so2, o3, co, temperature, "
                       "humidity, pressure, wind_speed FROM environment_data", conn)
    conn.close()
    return rows


def build_dataset(frames, min_hours):
    parts, used, skipped = [], {}, {}
    for city, h in frames.items():
        valid = int(h["naqi"].notna().sum())
        if valid < min_hours:
            skipped[city] = valid
            continue
        f = make_features(h)
        for (std, hz), (col, k) in TARGETS.items():
            f[f"y_{std}_{hz}"] = h[col].shift(-k)
        f["city"] = city
        # split by VALID hours (not calendar position), so a long gap in a city's history
        # can never push all of its real data into the training part
        valid_mask = (h["naqi"].notna() | h["us_aqi"].notna())
        rank = valid_mask.cumsum() / max(int(valid_mask.sum()), 1)
        f["split"] = np.where(rank < 0.70, "train", np.where(rank < 0.80, "val", "test"))
        parts.append(f)
        used[city] = valid
    if not parts:
        raise SystemExit(f"No city has at least {min_hours} hours of data. "
                         "Run backend/fetch_city_history.py first.")
    return pd.concat(parts), used, skipped


def metrics(y_true, y_pred):
    return {"mae": round(float(mean_absolute_error(y_true, y_pred)), 2),
            "rmse": round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 2),
            "r2": round(float(r2_score(y_true, y_pred)), 3)}


def new_xgb(n):
    return xgb.XGBRegressor(n_estimators=n, learning_rate=0.05, max_depth=6, subsample=0.8,
                            colsample_bytree=0.8, min_child_weight=5, reg_lambda=2.0,
                            tree_method="hist", n_jobs=-1, random_state=42,
                            early_stopping_rounds=50 if n > 400 or True else None)


def new_cat(n):
    return CatBoostRegressor(iterations=n, learning_rate=0.05, depth=6, loss_function="RMSE",
                             random_seed=42, verbose=0, allow_writing_files=False, thread_count=-1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=database.DATABASE)
    ap.add_argument("--fast", action="store_true", help="fewer trees - quick test run")
    ap.add_argument("--min-hours", type=int, default=1000, help="skip cities with less history")
    args = ap.parse_args()

    n_trees = 300 if args.fast else 1500
    started = time.time()
    print(f"Database: {args.db}")
    frames = city_frames(load_rows(args.db))
    ds, used, skipped = build_dataset(frames, args.min_hours)
    print(f"\nCities used ({len(used)}): " + ", ".join(f"{c} ({n:,} h)" for c, n in sorted(used.items(), key=lambda x: -x[1])[:12])
          + (" ..." if len(used) > 12 else ""))
    if skipped:
        names = ", ".join(skipped.keys()) if len(skipped) <= 6 else ", ".join(list(skipped)[:6]) + " ..."
        print(f"Skipped {len(skipped)} cities with less than {args.min_hours} hours of history: {names}")
        print("  (run backend/fetch_city_history.py to download their history)")
    print(f"Hourly rows: {len(ds):,}   features: {len(FEATURES)}")

    os.makedirs(MODEL_DIR, exist_ok=True)
    report, meta_targets, lines = {}, {}, []

    for (std, hz), (col, _) in TARGETS.items():
        name = f"{std}_{hz}h"
        d = ds[ds[f"y_{std}_{hz}"].notna() & ds[col].notna()].copy()
        d["delta"] = d[f"y_{std}_{hz}"] - d[col]          # models learn the CHANGE from now
        tr, va, te = (d[d.split == s] for s in ("train", "val", "test"))
        Xtr, Xva, Xte = tr[FEATURES], va[FEATURES], te[FEATURES]
        print(f"\n=== {name}: train {len(tr):,} | validation {len(va):,} | test {len(te):,} ===")

        cur_va, cur_te = va[col].to_numpy(), te[col].to_numpy()
        y_va, y_te = va[f"y_{std}_{hz}"].to_numpy(), te[f"y_{std}_{hz}"].to_numpy()

        res = {"persistence": metrics(y_te, cur_te)}

        # --- Random Forest (the old approach) on a sample, as a fair reference
        sample = tr.sample(min(len(tr), 150_000), random_state=1)
        med = Xtr.median()
        rf = RandomForestRegressor(n_estimators=150, max_depth=14, min_samples_leaf=3, n_jobs=-1, random_state=1)
        rf.fit(sample[FEATURES].fillna(med), sample["delta"])
        res["random_forest"] = metrics(y_te, cur_te + rf.predict(Xte.fillna(med)))

        # --- XGBoost
        mx = new_xgb(n_trees)
        mx.fit(Xtr, tr["delta"], eval_set=[(Xva, va["delta"])], verbose=False)
        px_va, px_te = mx.predict(Xva), mx.predict(Xte)
        res["xgboost"] = metrics(y_te, cur_te + px_te)

        # --- CatBoost
        mc = new_cat(n_trees)
        mc.fit(Xtr, tr["delta"], eval_set=(Xva, va["delta"]), early_stopping_rounds=60)
        pc_va, pc_te = mc.predict(Xva), mc.predict(Xte)
        res["catboost"] = metrics(y_te, cur_te + pc_te)

        res["xgb+cat average"] = metrics(y_te, cur_te + (px_te + pc_te) / 2)

        # --- choose by VALIDATION error (the test set is never used for choosing)
        val_mae = {"xgb": mean_absolute_error(y_va, cur_va + px_va),
                   "cat": mean_absolute_error(y_va, cur_va + pc_va),
                   "avg": mean_absolute_error(y_va, cur_va + (px_va + pc_va) / 2)}
        choice = min(val_mae, key=val_mae.get)

        best_x = int(getattr(mx, "best_iteration", n_trees) or n_trees)
        best_c = int(mc.get_best_iteration() or n_trees)

        # --- refit on ALL data (train+val+test) so the shipped model knows the latest period
        fx = new_xgb(int(best_x * 1.15) + 1)
        fx.set_params(early_stopping_rounds=None)
        fx.fit(d[FEATURES], d["delta"], verbose=False)
        fc = new_cat(int(best_c * 1.15) + 1)
        fc.fit(d[FEATURES], d["delta"])
        fx.save_model(os.path.join(MODEL_DIR, f"{name}_xgb.json"))
        fc.save_model(os.path.join(MODEL_DIR, f"{name}_cat.cbm"))

        top = pd.Series(fx.feature_importances_, index=FEATURES).sort_values(ascending=False).head(8)
        meta_targets[name] = {"choice": choice, "val_mae": {k: round(v, 2) for k, v in val_mae.items()},
                              "test": res, "best_iterations": {"xgb": best_x, "cat": best_c},
                              "top_features": {k: round(float(v), 3) for k, v in top.items()}}

        lines.append(f"\n{name}  (test period, {len(te):,} hours)   chosen: {choice}")
        lines.append(f"  {'model':<18}{'MAE':>8}{'RMSE':>8}{'R2':>8}")
        for k, v in res.items():
            lines.append(f"  {k:<18}{v['mae']:>8}{v['rmse']:>8}{v['r2']:>8}")
        print("\n".join(lines[-(len(res) + 2):]))

        if len(used) > 1:
            te = te.assign(err=np.abs(y_te - (cur_te + (px_te + pc_te) / 2)))
            worst = te.groupby("city")["err"].mean().sort_values()
            lines.append("  per-city MAE (average model): " + ", ".join(f"{c} {v:.1f}" for c, v in worst.items()))

    meta = {"trained_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "algorithms": ["XGBoost", "CatBoost"], "features": FEATURES,
            "cities": used, "skipped_cities": skipped,
            "rows": {s: int((ds.split == s).sum()) for s in ("train", "val", "test")},
            "data_range": [str(ds.index.min()), str(ds.index.max())],
            "targets": meta_targets, "note": "Models predict the CHANGE from the current AQI; prediction = current + change."}
    with open(os.path.join(MODEL_DIR, "model_meta.json"), "w") as fh:
        json.dump(meta, fh, indent=2)
    header = [f"AirSense model training report  -  {meta['trained_at']}",
              f"Cities: {len(used)}   hourly rows: {len(ds):,}   data: {meta['data_range'][0][:10]} .. {meta['data_range'][1][:10]}",
              "MAE = average error in AQI points (lower is better).  'persistence' = 'AQI stays the same as now'."]
    with open(os.path.join(MODEL_DIR, "training_report.txt"), "w") as fh:
        fh.write("\n".join(header + lines) + "\n")
    print(f"\nSaved models + report in {MODEL_DIR}   ({time.time() - started:.0f}s)")


if __name__ == "__main__":
    main()
