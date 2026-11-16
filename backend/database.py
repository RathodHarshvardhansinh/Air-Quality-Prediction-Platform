import os
import sqlite3

# Always use the DB that sits next to this file, no matter where you start Flask from
DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "airsense.db")

# UNITS STORED IN THE DATABASE (one standard, so history + model never mix units):
#   aqi            Indian NAQI          us_aqi   US EPA AQI
#   pm25 pm10 no2 o3 so2   ug/m3        co       ug/m3   (the API/dashboard show mg/m3)
#   temperature  C     humidity  %      pressure hPa     wind_speed  km/h
#   timestamp    'YYYY-MM-DD HH:MM:SS'  (local time)
COLUMNS = (
    "city, aqi, us_aqi, pm25, pm10, no2, co, o3, so2, temperature, humidity, "
    "pressure, wind_speed, traffic_speed, free_flow_speed, timestamp"
)


def normalize_ts(value):
    """'2025-01-01T00:00' / '2025-01-01 00:00:00' / datetime -> 'YYYY-MM-DD HH:MM:SS'."""
    from datetime import datetime
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    text = str(value).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19] if fmt.endswith("%S") else text, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return text


def _connect():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def create_database():
    connection = _connect()
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS environment_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT NOT NULL,
            aqi INTEGER,
            us_aqi INTEGER,
            pm25 REAL, pm10 REAL, no2 REAL, co REAL, o3 REAL, so2 REAL,
            temperature REAL,
            humidity INTEGER,
            pressure INTEGER,
            wind_speed REAL,
            traffic_speed REAL,
            free_flow_speed REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    # older databases have no us_aqi column yet
    existing = {row["name"] for row in connection.execute("PRAGMA table_info(environment_data)")}
    if "us_aqi" not in existing:
        connection.execute("ALTER TABLE environment_data ADD COLUMN us_aqi INTEGER")

    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_env_city_time "
        "ON environment_data(city COLLATE NOCASE, timestamp)"
    )
    # one row per city + timestamp (stops the double-import problem).
    # If an old database still has duplicates, run  python backend/fix_database.py  first.
    try:
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_env_city_ts "
            "ON environment_data(city COLLATE NOCASE, timestamp)"
        )
    except sqlite3.IntegrityError:
        print("NOTE: database has duplicate rows - run  python backend/fix_database.py")
    connection.commit()
    connection.close()


def get_history(limit=20):
    connection = _connect()
    rows = connection.execute(
        "SELECT * FROM environment_data ORDER BY timestamp DESC LIMIT ?",
        (limit,),
    ).fetchall()
    connection.close()
    return [dict(r) for r in rows]


def get_latest_record(city):
    connection = _connect()
    row = connection.execute(
        f"SELECT {COLUMNS} FROM environment_data "
        "WHERE LOWER(city) = LOWER(?) ORDER BY timestamp DESC LIMIT 1",
        (city,),
    ).fetchone()
    connection.close()
    return dict(row) if row else None


def minutes_since_last_save(city):
    """Minutes since this city was last saved (None if never)."""
    connection = _connect()
    row = connection.execute(
        "SELECT (julianday('now') - julianday(MAX(timestamp))) * 1440 AS m "
        "FROM environment_data WHERE LOWER(city) = LOWER(?)",
        (city,),
    ).fetchone()
    connection.close()
    if row is None or row["m"] is None:
        return None
    return float(row["m"])


def get_city_range_history(city, hours, start=None, end=None):
    """
    History for a city.

    The window is measured back from the city's LATEST stored record
    (not from 'now'), so the chart still shows data even when the
    collector has not run for a few days.  Pass start/end
    ('YYYY-MM-DD') for a custom range.
    """
    connection = _connect()

    if start and end:
        rows = connection.execute(
            f"SELECT {COLUMNS} FROM environment_data "
            "WHERE LOWER(city) = LOWER(?) "
            "AND date(timestamp) >= date(?) AND date(timestamp) <= date(?) "
            "ORDER BY timestamp ASC",
            (city, start, end),
        ).fetchall()
    else:
        rows = connection.execute(
            f"SELECT {COLUMNS} FROM environment_data "
            "WHERE LOWER(city) = LOWER(?) "
            "AND timestamp >= datetime("
            "  (SELECT MAX(timestamp) FROM environment_data WHERE LOWER(city) = LOWER(?)),"
            "  ?) "
            "ORDER BY timestamp ASC",
            (city, city, f"-{int(hours)} hours"),
        ).fetchall()

    connection.close()
    return [dict(r) for r in rows]


def get_city_history(city, limit=24):
    connection = _connect()
    rows = connection.execute(
        f"SELECT {COLUMNS} FROM ("
        f"  SELECT {COLUMNS} FROM environment_data "
        "  WHERE LOWER(city) = LOWER(?) ORDER BY timestamp DESC LIMIT ?"
        ") ORDER BY timestamp ASC",
        (city, limit),
    ).fetchall()
    connection.close()
    return [dict(r) for r in rows]


def get_known_cities():
    connection = _connect()
    rows = connection.execute(
        "SELECT city, COUNT(*) AS n, MAX(timestamp) AS last "
        "FROM environment_data GROUP BY city ORDER BY n DESC"
    ).fetchall()
    connection.close()
    return [dict(r) for r in rows]


# =====================================
# CITY NAME MATCHING  (Mehsana == Mahesana == Mahesāna,  Junagadh == Jūnāgadh)
# =====================================

_ALIASES = {"mahesana": "mehsana", "junagarh": "junagadh", "baroda": "vadodara",
            "bombay": "mumbai", "calcutta": "kolkata", "madras": "chennai",
            "bangalore": "bengaluru", "poona": "pune", "ahmadabad": "ahmedabad"}


def city_key(name):
    """Lower-case, accent-free key used to compare city names."""
    import unicodedata
    text = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode().lower().strip()
    return _ALIASES.get(text, text)


def resolve_db_city(name):
    """The exact spelling used in the database for this city, or `name` itself if unknown."""
    wanted = city_key(name)
    connection = _connect()
    rows = connection.execute("SELECT city, COUNT(*) AS n FROM environment_data GROUP BY city").fetchall()
    connection.close()
    best = None
    for row in rows:
        if city_key(row["city"]) == wanted and (best is None or row["n"] > best[1]):
            best = (row["city"], row["n"])
    return best[0] if best else name
