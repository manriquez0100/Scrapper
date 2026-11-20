"""
Script para completar la configuración de Firebase
Proyecto: store-ea555
"""

import json

def completar_configuracion_firebase():
    """Completar configuración de Firebase con credenciales de cuenta de servicio"""
    
    print("🔥 COMPLETAR CONFIGURACIÓN DE FIREBASE")
    print("="*50)
    print(f"📋 Proyecto ID: store-ea555")
    print(f"🌐 Auth Domain: store-ea555.firebaseapp.com")
    print()
    
    print("ℹ️  INFORMACIÓN IMPORTANTE:")
    print("Las credenciales que proporcionaste son para aplicaciones web (frontend).")
    print("Para usar Firebase desde Python (backend), necesitas credenciales de 'Cuenta de Servicio'.")
    print()
    
    print("📝 Para obtener las credenciales de cuenta de servicio:")
    print("="*55)
    print("1. Ve a Firebase Console: https://console.firebase.google.com")
    print("2. Selecciona tu proyecto: store-ea555")
    print("3. Ve a ⚙️ Configuración del proyecto")
    print("4. Pestaña 'Cuentas de servicio'")
    print("5. Haz clic en 'Generar nueva clave privada'")
    print("6. Descarga el archivo JSON")
    print("7. Usa ese archivo aquí")
    print()
    
    opcion = input("¿Tienes el archivo JSON de cuenta de servicio? (s/n): ").strip().lower()
    
    if opcion == 's':
        print("\n📋 Pega aquí el contenido completo del archivo JSON:")
        print("(Asegúrate de copiar todo desde { hasta })")
        
        try:
            json_content = ""
            print(">>> ", end="")
            while True:
                line = input()
                if line.strip() == "":
                    break
                json_content += line + "\n"
            
            # Parsear JSON
            credentials = json.loads(json_content)
            
            # Validar campos requeridos
            required_fields = ['project_id', 'private_key_id', 'private_key', 'client_email', 'client_id']
            missing_fields = [field for field in required_fields if field not in credentials]
            
            if missing_fields:
                print(f"❌ Faltan campos requeridos: {', '.join(missing_fields)}")
                return
            
            # Verificar que el project_id coincida
            if credentials['project_id'] != 'delabuenamemoriaapp':
                print(f"⚠️ Advertencia: El project_id en el JSON ({credentials['project_id']}) no coincide con el esperado (delabuenamemoriaapp)")
                continuar = input("¿Continuar de todas formas? (s/n): ").strip().lower()
                if continuar != 's':
                    return
            
            # Actualizar firebase_config.py
            config_content = f'''# Configuración de Firebase - Proyecto delabuenamemoriaapp
# Generado automáticamente - NO compartir este archivo

FIREBASE_CONFIG = {json.dumps(credentials, indent=4)}

# Información del proyecto
PROJECT_NUMBER = "789884238107"
PROJECT_ID = "{credentials['project_id']}"

# Nombre de la colección en Firestore
COLLECTION_NAME = "books"
'''
            
            with open('firebase_config.py', 'w', encoding='utf-8') as f:
                f.write(config_content)
            
            print("✅ Configuración completada exitosamente!")
            print(f"📧 Client Email: {credentials['client_email']}")
            print(f"🔑 Client ID: {credentials['client_id']}")
            print()
            print("🔒 IMPORTANTE:")
            print("- El archivo firebase_config.py contiene credenciales sensibles")
            print("- NO lo subas a repositorios públicos")
            print("- Mantén estas credenciales seguras")
            
            # Probar conexión
            probar = input("\n🧪 ¿Probar la conexión a Firebase? (s/n): ").strip().lower()
            if probar == 's':
                probar_conexion_firebase()
                
        except json.JSONDecodeError:
            print("❌ Error: El contenido no es un JSON válido")
        except Exception as e:
            print(f"❌ Error procesando credenciales: {e}")
    
    else:
        print("\n📝 CONFIGURACIÓN MANUAL:")
        print("Si prefieres configurar manualmente, necesitas estos datos del archivo JSON:")
        print()
        manual_config()

def manual_config():
    """Configuración manual paso a paso"""
    print("🔧 CONFIGURACIÓN MANUAL")
    print("="*25)
    
    try:
        private_key_id = input("Private Key ID: ").strip()
        print("\nPrivate Key (incluye -----BEGIN PRIVATE KEY----- y -----END PRIVATE KEY-----)")
        print("Puedes pegar línea por línea, presiona Enter dos veces para terminar:")
        
        private_key_lines = []
        while True:
            line = input()
            if line.strip() == "":
                break
            private_key_lines.append(line)
        
        private_key = "\n".join(private_key_lines)
        
        client_email = input("\nClient Email: ").strip()
        client_id = input("Client ID: ").strip()
        
        if not all([private_key_id, private_key, client_email, client_id]):
            print("❌ Todos los campos son obligatorios")
            return
        
        # Crear configuración
        credentials = {
            "type": "service_account",
            "project_id": "delabuenamemoriaapp",
            "private_key_id": private_key_id,
            "private_key": private_key,
            "client_email": client_email,
            "client_id": client_id,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{client_email.replace('@', '%40')}"
        }
        
        # Guardar configuración
        config_content = f'''# Configuración de Firebase - Proyecto delabuenamemoriaapp
# Generado automáticamente - NO compartir este archivo

FIREBASE_CONFIG = {json.dumps(credentials, indent=4)}

# Información del proyecto
PROJECT_NUMBER = "789884238107"
PROJECT_ID = "delabuenamemoriaapp"

# Nombre de la colección en Firestore
COLLECTION_NAME = "books"
'''
        
        with open('firebase_config.py', 'w', encoding='utf-8') as f:
            f.write(config_content)
        
        print("✅ Configuración guardada exitosamente!")
        
    except Exception as e:
        print(f"❌ Error en configuración manual: {e}")

def probar_conexion_firebase():
    """Probar conexión a Firebase"""
    print("\n🧪 PROBANDO CONEXIÓN A FIREBASE")
    print("="*35)
    
    try:
        # Instalar firebase-admin si no está instalado
        print("📦 Verificando firebase-admin...")
        import subprocess
        import sys
        
        try:
            import firebase_admin
        except ImportError:
            print("📦 Instalando firebase-admin...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "firebase-admin"])
            import firebase_admin
        
        # Probar conexión
        from firebase_uploader import FirebaseUploader
        
        print("🔗 Conectando a Firebase...")
        uploader = FirebaseUploader()
        
        if uploader.db:
            print("✅ ¡Conexión exitosa a Firebase!")
            print(f"📊 Conectado al proyecto: delabuenamemoriaapp")
            print(f"📚 Colección de destino: books")
            
            # Probar subida de datos de prueba
            test_book = {
                'nombre': 'Libro de Prueba - Configuración',
                'autor': 'Sistema de Prueba',
                'precio_numerico': 100,
                'url_libro': 'https://example.com/test',
                'url_imagen': 'https://example.com/test.jpg',
                'editorial': 'Editorial Test',
                'num_paginas': '200'
            }
            
            print("\n🧪 ¿Realizar prueba de subida de un libro de prueba? (s/n): ", end="")
            if input().strip().lower() == 's':
                doc_id = uploader.upload_book(test_book, "configuracion_test")
                if doc_id:
                    print(f"✅ ¡Prueba exitosa! Documento creado con ID: {doc_id}")
                    print("🗑️ Puedes eliminar este documento de prueba desde Firebase Console")
                else:
                    print("❌ Error en la prueba de subida")
        else:
            print("❌ Error: No se pudo establecer conexión con Firebase")
            
    except Exception as e:
        print(f"❌ Error probando conexión: {e}")
        print("\n💡 Verifica que:")
        print("- Las credenciales sean correctas")
        print("- El proyecto exista en Firebase")
        print("- Firestore esté habilitado")
        print("- La cuenta de servicio tenga permisos")

def main():
    """Función principal"""
    print("🔥 CONFIGURADOR FIREBASE - PROYECTO DELABUENAMEMORIAAPP")
    print("="*60)
    print()
    
    completar_configuracion_firebase()

if __name__ == "__main__":
    main()