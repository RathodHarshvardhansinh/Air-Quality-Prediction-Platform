import pandas as pd


# =====================================
# FILES
# =====================================

INPUT_FILE = "ml_dataset.csv"
OUTPUT_FILE = "future_6h_dataset.csv"


# =====================================
# LOAD DATA
# =====================================

df = pd.read_csv(INPUT_FILE)

df["datetime"] = pd.to_datetime(df["datetime"])

df = df.sort_values("datetime").reset_index(drop=True)

print("Original rows:", len(df))


# =====================================
# AQI LAG FEATURES
# =====================================

df["aqi_lag_1h"] = (
    df["us_aqi (USAQI)"].shift(1)
)

df["aqi_lag_3h"] = (
    df["us_aqi (USAQI)"].shift(3)
)

df["aqi_lag_6h"] = (
    df["us_aqi (USAQI)"].shift(6)
)

df["aqi_lag_12h"] = (
    df["us_aqi (USAQI)"].shift(12)
)

df["aqi_lag_24h"] = (
    df["us_aqi (USAQI)"].shift(24)
)


# =====================================
# PM2.5 LAG FEATURES
# =====================================

df["pm25_lag_1h"] = (
    df["pm2_5 (μg/m³)"].shift(1)
)

df["pm25_lag_3h"] = (
    df["pm2_5 (μg/m³)"].shift(3)
)

df["pm25_lag_6h"] = (
    df["pm2_5 (μg/m³)"].shift(6)
)


# =====================================
# WEATHER LAG FEATURES
# =====================================

df["temperature_lag_1h"] = (
    df["temperature_2m (°C)"].shift(1)
)

df["humidity_lag_1h"] = (
    df["relative_humidity_2m (%)"].shift(1)
)

df["wind_lag_1h"] = (
    df["wind_speed_10m (km/h)"].shift(1)
)


# =====================================
# 6-HOUR FUTURE TARGET
# =====================================

df["target_aqi_6h"] = (
    df["us_aqi (USAQI)"].shift(-6)
)


# =====================================
# REMOVE MISSING ROWS
# =====================================

before = len(df)

df = df.dropna()

after = len(df)

print(
    "Removed rows:",
    before - after
)


# =====================================
# SAVE
# =====================================

df.to_csv(
    OUTPUT_FILE,
    index=False
)


# =====================================
# SUMMARY
# =====================================

print("\n================================")
print("6-HOUR FUTURE DATASET CREATED")
print("================================")

print(
    "Rows:",
    len(df)
)

print(
    "Columns:",
    len(df.columns)
)

print(
    "Output:",
    OUTPUT_FILE
)

print("\nTarget:")
print("target_aqi_6h")