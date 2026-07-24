import requests


def get_aqi_data(latitude, longitude, city_name):

    url = "https://air-quality-api.open-meteo.com/v1/air-quality"

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": (
            "us_aqi,"
            "pm2_5,"
            "pm10,"
            "carbon_monoxide,"
            "nitrogen_dioxide,"
            "ozone,"
            "sulphur_dioxide"
        ),
        "timezone": "auto"
    }

    response = requests.get(url, params=params)

    if response.status_code != 200:
        print("Air Quality API Error:", response.status_code)
        print(response.text)
        return None

    data = response.json()
    current = data.get("current", {})

    return {
        "city": city_name,
        "aqi": current.get("us_aqi"),
        "pm25": current.get("pm2_5"),
        "pm10": current.get("pm10"),
        "no2": current.get("nitrogen_dioxide"),
        "co": current.get("carbon_monoxide"),
        "o3": current.get("ozone"),
        "so2": current.get("sulphur_dioxide"),
        "updated_at": current.get("time")
    }