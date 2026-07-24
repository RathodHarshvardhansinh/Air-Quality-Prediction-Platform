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


app = Flask(__name__)


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
        location["name"]
    )

    if weather_data is None:
        return jsonify({
            "error": "Unable to fetch weather data"
        }), 500

    return jsonify(weather_data)


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
        location["name"]
    )

    if aqi_data is None:
        return jsonify({
            "error": "Unable to fetch air quality data"
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
        location["name"]
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

    weather_data = get_weather_data()
    aqi_data = get_aqi_data()
    traffic_data = get_traffic_data()

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

    environment_data = {
        "weather": weather_data,
        "air_quality": aqi_data,
        "traffic": traffic_data,
        "updated_at": datetime.now().isoformat()
    }

    db.collection("environment_data").document("current").set(
        environment_data
    )

    return jsonify({
        "message": "Environment data saved to Firebase",
        "data": environment_data
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

if __name__ == "__main__":
    app.run(debug=True)