import firebase_admin
from firebase_admin import credentials, firestore
import os


firebase_credentials_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "firebase-service-account.json"
)


cred = credentials.Certificate(firebase_credentials_path)

firebase_admin.initialize_app(cred)

db = firestore.client()