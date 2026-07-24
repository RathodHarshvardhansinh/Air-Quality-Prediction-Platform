import requests

from config import (
    WEATHER_API_KEY,
    WEATHER_CITY,
    WEATHER_COUNTRY
)


def get_weather_data():
    url = "https://api.openweathermap.org/data/2.5/weather"

    params = {
        "q": f"{WEATHER_CITY},{WEATHER_COUNTRY}",
        "appid": WEATHER_API_KEY,
        "units": "metric"
    }

    response = requests.get(url, params=params)

    if response.status_code != 200:
        print("Weather API Error:", response.status_code)
        print(response.text)
        return None

    data = response.json()

    weather_data = {
        "city": data["name"],
        "temperature": data["main"]["temp"],
        "humidity": data["main"]["humidity"],
        "pressure": data["main"]["pressure"],
        "wind_speed": data["wind"]["speed"],
        "visibility": data.get("visibility")
    }

    return weather_data