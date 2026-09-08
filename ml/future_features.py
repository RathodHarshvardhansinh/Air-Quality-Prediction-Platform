import pandas as pd


# =====================================
# FILES
# =====================================

INPUT_FILE = "ml_dataset.csv"
OUTPUT_FILE = "future_ml_dataset.csv"


# =====================================
# LOAD DATA
# =====================================

df = pd.read_csv(INPUT_FILE)

df["datetime"] = pd.to_datetime(df["datetime"])

df = df.sort_values("datetime").reset_index(drop=True)


print("Original rows:", len(df))


# =====================================
# CREATE LAG FEATURES
# =====================================

# Previous AQI values

df["aqi_lag_1h"] = df["us_aqi (USAQI)"].shift(1)

df["aqi_lag_3h"] = df["us_aqi (USAQI)"].shift(3)

df["aqi_lag_6h"] = df["us_aqi (USAQI)"].shift(6)

df["aqi_lag_12h"] = df["us_aqi (USAQI)"].shift(12)

df["aqi_lag_24h"] = df["us_aqi (USAQI)"].shift(24)


# =====================================
# POLLUTION LAG FEATURES
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
# CREATE FUTURE TARGET
# =====================================

# Next hour AQI

df["target_aqi_1h"] = (
    df["us_aqi (USAQI)"].shift(-1)
)


# =====================================
# REMOVE INVALID ROWS
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


print("\n================================")
print("Future Dataset Created")
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

print("\nNew prediction features:")

print("aqi_lag_1h")
print("aqi_lag_3h")
print("aqi_lag_6h")
print("aqi_lag_12h")
print("aqi_lag_24h")

print("\nTarget:")
print("target_aqi_1h")