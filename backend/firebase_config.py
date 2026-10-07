import firebase_admin
from firebase_admin import credentials, firestore
from firebase_admin import db as realtime_db
import os

firebase_credentials_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "firebase-service-account.json"
)

cred = credentials.Certificate(firebase_credentials_path)

firebase_admin.initialize_app(
    cred,
    {
        "databaseURL": "https://airqualitypredictionplatform-default-rtdb.firebaseio.com"
    }
)

# Existing Firestore connection
db = firestore.client()

# Firebase Realtime Database
rtdb = realtime_db