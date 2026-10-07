import json
import math
import subprocess
import time
import requests

from config import CPCB_API_KEY


# =====================================
# DISTANCE CALCULATION (Haversine)
# =====================================

def calculate_distance(lat1, lon1, lat2, lon2):
    lat1 = float(lat1)
    lon1 = float(lon1)
    lat2 = float(lat2)
    lon2 = float(lon2)

    earth_radius = 6371  # km

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return earth_radius * c


# =====================================
# CPCB OFFICIAL BREAKPOINTS (NAQI Standard)
# =====================================

# PM2.5 (24-hour average in ug/m3)
PM25_BREAKPOINTS = [
    (0.0, 30.0, 0, 50),
    (30.0, 60.0, 51, 100),
    (60.0, 90.0, 101, 200),
    (90.0, 120.0, 201, 300),
    (120.0, 250.0, 301, 400),
    (250.0, 500.0, 401, 500),
]

# PM10 (24-hour average in ug/m3)
PM10_BREAKPOINTS = [
    (0.0, 50.0, 0, 50),
    (50.0, 100.0, 51, 100),
    (100.0, 250.0, 101, 200),
    (250.0, 350.0, 201, 300),
    (350.0, 430.0, 301, 400),
    (430.0, 600.0, 401, 500),
]

# NO2 (24-hour average in ug/m3)
NO2_BREAKPOINTS = [
    (0.0, 40.0, 0, 50),
    (40.0, 80.0, 51, 100),
    (80.0, 180.0, 101, 200),
    (180.0, 280.0, 201, 300),
    (280.0, 400.0, 301, 400),
    (400.0, 800.0, 401, 500),
]

# SO2 (24-hour average in ug/m3)
SO2_BREAKPOINTS = [
    (0.0, 40.0, 0, 50),
    (40.0, 80.0, 51, 100),
    (80.0, 380.0, 101, 200),
    (380.0, 800.0, 201, 300),
    (800.0, 1600.0, 301, 400),
    (1600.0, 2000.0, 401, 500),
]

# CO (8-hour average in mg/m3)
CO_BREAKPOINTS = [
    (0.0, 1.0, 0, 50),
    (1.0, 2.0, 51, 100),
    (2.0, 10.0, 101, 200),
    (10.0, 17.0, 201, 300),
    (17.0, 34.0, 301, 400),
    (34.0, 50.0, 401, 500),
]

# O3 / Ozone (8-hour average in ug/m3)
O3_BREAKPOINTS = [
    (0.0, 50.0, 0, 50),
    (50.0, 100.0, 51, 100),
    (100.0, 168.0, 101, 200),
    (168.0, 208.0, 201, 300),
    (208.0, 748.0, 301, 400),
    (748.0, 1000.0, 401, 500),
]

# NH3 / Ammonia (24-hour average in ug/m3)
NH3_BREAKPOINTS = [
    (0.0, 200.0, 0, 50),
    (200.0, 400.0, 51, 100),
    (400.0, 800.0, 101, 200),
    (800.0, 1200.0, 201, 300),
    (1200.0, 1800.0, 301, 400),
    (1800.0, 2500.0, 401, 500),
]


# =====================================
# SUB-INDEX CALCULATION
# =====================================

def calculate_sub_index(concentration, breakpoints):
    """
    Calculates sub-index Ip for a pollutant concentration Cp
    using the official linear interpolation formula:
    Ip = ((I_hi - I_lo) / (BP_hi - BP_lo)) * (Cp - BP_lo) + I_lo
    """
    if concentration is None:
        return None

    try:
        concentration = float(concentration)
    except (TypeError, ValueError):
        return None

    if concentration < 0:
        return 0.0

    for bp_low, bp_high, i_low, i_high in breakpoints:
        if bp_low <= concentration <= bp_high:
            sub_index = (
                ((i_high - i_low) / (bp_high - bp_low))
                * (concentration - bp_low)
            ) + i_low
            return round(sub_index, 2)

    # If concentration exceeds highest defined breakpoint
    if concentration > breakpoints[-1][1]:
        bp_low, bp_high, i_low, i_high = breakpoints[-1]
        sub_index = (
            ((i_high - i_low) / (bp_high - bp_low))
            * (concentration - bp_low)
        ) + i_low
        return round(sub_index, 2)

    return None


# =====================================
# AQI CATEGORY (Indian NAQI / CPCB Standard)
# =====================================

def get_aqi_category(aqi):
    if aqi is None:
        return "Unknown"
    if aqi <= 50:
        return "Good"
    if aqi <= 100:
        return "Satisfactory"
    if aqi <= 200:
        return "Moderate"
    if aqi <= 300:
        return "Poor"
    if aqi <= 400:
        return "Very Poor"
    return "Severe"


# =====================================
# OVERALL AQI CALCULATION
# =====================================

def calculate_aqi_details(
    pm25=None,
    pm10=None,
    no2=None,
    co=None,
    o3=None,
    so2=None,
    nh3=None
):
    """
    Calculates sub-indices and overall AQI based on CPCB standard.
    Overall AQI is the maximum of sub-indices.
    """
    sub_indices = {}

    if pm25 is not None:
        idx = calculate_sub_index(pm25, PM25_BREAKPOINTS)
        if idx is not None:
            sub_indices["PM2.5"] = idx

    if pm10 is not None:
        idx = calculate_sub_index(pm10, PM10_BREAKPOINTS)
        if idx is not None:
            sub_indices["PM10"] = idx

    if no2 is not None:
        idx = calculate_sub_index(no2, NO2_BREAKPOINTS)
        if idx is not None:
            sub_indices["NO2"] = idx

    if so2 is not None:
        idx = calculate_sub_index(so2, SO2_BREAKPOINTS)
        if idx is not None:
            sub_indices["SO2"] = idx

    if o3 is not None:
        idx = calculate_sub_index(o3, O3_BREAKPOINTS)
        if idx is not None:
            sub_indices["O3"] = idx

    if nh3 is not None:
        idx = calculate_sub_index(nh3, NH3_BREAKPOINTS)
        if idx is not None:
            sub_indices["NH3"] = idx

    if co is not None:
        try:
            co_val = float(co)
            # Normalize CO to mg/m3:
            # - If CO > 100 (e.g., 250 ug/m3 from Open-Meteo), convert ug/m3 to mg/m3 (/ 1000)
            # - If 1.0 < CO <= 100 (e.g., 45 from CPCB CAAQMS feed), convert to mg/m3 (/ 100)
            if co_val > 100.0:
                co_val = co_val / 1000.0
            elif co_val > 1.0:
                co_val = co_val / 100.0

            idx = calculate_sub_index(co_val, CO_BREAKPOINTS)
            if idx is not None:
                sub_indices["CO"] = idx
        except (TypeError, ValueError):
            pass

    if not sub_indices:
        return None, "Unknown", None, {}

    prominent = max(sub_indices, key=sub_indices.get)
    overall_aqi = round(sub_indices[prominent])
    category = get_aqi_category(overall_aqi)

    return overall_aqi, category, prominent, sub_indices


def calculate_aqi(pm25=None, pm10=None, no2=None, co=None, o3=None, so2=None, nh3=None):
    aqi, _, _, _ = calculate_aqi_details(pm25, pm10, no2, co, o3, so2, nh3)
    return aqi


# =====================================
# CPCB DATA FETCHER
# =====================================

_CPCB_CACHE = {"time": 0.0, "records": []}
_CPCB_TTL = 600  # seconds - the feed only changes about once an hour


def _download_cpcb(url):
    """requests first (works on Windows/Mac/Linux), curl only as a backup."""
    try:
        response = requests.get(url, timeout=(5, 10))
        if response.status_code == 200:
            return response.json()
        print("CPCB HTTP status:", response.status_code)
    except Exception as error:
        print("CPCB requests error:", error)

    for exe in ("curl.exe", "curl"):
        try:
            result = subprocess.run(
                [exe, "-4", "--connect-timeout", "5", "--max-time", "10", url],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            if result.returncode == 0 and result.stdout:
                return json.loads(result.stdout)
        except (FileNotFoundError, ValueError):
            continue
        except Exception as error:
            print("CPCB curl error:", error)
    return None


def get_cpcb_data():
    if not CPCB_API_KEY:
        print("CPCB_API_KEY is not configured.")
        return []

    # Cached: the CPCB download is big, do not repeat it for every request
    if _CPCB_CACHE["records"] and time.time() - _CPCB_CACHE["time"] < _CPCB_TTL:
        return _CPCB_CACHE["records"]

    url = (
        "https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
        f"?api-key={CPCB_API_KEY}&format=json&limit=5000"
    )

    data = _download_cpcb(url)
    if not data or data.get("status") != "ok":
        return _CPCB_CACHE["records"]  # old data is better than none

    records = data.get("records", [])
    print("CPCB records received:", len(records))
    _CPCB_CACHE["time"] = time.time()
    _CPCB_CACHE["records"] = records
    return records


# =====================================
# NEAREST STATION FINDER
# =====================================

def find_nearest_station(records, latitude, longitude):
    stations = {}

    for row in records:
        try:
            station_name = row.get("station")
            station_lat = float(row.get("latitude"))
            station_lon = float(row.get("longitude"))

            if not station_name:
                continue

            key = (station_name, station_lat, station_lon)
            stations[key] = True

        except (TypeError, ValueError):
            continue

    nearest = None
    nearest_distance = float("inf")

    for (station_name, station_lat, station_lon) in stations:
        distance = calculate_distance(latitude, longitude, station_lat, station_lon)
        if distance < nearest_distance:
            nearest_distance = distance
            nearest = {
                "station": station_name,
                "latitude": station_lat,
                "longitude": station_lon,
                "distance_km": round(distance, 2)
            }

    return nearest


# =====================================
# OPEN-METEO AIR QUALITY FETCHER
# =====================================

def get_open_meteo_raw_pollutants(latitude, longitude):
    """
    Fetch hourly pollutant data from Open-Meteo.

    Uses recent hourly values instead of the instantaneous
    'current' values so that the AQI calculation is more stable.
    """

    url = "https://air-quality-api.open-meteo.com/v1/air-quality"

    params = {
        "latitude": latitude,
        "longitude": longitude,

        "hourly": (
            "pm10,"
            "pm2_5,"
            "carbon_monoxide,"
            "nitrogen_dioxide,"
            "sulphur_dioxide,"
            "ozone"
        ),

        # Get the previous 24 hours
        "past_hours": 24,

        # No future forecast needed for the live AQI
        "forecast_hours": 0,

        "timezone": "auto"
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        if response.status_code != 200:
            print("Open-Meteo HTTP error:", response.status_code)
            return {}

        data = response.json()

        hourly = data.get("hourly", {})

        if not hourly:
            print("Open-Meteo hourly data missing")
            return {}

        def average(values):
            valid = []

            for value in values or []:
                try:
                    if value is not None:
                        valid.append(float(value))
                except (TypeError, ValueError):
                    pass

            if not valid:
                return None

            return sum(valid) / len(valid)

        return {
    "PM2.5": round(average(hourly.get("pm2_5")), 2) if average(hourly.get("pm2_5")) is not None else None,
    "PM10": round(average(hourly.get("pm10")), 2) if average(hourly.get("pm10")) is not None else None,
    "NO2": round(average(hourly.get("nitrogen_dioxide")), 2) if average(hourly.get("nitrogen_dioxide")) is not None else None,
    "SO2": round(average(hourly.get("sulphur_dioxide")), 2) if average(hourly.get("sulphur_dioxide")) is not None else None,
    "CO": round(average(hourly.get("carbon_monoxide")), 2) if average(hourly.get("carbon_monoxide")) is not None else None,
    "O3": round(average(hourly.get("ozone")), 2) if average(hourly.get("ozone")) is not None else None,
    "NH3": None
}

    except Exception as error:
        print("Open-Meteo hourly fetch error:", error)
        return {}

# =====================================
# MAIN AQI DATA HANDLER
# =====================================


# =====================================
# OPEN-METEO AQI CALCULATOR
# =====================================

def get_open_meteo_aqi(latitude, longitude, city_name):
    """
    Fetch pollutant data from Open-Meteo and calculate
    AQI using the CPCB/Indian NAQI breakpoint system.
    """

    pollutants = get_open_meteo_raw_pollutants(latitude, longitude)

    if not pollutants:
        return None

    pm25 = pollutants.get("PM2.5")
    pm10 = pollutants.get("PM10")
    no2 = pollutants.get("NO2")
    so2 = pollutants.get("SO2")
    co = pollutants.get("CO")
    o3 = pollutants.get("O3")
    nh3 = pollutants.get("NH3")

    aqi, category, prominent, sub_indices = calculate_aqi_details(
        pm25=pm25,
        pm10=pm10,
        no2=no2,
        co=co,
        o3=o3,
        so2=so2,
        nh3=nh3
    )

    if aqi is None:
        print(f"No valid AQI data available for {city_name}.")
        return None

    return {
        "city": city_name,
        "latitude": float(latitude),
        "longitude": float(longitude),

        "aqi": aqi,
        "category": category,
        "prominent_pollutant": prominent,

        "pm25": pm25,
        "pm10": pm10,
        "no2": no2,
        "so2": so2,
        "co": co,
        "o3": o3,
        "nh3": nh3,

        "sub_indices": sub_indices,

        "source": "Open-Meteo + CPCB NAQI calculation"
    }


# =====================================
# MAIN AQI DATA HANDLER
# =====================================

def get_aqi_data(latitude, longitude, city_name):
    """
    Returns AQI using Open-Meteo pollutant data
    with CPCB-standard AQI calculation.
    """

    try:
        print(f"Fetching Open-Meteo AQI for {city_name}...")

        result = get_open_meteo_aqi(
            latitude,
            longitude,
            city_name
        )

        if result:
            print("Open-Meteo AQI result:", result)
            return result

        print(f"Open-Meteo AQI unavailable for {city_name}.")
        return None

    except Exception as error:
        print("get_aqi_data error:", error)
        return None


