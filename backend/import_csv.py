# ---------------------------------------------------------------------------
# RETIRED: this old importer stored the US AQI inside the `aqi` column (and could add
# duplicate rows), which is what made the database inconsistent.
# Use instead:   python backend/fetch_city_history.py --cities "Surat,Rajkot"
# (run with --force only if you really want the old behaviour, then run fix_database.py)
# ---------------------------------------------------------------------------
import sys as _sys
if "--force" not in _sys.argv:
    raise SystemExit("This script is retired - use  python backend/fetch_city_history.py  "
                     "(see the note at the top of this file).")
_sys.argv = [a for a in _sys.argv if a != "--force"]

import csv
import sqlite3


DATABASE = "airsense.db"
CSV_FILE = "merged_visnagar.csv"


def import_csv_data():

    connection = sqlite3.connect(DATABASE)
    cursor = connection.cursor()

    with open(CSV_FILE, "r", encoding="utf-8") as file:

        reader = csv.DictReader(file)

        count = 0

        for row in reader:

            cursor.execute(
                """
                INSERT INTO environment_data (
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "Visnagar",

                    int(float(
                        row["us_aqi (USAQI)"]
                    )),

                    float(
                        row["pm2_5 (μg/m³)"]
                    ),

                    float(
                        row["pm10 (μg/m³)"]
                    ),

                    float(
                        row["nitrogen_dioxide (μg/m³)"]
                    ),

                    float(
                        row["carbon_monoxide (μg/m³)"]
                    ),

                    float(
                        row["ozone (μg/m³)"]
                    ),

                    float(
                        row["sulphur_dioxide (μg/m³)"]
                    ),

                    float(
                        row["temperature_2m (°C)"]
                    ),

                    int(float(
                        row["relative_humidity_2m (%)"]
                    )),

                    int(float(
                        row["pressure_msl (hPa)"]
                    )),

                    float(
                        row["wind_speed_10m (km/h)"]
                    ),

                    None,

                    None,

                    row["datetime"]
                )
            )

            count += 1

    connection.commit()
    connection.close()

    print("--------------------------------")
    print("CSV IMPORT SUCCESSFUL")
    print("Records imported:", count)
    print("--------------------------------")


if __name__ == "__main__":
    import_csv_data()