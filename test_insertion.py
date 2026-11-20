#!/usr/bin/env python
"""Test script to verify Firebase data insertion into books collection."""
import firebase_admin
from firebase_admin import credentials, firestore
import sys

def test_insertion():
    """Test that data can be inserted into Firebase Firestore books collection."""
    
    # Initialize Firebase with the service account key
    creds_path = 'implemented_firestore/store-ea555-firebase-adminsdk-4znay-e64b83a1f0.json'
    
    print("Inicializando Firebase con credenciales: " + creds_path)
    print("Proyecto destino: store-ea555")
    print("Colección: books")
    print()
    
    try:
        cred = credentials.Certificate(creds_path)
        app = firebase_admin.initialize_app(cred)
        db = firestore.client()
        
        collection_name = 'books'
        
        # Test document (matches the structure used by firebase_uploader.py)
        book_document = {
            'contacto': '',
            'disponible': 'true',
            'link': 'https://example.com/libro',
            'portada': 'https://example.com/capa.jpg',
            'precio': '150',
            'rating': '4.5',
            'textFromQuery': 'HISTORIA DE MEXICO',
            'titulo': 'Libro de Prueba - Test de Insercion',
            'autor': 'Autor de Prueba',
            'editorial': 'Editorial de Prueba',
            'num_paginas': '200',
            'precio_original': '200',
            'precio_con_envio': '150',
            'tiempo_entrega': '5 dias',
            'fuente': 'buscalibre.com.mx'
        }
        
        print("Insertando libro en Firebase Firestore...")
        print("Coleccion: " + collection_name)
        print()
        
        # Insert the book
        doc_ref = db.collection(collection_name).add(book_document)
        doc_id = doc_ref[1].id
        
        print("Resultado de la insercion:")
        print("  ID del documento: " + doc_id)
        print()
        
        # Verify the book was inserted
        print("Verificando que el libro se insertara correctamente...")
        doc = db.collection(collection_name).document(doc_id).get()
        
        if doc.exists:
            data = doc.to_dict()
            print()
            print("=== VERIFICACION EXITOSA ===")
            print("Libro encontrado en Firestore:")
            print("  Titulo: " + data.get('titulo', 'N/A'))
            print("  Autor: " + data.get('autor', 'N/A'))
            print("  Fuente: " + data.get('fuente', 'N/A'))
            print("  Precio: " + data.get('precio', 'N/A'))
            print("  Disponible: " + data.get('disponible', 'N/A'))
            print("  Link: " + data.get('link', 'N/A'))
            print()
            print("El dato SÍ se esta insertando en store-ea555/books")
            return True
        else:
            print()
            print("ERROR: Libro NO encontrado despues de insertar")
            print("El dato NO se guardó en Firestore")
            return False
            
    except Exception as e:
        print()
        print("ERROR durante la insercion:")
        print("  Tipo: " + type(e).__name__)
        print("  Mensaje: " + str(e))
        return False

if __name__ == "__main__":
    success = test_insertion()
    sys.exit(0 if success else 1)