from datetime import datetime, timezone
from math import radians, sin, cos, sqrt, atan2

from firebase_config import rtdb


MAX_SENSOR_AGE_MINUTES = 15
MAX_SENSOR_DISTANCE_KM = 10


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def distance_km(lat1, lon1, lat2, lon2):
    lat1 = radians(float(lat1))
    lon1 = radians(float(lon1))
    lat2 = radians(float(lat2))
    lon2 = radians(float(lon2))

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        sin(dlat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    )

    return 6371 * 2 * atan2(sqrt(a), sqrt(1 - a))


def _parse_timestamp(value):
    if not value:
        return None

    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt
    except (ValueError, TypeError):
        return None



def get_current_sensor_data():
    try:
        data = rtdb.reference("sensor_data/current").get()

        print("========== FIREBASE SENSOR TEST ==========")
        print("Raw Firebase data:", data)

        # Handle an extra "current" wrapper if it exists
        if (
            isinstance(data, dict)
            and "current" in data
            and isinstance(data["current"], dict)
            and "aqi" not in data
        ):
            data = data["current"]

        print("Processed sensor data:", data)
        print("==========================================")

        return data if isinstance(data, dict) else None

    except Exception as error:
        print("========== FIREBASE SENSOR ERROR ==========")
        print(error)
        print("==========================================")
        return None


def sensor_is_available_for_place(sensor, place):
    if not sensor or not place:
        return False

    # Check freshness.
    timestamp = _parse_timestamp(sensor.get("timestamp"))

    if timestamp:
        age_minutes = (
            datetime.now(timezone.utc) - timestamp
        ).total_seconds() / 60

        if age_minutes > MAX_SENSOR_AGE_MINUTES:
            return False

    # Prefer coordinate matching.
    sensor_lat = _float(sensor.get("latitude"))
    sensor_lon = _float(sensor.get("longitude"))
    place_lat = _float(place.get("latitude"))
    place_lon = _float(place.get("longitude"))

    if (
        sensor_lat is not None
        and sensor_lon is not None
        and place_lat is not None
        and place_lon is not None
    ):
        return (
            distance_km(
                sensor_lat,
                sensor_lon,
                place_lat,
                place_lon,
            )
            <= MAX_SENSOR_DISTANCE_KM
        )

    # Otherwise compare city names.
    sensor_city = str(sensor.get("city", "")).strip().lower()
    place_city = str(place.get("name", "")).strip().lower()
    
    print("Sensor record:", sensor)
    print("Selected place:", place)

    return bool(sensor_city and place_city and sensor_city == place_city)


def get_sensor_aqi(sensor, calculate_aqi_details):
    if not sensor:
        return None

    aqi = _float(sensor.get("aqi"))

    # If AQI is already supplied by ESP32/Firebase, use it.
    if aqi is not None:
        return {
            "aqi": round(aqi),
            "temperature": _float(sensor.get("temperature")),
            "humidity": _float(sensor.get("humidity")),
            "pm25": _float(sensor.get("pm25")),
            "pm10": _float(sensor.get("pm10")),
            "no2": _float(sensor.get("no2")),
            "co": _float(sensor.get("co")),
            "o3": _float(sensor.get("o3")),
            "so2": _float(sensor.get("so2")),
            "source": "ESP32 Sensor"
        }

    # Otherwise calculate AQI from pollutant values.
    result = calculate_aqi_details(
        pm25=_float(sensor.get("pm25")),
        pm10=_float(sensor.get("pm10")),
        no2=_float(sensor.get("no2")),
        co=_float(sensor.get("co")),
        o3=_float(sensor.get("o3")),
        so2=_float(sensor.get("so2")),
        nh3=_float(sensor.get("nh3")),
    )

    aqi, category, prominent, sub_indices = result

    if aqi is None:
        return None

    return {
        "aqi": aqi,
        "category": category,
        "prominent_pollutant": prominent,
        "sub_indices": sub_indices,
        "temperature": _float(sensor.get("temperature")),
        "humidity": _float(sensor.get("humidity")),
        "pm25": _float(sensor.get("pm25")),
        "pm10": _float(sensor.get("pm10")),
        "no2": _float(sensor.get("no2")),
        "co": _float(sensor.get("co")),
        "o3": _float(sensor.get("o3")),
        "so2": _float(sensor.get("so2")),
        "source": "ESP32 Sensor + CPCB NAQI"
    }