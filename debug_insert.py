#!/usr/bin/env python
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import os

# Make sure we're using the correct credentials
creds_path = 'implemented_firestore/store-ea555-firebase-adminsdk-4znay-e64b83a1f0.json'
print('Using credentials from:', creds_path)

cred = credentials.Certificate(creds_path)
app = firebase_admin.initialize_app(cred)
db = firestore.client()

collection_name = 'books'
print('Collection name:', collection_name)

# Test document
book_document = {
    'nombre': 'TEST DESDE DEBUG',
    'autor': 'Depurador',
    'precio_numerico': 999,
    'url_libro': 'https://example.com/debug',
    'url_imagen': 'https://example.com/debug.jpg',
    'fecha_agregado': datetime.now()
}

print('Attempting to insert document...')
try:
    doc_ref = db.collection(collection_name).add(book_document)
    doc_id = doc_ref[1].id
    print('Document inserted with ID: ' + doc_id)
    
    # Immediately read it back
    doc = db.collection(collection_name).document(doc_id).get()
    if doc.exists:
        print('Document read successfully:')
        data = doc.to_dict()
        for key, value in data.items():
            if key != 'fecha_agregado':
                print('  ' + key + ': ' + str(value))
            else:
                print('  ' + key + ': ' + str(value))
    else:
        print('Document NOT found after inserting')
        
except Exception as e:
    print('Error inserting: ' + type(e).__name__ + ' ' + str(e))