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