import os
import joblib
import pandas as pd
import sqlite3


# =====================================
# PATHS
# =====================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATABASE = os.path.join(
    BASE_DIR,
    "backend",
    "airsense.db"
)

MODEL_1H = os.path.join(
    BASE_DIR,
    "ml",
    "aqi_model_1h.pkl"
)

MODEL_6H = os.path.join(
    BASE_DIR,
    "ml",
    "aqi_model_6h.pkl"
)


# =====================================
# LOAD MODELS
# =====================================

model_1h = joblib.load(MODEL_1H)
model_6h = joblib.load(MODEL_6H)


# =====================================
# GET CITY DATA
# =====================================

def get_prediction_data(city):

    connection = sqlite3.connect(DATABASE)

    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM environment_data
        WHERE LOWER(city) = LOWER(?)
        ORDER BY timestamp ASC
        """,
        (city,)
    )

    rows = cursor.fetchall()

    connection.close()

    if not rows:
        return None

    df = pd.DataFrame(
        [dict(row) for row in rows]
    )

    return df


# =====================================
# CREATE FEATURES
# =====================================

def build_features(city):

    df = get_prediction_data(city)

    if df is None or len(df) < 25:
        return None

    df["timestamp"] = pd.to_datetime(
    df["timestamp"],
    format="mixed"
)

    df = df.sort_values(
        "timestamp"
    ).reset_index(drop=True)


    # -------------------------------
    # TIME FEATURES
    # -------------------------------

    latest = df.iloc[-1]

    timestamp = latest["timestamp"]

    df["hour"] = df["timestamp"].dt.hour
    df["day"] = df["timestamp"].dt.day
    df["month"] = df["timestamp"].dt.month


    # -------------------------------
    # AQI LAGS
    # -------------------------------

    df["aqi_lag_1h"] = (
        df["aqi"].shift(1)
    )

    df["aqi_lag_3h"] = (
        df["aqi"].shift(3)
    )

    df["aqi_lag_6h"] = (
        df["aqi"].shift(6)
    )

    df["aqi_lag_12h"] = (
        df["aqi"].shift(12)
    )

    df["aqi_lag_24h"] = (
        df["aqi"].shift(24)
    )


    # -------------------------------
    # PM2.5 LAGS
    # -------------------------------

    df["pm25_lag_1h"] = (
        df["pm25"].shift(1)
    )

    df["pm25_lag_3h"] = (
        df["pm25"].shift(3)
    )

    df["pm25_lag_6h"] = (
        df["pm25"].shift(6)
    )


    # -------------------------------
    # WEATHER LAGS
    # -------------------------------

    df["temperature_lag_1h"] = (
        df["temperature"].shift(1)
    )

    df["humidity_lag_1h"] = (
        df["humidity"].shift(1)
    )

    df["wind_lag_1h"] = (
        df["wind_speed"].shift(1)
    )


    df = df.dropna()

    if df.empty:
        return None


    latest_features = df.iloc[-1]


    # -------------------------------
    # MODEL FEATURES
    # -------------------------------

    features = {

        "temperature_2m (°C)":
            latest_features["temperature"],

        "relative_humidity_2m (%)":
            latest_features["humidity"],

        "dew_point_2m (°C)":
            0,

        "apparent_temperature (°C)":
            latest_features["temperature"],

        "precipitation (mm)":
            0,

        "rain (mm)":
            0,

        "pressure_msl (hPa)":
            latest_features["pressure"],

        "surface_pressure (hPa)":
            latest_features["pressure"],

        "cloud_cover (%)":
            0,

        "wind_speed_10m (km/h)":
            latest_features["wind_speed"],

        "wind_direction_10m (°)":
            0,

        "wind_gusts_10m (km/h)":
            latest_features["wind_speed"],

        "pm10 (μg/m³)":
            latest_features["pm10"],

        "pm2_5 (μg/m³)":
            latest_features["pm25"],

        "carbon_monoxide (μg/m³)":
            latest_features["co"],

        "nitrogen_dioxide (μg/m³)":
            latest_features["no2"],

        "sulphur_dioxide (μg/m³)":
            latest_features["so2"],

        "ozone (μg/m³)":
            latest_features["o3"],

        "hour":
            timestamp.hour,

        "day_of_week":
            timestamp.dayofweek,

        "day_of_month":
            timestamp.day,

        "month":
            timestamp.month,

        "is_weekend":
            1 if timestamp.dayofweek >= 5 else 0,

        "aqi_lag_1h":
            latest_features["aqi_lag_1h"],

        "aqi_lag_3h":
            latest_features["aqi_lag_3h"],

        "aqi_lag_6h":
            latest_features["aqi_lag_6h"],

        "aqi_lag_12h":
            latest_features["aqi_lag_12h"],

        "aqi_lag_24h":
            latest_features["aqi_lag_24h"],

        "pm25_lag_1h":
            latest_features["pm25_lag_1h"],

        "pm25_lag_3h":
            latest_features["pm25_lag_3h"],

        "pm25_lag_6h":
            latest_features["pm25_lag_6h"],

        "temperature_lag_1h":
            latest_features["temperature_lag_1h"],

        "humidity_lag_1h":
            latest_features["humidity_lag_1h"],

        "wind_lag_1h":
            latest_features["wind_lag_1h"]

    }

    return pd.DataFrame([features])

# =====================================
# GET AQI PREDICTIONS
# =====================================

def get_predictions(city):

    features = build_features(city)

    if features is None:
        return None

    prediction_1h = model_1h.predict(
        features
    )[0]

    prediction_6h = model_6h.predict(
        features
    )[0]

    return {
        "city": city,
        "prediction_1h": round(
            float(prediction_1h),
            2
        ),
        "prediction_6h": round(
            float(prediction_6h),
            2
        )
    }

if __name__ == "__main__":

    city = "Visnagar"

    print("\n==============================")
    print("Testing Prediction Pipeline")
    print("==============================")

    features = build_features(city)

    if features is None:

        print(
            f"Not enough historical data for {city}"
        )

    else:

        print("\nFeatures created successfully!")

        print(
            "Feature count:",
            len(features.columns)
        )

        print("\n1-Hour prediction:")

        prediction_1h = model_1h.predict(
            features
        )[0]

        print(
            round(prediction_1h, 2)
        )

        print("\n6-Hour prediction:")

        prediction_6h = model_6h.predict(
            features
        )[0]

        print(
            round(prediction_6h, 2)
        )