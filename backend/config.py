import os
from dotenv import load_dotenv

load_dotenv("C:/AirQualityPredictionPlatform/.env")

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
WEATHER_CITY = os.getenv("WEATHER_CITY")
WEATHER_COUNTRY = os.getenv("WEATHER_COUNTRY")

AQI_API_KEY = os.getenv("AQI_API_KEY")

TRAFFIC_API_KEY = os.getenv("TRAFFIC_API_KEY")

FIREBASE_WEB_API_KEY = os.getenv("FIREBASE_WEB_API_KEY")

CPCB_API_KEY = os.getenv("CPCB_API_KEY")