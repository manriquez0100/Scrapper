"""
Main script for inserting data into Firestore database.
This script demonstrates how to connect to Firebase Firestore and insert sample data.
"""

import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import os
import sys
from config import SERVICE_ACCOUNT_KEY_PATH, PROJECT_ID

def initialize_firebase():
    """Initialize Firebase Admin SDK with service account credentials."""
    try:
        # Check if Firebase app is already initialized
        if not firebase_admin._apps:
            # Use service account key file
            if os.path.exists(SERVICE_ACCOUNT_KEY_PATH):
                cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
                firebase_admin.initialize_app(cred)
                print(f"✅ Firebase initialized with service account key: {SERVICE_ACCOUNT_KEY_PATH}")
            else:
                # Try to use default credentials (for deployment environments)
                try:
                    cred = credentials.ApplicationDefault()
                    firebase_admin.initialize_app(cred, {
                        'projectId': PROJECT_ID,
                    })
                    print("✅ Firebase initialized with default application credentials")
                except Exception as e:
                    print(f"❌ Error: Could not initialize Firebase. {e}")
                    print(f"Please ensure you have a valid service account key file at: {SERVICE_ACCOUNT_KEY_PATH}")
                    print("Or download one from: https://console.firebase.google.com/project/{}/settings/serviceaccounts/adminsdk".format(PROJECT_ID))
                    return None
        else:
            print("✅ Firebase already initialized")
        
        # Return Firestore client
        db = firestore.client()
        return db
    
    except Exception as e:
        print(f"❌ Error initializing Firebase: {e}")
        return None

def insert_sample_data(db):
    """Insert sample data into Firestore collections."""
    try:
        print("\n📝 Inserting sample data into Firestore...")
        
        # Sample users data
        users_data = [
            {
                'name': 'juan perez',
                'email': 'john.doe@example.com',
                'age': 30,
                'created_at': datetime.now(),
                'active': True
            },
            {
                'name': 'Jane Smith',
                'email': 'jane.smith@example.com',
                'age': 25,
                'created_at': datetime.now(),
                'active': True
            },
            {
                'name': 'Bob Johnson',
                'email': 'bob.johnson@example.com',
                'age': 35,
                'created_at': datetime.now(),
                'active': False
            }
        ]
        
        # Insert users
        users_collection = db.collection('users')
        for user_data in users_data:
            doc_ref = users_collection.add(user_data)
            print(f"✅ Added user: {user_data['name']} with ID: {doc_ref[1].id}")
        
        # Sample products data
        products_data = [
            {
                'titulo': 'Laptop Gaming',
                'precio': 999.99,
                'contacto': 'vendor@example.com',
                'disponible': True,
                'link': 'https://example.com/laptop',
                'portada': 'https://example.com/images/laptop.jpg',
                'rating': 4.5,
                'textFromQuery': 'High-performance laptop for work and gaming'
            },
            {
                'titulo': 'Taza de Café',
                'precio': 12.99,
                'contacto': 'kitchen@example.com',
                'disponible': True,
                'link': 'https://example.com/mug',
                'portada': 'https://example.com/images/mug.jpg',
                'rating': 4.2,
                'textFromQuery': 'Ceramic coffee mug with ergonomic handle'
            },
            {
                'titulo': 'Mouse Inalámbrico',
                'precio': 29.99,
                'contacto': 'tech@example.com',
                'disponible': False,
                'link': 'https://example.com/mouse',
                'portada': 'https://example.com/images/mouse.jpg',
                'rating': 3.8,
                'textFromQuery': 'Wireless optical mouse with USB receiver'
            }
        ]
        
        # Insert products
        products_collection = db.collection('products')
        for product_data in products_data:
            doc_ref = products_collection.add(product_data)
            print(f"✅ Added product: {product_data['titulo']} with ID: {doc_ref[1].id}")
        
        print("\n🎉 Sample data insertion completed successfully!")
        return True
    
    except Exception as e:
        print(f"❌ Error inserting data: {e}")
        return False

def read_sample_data(db):
    """Read and display some sample data from Firestore."""
    try:
        print("\n📖 Reading sample data from Firestore...")
        
        # Read users
        users = db.collection('users').limit(3).stream()
        print("\n👥 Users:")
        for user in users:
            user_dict = user.to_dict()
            print(f"  - ID: {user.id}")
            print(f"    Name: {user_dict.get('name')}")
            print(f"    Email: {user_dict.get('email')}")
            print(f"    Age: {user_dict.get('age')}")
            print(f"    Active: {user_dict.get('active')}")
            print()
        
        # Read products
        products = db.collection('products').limit(3).stream()
        print("🛍️ Products:")
        for product in products:
            product_dict = product.to_dict()
            print(f"  - ID: {product.id}")
            print(f"    Titulo: {product_dict.get('titulo')}")
            print(f"    Precio: ${product_dict.get('precio')}")
            print(f"    Contacto: {product_dict.get('contacto')}")
            print(f"    Disponible: {product_dict.get('disponible')}")
            print(f"    Link: {product_dict.get('link')}")
            print(f"    Portada: {product_dict.get('portada')}")
            print(f"    Rating: {product_dict.get('rating')}")
            print(f"    TextFromQuery: {product_dict.get('textFromQuery')}")
            print()
        
        return True
    
    except Exception as e:
        print(f"❌ Error reading data: {e}")
        return False

def main():
    """Main function to run the Firestore data insertion script."""
    print("🚀 Starting Firestore Data Insertion Script")
    print(f"📊 Project ID: {PROJECT_ID}")
    
    # Initialize Firebase
    db = initialize_firebase()
    if not db:
        print("❌ Failed to initialize Firebase. Exiting.")
        sys.exit(1)
    
    # Insert sample data
    if insert_sample_data(db):
        # Read and display the inserted data
        read_sample_data(db)
        print("✨ Script completed successfully!")
    else:
        print("❌ Script failed to insert data.")
        sys.exit(1)

if __name__ == "__main__":
    main()