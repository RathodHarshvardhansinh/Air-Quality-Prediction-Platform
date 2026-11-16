import pandas as pd


# =====================================
# FILES
# =====================================

INPUT_FILE = "../merged_visnagar.csv"
OUTPUT_FILE = "ml_dataset.csv"


# =====================================
# LOAD DATA
# =====================================

df = pd.read_csv(INPUT_FILE)

print("Original data shape:", df.shape)


# =====================================
# DATETIME
# =====================================

df["datetime"] = pd.to_datetime(df["datetime"])

df = df.sort_values("datetime").reset_index(drop=True)


# =====================================
# TIME FEATURES
# =====================================

df["hour"] = df["datetime"].dt.hour

df["day_of_week"] = df["datetime"].dt.dayofweek

df["day_of_month"] = df["datetime"].dt.day

df["month"] = df["datetime"].dt.month

df["is_weekend"] = (
    df["day_of_week"] >= 5
).astype(int)


# =====================================
# SELECT FEATURES
# =====================================

features = [

    # Weather
    "temperature_2m (°C)",
    "relative_humidity_2m (%)",
    "dew_point_2m (°C)",
    "apparent_temperature (°C)",
    "precipitation (mm)",
    "rain (mm)",
    "pressure_msl (hPa)",
    "surface_pressure (hPa)",
    "cloud_cover (%)",
    "wind_speed_10m (km/h)",
    "wind_direction_10m (°)",
    "wind_gusts_10m (km/h)",

    # Air pollution
    "pm10 (μg/m³)",
    "pm2_5 (μg/m³)",
    "carbon_monoxide (μg/m³)",
    "nitrogen_dioxide (μg/m³)",
    "sulphur_dioxide (μg/m³)",
    "ozone (μg/m³)",

    # Time
    "hour",
    "day_of_week",
    "day_of_month",
    "month",
    "is_weekend"

]


# =====================================
# TARGET
# =====================================

target = "us_aqi (USAQI)"


# =====================================
# CREATE ML DATASET
# =====================================

ml_df = df[
    ["datetime"] + features + [target]
].copy()


# =====================================
# CHECK MISSING VALUES
# =====================================

print("\nMissing values:")

print(
    ml_df.isnull()
    .sum()
    .sort_values(ascending=False)
    .head(10)
)


# =====================================
# REMOVE MISSING VALUES
# =====================================

before = len(ml_df)

ml_df = ml_df.dropna()

after = len(ml_df)


print(
    f"\nRemoved {before - after} rows "
    "because of missing values."
)


# =====================================
# SAVE DATASET
# =====================================

ml_df.to_csv(
    OUTPUT_FILE,
    index=False
)


# =====================================
# SUMMARY
# =====================================

print("\n=================================")
print("Feature Engineering Completed")
print("=================================")

print("Original rows:", before)

print("Final rows:", after)

print("Features:", len(features))

print("Target:", target)

print("Output:", OUTPUT_FILE)

print("\nFinal columns:")

for column in ml_df.columns:
    print("-", column)