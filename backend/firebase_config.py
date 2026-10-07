import firebase_admin
from firebase_admin import credentials, firestore
from firebase_admin import db as realtime_db
import os

firebase_credentials_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "firebase-service-account.json"
)

database_url = os.getenv("FIREBASE_DATABASE_URL")

cred = credentials.Certificate(firebase_credentials_path)

firebase_admin.initialize_app(
    cred,
    {
        "databaseURL": database_url
    }
)

# Existing Firestore database - keep this for users/auth/profile
db = firestore.client()

# New Realtime Database - used for ESP32 sensor data
rtdb = realtime_db