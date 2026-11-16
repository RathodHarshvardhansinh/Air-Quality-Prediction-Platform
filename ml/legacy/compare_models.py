import pandas as pd
import numpy as np
import joblib
import json
import warnings
warnings.filterwarnings("ignore")

from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, HistGradientBoostingRegressor, ExtraTreesRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Try optional libraries (may not be installed in this sandbox - no internet here)
HAS_XGB = HAS_LGBM = HAS_CAT = False
try:
    from xgboost import XGBRegressor
    HAS_XGB = True
except ImportError:
    pass
try:
    from lightgbm import LGBMRegressor
    HAS_LGBM = True
except ImportError:
    pass
try:
    from catboost import CatBoostRegressor
    HAS_CAT = True
except ImportError:
    pass

print("xgboost available:", HAS_XGB)
print("lightgbm available:", HAS_LGBM)
print("catboost available:", HAS_CAT)

def get_models():
    models = {
        "RandomForest (current)": RandomForestRegressor(n_estimators=300, random_state=42, n_jobs=-1),
        "ExtraTrees": ExtraTreesRegressor(n_estimators=300, random_state=42, n_jobs=-1),
        "GradientBoosting (sklearn)": GradientBoostingRegressor(n_estimators=300, max_depth=4, learning_rate=0.05, random_state=42),
        "HistGradientBoosting (LightGBM-equivalent)": HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05, random_state=42),
    }
    if HAS_XGB:
        models["XGBoost"] = XGBRegressor(n_estimators=400, max_depth=6, learning_rate=0.05, random_state=42, n_jobs=-1)
    if HAS_LGBM:
        models["LightGBM"] = LGBMRegressor(n_estimators=400, max_depth=6, learning_rate=0.05, random_state=42, n_jobs=-1, verbose=-1)
    if HAS_CAT:
        models["CatBoost"] = CatBoostRegressor(iterations=400, depth=6, learning_rate=0.05, random_state=42, verbose=0)
    return models

def evaluate(data_file, target, label):
    df = pd.read_csv(data_file)
    drop_cols = ["datetime", "us_aqi (USAQI)", target]
    drop_cols = [c for c in drop_cols if c in df.columns]
    X = df.drop(columns=drop_cols)
    y = df[target]

    split_index = int(len(df) * 0.80)
    X_train, X_test = X.iloc[:split_index], X.iloc[split_index:]
    y_train, y_test = y.iloc[:split_index], y.iloc[split_index:]

    results = []
    trained = {}
    for name, model in get_models().items():
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        mae = mean_absolute_error(y_test, preds)
        rmse = mean_squared_error(y_test, preds) ** 0.5
        r2 = r2_score(y_test, preds)
        results.append({"model": name, "MAE": round(mae,2), "RMSE": round(rmse,2), "R2": round(r2,4)})
        trained[name] = model
        print(f"[{label}] {name:45s} MAE={mae:6.2f}  RMSE={rmse:6.2f}  R2={r2:.4f}")

    results_sorted = sorted(results, key=lambda r: r["MAE"])
    best_name = results_sorted[0]["model"]
    print(f"\n>>> BEST for {label}: {best_name}  (MAE={results_sorted[0]['MAE']})\n")
    return results_sorted, trained[best_name], best_name, X.columns.tolist()

print("\n" + "="*70)
print("1-HOUR PREDICTION MODEL COMPARISON")
print("="*70)
res_1h, best_model_1h, best_name_1h, feat_1h = evaluate(
    "/home/claude/aq_full/Air quallity project/ml/future_ml_dataset.csv", "target_aqi_1h", "1H"
)

print("\n" + "="*70)
print("6-HOUR PREDICTION MODEL COMPARISON")
print("="*70)
res_6h, best_model_6h, best_name_6h, feat_6h = evaluate(
    "/home/claude/aq_full/Air quallity project/ml/future_6h_dataset.csv", "target_aqi_6h", "6H"
)

# Save comparison results
with open("/home/claude/aq_full/work/comparison_results.json", "w") as f:
    json.dump({
        "1h": {"results": res_1h, "best": best_name_1h},
        "6h": {"results": res_6h, "best": best_name_6h},
    }, f, indent=2)

# Save best models
joblib.dump(best_model_1h, "/home/claude/aq_full/work/aqi_model_1h_new.pkl")
joblib.dump(best_model_6h, "/home/claude/aq_full/work/aqi_model_6h_new.pkl")
print("Saved new best models.")
