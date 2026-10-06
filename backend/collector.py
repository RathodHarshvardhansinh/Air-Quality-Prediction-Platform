
from save_data import save_environment_data
from location import get_city_coordinates
from aqi import get_aqi_data, calculate_aqi
from weather import get_weather_data
from traffic import get_traffic_data
from iot_sensor import get_iot_sensor_data
import time

CITIES = [

    
    "Visnagar",


]

def collect_city_data(city):

    print(f"Collecting data for {city}...")

    location = get_city_coordinates(city)

    if location is None:
        print(f"{city} not found")
        return

    latitude = location["latitude"]
    longitude = location["longitude"]
    city_name = location["name"]

    # =====================================
    # STEP 1: Try the user's own IoT sensor network first.
    # (See backend/iot_sensor.py — set IOT_DEVICE_URL in .env once your
    # ESP32 + sensors are ready. Until then this returns None and the
    # pipeline below falls back to the CPCB/Weather/Traffic APIs, so the
    # platform works accurately right now regardless.)
    # =====================================

    iot_reading = get_iot_sensor_data()

    weather = get_weather_data(
        latitude,
        longitude,
        city_name
    )

    traffic = get_traffic_data(
        latitude,
        longitude,
        city_name
    )

    if iot_reading:
        print(f"Using live IoT sensor reading for {city_name}")

        computed_aqi = calculate_aqi(
            pm25=iot_reading["pm25"],
            pm10=iot_reading["pm10"],
            no2=iot_reading["no2"],
            co=iot_reading["co"],
            o3=iot_reading["o3"],
            so2=iot_reading["so2"],
        )

        aqi = {
            "aqi": computed_aqi,
            "pm25": iot_reading["pm25"],
            "pm10": iot_reading["pm10"],
            "no2": iot_reading["no2"],
            "co": iot_reading["co"],
            "o3": iot_reading["o3"],
            "so2": iot_reading["so2"],
        }

        # Prefer the sensor's own temperature/humidity/pressure if the
        # weather API happened to fail, since the IoT device already has them.
        if not weather:
            weather = {
                "temperature": iot_reading["temperature"],
                "humidity": iot_reading["humidity"],
                "pressure": iot_reading["pressure"],
                "wind_speed": 0,
            }

    else:
        # STEP 2: No IoT device connected (or it's unreachable) — use the
        # existing, already-working CPCB AQI API pipeline.
        aqi = get_aqi_data(
            latitude,
            longitude,
            city_name
        )

    if not aqi or not weather or not traffic:
        print(f"Unable to fetch data for {city}")
        return

    save_environment_data(

    city=city_name,

    aqi=aqi["aqi"],

    pm25=aqi["pm25"],
    pm10=aqi["pm10"],
    no2=aqi["no2"],
    co=aqi["co"],
    o3=aqi["o3"],
    so2=aqi["so2"],

    temperature=weather["temperature"],

    humidity=weather["humidity"],

    pressure=weather["pressure"],

    wind_speed=weather["wind_speed"],

    traffic_speed=traffic["current_speed"],

    free_flow_speed=traffic["free_flow_speed"]

)

    print(f"✔ Saved {city_name}")


if __name__ == "__main__":

    COLLECTION_INTERVAL = 60 * 60  # 1 hour

    while True:

        print("\n==============================")
        print("Starting data collection...")
        print("==============================\n")

        for city in CITIES:

            try:
                collect_city_data(city)

            except Exception as error:

                print(
                    f"Error collecting {city}:",
                    error
                )

        print("\nAll cities collected.")

        print(
            f"\nWaiting {COLLECTION_INTERVAL // 60} minutes "
            "before next collection...\n"
        )

        time.sleep(COLLECTION_INTERVAL)