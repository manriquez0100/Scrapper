# Configuración de Firebase
# Reemplaza estos valores con tus credenciales reales de Firebase

FIREBASE_CONFIG = {
    "type": "service_account",
    "project_id": "tu-project-id-aqui",
    "private_key_id": "tu-private-key-id-aqui",
    "private_key": "-----BEGIN PRIVATE KEY-----\nTU_PRIVATE_KEY_AQUI\n-----END PRIVATE KEY-----\n",
    "client_email": "firebase-adminsdk-xxxxx@tu-project-id.iam.gserviceaccount.com",
    "client_id": "tu-client-id-aqui",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-xxxxx%40tu-project-id.iam.gserviceaccount.com"
}

# Nombre de tu proyecto de Firebase
PROJECT_ID = "tu-project-id-aqui"

# Nombre de la colección en Firestore
COLLECTION_NAME = "books"