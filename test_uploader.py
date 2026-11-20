#!/usr/bin/env python
import os
import sys

# Add the directory to path
sys.path.insert(0, '.')

# Try to import and use FirebaseUploader
try:
    from firebase_uploader import FirebaseUploader
    print('FirebaseUploader importado correctamente')
    
    # Try to initialize
    print('Inicializando Firebase...')
    uploader = FirebaseUploader()
    print('Firebase inicializado correctamente')
    
    # Try to upload a test book
    print('Subiendo libro de prueba...')
    libro_prueba = {
        'nombre': 'TEST DESDE UPLOADER',
        'autor': 'Test Autor',
        'precio_numerico': 500,
        'url_libro': 'https://example.com/libro',
        'url_imagen': 'https://example.com/capa.jpg'
    }
    
    doc_id = uploader.upload_book(libro_prueba, 'TEST')
    if doc_id:
        print('Libro subido exitosamente con ID: ' + str(doc_id))
    else:
        print('Error subiendo libro - returned None')
        
except ImportError as e:
    print('Error importando FirebaseUploader: ' + str(e))
    print('Asegurese de tener instalado firebase-admin: pip install firebase-admin')
except Exception as e:
    print('Error inesperado: ' + type(e).__name__ + ' ' + str(e))