from flask import Flask, jsonify

from weather import get_weather_data
from aqi import get_aqi_data
from traffic import get_traffic_data


app = Flask(__name__)


@app.route("/weather")
def weather():
    data = get_weather_data()

    if data is None:
        return jsonify({
            "error": "Unable to fetch weather data"
        }), 500

    return jsonify(data)


@app.route("/aqi")
def aqi():
    data = get_aqi_data()

    if data is None:
        return jsonify({
            "error": "Unable to fetch AQI data"
        }), 500

    return jsonify(data)


@app.route("/traffic")
def traffic():
    data = get_traffic_data()

    if data is None:
        return jsonify({
            "error": "Unable to fetch traffic data"
        }), 500

    return jsonify(data)


@app.route("/environment")
def environment():
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

    return jsonify({
        "weather": weather_data,
        "air_quality": aqi_data,
        "traffic": traffic_data
    })


@app.route("/")
def home():
    return jsonify({
        "message": "Air Quality Prediction Platform API",
        "endpoints": [
            "/weather",
            "/aqi",
            "/traffic",
            "/environment"
        ]
    })


if __name__ == "__main__":
    app.run(debug=True)