"""
Firebase configuration module.
Contains the Firebase project configuration based on the provided credentials.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Firebase configuration based on your provided JavaScript config
FIREBASE_CONFIG = {
    "type": "service_account",
    "project_id": os.getenv("FIREBASE_PROJECT_ID", "store-ea555"),
    "private_key_id": "",
    "private_key": "",
    "client_email": "",
    "client_id": "",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": ""
}

# Firebase web app configuration (from your JavaScript config)
FIREBASE_WEB_CONFIG = {
    "apiKey": os.getenv("FIREBASE_API_KEY", "AIzaSyC0dyLxc8R1SsO2SAURqUgTBWnq044_JPw"),
    "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN", "store-ea555.firebaseapp.com"),
    "projectId": os.getenv("FIREBASE_PROJECT_ID", "store-ea555"),
    "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET", "store-ea555.firebasestorage.app"),
    "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID", "76263447041"),
    "appId": os.getenv("FIREBASE_APP_ID", "1:76263447041:web:e58a4dcf641b826c69fe00"),
    "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID", "G-X6W1NLFY5B")
}

# Service account key file path
SERVICE_ACCOUNT_KEY_PATH = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY_PATH", "store-ea555-firebase-adminsdk-4znay-e64b83a1f0.json")

# Project ID for Firestore
PROJECT_ID = FIREBASE_WEB_CONFIG["projectId"]