#!/usr/bin/env python
import firebase_admin
from firebase_admin import credentials, firestore

creds_path = 'implemented_firestore/store-ea555-firebase-adminsdk-4znay-e64b83a1f0.json'
cred = credentials.Certificate(creds_path)
app = firebase_admin.initialize_app(cred)
db = firestore.client()

collection_name = 'books'
docs = list(db.collection(collection_name).stream())
print('Documentos actuales:')
for doc in docs:
    data = doc.to_dict()
    print('  -', data.get('title', 'N/A'), 'por', data.get('price', 'N/A'), 'MXN')

# Eliminar todos menos el que tenga 'Libro de Prueba'
ids_to_keep = []
for doc in docs:
    data = doc.to_dict()
    if 'Libro de Prueba' in data.get('title', ''):
        ids_to_keep.append(doc.id)
    else:
        db.collection(collection_name).document(doc.id).delete()

# Ahora lista final
docs_after = list(db.collection(collection_name).stream())
print()
print('Documentos finales:')
for doc in docs_after:
    data = doc.to_dict()
    print('  -', data.get('title', 'N/A'), 'por', data.get('price', 'N/A'), 'MXN')
print('Total:', len(docs_after), 'documentos')