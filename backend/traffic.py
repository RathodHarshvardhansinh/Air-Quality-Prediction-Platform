import requests

from config import TRAFFIC_API_KEY


def get_traffic_data(latitude, longitude, city_name):

    url = (
        "https://api.tomtom.com/traffic/services/4/"
        "flowSegmentData/absolute/10/json"
    )

    params = {
        "point": f"{latitude},{longitude}",
        "key": TRAFFIC_API_KEY
    }

    response = requests.get(url, params=params)

    if response.status_code != 200:
        print("Traffic API Error:", response.status_code)
        print(response.text)
        return None

    data = response.json()

    flow_data = data.get("flowSegmentData")

    if not flow_data:
        return None

    traffic_data = {
        "city": city_name,
        "latitude": latitude,
        "longitude": longitude,
        "current_speed": flow_data.get("currentSpeed"),
        "free_flow_speed": flow_data.get("freeFlowSpeed"),
        "current_travel_time": flow_data.get("currentTravelTime"),
        "free_flow_travel_time": flow_data.get("freeFlowTravelTime"),
        "confidence": flow_data.get("confidence")
    }

    return traffic_data