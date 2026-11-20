#!/usr/bin/env python
import sys
import os
sys.path.insert(0, '.')

# Cargar variables de entorno explícitamente
from dotenv import load_dotenv
load_dotenv(dotenv_path='.env')

print("=== Configuración de variables de entorno ===")
print(f"FIREBASE_PROJECT_ID: {os.getenv('FIREBASE_PROJECT_ID')}")
print(f"FIREBASE_SERVICE_ACCOUNT_KEY_PATH: {os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')}")
print(f"FIREBASE_CATALOG_ENABLED: {os.getenv('FIREBASE_CATALOG_ENABLED')}")
print(f"FIREBASE_CATALOG_COLLECTION: {os.getenv('FIREBASE_CATALOG_COLLECTION')}")
print()

# Verificar si el archivo de credenciales existe
key_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
if key_path:
    if not os.path.isabs(key_path):
        # Ruta relativa al directorio del script
        key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), key_path)
    print(f"Ruta completa del key_path: {key_path}")
    print(f"Archivo existe: {os.path.exists(key_path)}")

from firestore_catalog import persist_catalog_books, FirestoreCatalogWriter

print()
print("=== Verificando FirestoreCatalogWriter ===")
writer = FirestoreCatalogWriter()
print(f"Writer habilitado: {writer.enabled}")
print(f"Writer colección: {writer.collection}")
print(f"Writer db inicializado: {writer.db is not None}")

if writer.db is None:
    print("Intentando inicializar writer...")
    initialized = writer._initialize()
    print(f"Inicialización exitosa: {initialized}")
    print(f"Writer db después de inicializar: {writer.db is not None}")

print()
print("=== Probando persist_catalog_books ===")
# Simular los 3 libros que retorna el scraper
test_results = [
    {
        'title': 'Libro 1: El principito',
        'author': 'Antoine de Saint-Exupéry',
        'price': '120',
        'currency': 'MXN',
        'availability': True,
        'url': 'https://example.com/libro1',
        'image_url': 'https://example.com/capa1.jpg',
        'source': 'buscalibre'
    },
    {
        'title': 'Libro 2: Don Quijote',
        'author': 'Miguel de Cervantes',
        'price': '180',
        'currency': 'MXN',
        'availability': True,
        'url': 'https://example.com/libro2',
        'image_url': 'https://example.com/capa2.jpg',
        'source': 'buscalibre'
    },
    {
        'title': 'Libro 3: Cien años de soledad',
        'author': 'Gabriel García Márquez',
        'price': '250',
        'currency': 'MXN',
        'availability': True,
        'url': 'https://example.com/libro3',
        'image_url': 'https://example.com/capa3.jpg',
        'source': 'buscalibre'
    }
]

print(f'Intentando guardar {len(test_results)} libros...')
saved = persist_catalog_books(test_results, 'TEST QUERY')
print(f'Libros guardados en Firestore: {saved}')
print()
print('Verificando documentos en la colección books...')

# Verificar en Firestore directamente
import firebase_admin
from firebase_admin import credentials, firestore

cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
if not os.path.isabs(cred_path):
    cred_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), cred_path)

cred = credentials.Certificate(cred_path)
app = firebase_admin.initialize_app(cred)
db = firestore.client()

collection_name = os.getenv('FIREBASE_CATALOG_COLLECTION', 'books')
docs = list(db.collection(collection_name).stream())
print(f'Documentos en {collection_name} después de la inserción:')
for doc in docs:
    data = doc.to_dict()
    print('  -', data.get('title', 'N/A'), 'por', data.get('price', 'N/A'), 'MXN')

print(f'Total: {len(docs)} documentos')