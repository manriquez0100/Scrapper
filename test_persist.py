import os
import sys
from dotenv import load_dotenv
load_dotenv()

print("FIREBASE_PROJECT_ID:", os.getenv("FIREBASE_PROJECT_ID"))
print("FIREBASE_SERVICE_ACCOUNT_KEY_PATH:", os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY_PATH"))
print("FIREBASE_CATALOG_ENABLED:", os.getenv("FIREBASE_CATALOG_ENABLED"))

from firestore_catalog import persist_catalog_books

test_results = [
    {
        'title': 'Libro de Prueba 1',
        'author': 'Autor Test',
        'price': '150',
        'currency': 'MXN',
        'availability': True,
        'url': 'https://example.com/libro1',
        'image_url': 'https://example.com/capa1.jpg',
        'source': 'buscalibre'
    }
]

saved = persist_catalog_books(test_results, 'TEST QUERY')
print("Libros guardados:", saved)