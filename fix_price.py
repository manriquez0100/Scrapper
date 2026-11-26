import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timezone

creds_path = 'store-ea555-firebase-adminsdk-4znay-c3f26d3ea7.json'
cred = credentials.Certificate(creds_path)
app = firebase_admin.initialize_app(cred)
db = firestore.client()

# Get first doc
docs = list(db.collection('books').limit(1).stream())
if docs:
    doc_id = docs[0].id
    doc_ref = db.collection('books').document(doc_id)
    
    # Update with top-level price fields
    latest_price_entry = {'price': '1829', 'priceText': '$ 1,829', 'date': datetime.now(timezone.utc).isoformat(), 'source': 'buscalibre'}
    
    doc_ref_ref = db.collection('books').document(doc_id)
    doc_ref_ref.update({
        'price': latest_price_entry['price'],
        'priceText': latest_price_entry['priceText'],
        'updatedAt': latest_price_entry['date'],
    })
    
    # Verify
    doc = doc_ref_ref.get()
    data = doc.to_dict()
    print(f'price: {data.get("price")}')
    print(f'priceText: {data.get("priceText")}')