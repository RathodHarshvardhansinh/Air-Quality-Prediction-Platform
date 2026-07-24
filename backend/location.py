import requests


def get_city_coordinates(city):

    url = "https://geocoding-api.open-meteo.com/v1/search"

    params = {
        "name": city,
        "count": 1,
        "language": "en",
        "format": "json"
    }

    response = requests.get(url, params=params)

    if response.status_code != 200:
        print("Geocoding API Error:", response.status_code)
        return None

    data = response.json()

    results = data.get("results")

    if not results:
        return None

    location = results[0]

    return {
        "name": location.get("name"),
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
        "country": location.get("country"),
        "state": location.get("admin1")
    }