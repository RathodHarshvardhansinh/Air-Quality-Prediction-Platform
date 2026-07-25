import requests


# ==========================================
# FIND CITY LOCATION
# ==========================================

def get_city_coordinates(city_name):

    url = "https://geocoding-api.open-meteo.com/v1/search"

    params = {
        "name": city_name,
        "count": 1,
        "language": "en",
        "format": "json"
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        if response.status_code != 200:

            print(
                "Geocoding API Error:",
                response.status_code
            )

            return None


        data = response.json()

        results = data.get(
            "results",
            []
        )


        if not results:

            return None


        location = results[0]


        return {
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
            "city": location.get("name"),
            "country": location.get("country"),
            "state": location.get("admin1")
        }


    except requests.RequestException as error:

        print(
            "Geocoding Request Error:",
            error
        )

        return None


# ==========================================
# GET AQI DATA
# ==========================================

def get_aqi_data(
    latitude,
    longitude,
    city_name
):

    url = (
        "https://air-quality-api.open-meteo.com/v1/air-quality"
    )


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


    try:

        response = requests.get(
            url,
            params=params,
            timeout=10
        )


        if response.status_code != 200:

            print(
                "Air Quality API Error:",
                response.status_code
            )

            print(
                response.text
            )

            return None


        data = response.json()

        current = data.get(
            "current",
            {}
        )


        return {

            "city": city_name,

            "aqi": current.get(
                "us_aqi"
            ),

            "pm25": current.get(
                "pm2_5"
            ),

            "pm10": current.get(
                "pm10"
            ),

            "no2": current.get(
                "nitrogen_dioxide"
            ),

            "co": current.get(
                "carbon_monoxide"
            ),

            "o3": current.get(
                "ozone"
            ),

            "so2": current.get(
                "sulphur_dioxide"
            ),

            "updated_at": current.get(
                "time"
            )

        }


    except requests.RequestException as error:

        print(
            "AQI Request Error:",
            error
        )

        return None