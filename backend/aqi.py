import json
import math
import subprocess
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

def get_cpcb_data():
    if not CPCB_API_KEY:
        print("CPCB_API_KEY is not configured.")
        return []

    url = (
        "https://api.data.gov.in/resource/"
        "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
        f"?api-key={CPCB_API_KEY}"
        "&format=json"
        "&limit=5000"
    )

    try:
        result = subprocess.run(
            [
                "curl.exe",
                "-4",
                "--connect-timeout", "15",
                "--max-time", "45",
                url
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        if result.returncode != 0:
            print("CPCB curl error:", result.stderr)
            return []

        data = json.loads(result.stdout)
        if data.get("status") != "ok":
            print("CPCB API returned non-ok status:", data.get("status"))
            return []

        records = data.get("records", [])
        print("CPCB records received:", len(records))
        return records

    except Exception as error:
        print("CPCB API processing error:", error)
        return []


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
    Fetches raw pollutant measurements from Open-Meteo Air Quality.
    """
    url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": (
            "pm10,"
            "pm2_5,"
            "carbon_monoxide,"
            "nitrogen_dioxide,"
            "sulphur_dioxide,"
            "ozone,"
            "ammonia"
        ),
        "timezone": "auto"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            return {}

        data = response.json()
        current = data.get("current", {})
        return {
            "PM2.5": current.get("pm2_5"),
            "PM10": current.get("pm10"),
            "NO2": current.get("nitrogen_dioxide"),
            "SO2": current.get("sulphur_dioxide"),
            "CO": current.get("carbon_monoxide"),
            "O3": current.get("ozone"),
            "NH3": current.get("ammonia"),
        }
    except Exception as error:
        print("Open-Meteo raw fetch error:", error)
        return {}


def get_open_meteo_aqi(latitude, longitude, city_name):
    """
    Fetches real-time pollutant metrics from Open-Meteo Air Quality
    and calculates standard Indian CPCB AQI.
    """
    om_data = get_open_meteo_raw_pollutants(latitude, longitude)
    if not om_data:
        return None

    pm25 = om_data.get("PM2.5")
    pm10 = om_data.get("PM10")
    no2 = om_data.get("NO2")
    so2 = om_data.get("SO2")
    co = om_data.get("CO")
    o3 = om_data.get("O3")
    nh3 = om_data.get("NH3")

    aqi, category, prominent, sub_indices = calculate_aqi_details(
        pm25=pm25,
        pm10=pm10,
        no2=no2,
        co=co,
        o3=o3,
        so2=so2,
        nh3=nh3
    )

    return {
        "city": city_name,
        "station": f"Atmospheric Model ({city_name})",
        "station_distance_km": 0.0,
        "source": "Open-Meteo AQI (CPCB Standard)",
        "aqi": aqi,
        "category": category,
        "status": category,
        "prominent_pollutant": prominent,
        "sub_indices": sub_indices,
        "pm25": round(float(pm25), 2) if pm25 is not None else None,
        "pm10": round(float(pm10), 2) if pm10 is not None else None,
        "no2": round(float(no2), 2) if no2 is not None else None,
        "co": round(float(co) / 1000.0, 2) if co is not None else None,  # in mg/m3
        "o3": round(float(o3), 2) if o3 is not None else None,
        "so2": round(float(so2), 2) if so2 is not None else None,
        "nh3": round(float(nh3), 2) if nh3 is not None else None,
    }


# =====================================
# MAIN AQI DATA HANDLER
# =====================================

def get_aqi_data(latitude, longitude, city_name):
    """
    Returns accurate real-time AQI matching official CPCB / aqi.in standard.
    - Ground measurements from CPCB stations are prioritized.
    - Any missing pollutant parameters (due to inactive/missing sensors at that station)
      are automatically filled using Open-Meteo atmospheric sensors.
    - If CPCB is unreachable or station > 60km, Open-Meteo is used completely.
    """
    try:
        records = get_cpcb_data()

        if records:
            station = find_nearest_station(records, latitude, longitude)

            # If an active CPCB station exists within 60 km radius
            if station and station["distance_km"] <= 60.0:
                print(f"Using nearest CPCB station: {station['station']} ({station['distance_km']} km)")

                station_records = []
                for row in records:
                    try:
                        row_lat = float(row.get("latitude"))
                        row_lon = float(row.get("longitude"))
                    except (TypeError, ValueError):
                        continue

                    if (
                        abs(row_lat - station["latitude"]) < 0.0001
                        and abs(row_lon - station["longitude"]) < 0.0001
                    ):
                        station_records.append(row)

                pollutants = {}
                for row in station_records:
                    raw_id = (row.get("pollutant_id") or "").strip().upper()

                    # Normalize pollutant IDs
                    if raw_id in ("PM2.5", "PM25", "PM2_5"):
                        pollutant = "PM2.5"
                    elif raw_id in ("PM10", "PM_10"):
                        pollutant = "PM10"
                    elif raw_id in ("NO2", "NO_2"):
                        pollutant = "NO2"
                    elif raw_id in ("SO2", "SO_2"):
                        pollutant = "SO2"
                    elif raw_id in ("CO", "CARBON_MONOXIDE"):
                        pollutant = "CO"
                    elif raw_id in ("OZONE", "O3"):
                        pollutant = "O3"
                    elif raw_id in ("NH3", "AMMONIA"):
                        pollutant = "NH3"
                    else:
                        pollutant = raw_id

                    try:
                        value = float(row.get("avg_value"))
                        pollutants[pollutant] = value
                    except (TypeError, ValueError):
                        continue

                # Check if any main pollutants are missing from this station
                essential_keys = ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3"]
                has_missing = any(pollutants.get(k) is None for k in essential_keys)

                if has_missing:
                    # Fill missing pollutants with high-resolution Open-Meteo atmospheric data
                    om_fallback = get_open_meteo_raw_pollutants(latitude, longitude)
                    for k in essential_keys:
                        if pollutants.get(k) is None and om_fallback.get(k) is not None:
                            pollutants[k] = om_fallback[k]

                pm25 = pollutants.get("PM2.5")
                pm10 = pollutants.get("PM10")
                no2 = pollutants.get("NO2")
                co = pollutants.get("CO")
                o3 = pollutants.get("O3")
                so2 = pollutants.get("SO2")
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

                if aqi is not None:
                    # Format CO in mg/m3 for display
                    display_co = co
                    if display_co is not None:
                        if display_co > 100:
                            display_co = round(display_co / 1000.0, 2)
                        elif display_co > 1.0:
                            display_co = round(display_co / 100.0, 2)

                    result = {
                        "city": city_name,
                        "station": station["station"],
                        "station_distance_km": station["distance_km"],
                        "source": "CPCB Official Station",
                        "aqi": aqi,
                        "category": category,
                        "status": category,
                        "prominent_pollutant": prominent,
                        "sub_indices": sub_indices,
                        "pm25": round(pm25, 2) if pm25 is not None else None,
                        "pm10": round(pm10, 2) if pm10 is not None else None,
                        "no2": round(no2, 2) if no2 is not None else None,
                        "co": display_co,
                        "o3": round(o3, 2) if o3 is not None else None,
                        "so2": round(so2, 2) if so2 is not None else None,
                        "nh3": round(nh3, 2) if nh3 is not None else None,
                    }

                    print("CPCB AQI result:", result)
                    return result

        # If CPCB data is unavailable or station is too far (> 60km), use fallback
        print(f"Falling back to Open-Meteo AQI for {city_name}...")
        return get_open_meteo_aqi(latitude, longitude, city_name)

    except Exception as error:
        print("get_aqi_data error:", error)
        return get_open_meteo_aqi(latitude, longitude, city_name)

    except Exception as error:
        print("get_aqi_data error:", error)
        return get_open_meteo_aqi(latitude, longitude, city_name)


if __name__ == "__main__":
    print("\n==============================")
    print("Testing CPCB AQI Pipeline")
    print("==============================")

    cities = [
        ("Visnagar", 23.6010, 72.3990),
        ("Ahmedabad", 23.0225, 72.5714),
        ("Surat", 21.1702, 72.8311),
    ]

    for city, lat, lon in cities:
        print(f"\n--- Testing {city} ---")
        res = get_aqi_data(lat, lon, city)
        print(f"Result for {city}:")
        print(json.dumps(res, indent=2))