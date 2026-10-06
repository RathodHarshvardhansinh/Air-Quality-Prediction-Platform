"""
IoT Sensor Integration
=======================

THIS IS THE ONLY PIECE LEFT TO CONNECT YOUR REAL HARDWARE.

Right now AirSense gets its readings from the CPCB AQI API, the Weather API,
and the Traffic API (see collector.py). That is why the platform already
works end-to-end with accurate data even without a physical sensor.

Once your own ESP32 + sensor network (PM2.5, PM10, CO, NO2, SO2, O3,
temperature, humidity, pressure) is ready, you only need to do TWO things:

1. Set IOT_DEVICE_URL in your .env file to your ESP32's local endpoint, e.g.:
       IOT_DEVICE_URL=http://192.168.1.50/data

   Your ESP32 should expose a simple HTTP GET endpoint (via WiFi, matching
   the "Connectivity Layer" + "IoT Communication Layer" stages in your
   architecture diagram) that returns JSON in this exact shape:

       {
         "pm25": 42.5,
         "pm10": 88.0,
         "no2": 12.3,
         "co": 0.8,
         "o3": 30.1,
         "so2": 5.4,
         "temperature": 29.4,
         "humidity": 55,
         "pressure": 1008
       }

   (Units: pm25/pm10/no2/so2/o3 in µg/m³, co in mg/m³, temperature in °C,
   humidity in %, pressure in hPa — same units the rest of the pipeline
   already uses, so no other code needs to change.)

2. That's it. collector.py (below) already checks for IOT_DEVICE_URL first
   and will automatically use your live sensor instead of the APIs the
   moment it responds successfully — with zero other code changes needed.
   If your device is offline or unreachable, it silently falls back to the
   CPCB/Weather/Traffic APIs, so the platform never breaks.

If you're using MQTT instead of plain HTTP (as shown in your diagram's
"IoT Communication Layer"), replace the `requests.get()` call below with
an MQTT subscriber (e.g. using `paho-mqtt`) that updates a small in-memory
cache which this function then returns.
"""

import requests

from config import IOT_DEVICE_URL


def get_iot_sensor_data(timeout=3):
    """
    Attempts to fetch a live reading from the user's own IoT sensor network.

    Returns a dict matching the environment_data schema on success,
    or None if no device is configured / the device is unreachable
    (collector.py will then fall back to the API-based pipeline).
    """

    if not IOT_DEVICE_URL:
        # No device connected yet — this is expected until the student
        # wires up their own ESP32 + sensors.
        return None

    try:
        response = requests.get(IOT_DEVICE_URL, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        required_fields = [
            "pm25", "pm10", "no2", "co", "o3", "so2",
            "temperature", "humidity", "pressure",
        ]

        missing = [f for f in required_fields if f not in data]
        if missing:
            print(f"IoT sensor response missing fields: {missing}. Falling back to APIs.")
            return None

        return data

    except Exception as error:
        print(f"IoT sensor unreachable ({error}). Falling back to CPCB/Weather/Traffic APIs.")
        return None
