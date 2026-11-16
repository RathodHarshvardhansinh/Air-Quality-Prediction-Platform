"""
iot.py  -  IoT sensor devices: registry, receiving readings, location matching, online/offline
=============================================================================================
Your physical device POSTs its readings to the AirSense backend; the dashboard then shows them
NEXT TO (never mixed with) the external-API values.

Same SQLite file as everything else (backend/airsense.db), two extra tables:
    iot_devices   one row per registered device  (id, name, installed location, key hash)
    iot_readings  every reading a device sent    (kept forever, survives restarts)
`environment_data` is NOT touched - it stays pure external-API history, which the ML models use.

REGISTER A DEVICE (once, on the computer that runs the backend):
    python backend/iot.py register --id ESP32-VSN-01 --name "Visnagar rooftop" \
           --city Visnagar --state Gujarat --lat 23.699 --lon 72.546
    -> prints a DEVICE KEY. Put it in your Arduino sketch.  (It is shown only once.)
Other commands:   python backend/iot.py list | rotate-key --id X | deactivate --id X

THE DEVICE SENDS  (HTTP POST, JSON, header  X-Device-Key: <key>)   to   http://<pc-ip>:5000/iot/readings
    {"device_id": "ESP32-VSN-01", "pm25": 32, "pm10": 48, "temperature": 28.5, "humidity": 62, "mq": 150}
    optional: aqi, pressure, co, no2, o3, so2, latitude, longitude, timestamp (ISO text or epoch seconds)
All values are optional but at least one valid measurement is needed.

Settings (.env, optional):
    IOT_FRESH_MINUTES=10      device counts as ONLINE only if its last reading is this recent
    IOT_MATCH_RADIUS_KM=10    a searched place is matched to a device within this distance
"""

import argparse
import hashlib
import hmac
import math
import os
import secrets
import sqlite3
import sys
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

import config  # noqa: F401  (loads .env)
from database import DATABASE, city_key, normalize_ts

FRESH_MINUTES = float(os.getenv("IOT_FRESH_MINUTES", "10"))
MATCH_RADIUS_KM = float(os.getenv("IOT_MATCH_RADIUS_KM", "10"))

iot_bp = Blueprint("iot", __name__)

# accepted measurements and their believable range (outside = rejected, never stored)
FIELDS = {
    "aqi": (0, 1000), "pm25": (0, 2000), "pm10": (0, 3000),
    "temperature": (-50, 100), "humidity": (0, 100), "pressure": (300, 1100),
    "mq": (0, 65535), "co": (0, 1000), "no2": (0, 5000), "o3": (0, 5000), "so2": (0, 5000),
}
ALIASES = {
    "pm2_5": "pm25", "pm2.5": "pm25", "temp": "temperature", "hum": "humidity",
    "mq_value": "mq", "mq_sensor": "mq", "mq135": "mq", "gas": "mq",
    "lat": "latitude", "lon": "longitude", "lng": "longitude", "ts": "timestamp", "time": "timestamp",
}


def _now():
    return datetime.now()


def _conn():
    c = sqlite3.connect(DATABASE)
    c.row_factory = sqlite3.Row
    return c


def create_iot_tables():
    c = _conn()
    c.execute("""
        CREATE TABLE IF NOT EXISTS iot_devices (
            device_id     TEXT PRIMARY KEY COLLATE NOCASE,
            name          TEXT,
            location_name TEXT NOT NULL,
            state         TEXT,
            latitude      REAL NOT NULL,
            longitude     REAL NOT NULL,
            key_hash      TEXT NOT NULL,
            active        INTEGER NOT NULL DEFAULT 1,
            created_at    TEXT NOT NULL
        )""")
    c.execute("""
        CREATE TABLE IF NOT EXISTS iot_readings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id   TEXT NOT NULL COLLATE NOCASE,
            received_at TEXT NOT NULL,          -- server clock, local time: used for online/offline
            sensor_time TEXT,                   -- clock of the device, only if it sent a believable one
            aqi REAL, pm25 REAL, pm10 REAL, temperature REAL, humidity REAL, pressure REAL,
            mq REAL, co REAL, no2 REAL, o3 REAL, so2 REAL,
            latitude REAL, longitude REAL
        )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_iot_dev_time ON iot_readings(device_id, id)")
    c.commit()
    c.close()


# --------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------

def _hash(key):
    return hashlib.sha256(key.encode()).hexdigest()


def _distance_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _number(value):
    """A real, finite number - or None.  (bool, text like 'nan', None are all rejected.)"""
    if value is None or isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _parse_sensor_time(value):
    """Device clock -> local 'YYYY-MM-DD HH:MM:SS', or None if missing / not believable."""
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)) or str(value).replace(".", "", 1).isdigit():
            x = float(value)
            dt = datetime.fromtimestamp(x / 1000.0 if x > 1e11 else x)
        else:
            text = str(value).strip().replace("Z", "+00:00")
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is not None:
                dt = dt.astimezone().replace(tzinfo=None)
    except (ValueError, OSError, OverflowError):
        return None
    now = _now()
    if dt < now - timedelta(days=30) or dt > now + timedelta(days=1):    # unset RTC, 1970, far future ...
        return None
    return normalize_ts(dt)


def _valid_gps(lat, lon):
    return (lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180
            and not (abs(lat) < 0.0001 and abs(lon) < 0.0001))


def clean_reading(payload):
    """
    payload (dict from the device) -> (clean dict, rejected list, error text or None).
    Unknown keys are ignored, values outside their believable range are dropped (and reported).
    """
    data = {}
    for key, value in payload.items():
        k = ALIASES.get(str(key).lower(), str(key).lower())
        data.setdefault(k, value)

    clean, rejected = {}, []
    for name, (lo, hi) in FIELDS.items():
        if name not in data or data[name] in (None, ""):
            continue
        x = _number(data[name])
        if x is None or not (lo <= x <= hi):
            rejected.append(name)
        else:
            clean[name] = x
    if not clean:
        return None, rejected, "No valid measurement in the request (need at least one of: " + ", ".join(FIELDS) + ")"

    lat, lon = _number(data.get("latitude")), _number(data.get("longitude"))
    if _valid_gps(lat, lon):
        clean["latitude"], clean["longitude"] = lat, lon
    clean["sensor_time"] = _parse_sensor_time(data.get("timestamp"))
    return clean, rejected, None


# --------------------------------------------------------------------------------------
# status of devices
# --------------------------------------------------------------------------------------

def _latest_by_device(conn):
    rows = conn.execute("SELECT * FROM iot_readings WHERE id IN (SELECT MAX(id) FROM iot_readings GROUP BY device_id)")
    return {r["device_id"].lower(): r for r in rows}


def _device_state(dev, latest):
    """dict describing one device: online / offline, last seen, effective location."""
    lat, lon = dev["latitude"], dev["longitude"]
    if latest is not None and _valid_gps(latest["latitude"], latest["longitude"]):
        lat, lon = latest["latitude"], latest["longitude"]          # a device that reports its own GPS

    status, last_seen, ago = "offline", None, None
    if latest is not None:
        last_seen = latest["received_at"]
        ago = (_now() - datetime.strptime(last_seen, "%Y-%m-%d %H:%M:%S")).total_seconds()
        if -60 <= ago <= FRESH_MINUTES * 60:                        # small tolerance for clock drift
            status = "online"
    return {"status": status, "last_seen": last_seen, "last_seen_ago_s": None if ago is None else max(0, int(ago)),
            "lat": lat, "lon": lon}


def _public_device(dev, state, distance=None):
    return {"device_id": dev["device_id"], "name": dev["name"], "location_name": dev["location_name"],
            "state": dev["state"], "latitude": state["lat"], "longitude": state["lon"],
            "distance_km": None if distance is None else round(distance, 2)}


def _reading_payload(row):
    out = {k: row[k] for k in FIELDS if row[k] is not None}
    out["sensor_time"] = row["sensor_time"]
    out["received_at"] = row["received_at"]
    return out


def iot_status_for(lat, lon, place_name=None):
    """
    The IoT device (if any) installed at the searched place.

      status "online"   registered + last reading within IOT_FRESH_MINUTES -> readings included
      status "offline"  registered here but silent for longer              -> NO readings (not live)
      status "none"     no registered device at this location

    Matching is by DISTANCE from the place (IOT_MATCH_RADIUS_KM); the same city name also counts
    out to 3x that radius.  Nothing is ever matched by name alone, so one city's device can never
    appear on another city's dashboard.
    """
    conn = _conn()
    try:
        devices = conn.execute("SELECT * FROM iot_devices WHERE active = 1").fetchall()
        latest = _latest_by_device(conn)
    finally:
        conn.close()

    wanted = city_key(place_name) if place_name else None
    candidates = []
    for dev in devices:
        last = latest.get(dev["device_id"].lower())
        state = _device_state(dev, last)
        d = _distance_km(lat, lon, state["lat"], state["lon"])
        same_name = wanted is not None and city_key(dev["location_name"]) == wanted
        if d <= MATCH_RADIUS_KM or (same_name and d <= 3 * MATCH_RADIUS_KM):
            candidates.append((state["status"] != "online", d, dev, state, last))

    base = {"fresh_minutes": FRESH_MINUTES, "radius_km": MATCH_RADIUS_KM, "devices_here": len(candidates)}
    if not candidates:
        return {**base, "connected": False, "status": "none", "device": None, "reading": None,
                "last_seen": None, "message": "No IoT Device Connected at This Location"}

    candidates.sort(key=lambda c: (c[0], c[1]))                      # online first, then nearest
    _, dist, dev, state, last = candidates[0]
    online = state["status"] == "online"
    return {
        **base,
        "connected": online,
        "status": state["status"],
        "device": _public_device(dev, state, dist),
        "last_seen": state["last_seen"],
        "last_seen_ago_s": state["last_seen_ago_s"],
        "sensor_time": last["sensor_time"] if (online and last) else None,
        "reading": _reading_payload(last) if online else None,      # an old reading is never shown as live
        "message": None if online else
        f"IoT device offline - no reading for more than {FRESH_MINUTES:g} minutes",
    }


# --------------------------------------------------------------------------------------
# HTTP endpoints
# --------------------------------------------------------------------------------------

@iot_bp.route("/iot/readings", methods=["POST"])
def receive_reading():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Send a JSON object"}), 400

    device_id = str(payload.get("device_id") or "").strip()
    key = request.headers.get("X-Device-Key") or str(payload.get("device_key") or "")
    if not device_id:
        return jsonify({"error": "device_id is required"}), 400

    conn = _conn()
    try:
        dev = conn.execute("SELECT * FROM iot_devices WHERE device_id = ?", (device_id,)).fetchone()
        # same answer for "unknown device" and "wrong key": do not reveal which device ids exist
        if dev is None or not dev["active"] or not key or not hmac.compare_digest(dev["key_hash"], _hash(key)):
            return jsonify({"error": "Unknown device or wrong device key"}), 401

        clean, rejected, error = clean_reading(payload)
        if error:
            return jsonify({"error": error, "rejected_fields": rejected}), 400

        cur = conn.execute(
            "INSERT INTO iot_readings(device_id, received_at, sensor_time, aqi, pm25, pm10, temperature, humidity, "
            "pressure, mq, co, no2, o3, so2, latitude, longitude) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (dev["device_id"], normalize_ts(_now()), clean.get("sensor_time"),
             *[clean.get(k) for k in ("aqi", "pm25", "pm10", "temperature", "humidity", "pressure",
                                      "mq", "co", "no2", "o3", "so2", "latitude", "longitude")]))
        conn.commit()
        return jsonify({"ok": True, "id": cur.lastrowid, "stored": [k for k in clean if k in FIELDS],
                        "rejected_fields": rejected}), 201
    finally:
        conn.close()


@iot_bp.route("/iot/devices")
def list_devices():
    conn = _conn()
    try:
        devices = conn.execute("SELECT * FROM iot_devices WHERE active = 1 ORDER BY device_id").fetchall()
        latest = _latest_by_device(conn)
    finally:
        conn.close()
    out = []
    for dev in devices:
        state = _device_state(dev, latest.get(dev["device_id"].lower()))
        out.append({**_public_device(dev, state), "status": state["status"], "last_seen": state["last_seen"]})
    return jsonify({"fresh_minutes": FRESH_MINUTES, "devices": out})


@iot_bp.route("/iot/history")
def device_history():
    """Stored readings of one device (survive backend restarts).  ?device_id=..&hours=24"""
    device_id = (request.args.get("device_id") or "").strip()
    if not device_id:
        return jsonify({"error": "device_id is required"}), 400
    try:
        hours = max(1, min(int(request.args.get("hours", 24)), 24 * 90))
    except ValueError:
        return jsonify({"error": "hours must be a number"}), 400
    since = normalize_ts(_now() - timedelta(hours=hours))
    conn = _conn()
    try:
        dev = conn.execute("SELECT device_id, name, location_name FROM iot_devices WHERE device_id = ?", (device_id,)).fetchone()
        if dev is None:
            return jsonify({"error": "Unknown device"}), 404
        rows = conn.execute("SELECT * FROM iot_readings WHERE device_id = ? AND received_at >= ? ORDER BY id LIMIT 20000",
                            (dev["device_id"], since)).fetchall()
    finally:
        conn.close()
    return jsonify({"device": dict(dev), "hours": hours, "count": len(rows), "records": [_reading_payload(r) for r in rows]})


# --------------------------------------------------------------------------------------
# command line:  python backend/iot.py register|list|rotate-key|deactivate
# --------------------------------------------------------------------------------------

def _cli():
    ap = argparse.ArgumentParser(description="Manage AirSense IoT devices")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("register", help="add a device and print its key")
    r.add_argument("--id", required=True)
    r.add_argument("--name", default="")
    r.add_argument("--city", required=True, help="location name where it is installed, e.g. Visnagar")
    r.add_argument("--state", default="")
    r.add_argument("--lat", type=float, required=True)
    r.add_argument("--lon", type=float, required=True)
    sub.add_parser("list")
    k = sub.add_parser("rotate-key", help="make a new key for a device (old one stops working)")
    k.add_argument("--id", required=True)
    d = sub.add_parser("deactivate", help="stop accepting a device")
    d.add_argument("--id", required=True)
    a = ap.parse_args()

    create_iot_tables()
    conn = _conn()
    if a.cmd == "register":
        if not _valid_gps(a.lat, a.lon):
            sys.exit("Latitude/longitude are not valid.")
        key = secrets.token_urlsafe(24)
        try:
            conn.execute("INSERT INTO iot_devices(device_id, name, location_name, state, latitude, longitude, key_hash, "
                         "created_at) VALUES (?,?,?,?,?,?,?,?)",
                         (a.id, a.name or a.id, a.city, a.state, a.lat, a.lon, _hash(key), normalize_ts(_now())))
        except sqlite3.IntegrityError:
            sys.exit(f"Device '{a.id}' already exists. Use rotate-key if you lost its key.")
        conn.commit()
        print(f"Registered {a.id} at {a.city}.\n\nDEVICE KEY (shown only once, put it in your sketch):\n\n    {key}\n")
    elif a.cmd == "rotate-key":
        key = secrets.token_urlsafe(24)
        if conn.execute("UPDATE iot_devices SET key_hash=? WHERE device_id=?", (_hash(key), a.id)).rowcount == 0:
            sys.exit("No such device.")
        conn.commit()
        print(f"New DEVICE KEY for {a.id}:\n\n    {key}\n")
    elif a.cmd == "deactivate":
        n = conn.execute("UPDATE iot_devices SET active=0 WHERE device_id=?", (a.id,)).rowcount
        conn.commit()
        print("Deactivated." if n else "No such device.")
    else:
        for dev in conn.execute("SELECT * FROM iot_devices ORDER BY device_id"):
            last = conn.execute("SELECT MAX(received_at) FROM iot_readings WHERE device_id=?", (dev["device_id"],)).fetchone()[0]
            print(f"{dev['device_id']:20s} {dev['location_name']:16s} ({dev['latitude']:.3f}, {dev['longitude']:.3f})  "
                  f"{'active' if dev['active'] else 'DEACTIVATED'}  last reading: {last or 'never'}")
    conn.close()


if __name__ == "__main__":
    _cli()