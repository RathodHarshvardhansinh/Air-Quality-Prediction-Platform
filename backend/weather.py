import requests

from config import WEATHER_API_KEY

# Open-Meteo weather codes -> OpenWeather-style words (used only for the fallback)
_WMO = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast clouds",
    45: "fog", 48: "fog", 51: "drizzle", 53: "drizzle", 55: "drizzle",
    61: "rain", 63: "rain", 65: "heavy rain", 80: "rain showers",
    81: "rain showers", 82: "heavy rain", 95: "thunderstorm",
    96: "thunderstorm", 99: "thunderstorm",
}


def _openweather(latitude, longitude, city_name):
    if not WEATHER_API_KEY:
        return None
    response = requests.get(
        "https://api.openweathermap.org/data/2.5/weather",
        params={"lat": latitude, "lon": longitude, "appid": WEATHER_API_KEY, "units": "metric"},
        timeout=10,
    )
    if response.status_code != 200:
        print("OpenWeather error:", response.status_code, response.text[:200])
        return None
    data = response.json()
    return {
        "city": city_name,
        "temperature": data["main"]["temp"],
        "humidity": data["main"]["humidity"],
        "pressure": data["main"]["pressure"],
        "wind_speed": data["wind"]["speed"],
        "visibility": data.get("visibility"),
        "description": data["weather"][0]["description"],
        "source": "OpenWeather",
    }


def _open_meteo(latitude, longitude, city_name):
    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,pressure_msl,wind_speed_10m,weather_code",
            "wind_speed_unit": "ms",
            "timezone": "auto",
        },
        timeout=10,
    )
    if response.status_code != 200:
        return None
    c = response.json().get("current", {})
    if c.get("temperature_2m") is None:
        return None
    return {
        "city": city_name,
        "temperature": c.get("temperature_2m"),
        "humidity": c.get("relative_humidity_2m"),
        "pressure": round(c["pressure_msl"]) if c.get("pressure_msl") is not None else None,
        "wind_speed": c.get("wind_speed_10m"),
        "visibility": None,
        "description": _WMO.get(c.get("weather_code"), "clear sky"),
        "source": "Open-Meteo",
    }


def get_weather_data(latitude, longitude, city_name):
    """OpenWeather first, free Open-Meteo as automatic backup."""
    for fetch in (_openweather, _open_meteo):
        try:
            data = fetch(latitude, longitude, city_name)
            if data:
                return data
        except Exception as error:
            print(f"{fetch.__name__} failed:", error)
    return None
