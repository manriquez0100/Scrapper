import firebase_admin
from firebase_admin import credentials, firestore
import os

creds_path = 'store-ea555-firebase-adminsdk-4znay-c3f26d3ea7.json'
cred = credentials.Certificate(creds_path)
app = firebase_admin.initialize_app(cred)
db = firestore.client()

docs = db.collection('books').limit(3).stream()
for doc in docs:
    data = doc.to_dict()
    price = data.get('price', 'N/A')
    priceText = data.get('priceText', 'N/A')
    title = data.get('title', 'N/A')[:40]
    print(f'Title: {title}...')
    print(f'  price: {price} (type: {type(price).__name__})')
    print(f'  priceText: {priceText} (type: {type(priceText).__name__})')
    print()