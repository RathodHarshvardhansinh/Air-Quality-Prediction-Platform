import pandas as pd
import joblib

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


# =====================================
# LOAD DATA
# =====================================

DATA_FILE = "future_6h_dataset.csv"

df = pd.read_csv(DATA_FILE)

print("Dataset shape:", df.shape)


# =====================================
# TARGET
# =====================================

target = "target_aqi_6h"


# =====================================
# FEATURES
# =====================================

X = df.drop(
    columns=[
        "datetime",
        "us_aqi (USAQI)",
        "target_aqi_6h"
    ]
)

y = df[target]


# =====================================
# CHRONOLOGICAL SPLIT
# =====================================

split_index = int(
    len(df) * 0.80
)

X_train = X.iloc[:split_index]
X_test = X.iloc[split_index:]

y_train = y.iloc[:split_index]
y_test = y.iloc[split_index:]


print("\nTraining records:", len(X_train))
print("Testing records:", len(X_test))


# =====================================
# MODEL
# =====================================

model = RandomForestRegressor(

    n_estimators=300,

    random_state=42,

    n_jobs=-1

)


# =====================================
# TRAIN
# =====================================

print("\nTraining 6-hour prediction model...")

model.fit(
    X_train,
    y_train
)

print("Training completed!")

joblib.dump(
    model,
    "aqi_model_6h.pkl"
)

print("6-hour model saved as aqi_model_6h.pkl")


# =====================================
# PREDICTIONS
# =====================================

predictions = model.predict(
    X_test
)


# =====================================
# EVALUATION
# =====================================

mae = mean_absolute_error(
    y_test,
    predictions
)

rmse = mean_squared_error(
    y_test,
    predictions
) ** 0.5

r2 = r2_score(
    y_test,
    predictions
)


# =====================================
# RESULTS
# =====================================

print("\n================================")
print("6-HOUR AQI PREDICTION RESULTS")
print("================================")

print(
    f"MAE  : {mae:.2f}"
)

print(
    f"RMSE : {rmse:.2f}"
)

print(
    f"R²   : {r2:.3f}"
)


# =====================================
# SAMPLE PREDICTIONS
# =====================================

results = pd.DataFrame({

    "Actual_AQI": y_test.values,

    "Predicted_AQI": predictions

})


print("\nSample predictions:")

print(
    results.head(15)
)