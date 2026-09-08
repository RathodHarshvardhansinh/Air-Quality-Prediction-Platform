import requests

from flask import Flask, jsonify, request

from weather import get_weather_data
from aqi import get_aqi_data
from traffic import get_traffic_data
from firebase_config import db
from cities import CITIES
from location import get_city_coordinates
from firebase_admin import auth
from config import FIREBASE_WEB_API_KEY
from flask_cors import CORS

from database import create_database
from save_data import save_environment_data
from database import get_history

from prediction import get_predictions
from database import get_city_range_history

from datetime import datetime

app = Flask(__name__)
CORS(app)

CORS(
    app,
    resources={
        r"/*": {
            "origins": "*"
        }
    }
)

@app.route("/")
def home():
    return jsonify({
        "message": "Air Quality Prediction Platform API",
        "endpoints": [
            "/weather",
            "/aqi",
            "/traffic",
            "/environment",
            "/firebase-test"
        ]
    })


@app.route("/weather")
def weather():

    city = request.args.get("city")

    if not city:
        return jsonify({
            "error": "Please provide a city"
        }), 400

    location = get_city_coordinates(city)

    if location is None:
        return jsonify({
            "error": "City not found"
        }), 404

    weather_data = get_weather_data(
        location["latitude"],
        location["longitude"],
        city
    )

    if weather_data is None:
        return jsonify({
            "error": "Unable to fetch weather data"
        }), 500

    return jsonify(weather_data)

@app.route("/location")
def location():

    latitude = request.args.get("latitude")
    longitude = request.args.get("longitude")

    if not latitude or not longitude:
        return jsonify({
            "error": "Latitude and longitude are required"
        }), 400

    try:
        latitude = float(latitude)
        longitude = float(longitude)

    except ValueError:
        return jsonify({
            "error": "Invalid latitude or longitude"
        }), 400

    # Reverse geocoding API
    url = "https://nominatim.openstreetmap.org/reverse"

    params = {
        "lat": latitude,
        "lon": longitude,
        "format": "json",
        "zoom": 10,
        "addressdetails": 1
    }

    headers = {
        "User-Agent": "AirQualityPredictionPlatform/1.0"
    }

    try:

        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=10
        )

        if response.status_code != 200:
            return jsonify({
                "error": "Unable to detect city"
            }), 500

        data = response.json()

        address = data.get(
            "address",
            {}
        )

        city = (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("municipality")
            or address.get("county")
        )

        if not city:
            return jsonify({
                "error": "City not found"
            }), 404

        return jsonify({
            "city": city,
            "latitude": latitude,
            "longitude": longitude
        })

    except requests.RequestException as error:

        print(
            "Location Request Error:",
            error
        )

        return jsonify({
            "error": "Unable to detect location"
        }), 500

@app.route("/aqi")
def aqi():

    city = request.args.get("city")

    if not city:
        return jsonify({
            "error": "Please provide a city"
        }), 400

    location = get_city_coordinates(city)

    if location is None:
        return jsonify({
            "error": "City not found"
        }), 404

    aqi_data = get_aqi_data(
        location["latitude"],
        location["longitude"],
        city
    )

    if aqi_data is None:
        return jsonify({
            "error": "Unable to fetch AQI data"
        }), 500

    return jsonify(aqi_data)


@app.route("/traffic")
def traffic():

    city = request.args.get("city")

    if not city:
        return jsonify({
            "error": "Please provide a city"
        }), 400

    location = get_city_coordinates(city)

    if location is None:
        return jsonify({
            "error": "City not found"
        }), 404

    traffic_data = get_traffic_data(
        location["latitude"],
        location["longitude"],
        city
    )

    if traffic_data is None:
        return jsonify({
            "error": "Unable to fetch traffic data"
        }), 500

    return jsonify(traffic_data)


@app.route("/environment")
def environment():

    city = request.args.get("city")

    if not city:
        return jsonify({
            "error": "Please provide a city"
        }), 400

    location = get_city_coordinates(city)

    if location is None:
        return jsonify({
            "error": "City not found"
        }), 404

    latitude = location["latitude"]
    longitude = location["longitude"]
    city_name = location["name"]

    # Weather
    weather_data = get_weather_data(
        latitude,
        longitude,
        city_name
    )

    if weather_data is None:
        return jsonify({
            "error": "Unable to fetch weather data"
        }), 500

    # AQI
    aqi_data = get_aqi_data(
        latitude,
        longitude,
        city_name
    )

    if aqi_data is None:
        return jsonify({
            "error": "Unable to fetch air quality data"
        }), 500

    # Traffic
    traffic_data = get_traffic_data(
        latitude,
        longitude,
        city_name
    )

    if traffic_data is None:
        return jsonify({
            "error": "Unable to fetch traffic data"
        }), 500

    return jsonify({
        "location": location,
        "weather": weather_data,
        "air_quality": aqi_data,
        "traffic": traffic_data
    })


@app.route("/firebase-test")
def firebase_test():
    test_data = {
        "message": "Firebase connection successful",
        "status": "working"
    }

    db.collection("test").document("connection").set(test_data)

    return jsonify(test_data)

@app.route("/save-environment")
def save_environment():

    city = request.args.get("city")

    if not city:
        return jsonify({
            "error": "Please provide a city"
        }), 400


    # =====================================
    # GET CITY COORDINATES
    # =====================================

    location = get_city_coordinates(city)

    if location is None:
        return jsonify({
            "error": "City not found"
        }), 404


    latitude = location["latitude"]
    longitude = location["longitude"]


    # =====================================
    # FETCH WEATHER
    # =====================================

    weather_data = get_weather_data(
        latitude,
        longitude,
        city
    )


    # =====================================
    # FETCH AQI
    # =====================================

    aqi_data = get_aqi_data(
    latitude,
    longitude,
    city
)
    

    # =====================================
    # FETCH TRAFFIC
    # =====================================

    traffic_data = get_traffic_data(
        latitude,
        longitude,
        city
    )


    if weather_data is None:
        return jsonify({
            "error": "Unable to fetch weather data"
        }), 500

    if aqi_data is None:
        return jsonify({
            "error": "Unable to fetch AQI data"
        }), 500

    if traffic_data is None:
        return jsonify({
            "error": "Unable to fetch traffic data"
        }), 500


    # =====================================
    # FIREBASE DATA
    # =====================================

    environment_data = {

        "city": city,

        "weather": weather_data,

        "air_quality": aqi_data,

        "traffic": traffic_data,

        "updated_at":
            datetime.now().isoformat()

    }


    db.collection(
        "environment_data"
    ).document("current").set(
        environment_data
    )


    # =====================================
    # DEBUG OUTPUT
    # =====================================

    print("\n==============================")
    print("WEATHER DATA:")
    print(weather_data)

    print("\nAQI DATA:")
    print(aqi_data)

    print("\nTRAFFIC DATA:")
    print(traffic_data)
    print("==============================\n")


    return jsonify({

        "message":
            "Environment data fetched successfully",

        "city":
            city,

        "firebase":
            "saved",

        "data":
            environment_data

    })

@app.route("/register", methods=["POST"])
def register():

    data = request.get_json()

    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if not name or not email or not password:
        return jsonify({
            "error": "Name, email and password are required"
        }), 400

    try:
        # Create user in Firebase Authentication
        user = auth.create_user(
            email=email,
            password=password
        )

        # Save user profile in Firestore
        user_data = {
            "uid": user.uid,
            "name": name,
            "email": email,
            "authProvider": "email_password"
        }

        db.collection("users").document(user.uid).set(user_data)

        return jsonify({
            "message": "User registered successfully",
            "user": user_data
        }), 201

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 400
        
@app.route("/login", methods=["POST"])
def login():

    data = request.get_json()

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({
            "error": "Email and password are required"
        }), 400

    url = (
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
        f"?key={FIREBASE_WEB_API_KEY}"
    )

    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }

    try:
        response = requests.post(url, json=payload)

        result = response.json()

        if response.status_code != 200:
            return jsonify({
                "error": result.get("error", {}).get(
                    "message",
                    "Login failed"
                )
            }), 401

        return jsonify({
            "message": "Login successful",
            "uid": result.get("localId"),
            "email": result.get("email"),
            "idToken": result.get("idToken")
        }), 200

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500
@app.route("/profile", methods=["GET"])
def profile():

    auth_header = request.headers.get("Authorization")

    if not auth_header:
        return jsonify({
            "error": "Authorization token is required"
        }), 401

    if not auth_header.startswith("Bearer "):
        return jsonify({
            "error": "Invalid authorization format"
        }), 401

    id_token = auth_header.split("Bearer ")[1]

    try:
        # Verify Firebase ID token
        decoded_token = auth.verify_id_token(id_token)

        uid = decoded_token["uid"]

        # Get user data from Firestore
        user_doc = db.collection("users").document(uid).get()

        if not user_doc.exists:
            return jsonify({
                "error": "User profile not found"
            }), 404

        user_data = user_doc.to_dict()

        return jsonify({
            "message": "Profile fetched successfully",
            "user": user_data
        }), 200

    except Exception as e:
        return jsonify({
            "error": "Invalid or expired token"
        }), 401     
        
@app.route("/save-data")
def save_data():

    city = request.args.get("city")

    if not city:
        return jsonify({
            "error": "Please provide a city"
        }), 400

    # Get City Coordinates
    location = get_city_coordinates(city)

    if location is None:
        return jsonify({
            "error": "City not found"
        }), 404

    latitude = location["latitude"]
    longitude = location["longitude"]
    city_name = location["name"]

    # AQI
    aqi = get_aqi_data(
        latitude,
        longitude,
        city_name
    )

    # Weather
    weather = get_weather_data(
        latitude,
        longitude,
        city_name
    )

    # Traffic
    traffic = get_traffic_data(
        latitude,
        longitude,
        city_name
    )

    if not aqi or not weather or not traffic:
        return jsonify({
            "error": "Unable to fetch live data"
        }), 500

    # Save into SQLite
    save_environment_data(

        city=city_name,

        aqi=aqi["aqi"],

        pm25=aqi.get("pm25"),
        pm10=aqi.get("pm10"),
        no2=aqi.get("no2"),
        co=aqi.get("co"),
        o3=aqi.get("o3"),
        so2=aqi.get("so2"),

        temperature=weather["temperature"],

        humidity=weather["humidity"],

        pressure=weather["pressure"],

        wind_speed=weather["wind_speed"],

        traffic_speed=traffic["current_speed"],

        free_flow_speed=traffic["free_flow_speed"]

    )

    return jsonify({
        "message": "Data Saved Successfully"
    })

# =====================================
# 1-HOUR AQI PREDICTION
# =====================================

@app.route("/predict/1h")
def predict_1h():

    city = request.args.get("city")

    if not city:

        return jsonify({
            "error": "Please provide a city"
        }), 400


    predictions = get_predictions(city)


    if predictions is None:

        return jsonify({
            "error": "Not enough historical data"
        }), 400


    return jsonify({

        "city": predictions["city"],

        "prediction_hours": 1,

        "predicted_aqi":
            predictions["prediction_1h"]

    })


# =====================================
# 6-HOUR AQI PREDICTION
# =====================================

@app.route("/predict/6h")
def predict_6h():

    city = request.args.get("city")

    if not city:

        return jsonify({
            "error": "Please provide a city"
        }), 400


    predictions = get_predictions(city)


    if predictions is None:

        return jsonify({
            "error": "Not enough historical data"
        }), 400


    return jsonify({

        "city": predictions["city"],

        "prediction_hours": 6,

        "predicted_aqi":
            predictions["prediction_6h"]

    })

@app.route("/history")
def history():

    data = get_history()

    return jsonify(data)


@app.route("/history/<period>")
def history_period(period):

    city = request.args.get("city")

    if not city:
        return jsonify({
            "error": "City is required"
        }), 400

    if period == "24h":
        hours = 24

    elif period == "7d":
        hours = 24 * 7

    elif period == "30d":
        hours = 24 * 30

    else:
        return jsonify({
            "error": "Invalid period"
        }), 400

    try:

        data = get_city_range_history(
            city,
            hours
        )

        return jsonify(data)

    except Exception as error:

        print("History error:", error)

        return jsonify({
            "error": str(error)
        }), 500


if __name__ == "__main__":

    create_database()

    app.run(
        debug=True,
        port=5000
    )