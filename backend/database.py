import sqlite3

DATABASE = "airsense.db"


def create_database():

    connection = sqlite3.connect(DATABASE)

    cursor = connection.cursor()

    cursor.execute("""
       CREATE TABLE IF NOT EXISTS environment_data (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    city TEXT NOT NULL,

    aqi INTEGER,

    pm25 REAL,

    pm10 REAL,

    no2 REAL,

    co REAL,

    o3 REAL,

    so2 REAL,

    temperature REAL,

    humidity INTEGER,

    pressure INTEGER,

    wind_speed REAL,

    traffic_speed REAL,

    free_flow_speed REAL,

    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP

)
    """)

    connection.commit()

    connection.close()


def get_history():

    connection = sqlite3.connect(DATABASE)

    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    cursor.execute("""

        SELECT *

        FROM environment_data

        ORDER BY timestamp DESC

        LIMIT 20

    """)

    rows = cursor.fetchall()

    connection.close()

    return [dict(row) for row in rows]

def get_city_history(city, limit=24):

    connection = sqlite3.connect(DATABASE)

    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            city,
            aqi,
            temperature,
            humidity,
            pressure,
            wind_speed,
            traffic_speed,
            free_flow_speed,
            timestamp

        FROM environment_data

        WHERE LOWER(city) = LOWER(?)

        ORDER BY timestamp ASC

        LIMIT ?
        """,
        (city, limit)
    )

    rows = cursor.fetchall()

    connection.close()

    return [dict(row) for row in rows]

def get_city_history_by_range(city, hours):
    connection = sqlite3.connect(DATABASE)

    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            city,
            aqi,
            temperature,
            humidity,
            pressure,
            wind_speed,
            traffic_speed,
            free_flow_speed,
            timestamp

        FROM environment_data

        WHERE LOWER(city) = LOWER(?)

        AND timestamp >= datetime('now', ?)

        ORDER BY timestamp ASC
        """,
        (
            city,
            f"-{hours} hours"
        )
    )

    rows = cursor.fetchall()

    connection.close()

    return [dict(row) for row in rows]

def get_city_range_history(city, hours):
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
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
        FROM environment_data
        WHERE LOWER(city) = LOWER(?)
        AND timestamp >= datetime('now', ?)
        ORDER BY timestamp ASC
        """,
        (city, f"-{hours} hours")
    )

    rows = cursor.fetchall()

    connection.close()

    return [dict(row) for row in rows]