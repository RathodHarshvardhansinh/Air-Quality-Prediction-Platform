import requests

from config import (
    AQI_API_KEY,
    WEATHER_CITY
)


def get_aqi_data():
    url = f"https://api.waqi.info/feed/{WEATHER_CITY}/"

    params = {
        "token": AQI_API_KEY
    }

    response = requests.get(url, params=params)

    if response.status_code != 200:
        print("AQI API Error:", response.status_code)
        print(response.text)
        return None

    result = response.json()

    if result.get("status") != "ok":
        print("AQI API returned an error:", result)
        return None

    data = result["data"]

    aqi_data = {
        "city": data.get("city", {}).get("name"),
        "aqi": data.get("aqi"),
        "pm25": data.get("iaqi", {}).get("pm25", {}).get("v"),
        "pm10": data.get("iaqi", {}).get("pm10", {}).get("v"),
        "no2": data.get("iaqi", {}).get("no2", {}).get("v"),
        "co": data.get("iaqi", {}).get("co", {}).get("v"),
        "o3": data.get("iaqi", {}).get("o3", {}).get("v"),
        "so2": data.get("iaqi", {}).get("so2", {}).get("v")
    }

    return aqi_data