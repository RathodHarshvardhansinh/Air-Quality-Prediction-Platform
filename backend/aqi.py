import json
import math
import time
from datetime import datetime, timedelta

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
# INDIAN NAQI  (CPCB)  -  overall AQI
#
# IMPORTANT UNITS used everywhere in this file:
#   PM2.5, PM10, NO2, SO2, O3, NH3 ... ug/m3
#   CO .............................. mg/m3   (NOT ug/m3)
# =====================================

def naqi_is_complete(sub_indices):
    """Official rule: at least 3 pollutants, and one of them must be PM2.5 or PM10."""
    return len(sub_indices) >= 3 and ("PM2.5" in sub_indices or "PM10" in sub_indices)


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
    Indian NAQI.  Overall AQI = highest sub-index.
    `co` must be in mg/m3.  (The old version guessed the unit from the size of the
    number, which made real CPCB CO readings 100x too small.)
    """
    sub_indices = {}

    for name, value, table in (
        ("PM2.5", pm25, PM25_BREAKPOINTS),
        ("PM10", pm10, PM10_BREAKPOINTS),
        ("NO2", no2, NO2_BREAKPOINTS),
        ("SO2", so2, SO2_BREAKPOINTS),
        ("O3", o3, O3_BREAKPOINTS),
        ("NH3", nh3, NH3_BREAKPOINTS),
        ("CO", co, CO_BREAKPOINTS),
    ):
        if value is None:
            continue
        idx = calculate_sub_index(value, table)
        if idx is not None:
            sub_indices[name] = idx

    if not sub_indices:
        return None, "Unknown", None, {}

    prominent = max(sub_indices, key=sub_indices.get)
    overall_aqi = int(round(sub_indices[prominent]))
    return overall_aqi, get_aqi_category(overall_aqi), prominent, sub_indices


def calculate_aqi(pm25=None, pm10=None, no2=None, co=None, o3=None, so2=None, nh3=None):
    aqi, _, _, _ = calculate_aqi_details(pm25, pm10, no2, co, o3, so2, nh3)
    return aqi


# =====================================
# US EPA AQI  (what IQAir, Google, AccuWeather, most phone apps show)
# PM breakpoints = EPA 2024 revision.
# =====================================

US_PM25 = [(0.0, 9.0, 0, 50), (9.1, 35.4, 51, 100), (35.5, 55.4, 101, 150),
           (55.5, 125.4, 151, 200), (125.5, 225.4, 201, 300), (225.5, 325.4, 301, 500)]
US_PM10 = [(0, 54, 0, 50), (55, 154, 51, 100), (155, 254, 101, 150),
           (255, 354, 151, 200), (355, 424, 201, 300), (425, 504, 301, 400), (505, 604, 401, 500)]
US_O3_PPB = [(0, 54, 0, 50), (55, 70, 51, 100), (71, 85, 101, 150), (86, 105, 151, 200), (106, 200, 201, 300)]
US_CO_PPM = [(0.0, 4.4, 0, 50), (4.5, 9.4, 51, 100), (9.5, 12.4, 101, 150), (12.5, 15.4, 151, 200),
             (15.5, 30.4, 201, 300), (30.5, 40.4, 301, 400), (40.5, 50.4, 401, 500)]
US_SO2_PPB = [(0, 35, 0, 50), (36, 75, 51, 100), (76, 185, 101, 150), (186, 304, 151, 200),
              (305, 604, 201, 300), (605, 804, 301, 400), (805, 1004, 401, 500)]
US_NO2_PPB = [(0, 53, 0, 50), (54, 100, 51, 100), (101, 360, 101, 150), (361, 649, 151, 200),
              (650, 1249, 201, 300), (1250, 1649, 301, 400), (1650, 2049, 401, 500)]


def get_us_aqi_category(aqi):
    if aqi is None:
        return "Unknown"
    if aqi <= 50:
        return "Good"
    if aqi <= 100:
        return "Moderate"
    if aqi <= 150:
        return "Unhealthy for Sensitive Groups"
    if aqi <= 200:
        return "Unhealthy"
    if aqi <= 300:
        return "Very Unhealthy"
    return "Hazardous"


def _us_sub(value, table, decimals):
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return 0.0
    factor = 10 ** decimals
    value = math.floor(value * factor) / factor          # EPA truncates, it does not round
    for lo, hi, i_lo, i_hi in table:
        if lo <= value <= hi:
            return round((i_hi - i_lo) / (hi - lo) * (value - lo) + i_lo, 2)
    lo, hi, i_lo, i_hi = table[-1]
    if value > hi:
        return min(500.0, round((i_hi - i_lo) / (hi - lo) * (value - lo) + i_lo, 2))
    return None


def calculate_us_aqi_details(pm25=None, pm10=None, no2=None, so2=None, co=None, o3=None):
    """
    US AQI.  pm25/pm10: ug/m3 (ideally NowCast values).  no2/so2/o3: ug/m3.  co: mg/m3.
    Gas conversions use 25 C / 1 atm.
    """
    subs = {}

    def put(name, idx):
        if idx is not None:
            subs[name] = idx

    put("PM2.5", _us_sub(pm25, US_PM25, 1))
    put("PM10", _us_sub(pm10, US_PM10, 0))
    put("NO2", _us_sub(None if no2 is None else no2 * 0.5314, US_NO2_PPB, 0))
    put("SO2", _us_sub(None if so2 is None else so2 * 0.3816, US_SO2_PPB, 0))
    put("O3", _us_sub(None if o3 is None else o3 * 0.5094, US_O3_PPB, 0))
    put("CO", _us_sub(None if co is None else co * 0.8729, US_CO_PPM, 1))

    if not subs:
        return None, "Unknown", None, {}
    prominent = max(subs, key=subs.get)
    aqi = int(round(subs[prominent]))
    return aqi, get_us_aqi_category(aqi), prominent, subs


def nowcast(values_recent_first):
    """EPA NowCast for PM: weighted average of the last 12 hours (recent hours count more)."""
    v = list(values_recent_first)[:12]
    if len(v) < 3 or sum(1 for x in v[:3] if x is not None) < 2:
        return None
    valid = [x for x in v if x is not None]
    c_max, c_min = max(valid), min(valid)
    w = (c_min / c_max) if c_max > 0 else 1.0
    w = max(w, 0.5)
    num = den = 0.0
    for i, x in enumerate(v):
        if x is None:
            continue
        num += x * (w ** i)
        den += w ** i
    return num / den if den else None


# =====================================
# OPEN-METEO HOURLY SERIES  ->  proper averages
# =====================================

_OM_VARS = ["pm10", "pm2_5", "carbon_monoxide", "nitrogen_dioxide", "sulphur_dioxide", "ozone", "ammonia"]


def get_open_meteo_series(latitude, longitude, past_hours=48):
    """Last `past_hours` hours + the current hour (oldest first).  None if unavailable."""
    try:
        response = requests.get(
            "https://air-quality-api.open-meteo.com/v1/air-quality",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "hourly": ",".join(_OM_VARS),
                "past_hours": past_hours,
                "forecast_hours": 1,
                "timezone": "auto",
            },
            timeout=10,
        )
        if response.status_code != 200:
            return None
        hourly = response.json().get("hourly") or {}
        times = hourly.get("time") or []
        if not times:
            return None
        return {"time": times, **{k: hourly.get(k) or [None] * len(times) for k in _OM_VARS}}
    except Exception as error:
        print("Open-Meteo series error:", error)
        return None


def _mean(values, min_count):
    vals = [x for x in values if x is not None]
    return sum(vals) / len(vals) if len(vals) >= min_count else None


def aqi_inputs_from_series(series):
    """
    Turns an hourly series (oldest first, ug/m3) into:
      naqi_in : 24-h averages for PM/NO2/SO2/NH3, latest 8-h average for CO/O3 (CO in mg/m3)
      us_in   : NowCast for PM, latest 8-h average for CO/O3, latest hour for NO2/SO2
      now     : the latest hourly values (for display)
    """
    n = len(series["time"])
    col = lambda k: list(series[k])
    last24 = lambda k: col(k)[-24:]

    co_mg = [None if x is None else x / 1000.0 for x in col("carbon_monoxide")]

    naqi_in = {
        "pm25": _mean(last24("pm2_5"), 16),
        "pm10": _mean(last24("pm10"), 16),
        "no2": _mean(last24("nitrogen_dioxide"), 16),
        "so2": _mean(last24("sulphur_dioxide"), 16),
        "nh3": _mean(last24("ammonia"), 16),
        "co": _mean(co_mg[-8:], 6),                  # latest 8-hour average (CPCB real-time rule)
        "o3": _mean(col("ozone")[-8:], 6),
    }
    latest = lambda k: (col(k)[-1] if n else None)
    rev = lambda k: list(reversed(col(k)))

    us_in = {
        "pm25": nowcast(rev("pm2_5")),
        "pm10": nowcast(rev("pm10")),
        "no2": latest("nitrogen_dioxide"),
        "so2": latest("sulphur_dioxide"),
        "co": _mean(co_mg[-8:], 6),
        "o3": _mean(col("ozone")[-8:], 6),
    }
    now = {
        "pm25": latest("pm2_5"), "pm10": latest("pm10"), "no2": latest("nitrogen_dioxide"),
        "so2": latest("sulphur_dioxide"), "o3": latest("ozone"), "nh3": latest("ammonia"),
        "co": None if latest("carbon_monoxide") is None else latest("carbon_monoxide") / 1000.0,
    }
    return naqi_in, us_in, now


def _r(value, digits=2):
    return None if value is None else round(float(value), digits)


def build_result(city_name, station, distance, source, source_type, naqi_in, us_in, shown,
                 measured_at, mixed=False):
    aqi, category, prominent, subs = calculate_aqi_details(
        pm25=naqi_in.get("pm25"), pm10=naqi_in.get("pm10"), no2=naqi_in.get("no2"),
        co=naqi_in.get("co"), o3=naqi_in.get("o3"), so2=naqi_in.get("so2"), nh3=naqi_in.get("nh3"))
    us_aqi, us_category, us_prominent, us_subs = calculate_us_aqi_details(
        pm25=us_in.get("pm25"), pm10=us_in.get("pm10"), no2=us_in.get("no2"),
        so2=us_in.get("so2"), co=us_in.get("co"), o3=us_in.get("o3"))
    if us_aqi is not None and "PM2.5" not in us_subs and "PM10" not in us_subs:
        us_aqi, us_category, us_prominent, us_subs = None, "Unknown", None, {}   # gases alone mislead
    if aqi is None and us_aqi is None:
        return None
    return {
        "city": city_name,
        "station": station,
        "station_distance_km": distance,
        "source": source,
        "source_type": source_type,                 # "station" (ground sensors) or "model"
        "mixed_sources": mixed,
        "measured_at": measured_at,
        "aqi": aqi,                                  # Indian NAQI
        "category": category,
        "status": category,
        "prominent_pollutant": prominent,
        "sub_indices": subs,
        "partial": not naqi_is_complete(subs),
        "us_aqi": us_aqi,                            # US EPA AQI
        "us_category": us_category,
        "us_prominent_pollutant": us_prominent,
        "us_sub_indices": us_subs,
        "averaging": ("NAQI: 24-h average (8-h for CO/O3). US AQI: NowCast"
                      if source_type == "model" else "Latest hourly station average"),
        # concentrations shown on the dashboard = latest hour  (CO in mg/m3)
        "pm25": _r(shown.get("pm25")), "pm10": _r(shown.get("pm10")), "no2": _r(shown.get("no2")),
        "co": _r(shown.get("co")), "o3": _r(shown.get("o3")), "so2": _r(shown.get("so2")),
        "nh3": _r(shown.get("nh3")),
    }


def get_open_meteo_aqi(latitude, longitude, city_name):
    """Model-based fallback (CAMS via Open-Meteo).  Proper 24-h averaging, both standards."""
    series = get_open_meteo_series(latitude, longitude)
    if not series:
        return None
    naqi_in, us_in, now = aqi_inputs_from_series(series)
    return build_result(
        city_name, f"Atmospheric Model ({city_name})", 0.0,
        "Open-Meteo / CAMS model estimate", "model", naqi_in, us_in, now,
        series["time"][-1],
    )


# kept for backwards compatibility (older scripts import it)
def get_open_meteo_raw_pollutants(latitude, longitude):
    series = get_open_meteo_series(latitude, longitude, past_hours=1)
    if not series:
        return {}
    _, _, now = aqi_inputs_from_series(series)
    return {"PM2.5": now["pm25"], "PM10": now["pm10"], "NO2": now["no2"], "SO2": now["so2"],
            "CO": now["co"], "O3": now["o3"], "NH3": now["nh3"]}


# =====================================
# CPCB OFFICIAL STATION FEED
# =====================================

_CPCB_CACHE = {"time": 0.0, "records": [], "failed_at": 0.0}
_CPCB_TTL = 600           # keep a good download for 10 minutes
_CPCB_RETRY_AFTER = 300   # after a failure, skip CPCB for 5 minutes (searches stay fast)
_CPCB_TIMEOUT = (5, 10)   # connect, read  - this server is often slow, so fail fast
MAX_STATION_KM = 30.0     # was 60 km: a station that far away is a different place
MAX_STATION_AGE_H = 6


def get_cpcb_data():
    if not CPCB_API_KEY:
        return []

    now = time.time()
    if _CPCB_CACHE["records"] and now - _CPCB_CACHE["time"] < _CPCB_TTL:
        return _CPCB_CACHE["records"]
    if now - _CPCB_CACHE["failed_at"] < _CPCB_RETRY_AFTER:
        return _CPCB_CACHE["records"]

    url = ("https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
           f"?api-key={CPCB_API_KEY}&format=json&limit=5000")
    try:
        response = requests.get(url, timeout=_CPCB_TIMEOUT)
        data = response.json() if response.status_code == 200 else None
    except Exception as error:
        print("CPCB unavailable (using the model for 5 min):", type(error).__name__)
        data = None

    if not data or data.get("status") != "ok":
        _CPCB_CACHE["failed_at"] = time.time()
        return _CPCB_CACHE["records"]

    _CPCB_CACHE["time"] = time.time()
    _CPCB_CACHE["records"] = data.get("records", [])
    print("CPCB records received:", len(_CPCB_CACHE["records"]))
    return _CPCB_CACHE["records"]


_POLLUTANT_NAMES = {
    "PM2.5": "pm25", "PM25": "pm25", "PM2_5": "pm25", "PM10": "pm10", "PM_10": "pm10",
    "NO2": "no2", "NO_2": "no2", "SO2": "so2", "SO_2": "so2", "CO": "co",
    "CARBON_MONOXIDE": "co", "OZONE": "o3", "O3": "o3", "NH3": "nh3", "AMMONIA": "nh3",
}


def _parse_update(text):
    for fmt in ("%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M"):
        try:
            return datetime.strptime(text.strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return None


def find_nearest_station(records, latitude, longitude):
    """Nearest station that has PM data and a recent update (within MAX_STATION_AGE_H)."""
    stations = {}
    for row in records:
        try:
            key = (row.get("station"), float(row.get("latitude")), float(row.get("longitude")))
        except (TypeError, ValueError):
            continue
        if not key[0]:
            continue
        info = stations.setdefault(key, {"pm": False, "updated": None})
        if _POLLUTANT_NAMES.get((row.get("pollutant_id") or "").strip().upper()) in ("pm25", "pm10"):
            if row.get("avg_value") not in (None, "", "NA"):
                info["pm"] = True
        upd = _parse_update(row.get("last_update") or "")
        if upd and (info["updated"] is None or upd > info["updated"]):
            info["updated"] = upd

    best = None
    for (name, lat, lon), info in stations.items():
        if not info["pm"]:
            continue
        if info["updated"] and datetime.now() - info["updated"] > timedelta(hours=MAX_STATION_AGE_H):
            continue
        d = calculate_distance(latitude, longitude, lat, lon)
        if best is None or d < best["distance_km"]:
            best = {"station": name, "latitude": lat, "longitude": lon,
                    "distance_km": round(d, 2),
                    "updated": info["updated"].strftime("%Y-%m-%d %H:%M") if info["updated"] else None}
    return best


def _station_values(records, station):
    values = {}
    for row in records:
        try:
            if (abs(float(row.get("latitude")) - station["latitude"]) > 0.0001 or
                    abs(float(row.get("longitude")) - station["longitude"]) > 0.0001):
                continue
            key = _POLLUTANT_NAMES.get((row.get("pollutant_id") or "").strip().upper())
            if key:
                values[key] = float(row.get("avg_value"))
        except (TypeError, ValueError):
            continue
    return values            # CPCB reports CO in mg/m3 and everything else in ug/m3


# =====================================
# MAIN HANDLER
# =====================================

def get_aqi_data(latitude, longitude, city_name):
    """
    1) Ground station (CPCB) within 30 km with fresh data   -> source_type "station"
       Missing gases are filled from the model and flagged "mixed_sources".
    2) Otherwise the Open-Meteo / CAMS model                -> source_type "model"
    Both Indian NAQI (`aqi`) and US AQI (`us_aqi`) are returned.
    """
    try:
        records = get_cpcb_data()
        if records:
            station = find_nearest_station(records, latitude, longitude)
            if station and station["distance_km"] <= MAX_STATION_KM:
                vals = _station_values(records, station)
                mixed = False
                missing = [k for k in ("pm25", "pm10", "no2", "so2", "co", "o3") if vals.get(k) is None]
                if missing:
                    series = get_open_meteo_series(latitude, longitude, past_hours=24)
                    if series:
                        naqi_m, _, now_m = aqi_inputs_from_series(series)
                        for k in missing:
                            if now_m.get(k) is not None:
                                vals[k] = now_m[k]
                                mixed = True
                result = build_result(
                    city_name, station["station"], station["distance_km"],
                    "CPCB official station", "station", vals, vals, vals,
                    station["updated"], mixed=mixed)
                if result and result["aqi"] is not None:
                    return result

        print(f"Using the Open-Meteo model for {city_name} (no fresh CPCB station within {MAX_STATION_KM:.0f} km)")
        return get_open_meteo_aqi(latitude, longitude, city_name)
    except Exception as error:
        print("get_aqi_data error:", error)
        return get_open_meteo_aqi(latitude, longitude, city_name)


if __name__ == "__main__":
    for city, lat, lon in [("Visnagar", 23.6010, 72.3990), ("Ahmedabad", 23.0225, 72.5714), ("Surat", 21.1702, 72.8311)]:
        print(f"\n--- {city} ---")
        print(json.dumps(get_aqi_data(lat, lon, city), indent=2))
