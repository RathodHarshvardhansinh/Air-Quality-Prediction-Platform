import sys

from save_data import save_reading
from location import get_city_coordinates
from aqi import get_aqi_data, calculate_aqi_details, calculate_us_aqi_details
from weather import get_weather_data
from traffic import get_traffic_data
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

    # IoT sensor readings are NOT mixed into this table (they arrive by POST /iot/readings and are
    # stored separately in iot_readings - see backend/iot.py).  Every row saved here is external-API data.
    weather = get_weather_data(latitude, longitude, city_name)
    traffic = get_traffic_data(latitude, longitude, city_name)
    aqi = get_aqi_data(latitude, longitude, city_name)

    # traffic is optional: TomTom has no data on many roads and that must not stop
    # the air-quality history from being saved.
    if not aqi or not weather:
        print(f"Unable to fetch data for {city}")
        return

    save_reading(city_name, aqi, weather, traffic)
    print(f"Saved {city_name}  (NAQI {aqi.get('aqi')}, US AQI {aqi.get('us_aqi')})")


if __name__ == "__main__":

    if len(sys.argv) > 1:
        CITIES = sys.argv[1:]          # e.g.  python collector.py Surat Rajkot

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