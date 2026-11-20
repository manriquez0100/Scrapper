#!/usr/bin/env python
import firebase_admin
from firebase_admin import credentials, firestore

creds_path = 'implemented_firestore/store-ea555-firebase-adminsdk-4znay-e64b83a1f0.json'
cred = credentials.Certificate(creds_path)
app = firebase_admin.initialize_app(cred)
db = firestore.client()

collection_name = 'books'
docs = list(db.collection(collection_name).stream())
print('Documentos actuales en store-ea555/books:')
for doc in docs:
    data = doc.to_dict()
    print('  - ID: ' + doc.id + ', titulo: ' + data.get('titulo', 'N/A') + ', fuente: ' + data.get('fuente', 'N/A'))
print('Total: ' + str(len(docs)) + ' documentos')