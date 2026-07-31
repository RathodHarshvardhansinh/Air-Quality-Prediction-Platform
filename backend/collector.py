
from save_data import save_environment_data
from location import get_city_coordinates
from aqi import get_aqi_data
from weather import get_weather_data
from traffic import get_traffic_data
import time

CITIES = [

    "Ahmedabad",
    "Surat",
    "Vadodara",
    "Rajkot",
    "Visnagar",

    "Mumbai",
    "Pune",
    "Delhi",
    "Jaipur",
    "Lucknow",

    "Indore",
    "Bhopal",
    "Nagpur",
    "Hyderabad",
    "Bangalore",

    "Chennai",
    "Kolkata",
    "Patna",
    "Chandigarh",
    "Udaipur"

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

    aqi = get_aqi_data(
        latitude,
        longitude,
        city_name
    )

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

    if not aqi or not weather or not traffic:
        print(f"Unable to fetch data for {city}")
        return

    save_environment_data(

        city=city_name,

        aqi=aqi["aqi"],

        temperature=weather["temperature"],

        humidity=weather["humidity"],

        pressure=weather["pressure"],

        wind_speed=weather["wind_speed"],

        traffic_speed=traffic["current_speed"],

        free_flow_speed=traffic["free_flow_speed"]

    )

    print(f"✔ Saved {city_name}")


if __name__ == "__main__":

    while True:

        print("\n==============================")
        print("Starting data collection...")
        print("==============================\n")

        for city in CITIES:

            collect_city_data(city)

        print("\nAll cities collected.")

        print("Waiting 1 hour before next collection...\n")

        COLLECTION_INTERVAL = 60