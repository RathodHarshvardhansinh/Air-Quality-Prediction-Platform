import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, redirect, request
from flask_cors import CORS

from aqi import (
    get_aqi_data,
    calculate_aqi_details,
    get_aqi_category,
)

from config import FIREBASE_WEB_API_KEY

from database import (
    create_database,
    get_city_range_history,
    get_history,
    get_known_cities,
    get_latest_record,
    minutes_since_last_save,
)

from location import get_city_coordinates, reverse_geocode
from save_data import save_environment_data
from traffic import get_traffic_data
from weather import get_weather_data

from sensor_data import (
    get_current_sensor_data,
    get_sensor_aqi,
    sensor_is_available_for_place,
)

# Firebase is only needed for register / login / profile.  If the key file
# is missing the dashboard itself still works.
try:
    from firebase_admin import auth
    from firebase_config import db
except Exception as error:  # pragma: no cover
    print("Firebase unavailable:", error)
    auth = None
    db = None

# Predictions need the ML models + pandas.  Same idea: optional.
try:
    from prediction import get_predictions
except Exception as error:  # pragma: no cover
    print("Prediction module unavailable:", error)
    get_predictions = None


FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend"
)

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="/app")
CORS(app, resources={r"/*": {"origins": "*"}})

SAVE_EVERY_MINUTES = 30  # do not write a new history row more often than this


# =====================================
# HELPERS
# =====================================

def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def resolve_place():
    """
    Works out WHERE the request is about.

    Accepts  ?lat=..&lon=..[&city=..]   (best - exact GPS position)
         or  ?city=..                    (name is geocoded)

    Returns (place_dict, None) or (None, (json, status)).
    """
    lat = _float(request.args.get("lat") or request.args.get("latitude"))
    lon = _float(request.args.get("lon") or request.args.get("longitude"))
    city = (request.args.get("city") or "").strip()

    if lat is not None and lon is not None:
        name = city
        state = None
        if not name:
            try:
                info = reverse_geocode(lat, lon)
                name = info.get("city")
                state = info.get("state")
            except Exception as error:
                print("Reverse geocode failed:", error)
        return {
            "name": name or "Current location",
            "latitude": lat,
            "longitude": lon,
            "state": state,
        }, None

    if not city:
        return None, (jsonify({"error": "Please provide a city or lat/lon"}), 400)

    found = get_city_coordinates(city)
    if found is None:
        return None, (jsonify({"error": f"Could not find a place called '{city}'"}), 404)

    return {
        "name": found["name"] or city,
        "latitude": found["latitude"],
        "longitude": found["longitude"],
        "state": found.get("state"),
        "country": found.get("country"),
    }, None


def _traffic_from_history(city):
    """If TomTom has nothing right now, fall back to the last saved reading (max 6h old)."""
    row = get_latest_record(city)
    if not row or row.get("traffic_speed") is None or not row.get("free_flow_speed"):
        return None
    try:
        saved = datetime.strptime(row["timestamp"][:19], "%Y-%m-%d %H:%M:%S")
        age_h = (datetime.utcnow() - saved).total_seconds() / 3600
    except (TypeError, ValueError):
        return None
    if age_h > 6:
        return None
    return {
        "city": city,
        "current_speed": row["traffic_speed"],
        "free_flow_speed": row["free_flow_speed"],
        "current_travel_time": None,
        "free_flow_travel_time": None,
        "source": "last saved reading",
    }


# =====================================
# BASIC
# =====================================

@app.route("/")
def home():
    return redirect("/app/index.html")


@app.route("/api")
def api_info():
    return jsonify({
        "message": "AirSense Air Quality Prediction Platform API",
        "endpoints": [
            "/environment?lat=..&lon=..", "/aqi", "/weather", "/traffic",
            "/predict", "/history/24h|7d|30d|custom", "/location", "/profile",
        ],
    })


# =====================================
# LOCATION  (GPS -> city name)
# =====================================

@app.route("/location")
def location():
    lat = _float(request.args.get("latitude") or request.args.get("lat"))
    lon = _float(request.args.get("longitude") or request.args.get("lon"))

    if lat is None or lon is None:
        return jsonify({"error": "Latitude and longitude are required"}), 400

    try:
        info = reverse_geocode(lat, lon)
    except Exception as error:
        print("Location error:", error)
        info = {}

    return jsonify({
        "city": info.get("city") or "Current location",
        "state": info.get("state"),
        "country": info.get("country"),
        "latitude": lat,
        "longitude": lon,
    })


# =====================================
# SINGLE-PURPOSE ENDPOINTS
# =====================================

@app.route("/weather")
def weather():
    place, err = resolve_place()
    if err:
        return err
    data = get_weather_data(place["latitude"], place["longitude"], place["name"])
    if data is None:
        return jsonify({"error": "Unable to fetch weather data"}), 502
    return jsonify(data)


@app.route("/aqi")
def aqi():
    place, err = resolve_place()
    if err:
        return err
    data = get_aqi_data(place["latitude"], place["longitude"], place["name"])
    if data is None:
        return jsonify({"error": "Unable to fetch AQI data"}), 502
    return jsonify(data)


@app.route("/traffic")
def traffic():
    place, err = resolve_place()
    if err:
        return err
    data = get_traffic_data(place["latitude"], place["longitude"], place["name"])
    if data is None:
        data = _traffic_from_history(place["name"])
    if data is None:
        return jsonify({"error": "No live traffic data for this location"}), 404
    return jsonify(data)


# =====================================
# EVERYTHING IN ONE CALL  (used by the dashboard)
# Each part is fetched in parallel and fails on its own, so one broken
# API no longer blanks the whole dashboard.
# =====================================

@app.route("/environment")
def environment():
    place, err = resolve_place()
    if err:
        return err

    lat, lon, name = place["latitude"], place["longitude"], place["name"]

    with ThreadPoolExecutor(max_workers=3) as pool:
        f_weather = pool.submit(get_weather_data, lat, lon, name)
        f_aqi = pool.submit(get_aqi_data, lat, lon, name)
        f_traffic = pool.submit(get_traffic_data, lat, lon, name)

        def safe(future, label):
            try:
                return future.result(timeout=60)
            except Exception as error:
                print(f"{label} failed:", error)
                return None

        weather_data = safe(f_weather, "weather")
        aqi_data = safe(f_aqi, "aqi")
        traffic_data = safe(f_traffic, "traffic")

    # -------------------------------------------------
    # SENSOR + API AQI LOGIC
    # -------------------------------------------------
    sensor_data = get_current_sensor_data()
    sensor_aqi_data = None

    if sensor_data:
        try:
            if sensor_is_available_for_place(sensor_data, place):
                sensor_aqi_data = get_sensor_aqi(
                    sensor_data,
                    calculate_aqi_details
                )
                print("Valid sensor data found:", sensor_aqi_data)
            else:
                print("Sensor exists, but not for this location or is stale.")
        except Exception as error:
            print("Sensor processing failed:", error)

    # Case 1: Sensor + API available
    if sensor_aqi_data and aqi_data:
        sensor_value = sensor_aqi_data.get("aqi")
        api_value = aqi_data.get("aqi")

        if sensor_value is not None and api_value is not None:
            combined_aqi = round((sensor_value + api_value) / 2)
            combined_aqi = max(0, min(combined_aqi, 500))

            original_api_aqi = api_value

            aqi_data = {
                **aqi_data,
                "aqi": combined_aqi,
                "category": get_aqi_category(combined_aqi),
                "source": "ESP32 Sensor + API (Combined)",
                "sensor_aqi": sensor_value,
                "api_aqi": original_api_aqi,
            }

    # Case 2: API unavailable, but sensor available
    elif sensor_aqi_data:
        aqi_data = {
            **sensor_aqi_data,
            "source": "ESP32 Sensor (API unavailable)",
            "sensor_aqi": sensor_aqi_data.get("aqi"),
            "api_aqi": None,
        }

    # Case 3: Sensor unavailable, but API available
    elif aqi_data:
        api_value = aqi_data.get("aqi")

        aqi_data = {
            **aqi_data,
            "source": "API (Sensor unavailable)",
            "sensor_aqi": None,
            "api_aqi": api_value,
        }

    # -------------------------------------------------
    # TRAFFIC FALLBACK
    # -------------------------------------------------
    if traffic_data is None:
        traffic_data = _traffic_from_history(name)

    # -------------------------------------------------
    # ERRORS
    # -------------------------------------------------
    errors = {}

    if weather_data is None:
        errors["weather"] = "Weather service unavailable"

    if aqi_data is None:
        errors["air_quality"] = "No sensor or API air-quality data available"

    if traffic_data is None:
        errors["traffic"] = "No live traffic data for this location"

    # -------------------------------------------------
    # SAVE HISTORY
    # -------------------------------------------------
    saved = False

    if aqi_data and aqi_data.get("aqi") is not None and weather_data:
        minutes = minutes_since_last_save(name)

        if minutes is None or minutes >= SAVE_EVERY_MINUTES:
            try:
                save_environment_data(
                    city=name,
                    aqi=aqi_data["aqi"],
                    pm25=aqi_data.get("pm25"),
                    pm10=aqi_data.get("pm10"),
                    no2=aqi_data.get("no2"),
                    co=aqi_data.get("co"),
                    o3=aqi_data.get("o3"),
                    so2=aqi_data.get("so2"),
                    temperature=weather_data.get("temperature"),
                    humidity=weather_data.get("humidity"),
                    pressure=weather_data.get("pressure"),
                    wind_speed=weather_data.get("wind_speed"),
                    traffic_speed=(traffic_data or {}).get("current_speed"),
                    free_flow_speed=(traffic_data or {}).get("free_flow_speed"),
                )

                saved = True

            except Exception as error:
                print("Could not save history row:", error)

    return jsonify({
        "location": place,
        "weather": weather_data,
        "air_quality": aqi_data,
        "traffic": traffic_data,
        "errors": errors,
        "saved_to_history": saved,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

# =====================================
# PREDICTIONS
# =====================================

def _predictions_for(city):
    if get_predictions is None:
        return None, "Prediction model is not available on this server"
    try:
        result = get_predictions(city)
    except Exception as error:
        print("Prediction error:", error)
        return None, "Prediction failed"
    if result is None:
        return None, "Not enough historical data for this city yet"
    return result, None


@app.route("/predict")
def predict_both():
    city = (request.args.get("city") or "").strip()
    if not city:
        return jsonify({"error": "Please provide a city"}), 400
    result, error = _predictions_for(city)
    if error:
        return jsonify({"error": error}), 400
    return jsonify({
        "city": result["city"],
        "prediction_1h": result["prediction_1h"],
        "prediction_6h": result["prediction_6h"],
    })


@app.route("/predict/1h")
def predict_1h():
    city = (request.args.get("city") or "").strip()
    if not city:
        return jsonify({"error": "Please provide a city"}), 400
    result, error = _predictions_for(city)
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"city": result["city"], "prediction_hours": 1,
                    "predicted_aqi": result["prediction_1h"]})


@app.route("/predict/6h")
def predict_6h():
    city = (request.args.get("city") or "").strip()
    if not city:
        return jsonify({"error": "Please provide a city"}), 400
    result, error = _predictions_for(city)
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"city": result["city"], "prediction_hours": 6,
                    "predicted_aqi": result["prediction_6h"]})


# =====================================
# HISTORY
# =====================================

@app.route("/history")
def history():
    return jsonify(get_history())


@app.route("/cities")
def cities():
    return jsonify(get_known_cities())


@app.route("/history/<period>")
def history_period(period):
    city = (request.args.get("city") or "").strip()
    if not city:
        return jsonify({"error": "City is required"}), 400

    hours = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30}.get(period)
    start = end = None

    if period == "custom":
        start = request.args.get("start")
        end = request.args.get("end")
        if not start or not end:
            return jsonify({"error": "Pick a start and end date"}), 400
    elif hours is None:
        return jsonify({"error": "Invalid period"}), 400

    try:
        rows = get_city_range_history(city, hours, start, end)
    except Exception as error:
        print("History error:", error)
        return jsonify({"error": "Could not read history"}), 500

    latest = rows[-1]["timestamp"] if rows else None
    return jsonify({
        "city": city,
        "period": period,
        "count": len(rows),
        "latest": latest,
        "records": rows,
    })


# =====================================
# ACCOUNTS (Firebase)
# =====================================

def _need_firebase():
    if auth is None or db is None:
        return jsonify({"error": "Account service is not configured on the server"}), 503
    return None


@app.route("/register", methods=["POST"])
def register():
    bad = _need_firebase()
    if bad:
        return bad
    data = request.get_json(silent=True) or {}
    name, email, password = data.get("name"), data.get("email"), data.get("password")

    if not name or not email or not password:
        return jsonify({"error": "Name, email and password are required"}), 400

    try:
        user = auth.create_user(email=email, password=password)
        user_data = {"uid": user.uid, "name": name, "email": email,
                     "authProvider": "email_password"}
        db.collection("users").document(user.uid).set(user_data)
        return jsonify({"message": "User registered successfully", "user": user_data}), 201
    except Exception as error:
        return jsonify({"error": str(error)}), 400


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email, password = data.get("email"), data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    url = ("https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
           f"?key={FIREBASE_WEB_API_KEY}")
    try:
        response = requests.post(
            url,
            json={"email": email, "password": password, "returnSecureToken": True},
            timeout=15,
        )
        result = response.json()
        if response.status_code != 200:
            return jsonify({"error": result.get("error", {}).get("message", "Login failed")}), 401
        return jsonify({
            "message": "Login successful",
            "uid": result.get("localId"),
            "email": result.get("email"),
            "idToken": result.get("idToken"),
        }), 200
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@app.route("/profile", methods=["GET"])
def profile():
    bad = _need_firebase()
    if bad:
        return bad
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return jsonify({"error": "Authorization token is required"}), 401

    try:
        decoded = auth.verify_id_token(header.split("Bearer ", 1)[1])
        doc = db.collection("users").document(decoded["uid"]).get()
        if not doc.exists:
            return jsonify({"error": "User profile not found"}), 404
        return jsonify({"message": "Profile fetched successfully", "user": doc.to_dict()}), 200
    except Exception:
        return jsonify({"error": "Invalid or expired token"}), 401


# =====================================
# LEGACY HELPERS (kept so old links still work)
# =====================================

@app.route("/firebase-test")
def firebase_test():
    bad = _need_firebase()
    if bad:
        return bad
    payload = {"message": "Firebase connection successful", "status": "working"}
    db.collection("test").document("connection").set(payload)
    return jsonify(payload)


@app.route("/save-data")
def save_data():
    """Force-save one reading (the collector does this hourly)."""
    place, err = resolve_place()
    if err:
        return err
    lat, lon, name = place["latitude"], place["longitude"], place["name"]
    aqi_data = get_aqi_data(lat, lon, name)
    weather_data = get_weather_data(lat, lon, name)
    traffic_data = get_traffic_data(lat, lon, name) or {}
    if not aqi_data or not weather_data:
        return jsonify({"error": "Unable to fetch live data"}), 502
    save_environment_data(
        city=name, aqi=aqi_data["aqi"],
        pm25=aqi_data.get("pm25"), pm10=aqi_data.get("pm10"), no2=aqi_data.get("no2"),
        co=aqi_data.get("co"), o3=aqi_data.get("o3"), so2=aqi_data.get("so2"),
        temperature=weather_data["temperature"], humidity=weather_data["humidity"],
        pressure=weather_data["pressure"], wind_speed=weather_data["wind_speed"],
        traffic_speed=traffic_data.get("current_speed"),
        free_flow_speed=traffic_data.get("free_flow_speed"),
    )
    return jsonify({"message": "Data Saved Successfully", "city": name})


if __name__ == "__main__":
    create_database()
    print("\nAirSense running ->  http://127.0.0.1:5000\n")
    app.run(debug=True, port=5000)
