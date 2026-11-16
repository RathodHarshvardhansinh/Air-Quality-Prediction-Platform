import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, redirect, request
from flask_cors import CORS

from aqi import get_aqi_data
from config import FIREBASE_WEB_API_KEY
from database import (
    create_database,
    get_city_range_history,
    get_history,
    get_known_cities,
    get_latest_record,
    minutes_since_last_save,
    resolve_db_city,
)
from iot import create_iot_tables, iot_bp, iot_status_for
from location import get_city_coordinates, reverse_geocode
from save_data import save_reading
from traffic import get_traffic_data
from weather import get_weather_data

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
    from prediction import get_predictions, model_info, PredictionError
except Exception as error:  # pragma: no cover
    print("Prediction module unavailable:", error)
    get_predictions = None
    model_info = None
    PredictionError = Exception


FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend"
)

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="/app")
CORS(app, resources={r"/*": {"origins": "*"}})

SAVE_EVERY_MINUTES = 30  # do not write a new history row more often than this

create_database()        # makes sure the table / new columns exist
create_iot_tables()      # IoT device registry + readings (separate from the external-API history)
app.register_blueprint(iot_bp)


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
        country = None
        try:
            info = reverse_geocode(lat, lon)
            name = name or info.get("city")
            state = info.get("state")
            country = info.get("country")
        except Exception as error:
            print("Reverse geocode failed:", error)
        return {
            "name": name or "Current location",
            "latitude": lat,
            "longitude": lon,
            "state": state,
            "country": country,
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

    if traffic_data is None:
        traffic_data = _traffic_from_history(name)

    errors = {}
    if weather_data is None:
        errors["weather"] = "Weather service unavailable"
    if aqi_data is None:
        errors["air_quality"] = "Air quality service unavailable"
    if traffic_data is None:
        errors["traffic"] = "No live traffic data for this location"

    # Save a history row (throttled).  save_reading() converts to the database units
    # (CO mg/m3 -> ug/m3, wind m/s -> km/h) and stamps LOCAL time.
    saved = False
    if aqi_data and aqi_data.get("aqi") is not None and weather_data:
        minutes = minutes_since_last_save(name)
        if minutes is None or minutes >= SAVE_EVERY_MINUTES:
            try:
                saved = bool(save_reading(name, aqi_data, weather_data, traffic_data))
            except Exception as error:
                print("Could not save history row:", error)

    try:
        iot_data = iot_status_for(lat, lon, name)
    except Exception as error:
        print("IoT status failed:", error)
        iot_data = {"connected": False, "status": "error", "device": None, "reading": None,
                    "message": "IoT status unavailable"}

    return jsonify({
        "location": place,
        "weather": weather_data,
        "air_quality": aqi_data,
        "traffic": traffic_data,
        "iot": iot_data,
        "errors": errors,
        "saved_to_history": saved,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/iot/status")
def iot_status():
    """Is a registered IoT device online at this place?   ?lat=..&lon=..[&city=..]  or  ?city=.."""
    place, err = resolve_place()
    if err:
        return err
    return jsonify(iot_status_for(place["latitude"], place["longitude"], place["name"]))


# =====================================
# PREDICTIONS
# =====================================

def _predictions_for(city):
    if get_predictions is None:
        return None, "Prediction model is not available on this server"
    lat = _float(request.args.get("lat"))
    lon = _float(request.args.get("lon"))
    try:
        return get_predictions(city, lat, lon), None
    except PredictionError as error:
        return None, str(error)
    except Exception as error:
        print("Prediction error:", error)
        return None, "Prediction failed"


@app.route("/model-info")
def model_info_route():
    if model_info is None:
        return jsonify({"error": "Prediction module unavailable"}), 503
    return jsonify(model_info())


@app.route("/predict")
def predict_both():
    city = (request.args.get("city") or "").strip()
    if not city:
        return jsonify({"error": "Please provide a city"}), 400
    result, error = _predictions_for(city)
    if error:
        return jsonify({"error": error}), 400
    return jsonify(result)


@app.route("/predict/1h")
def predict_1h():
    city = (request.args.get("city") or "").strip()
    if not city:
        return jsonify({"error": "Please provide a city"}), 400
    result, error = _predictions_for(city)
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"city": result["city"], "prediction_hours": 1,
                    "predicted_aqi": result["prediction_1h"], "predicted_us_aqi": result["us_prediction_1h"]})


@app.route("/predict/6h")
def predict_6h():
    city = (request.args.get("city") or "").strip()
    if not city:
        return jsonify({"error": "Please provide a city"}), 400
    result, error = _predictions_for(city)
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"city": result["city"], "prediction_hours": 6,
                    "predicted_aqi": result["prediction_6h"], "predicted_us_aqi": result["us_prediction_6h"]})


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
        rows = get_city_range_history(resolve_db_city(city), hours, start, end)
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

@app.route("/save-data")
def save_data():
    """Force-save one reading (the collector does this on a schedule)."""
    place, err = resolve_place()
    if err:
        return err
    lat, lon, name = place["latitude"], place["longitude"], place["name"]
    aqi_data = get_aqi_data(lat, lon, name)
    weather_data = get_weather_data(lat, lon, name)
    traffic_data = get_traffic_data(lat, lon, name)
    if not aqi_data or not weather_data:
        return jsonify({"error": "Unable to fetch live data"}), 502
    save_reading(name, aqi_data, weather_data, traffic_data)
    return jsonify({"message": "Data Saved Successfully", "city": name})



def _check_libraries():
    """Check required libraries and report optional ML packages."""
    import importlib.util
    import sys

    missing = [
        m for m in ("pandas", "numpy")
        if importlib.util.find_spec(m) is None
    ]

    optional_missing = [
        m for m in ("xgboost", "catboost")
        if importlib.util.find_spec(m) is None
    ]

    if missing:
        print("\n" + "!" * 70)
        print("  REQUIRED PREDICTION LIBRARIES MISSING:", ", ".join(missing))
        print("  Install them using:")
        print(f'     "{sys.executable}" -m pip install pandas numpy')
        print("!" * 70 + "\n")

    if optional_missing:
        print("\nOptional ML packages not installed:", ", ".join(optional_missing))
        print("AirSense will use its built-in XGBoost Lite prediction mode.")
        print("For the full model locally, install with:")
        print(f'     "{sys.executable}" -m pip install xgboost catboost')
        print()



if __name__ == "__main__":
    _check_libraries()
    create_database()
    print("\nAirSense running ->  http://127.0.0.1:5000\n")
    # AIRSENSE_HOST=0.0.0.0 in .env lets an ESP32 on your Wi-Fi reach the server (see IOT_SETUP.md).
    # Default stays 127.0.0.1 = only this computer.
    app.run(host=os.getenv("AIRSENSE_HOST", "127.0.0.1"), port=5000, debug=os.getenv("AIRSENSE_DEBUG") == "1")