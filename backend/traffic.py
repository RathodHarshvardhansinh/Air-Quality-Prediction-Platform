import requests

from config import TRAFFIC_API_KEY


def get_traffic_data(latitude, longitude, city_name):
    """Live road speed from TomTom.  Returns None when TomTom has no data here."""
    if not TRAFFIC_API_KEY:
        print("TRAFFIC_API_KEY is not configured.")
        return None

    try:
        response = requests.get(
            "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json",
            params={"point": f"{latitude},{longitude}", "key": TRAFFIC_API_KEY},
            timeout=10,
        )
    except requests.RequestException as error:
        print("Traffic API request failed:", error)
        return None

    if response.status_code != 200:
        print("Traffic API Error:", response.status_code, response.text[:200])
        return None

    flow = response.json().get("flowSegmentData")
    if not flow:
        return None

    return {
        "city": city_name,
        "latitude": latitude,
        "longitude": longitude,
        "current_speed": flow.get("currentSpeed"),
        "free_flow_speed": flow.get("freeFlowSpeed"),
        "current_travel_time": flow.get("currentTravelTime"),
        "free_flow_travel_time": flow.get("freeFlowTravelTime"),
        "confidence": flow.get("confidence"),
        "road_closure": flow.get("roadClosure", False),
    }
