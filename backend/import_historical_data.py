import sqlite3
import pandas as pd
import os


# =====================================
# FILE PATHS
# =====================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

CSV_FILE = os.path.join(
    BASE_DIR,
    "merged_visnagar.csv"
)

DATABASE = os.path.join(
    BASE_DIR,
    "backend",
    "airsense.db"
)


# =====================================
# CHECK CSV
# =====================================

if not os.path.exists(CSV_FILE):

    print("CSV file not found:")
    print(CSV_FILE)

    raise SystemExit


print("Reading CSV:")
print(CSV_FILE)


# =====================================
# LOAD CSV
# =====================================

df = pd.read_csv(CSV_FILE)


print("\nCSV rows:", len(df))

print("CSV columns:")
print(list(df.columns))


# =====================================
# REQUIRED COLUMNS
# =====================================

required_columns = [

    "datetime",

    "temperature_2m (°C)",

    "relative_humidity_2m (%)",

    "pressure_msl (hPa)",

    "wind_speed_10m (km/h)",

    "pm10 (μg/m³)",

    "pm2_5 (μg/m³)",

    "carbon_monoxide (μg/m³)",

    "nitrogen_dioxide (μg/m³)",

    "sulphur_dioxide (μg/m³)",

    "ozone (μg/m³)",

    "us_aqi (USAQI)"

]


missing = [

    column
    for column in required_columns
    if column not in df.columns

]


if missing:

    print("\nMissing columns:")

    for column in missing:
        print("-", column)

    raise SystemExit


# =====================================
# CLEAN DATA
# =====================================

df["datetime"] = pd.to_datetime(
    df["datetime"],
    errors="coerce"
)


numeric_columns = [

    "temperature_2m (°C)",

    "relative_humidity_2m (%)",

    "pressure_msl (hPa)",

    "wind_speed_10m (km/h)",

    "pm10 (μg/m³)",

    "pm2_5 (μg/m³)",

    "carbon_monoxide (μg/m³)",

    "nitrogen_dioxide (μg/m³)",

    "sulphur_dioxide (μg/m³)",

    "ozone (μg/m³)",

    "us_aqi (USAQI)"

]


for column in numeric_columns:

    df[column] = pd.to_numeric(
        df[column],
        errors="coerce"
    )


# Remove invalid rows

df = df.dropna(
    subset=[
        "datetime",
        "us_aqi (USAQI)"
    ]
)


# Remove duplicate timestamps

df = df.drop_duplicates(
    subset=["datetime"]
)


df = df.sort_values(
    "datetime"
)


print(
    "\nValid CSV rows:",
    len(df)
)


# =====================================
# CONNECT DATABASE
# =====================================

connection = sqlite3.connect(
    DATABASE
)

cursor = connection.cursor()


# =====================================
# IMPORT
# =====================================

inserted = 0
skipped = 0


for _, row in df.iterrows():

    timestamp = row["datetime"].strftime(
        "%Y-%m-%d %H:%M:%S"
    )


    # Check duplicate

    cursor.execute(
        """
        SELECT id
        FROM environment_data

        WHERE LOWER(city) = LOWER(?)

        AND timestamp = ?

        LIMIT 1
        """,

        (
            "Visnagar",
            timestamp
        )
    )


    existing = cursor.fetchone()


    if existing:

        skipped += 1

        continue


    cursor.execute(
        """
        INSERT INTO environment_data(

            city,

            aqi,

            pm25,
            pm10,
            no2,
            co,
            o3,
            so2,

            temperature,
            humidity,
            pressure,
            wind_speed,

            traffic_speed,
            free_flow_speed,

            timestamp

        )

        VALUES(

            ?,

            ?,

            ?,
            ?,
            ?,
            ?,
            ?,
            ?,

            ?,
            ?,
            ?,
            ?,

            NULL,
            NULL,

            ?

        )
        """,

        (

            "Visnagar",

            int(row["us_aqi (USAQI)"]),

            float(row["pm2_5 (μg/m³)"]),
            float(row["pm10 (μg/m³)"]),
            float(row["nitrogen_dioxide (μg/m³)"]),
            float(row["carbon_monoxide (μg/m³)"]),
            float(row["ozone (μg/m³)"]),
            float(row["sulphur_dioxide (μg/m³)"]),

            float(row["temperature_2m (°C)"]),
            int(row["relative_humidity_2m (%)"]),
            float(row["pressure_msl (hPa)"]),
            float(row["wind_speed_10m (km/h)"]),

            timestamp

        )

    )


    inserted += 1


# =====================================
# SAVE
# =====================================

connection.commit()

connection.close()


# =====================================
# RESULT
# =====================================

print("\n================================")
print("HISTORICAL DATA IMPORT COMPLETE")
print("================================")

print(
    "Inserted:",
    inserted
)

print(
    "Skipped duplicates:",
    skipped
)

print(
    "Total processed:",
    len(df)
)

print("\nDatabase:")
print(DATABASE)