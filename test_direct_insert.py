#!/usr/bin/env python
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

# Use the same credentials as the uploader
creds_path = 'implemented_firestore/store-ea555-firebase-adminsdk-4znay-e64b83a1f0.json'
cred = credentials.Certificate(creds_path)
app = firebase_admin.initialize_app(cred)
db = firestore.client()

collection_name = 'books'

# Test document (same structure as firebase_uploader.py uses)
book_document = {
    'contacto': '',
    'disponible': 'true',
    'link': 'https://example.com/libro',
    'portada': 'https://example.com/capa.jpg',
    'precio': '999',
    'rating': '4.5',
    'textFromQuery': 'TEST',
    'titulo': 'Libro Directo desde Prueba',
    
    # Additional fields from the uploader
    'autor': 'Autor Test',
    'editorial': 'Editorial Test',
    'num_paginas': '300',
    'precio_original': '800',
    'precio_con_envio': '999',
    'tiempo_entrega': '3 dias',
    'fecha_agregado': datetime.now(),
    'fuente': 'buscalibre.com.mx'
}

print('Intentando insertar documento en ' + collection_name)
print('Proyecto Firebase: store-ea555')

try:
    doc_ref = db.collection(collection_name).add(book_document)
    doc_id = doc_ref[1].id
    print('✅ ÉXITO: Documento insertado con ID: ' + doc_id)
    
    # Verify it was inserted
    doc = db.collection(collection_name).document(doc_id).get()
    if doc.exists:
        data = doc.to_dict()
        print('✅ Verificación exitosa: Documento encontrado')
        print('   Título: ' + data.get('titulo', 'N/A'))
        print('   Fuente: ' + data.get('fuente', 'N/A'))
        print('   Precio: ' + data.get('precio', 'N/A'))
    else:
        print('❌ Error: Documento no encontrado después de insertar')
        
except Exception as e:
    print('❌ Error durante la inserción: ' + type(e).__name__)
    print('   Mensaje: ' + str(e))