#!/usr/bin/env python
import os
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

creds_path = 'implemented_firestore/store-ea555-firebase-adminsdk-4znay-c3f26d3ea7.json'
cred = credentials.Certificate(creds_path)
app = firebase_admin.initialize_app(cred)
db = firestore.client()

collection_name = 'books'

# Insert test book
book_document = {
    'contacto': '',
    'disponible': 'true',
    'link': 'https://example.com/libro',
    'portada': 'https://example.com/capa.jpg',
    'precio': '100',
    'rating': '4.5',
    'textFromQuery': 'HISTORIA DE MEXICO',
    'titulo': 'Libro de Prueba desde Python',
    'autor': 'Autor Test',
    'editorial': 'Editorial Test',
    'num_paginas': '200',
    'precio_original': '120',
    'precio_con_envio': '100',
    'tiempo_entrega': '2 dias',
    'fecha_agregado': datetime.now(),
    'fuente': 'buscalibre.com.mx'
}

doc_ref = db.collection(collection_name).add(book_document)
doc_id = doc_ref[1].id
print('Libro subido exitosamente con ID: ' + doc_id)

# Read it back
doc = db.collection(collection_name).document(doc_id).get()
print('Libro leido de Firestore:')
for key, value in doc.to_dict().items():
    if key != 'fecha_agregado':
        print('  ' + key + ': ' + str(value))
    else:
        print('  ' + key + ': ' + str(value))

print('')
print('Documento mantenido en Firestore (no eliminado)')