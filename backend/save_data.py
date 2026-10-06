import sqlite3

from database import DATABASE, create_database


def save_environment_data(
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
    free_flow_speed
):

    create_database()

    connection = sqlite3.connect(DATABASE)

    cursor = connection.cursor()

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
            free_flow_speed

        )

        VALUES(
            ?,?,?,?,?,?,?,?,?,?,?,?,?,?
        )
        """,

        (
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
            free_flow_speed
        )

    )

    connection.commit()

    connection.close()