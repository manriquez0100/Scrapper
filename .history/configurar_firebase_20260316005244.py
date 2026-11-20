"""
Script para configurar credenciales de Firebase
Ejecuta este script para configurar automáticamente tus credenciales de Firebase
"""

import json
import os

def configurar_firebase():
    """Configurar credenciales de Firebase interactivamente"""
    print("🔥 CONFIGURACIÓN DE FIREBASE")
    print("="*50)
    
    print("\nOpción 1: Archivo JSON de credenciales")
    print("- Descarga el archivo JSON desde Firebase Console")
    print("- Guárdalo como 'firebase-credentials.json' en esta carpeta")
    
    print("\nOpción 2: Configurar credenciales manualmente")
    print("- Te ayudaremos a configurar cada campo")
    
    opcion = input("\n¿Qué opción prefieres? (1/2): ").strip()
    
    if opcion == "1":
        configurar_con_archivo()
    elif opcion == "2":
        configurar_manualmente()
    else:
        print("❌ Opción no válida")

def configurar_con_archivo():
    """Configurar usando archivo JSON de credenciales"""
    archivo_json = "firebase-credentials.json"
    
    if os.path.exists(archivo_json):
        print(f"✅ Archivo {archivo_json} encontrado")
        
        try:
            with open(archivo_json, 'r') as f:
                credenciales = json.load(f)
            
            # Validar campos requeridos
            campos_requeridos = ['project_id', 'private_key', 'client_email']
            for campo in campos_requeridos:
                if campo not in credenciales:
                    print(f"❌ Campo requerido '{campo}' no encontrado en el archivo")
                    return
            
            print("✅ Archivo de credenciales válido")
            print(f"📋 Proyecto: {credenciales.get('project_id')}")
            print(f"📧 Email: {credenciales.get('client_email')}")
            
            # Actualizar firebase_config.py
            actualizar_config_file(credenciales)
            
        except json.JSONDecodeError:
            print("❌ Error: El archivo no es un JSON válido")
        except Exception as e:
            print(f"❌ Error leyendo archivo: {e}")
    else:
        print(f"❌ Archivo {archivo_json} no encontrado")
        print("\n📝 Pasos para obtener el archivo:")
        print("1. Ve a Firebase Console (https://console.firebase.google.com)")
        print("2. Selecciona tu proyecto")
        print("3. Ve a Configuración del proyecto > Cuentas de servicio")
        print("4. Genera nueva clave privada")
        print("5. Guarda el archivo como 'firebase-credentials.json' aquí")

def configurar_manualmente():
    """Configurar credenciales manualmente"""
    print("\n📝 Ingresa las credenciales de Firebase:")
    print("(Puedes encontrarlas en Firebase Console > Configuración del proyecto > Cuentas de servicio)")
    
    try:
        project_id = input("Project ID: ").strip()
        private_key_id = input("Private Key ID: ").strip()
        private_key = input("Private Key (completa, con -----BEGIN PRIVATE KEY-----): ").strip()
        client_email = input("Client Email: ").strip()
        client_id = input("Client ID: ").strip()
        
        if not all([project_id, private_key_id, private_key, client_email, client_id]):
            print("❌ Todos los campos son requeridos")
            return
        
        # Crear diccionario de credenciales
        credenciales = {
            "type": "service_account",
            "project_id": project_id,
            "private_key_id": private_key_id,
            "private_key": private_key,
            "client_email": client_email,
            "client_id": client_id,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{client_email.replace('@', '%40')}"
        }
        
        # Actualizar firebase_config.py
        actualizar_config_file(credenciales)
        
    except KeyboardInterrupt:
        print("\n❌ Configuración cancelada")
    except Exception as e:
        print(f"❌ Error en configuración: {e}")

def actualizar_config_file(credenciales):
    """Actualizar archivo firebase_config.py con las credenciales"""
    try:
        config_content = f"""# Configuración de Firebase - Generado automáticamente
# No compartas este archivo. Añádelo a .gitignore

FIREBASE_CONFIG = {json.dumps(credenciales, indent=4)}

# Nombre de tu proyecto de Firebase
PROJECT_ID = "{credenciales.get('project_id')}"

# Nombre de la colección en Firestore
COLLECTION_NAME = "books"
"""
        
        with open('firebase_config.py', 'w', encoding='utf-8') as f:
            f.write(config_content)
        
        print("✅ Credenciales configuradas correctamente en firebase_config.py")
        print("⚠️  IMPORTANTE: No compartas el archivo firebase_config.py")
        print("💡 Añade firebase_config.py a tu .gitignore si usas git")
        
        # Crear .gitignore si no existe
        crear_gitignore()
        
    except Exception as e:
        print(f"❌ Error guardando configuración: {e}")

def crear_gitignore():
    """Crear o actualizar .gitignore con archivos sensibles"""
    gitignore_path = ".gitignore"
    archivos_sensibles = [
        "firebase_config.py",
        "firebase-credentials.json",
        "*.pyc",
        "__pycache__/",
        ".env",
        "*.log"
    ]
    
    try:
        # Leer .gitignore existente
        if os.path.exists(gitignore_path):
            with open(gitignore_path, 'r') as f:
                contenido_existente = f.read()
        else:
            contenido_existente = ""
        
        # Agregar archivos sensibles si no están
        contenido_nuevo = contenido_existente
        for archivo in archivos_sensibles:
            if archivo not in contenido_existente:
                contenido_nuevo += f"\n{archivo}"
        
        # Escribir .gitignore actualizado
        with open(gitignore_path, 'w') as f:
            f.write(contenido_nuevo.strip() + "\n")
        
        print(f"✅ .gitignore actualizado")
        
    except Exception as e:
        print(f"⚠️ Error actualizando .gitignore: {e}")

def probar_conexion():
    """Probar conexión a Firebase"""
    print("\n🧪 PROBANDO CONEXIÓN A FIREBASE")
    print("="*40)
    
    try:
        from firebase_uploader import FirebaseUploader
        
        uploader = FirebaseUploader()
        print("✅ Conexión a Firebase exitosa")
        
        # Probar subida de datos de prueba
        test_book = {
            'nombre': 'Libro de Prueba',
            'autor': 'Autor Test',
            'precio_numerico': 100,
            'url_libro': 'https://example.com',
            'url_imagen': 'https://example.com/image.jpg'
        }
        
        respuesta = input("¿Quieres probar subiendo un libro de prueba? (y/n): ").strip().lower()
        if respuesta == 'y':
            doc_id = uploader.upload_book(test_book, "test")
            if doc_id:
                print("✅ Prueba de subida exitosa")
            else:
                print("❌ Error en prueba de subida")
        
    except ImportError:
        print("❌ Error: firebase_uploader no está disponible")
        print("💡 Asegúrate de tener instalado firebase-admin:")
        print("   pip install firebase-admin")
    except Exception as e:
        print(f"❌ Error probando conexión: {e}")

def main():
    """Función principal"""
    print("🔥 CONFIGURADOR DE FIREBASE PARA BUSCALIBRE SCRAPER")
    print("="*60)
    
    while True:
        print("\n📋 MENÚ:")
        print("1. Configurar credenciales de Firebase")
        print("2. Probar conexión a Firebase")
        print("3. Mostrar información del proyecto")
        print("4. Salir")
        
        opcion = input("\nSelecciona una opción (1-4): ").strip()
        
        if opcion == "1":
            configurar_firebase()
        elif opcion == "2":
            probar_conexion()
        elif opcion == "3":
            mostrar_info_proyecto()
        elif opcion == "4":
            print("👋 ¡Hasta luego!")
            break
        else:
            print("❌ Opción no válida")

def mostrar_info_proyecto():
    """Mostrar información del proyecto actual"""
    print("\n📊 INFORMACIÓN DEL PROYECTO")
    print("="*35)
    
    try:
        from firebase_config import PROJECT_ID, COLLECTION_NAME
        print(f"📋 Project ID: {PROJECT_ID}")
        print(f"📚 Colección: {COLLECTION_NAME}")
        
        if PROJECT_ID != "tu-project-id-aqui":
            print("✅ Credenciales configuradas")
        else:
            print("⚠️ Credenciales no configuradas")
            
    except ImportError:
        print("❌ Archivo firebase_config.py no encontrado")

if __name__ == "__main__":
    main()