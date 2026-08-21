import subprocess
import json
import math

from config import CPCB_API_KEY

from requests.adapters import HTTPAdapter
from urllib3.util.connection import allowed_gai_family


# Force IPv4 for requests
def force_ipv4():

    original = allowed_gai_family

    def ipv4_only():
        return socket.AF_INET

    import urllib3.util.connection

    urllib3.util.connection.allowed_gai_family = ipv4_only
    
    force_ipv4()




# =====================================
# CPCB API
# =====================================

CPCB_URL = (
    "https://api.data.gov.in/resource/"
    "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
)


# =====================================
# DISTANCE CALCULATION
# =====================================

def calculate_distance(
    lat1,
    lon1,
    lat2,
    lon2
):

    lat1 = float(lat1)
    lon1 = float(lon1)
    lat2 = float(lat2)
    lon2 = float(lon2)

    earth_radius = 6371

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        +
        math.cos(math.radians(lat1))
        *
        math.cos(math.radians(lat2))
        *
        math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    return earth_radius * c


# =====================================
# GET CPCB DATA
# =====================================

def get_cpcb_data():

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
                "--connect-timeout",
                "10",
                "--max-time",
                "60",
                url
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        if result.returncode != 0:

            print("CPCB curl error:")
            print(result.stderr)

            return []

        data = json.loads(result.stdout)

        if data.get("status") != "ok":

            print("CPCB API returned:")
            print(data)

            return []

        print(
            "CPCB records received:",
            len(data.get("records", []))
        )

        return data.get("records", [])

    except Exception as error:

        print(
            "CPCB API processing error:",
            error
        )

        return []


# =====================================
# FIND NEAREST STATION
# =====================================

def find_nearest_station(
    records,
    latitude,
    longitude
):

    stations = {}

    for row in records:

        try:

            station_name = row.get(
                "station"
            )

            station_lat = float(
                row.get("latitude")
            )

            station_lon = float(
                row.get("longitude")
            )

            if not station_name:
                continue

            key = (
                station_name,
                station_lat,
                station_lon
            )

            stations[key] = True

        except (
            TypeError,
            ValueError
        ):

            continue


    nearest = None

    nearest_distance = float(
        "inf"
    )


    for (
        station_name,
        station_lat,
        station_lon
    ) in stations:

        distance = calculate_distance(

            latitude,
            longitude,

            station_lat,
            station_lon

        )


        if distance < nearest_distance:

            nearest_distance = distance

            nearest = {

                "station": station_name,

                "latitude":
                    station_lat,

                "longitude":
                    station_lon,

                "distance_km":
                    round(
                        distance,
                        2
                    )

            }


    return nearest

# =====================================
# CPCB AQI CALCULATION
# =====================================

def calculate_sub_index(
    concentration,
    breakpoints
):

    if concentration is None:
        return None

    try:
        concentration = float(concentration)
    except (TypeError, ValueError):
        return None

    for bp_low, bp_high, i_low, i_high in breakpoints:

        if bp_low <= concentration <= bp_high:

            return (
                (
                    (i_high - i_low)
                    /
                    (bp_high - bp_low)
                )
                *
                (concentration - bp_low)
            )
            + i_low

    # Above highest breakpoint
    if concentration > breakpoints[-1][1]:

        bp_low, bp_high, i_low, i_high = breakpoints[-1]

        return (
            (
                (i_high - i_low)
                /
                (bp_high - bp_low)
            )
            *
            (concentration - bp_low)
        )
        + i_low

    return None


# =====================================
# CPCB BREAKPOINTS
# =====================================

PM25_BREAKPOINTS = [
    (0, 30, 0, 50),
    (31, 60, 51, 100),
    (61, 90, 101, 200),
    (91, 120, 201, 300),
    (121, 250, 301, 400),
    (251, 500, 401, 500),
]


PM10_BREAKPOINTS = [
    (0, 50, 0, 50),
    (51, 100, 51, 100),
    (101, 250, 101, 200),
    (251, 350, 201, 300),
    (351, 430, 301, 400),
    (431, 600, 401, 500),
]


NO2_BREAKPOINTS = [
    (0, 40, 0, 50),
    (41, 80, 51, 100),
    (81, 180, 101, 200),
    (181, 280, 201, 300),
    (281, 400, 301, 400),
    (401, 800, 401, 500),
]


SO2_BREAKPOINTS = [
    (0, 40, 0, 50),
    (41, 80, 51, 100),
    (81, 380, 101, 200),
    (381, 800, 201, 300),
    (801, 1600, 301, 400),
    (1601, 2000, 401, 500),
]


# CO is mg/m3 in CPCB AQI breakpoints
CO_BREAKPOINTS = [
    (0, 1.0, 0, 50),
    (1.1, 2.0, 51, 100),
    (2.1, 10, 101, 200),
    (10.1, 17, 201, 300),
    (17.1, 34, 301, 400),
    (34.1, 50, 401, 500),
]


O3_BREAKPOINTS = [
    (0, 50, 0, 50),
    (51, 100, 51, 100),
    (101, 168, 101, 200),
    (169, 208, 201, 300),
    (209, 748, 301, 400),
    (749, 1000, 401, 500),
]


# =====================================
# CALCULATE OVERALL AQI
# =====================================

def calculate_aqi(
    pm25=None,
    pm10=None,
    no2=None,
    co=None,
    o3=None,
    so2=None
):

    sub_indices = {}

    pm25_index = calculate_sub_index(
        pm25,
        PM25_BREAKPOINTS
    )

    if pm25_index is not None:
        sub_indices["PM2.5"] = pm25_index


    pm10_index = calculate_sub_index(
        pm10,
        PM10_BREAKPOINTS
    )

    if pm10_index is not None:
        sub_indices["PM10"] = pm10_index


    no2_index = calculate_sub_index(
        no2,
        NO2_BREAKPOINTS
    )

    if no2_index is not None:
        sub_indices["NO2"] = no2_index


    so2_index = calculate_sub_index(
        so2,
        SO2_BREAKPOINTS
    )

    if so2_index is not None:
        sub_indices["SO2"] = so2_index


    o3_index = calculate_sub_index(
        o3,
        O3_BREAKPOINTS
    )

    if o3_index is not None:
        sub_indices["O3"] = o3_index


    # IMPORTANT:
    # CPCB CO breakpoint uses mg/m3.
    # Your API may return another unit.
    # So don't calculate CO until its unit is confirmed.


    if not sub_indices:
        return None


    return round(
        max(sub_indices.values())
    )

# =====================================
# GET AQI DATA
# =====================================

def get_aqi_data(
    latitude,
    longitude,
    city_name
):

    try:

        records = get_cpcb_data()


        if not records:

            print(
                "No CPCB records received"
            )

            return None


        station = find_nearest_station(

            records,

            latitude,
            longitude

        )


        if station is None:

            print(
                "No nearby CPCB station found"
            )

            return None


        print(
            "Nearest CPCB station:",
            station
        )


        # =================================
        # DISTANCE SAFETY CHECK
        # =================================

        if station["distance_km"] > 100:

            print(
                "Nearest CPCB station is too far:",
                station["distance_km"],
                "km"
            )

            return None


        # =================================
        # COLLECT POLLUTANTS
        # =================================

        station_records = []


        for row in records:

            try:

                row_lat = float(
                    row.get("latitude")
                )

                row_lon = float(
                    row.get("longitude")
                )

            except (
                TypeError,
                ValueError
            ):

                continue


            if (

                abs(
                    row_lat -
                    station["latitude"]
                ) < 0.0001

                and

                abs(
                    row_lon -
                    station["longitude"]
                ) < 0.0001

            ):

                station_records.append(
                    row
                )


        pollutants = {}


        for row in station_records:

            pollutant = (
                row.get(
                    "pollutant_id"
                )
                or ""
            ).upper()


            try:

                value = float(
                    row.get(
                        "avg_value"
                    )
                )

            except (
                TypeError,
                ValueError
            ):

                continue


            pollutants[
                pollutant
            ] = value


        # =================================
        # RETURN FORMAT
        # =================================

        result = {

            "city":
                city_name,

            "station":
                station["station"],

            "station_distance_km":
                station["distance_km"],

            "aqi": calculate_aqi(
    pm25=pollutants.get("PM2.5"),
    pm10=pollutants.get("PM10"),
    no2=pollutants.get("NO2"),
    co=None,
    o3=pollutants.get("O3"),
    so2=pollutants.get("SO2")
),

            "pm25":
                pollutants.get(
                    "PM2.5"
                ),

            "pm10":
                pollutants.get(
                    "PM10"
                ),

            "no2":
                pollutants.get(
                    "NO2"
                ),

            "co":
                pollutants.get(
                    "CO"
                ),

            "o3":
                pollutants.get(
                    "O3"
                ),

            "so2":
                pollutants.get(
                    "SO2"
                )

        }


        print(
            "CPCB AQI data:",
            result
        )


        return result


    except requests.exceptions.RequestException as error:

        print(
            "CPCB API Error:",
            error
        )

        return None


    except Exception as error:

        print(
            "CPCB processing error:",
            error
        )

        return None
    
if __name__ == "__main__":

    print("\n==============================")
    print("Testing CPCB AQI Pipeline")
    print("==============================")

    result = get_aqi_data(
        23.6010,
        72.3990,
        "Visnagar"
    )

    print("\nFINAL RESULT:")
    print(result)