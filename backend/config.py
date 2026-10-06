import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root, regardless of which machine/OS this runs on
# (previously hardcoded to "C:/AirQualityPredictionPlatform/.env" which only
# worked on one specific Windows PC). This now works on Windows/Mac/Linux and
# whichever folder you clone the project into.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
WEATHER_CITY = os.getenv("WEATHER_CITY")
WEATHER_COUNTRY = os.getenv("WEATHER_COUNTRY")

AQI_API_KEY = os.getenv("AQI_API_KEY")

TRAFFIC_API_KEY = os.getenv("TRAFFIC_API_KEY")

FIREBASE_WEB_API_KEY = os.getenv("FIREBASE_WEB_API_KEY")

CPCB_API_KEY = os.getenv("CPCB_API_KEY")

# Set this once your own ESP32 + sensor network is ready, e.g.
# IOT_DEVICE_URL=http://192.168.1.50/data
# Leave blank/unset to keep using the CPCB/Weather/Traffic APIs (default).
# See backend/iot_sensor.py for the exact expected response format.
IOT_DEVICE_URL = os.getenv("IOT_DEVICE_URL")
