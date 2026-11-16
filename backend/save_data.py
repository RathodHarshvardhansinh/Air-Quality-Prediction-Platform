import sqlite3

from datetime import datetime

from database import DATABASE, create_database, normalize_ts


def save_environment_data(
    city,
    aqi,
    pm25=None, pm10=None, no2=None, co=None, o3=None, so2=None,
    temperature=None, humidity=None, pressure=None, wind_speed=None,
    traffic_speed=None, free_flow_speed=None,
    us_aqi=None,
    timestamp=None,
):
    """
    Low-level insert.  Values must already be in DATABASE units
    (co in ug/m3, wind_speed in km/h) - see database.py.
    Duplicate (city, timestamp) rows are ignored.
    """
    create_database()

    connection = sqlite3.connect(DATABASE)
    columns = ("city, aqi, us_aqi, pm25, pm10, no2, co, o3, so2, temperature, humidity, "
               "pressure, wind_speed, traffic_speed, free_flow_speed")
    values = [city, aqi, us_aqi, pm25, pm10, no2, co, o3, so2, temperature, humidity,
              pressure, wind_speed, traffic_speed, free_flow_speed]
    # always LOCAL time, like the imported history (SQLite's own default would be UTC)
    columns += ", timestamp"
    values.append(normalize_ts(timestamp if timestamp is not None else datetime.now()))

    placeholders = ", ".join("?" for _ in values)
    cursor = connection.execute(
        f"INSERT OR IGNORE INTO environment_data({columns}) VALUES ({placeholders})", values
    )
    inserted = cursor.rowcount
    connection.commit()
    connection.close()
    return inserted


def save_reading(city, aqi_data, weather_data, traffic_data=None):
    """
    High-level save used by the API and the collector.
    Takes the dicts the API returns and converts them to DATABASE units:
      CO  mg/m3 -> ug/m3      wind  m/s -> km/h
    """
    if not aqi_data or aqi_data.get("aqi") is None or not weather_data:
        return 0

    co_mg = aqi_data.get("co")
    wind = weather_data.get("wind_speed")
    traffic_data = traffic_data or {}

    return save_environment_data(
        city=city,
        aqi=aqi_data.get("aqi"),
        us_aqi=aqi_data.get("us_aqi"),
        pm25=aqi_data.get("pm25"), pm10=aqi_data.get("pm10"), no2=aqi_data.get("no2"),
        co=None if co_mg is None else round(co_mg * 1000.0, 1),
        o3=aqi_data.get("o3"), so2=aqi_data.get("so2"),
        temperature=weather_data.get("temperature"),
        humidity=weather_data.get("humidity"),
        pressure=weather_data.get("pressure"),
        wind_speed=None if wind is None else round(wind * 3.6, 1),
        traffic_speed=traffic_data.get("current_speed"),
        free_flow_speed=traffic_data.get("free_flow_speed"),
    )
