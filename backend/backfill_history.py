"""
backfill_history.py
====================

Purpose:
    Fill in the last N hours of REAL historical weather + air quality
    data for one or more cities, so /predict/1h and /predict/6h work
    immediately instead of needing 25+ hours of live collection first.

    This does NOT touch collector.py, app.py, database.py, save_data.py,
    or location.py. It only imports and reuses them.

Data source:
    Open-Meteo's free Archive/History APIs (no API key needed):
      - https://archive-api.open-meteo.com/v1/archive        (weather)
      - https://air-quality-api.open-meteo.com/v1/air-quality (AQI, past_days param)

    Traffic has no historical API (TomTom/etc only give "current"), so
    backfilled rows are saved with traffic_speed = NULL. Once collector.py
    runs live going forward, traffic fills in naturally.

How to use:
    1. Copy this file into your backend/ folder, next to save_data.py,
       location.py, database.py.
    2. From inside backend/, run:

         python backfill_history.py "Ahmedabad" "Surat" "Rajkot"

       (or edit the CITIES list below and just run it with no arguments)

    3. Check with check_records.py or your /history endpoint that rows
       showed up.

Safe to re-run: it only INSERTs rows, it does not delete or dedupe.
If you re-run it for the same city/hours you'll get duplicate rows —
run it once per city.
"""

import sys
import time
import requests
from datetime import datetime

from location import get_city_coordinates
from save_data import save_environment_data
from database import create_database


# =====================================
# CONFIG
# =====================================

# Used only if you run this file with no command-line arguments.
CITIES =[
    "Ahmedabad",
    "Mehsana",
    "Vadodara",
    "Surat",
    "Rajkot",
    "Gandhinagar",
    "Bhavnagar",
    "Jamnagar",
    "Junagadh",
    "Anand",
    "Navsari",
    "Porbandar",
    "Bhuj",
    "Valsad",
    "Patan",
    "Bharuch",
    "Surendranagar",
    "Gandhidham",
    "Morbi",
    "Amreli",
    "Nadiad",
    "Dahod",
    "Vapi",
    "Anjar",
    "Godhra",
    "Veraval",
    "Wadhwan",
    "Palitana",
    "Dhoraji",
    "Deesa",
    "Palanpur",
    "Mahuva",
    "Keshod",
    "Jetpur",
    "Mangrol",
    "Bardoli",
    "Kalol",
    "Viramgam",
    "Chhota Udaipur",
    "Mansa",
    "Savarkundla",
    "Kadi",
    "Talaja",
    "Dabhoi",
    "Sidhpur",
    "Borsad",
    "Vijapur",
    "visnagar",
    "Umreth",
    "Idar",
    "Pardi",
    "Kheda",
    "Bhayavadar",
    "Lunawada",
    "himmatnagar",
    
    
]
CITIES = list(dict.fromkeys(CITIES))  # remove duplicate city names, if any

# How many past hours of data to pull. 48 gives a safe buffer above the
# 25-hour minimum prediction.py needs.
HOURS_BACK = 48


# =====================================
# FETCH HISTORICAL WEATHER (Open-Meteo Archive API)
# =====================================

def fetch_historical_weather(latitude, longitude, hours_back):

    url = "https://archive-api.open-meteo.com/v1/archive"

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "temperature_2m,relative_humidity_2m,pressure_msl,wind_speed_10m",
        "past_days": max(1, (hours_back // 24) + 1),
        "timezone": "auto",
    }

    response = requests.get(url, params=params, timeout=15)

    if response.status_code != 200:
        print("Weather history API error:", response.status_code, response.text)
        return None

    data = response.json()
    hourly = data.get("hourly", {})

    if not hourly.get("time"):
        return None

    return hourly


# =====================================
# FETCH HISTORICAL AIR QUALITY (Open-Meteo Air Quality API, past_days)
# =====================================

def fetch_historical_aqi(latitude, longitude, hours_back):

    url = "https://air-quality-api.open-meteo.com/v1/air-quality"

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "us_aqi,pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone",
        "past_days": max(1, (hours_back // 24) + 1),
        "timezone": "auto",
    }

    response = requests.get(url, params=params, timeout=15)

    if response.status_code != 200:
        print("AQI history API error:", response.status_code, response.text)
        return None

    data = response.json()
    hourly = data.get("hourly", {})

    if not hourly.get("time"):
        return None

    return hourly


# =====================================
# BACKFILL ONE CITY
# =====================================

def backfill_city(city, hours_back=HOURS_BACK):

    print(f"\n=== Backfilling {city} ===")

    location = get_city_coordinates(city)

    if location is None:
        print(f"Could not find coordinates for {city}, skipping.")
        return

    latitude = location["latitude"]
    longitude = location["longitude"]
    city_name = location["name"]

    weather = fetch_historical_weather(latitude, longitude, hours_back)
    aqi = fetch_historical_aqi(latitude, longitude, hours_back)

    if weather is None or aqi is None:
        print(f"Could not fetch historical data for {city_name}, skipping.")
        return

    # Align on timestamps common to both weather and AQI responses
    weather_times = weather["time"]
    aqi_times = aqi["time"]
    common_times = [t for t in weather_times if t in aqi_times]

    # Only keep the most recent `hours_back` hours
    common_times = common_times[-hours_back:]

    saved = 0

    for ts in common_times:

        w_idx = weather_times.index(ts)
        a_idx = aqi_times.index(ts)

        temperature = weather["temperature_2m"][w_idx]
        humidity = weather["relative_humidity_2m"][w_idx]
        pressure = weather["pressure_msl"][w_idx]
        wind_speed = weather["wind_speed_10m"][w_idx]

        us_aqi = aqi["us_aqi"][a_idx]
        pm10 = aqi["pm10"][a_idx]
        pm25 = aqi["pm2_5"][a_idx]
        co = aqi["carbon_monoxide"][a_idx]
        no2 = aqi["nitrogen_dioxide"][a_idx]
        so2 = aqi["sulphur_dioxide"][a_idx]
        o3 = aqi["ozone"][a_idx]

        # Skip incomplete rows rather than saving broken data
        if None in (temperature, humidity, pressure, wind_speed, us_aqi, pm10, pm25, co, no2, so2, o3):
            continue

        save_environment_data(
            city=city_name,
            aqi=us_aqi,
            pm25=pm25,
            pm10=pm10,
            no2=no2,
            co=co,
            o3=o3,
            so2=so2,
            temperature=temperature,
            humidity=humidity,
            pressure=pressure,
            wind_speed=wind_speed,
            traffic_speed=None,       # no historical traffic API available
            free_flow_speed=None,
        )

        saved += 1

    print(f"Saved {saved} historical rows for {city_name}.")


# =====================================
# MAIN
# =====================================

if __name__ == "__main__":

    create_database()

    cities_to_run = sys.argv[1:] if len(sys.argv) > 1 else CITIES

    print("Backfilling cities:", cities_to_run)

    for city in cities_to_run:
        backfill_city(city)
        time.sleep(2)  # small gap between cities so we don't hammer the free API

    print("\nDone. Predictions should now work immediately for these cities")
    print("(as long as they have >= 25 saved rows).")