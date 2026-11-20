import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
from datetime import datetime

# Importar configuracion de Firebase
try:
    from firebase_config import FIREBASE_CONFIG, PROJECT_ID, COLLECTION_NAME
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False

class FirebaseUploader:
    def __init__(self):
        """Inicializar conexion a Firebase"""
        self.db = None
        self.initialize_firebase()
    
    def initialize_firebase(self):
        """Configurar credenciales y conexion a Firebase"""
        try:
            # Verificar si Firebase ya esta inicializado
            if not firebase_admin._apps:
                
                # Buscar archivo de credenciales especifico del proyecto store-ea555
                credentials_file = "store-ea555-firebase-adminsdk-4znay-58bf088886.json"
                
                if os.path.exists(credentials_file):
                    cred = credentials.Certificate(credentials_file)
                    print("Usando credenciales: " + credentials_file)
                elif CONFIG_AVAILABLE and FIREBASE_CONFIG.get('project_id') not in ['tu-project-id-aqui', 'NECESITA_CONFIGURARSE']:
                    # Usar configuracion del archivo firebase_config.py si esta completa
                    cred = credentials.Certificate(FIREBASE_CONFIG)
                    print("Usando credenciales de firebase_config.py")
                else:
                    # Opciones alternativas de credenciales
                    print("Configure sus credenciales de Firebase:")
                    print("1. Edite firebase_config.py con sus credenciales reales")
                    print("2. O descargue el archivo JSON de credenciales de Firebase Console")
                    print("3. O configure las variables de entorno de Google Cloud")
                    
                    # Intentar usar archivo JSON de credenciales genérico
                    generic_credentials_file = "firebase-credentials.json"
                    if os.path.exists(generic_credentials_file):
                        cred = credentials.Certificate(generic_credentials_file)
                        print("Usando archivo de credenciales: " + generic_credentials_file)
                    else:
                        # Usar credenciales por defecto del sistema
                        cred = credentials.ApplicationDefault()
                        print("Usando credenciales por defecto del sistema")
                
                firebase_admin.initialize_app(cred)
            
            self.db = firestore.client()
            print("Conexion a Firebase establecida")
            
        except Exception as e:
            print("Error conectando a Firebase: " + str(e))
            print("Pasos para configurar Firebase:")
            print("1. Ve a Firebase Console > Configuracion del proyecto > Cuentas de servicio")
            print("2. Genera una nueva clave privada y descarga el archivo JSON")
            print("3. Guarda el archivo como 'store-ea555-firebase-adminsdk-4znay-58bf088886.json' en esta carpeta")
            print("4. O edite 'firebase_config.py' con tus credenciales")
    
    def upload_book(self, libro_data, search_term):
        """
        Subir un libro individual a Firestore
        
        Args:
            libro_data (dict): Datos del libro extraidos
            search_term (str): Termino de busqueda usado
        
        Returns:
            str: ID del documento creado o None si falla
        """
        if not self.db:
            print("No hay conexion a Firebase")
            return None
        
        try:
            # Preparar datos del libro segun la estructura de Firestore mostrada
            book_document = {
                'contacto': "",  # Campo vacio por defecto
                'disponible': "true",  # Disponible por defecto
                'link': libro_data.get('url_libro', ''),
                'portada': libro_data.get('url_imagen', ''),
                'precio': str(libro_data.get('precio_numerico', 0)),  # Precio como string
                'rating': "4.5",  # Rating por defecto
                'textFromQuery': search_term,
                'titulo': libro_data.get('nombre', ''),
                
                # Campos adicionales que podrias agregar
                'autor': libro_data.get('autor', ''),
                'editorial': libro_data.get('editorial', ''),
                'num_paginas': libro_data.get('num_paginas', ''),
                'precio_original': libro_data.get('precio_original', ''),
                'precio_con_envio': libro_data.get('precio_con_envio', ''),
                'tiempo_entrega': libro_data.get('tiempo_entrega', ''),
                'fecha_agregado': datetime.now(),
                'fuente': 'buscalibre.com.mx'
            }
            
            # Agregar a la coleccion 'books'
            collection_name = COLLECTION_NAME if CONFIG_AVAILABLE else 'books'
            doc_ref = self.db.collection(collection_name).add(book_document)
            doc_id = doc_ref[1].id
            
            print("Libro agregado con ID: " + str(doc_id))
            return doc_id
            
        except Exception as e:
            print("Error subiendo libro: " + str(e))
            return None
    
    def upload_books_from_file(self, archivo_txt, search_term):
        """
        Leer archivo de texto y subir todos los libros a Firebase
        
        Args:
            archivo_txt (str): Ruta al archivo de texto con informacion de libros
            search_term (str): Termino de busqueda usado
        """
        if not os.path.exists(archivo_txt):
            print("No se encontro el archivo: " + archivo_txt)
            return
        
        print(" Leyendo libros desde: " + archivo_txt)
        
        try:
            with open(archivo_txt, 'r', encoding='utf-8') as f:
                contenido = f.read()
            
            # Parsear el contenido para extraer informacion de cada libro
            libros_parseados = self.parse_books_from_text(contenido)
            
            print(" Encontrados " + str(len(libros_parseados)) + " libros para subir")
            
            # Subir cada libro
            libros_subidos = 0
            for libro in libros_parseados:
                doc_id = self.upload_book(libro, search_term)
                if doc_id:
                    libros_subidos += 1
            
            print(" Subida completada: " + str(libros_subidos) + "/" + str(len(libros_parseados)) + " libros")
            
        except Exception as e:
            print("Error procesando archivo: " + str(e))
    
    def parse_books_from_text(self, texto):
        """
        Parsear el texto del archivo para extraer informacion de libros
        
        Args:
            texto (str): Contenido del archivo de texto
            
        Returns:
            list: Lista de diccionarios con informacion de libros
        """
        libros = []
        
        # Dividir por secciones de libros (usando las lineas de separacion)
        secciones = texto.split('='*70)
        
        for seccion in secciones:
            if 'LIBRO #' in seccion:
                libro_data = self.extract_book_info(seccion)
                if libro_data:
                    libros.append(libro_data)
        
        return libros
    
    def extract_book_info(self, seccion_texto):
        """
        Extraer informacion de un libro desde una seccion de texto
        
        Args:
            seccion_texto (str): Texto de una seccion de libro
            
        Returns:
            dict: Informacion del libro extraida
        """
        libro = {}
        
        lineas = seccion_texto.strip().split('\n')
        
        for linea in lineas:
            linea = linea.strip()
            
            if 'Nombre:' in linea:
                libro['nombre'] = linea.replace('Nombre:', '').strip()
            elif 'Autor:' in linea:
                libro['autor'] = linea.replace('Autor:', '').strip()
            elif 'Editorial:' in linea:
                libro['editorial'] = linea.replace('Editorial:', '').strip()
            elif 'Paginas:' in linea:
                libro['num_paginas'] = linea.replace('Paginas:', '').strip()
            elif 'Precio original:' in linea:
                precio_original = linea.replace('Precio original:', '').strip()
                libro['precio_original'] = precio_original
                # Extraer precio numerico para Firebase
                import re
                precio_numerico = re.search(r'[\d,]+\.?\d*', precio_original)
                if precio_numerico:
                    libro['precio_numerico'] = float(precio_numerico.group().replace(',', ''))
            elif 'Precio con envio' in linea:
                libro['precio_con_envio'] = linea.split(':', 1)[1].strip()
            elif 'Tiempo de entrega:' in linea:
                libro['tiempo_entrega'] = linea.replace('Tiempo de entrega:', '').strip()
        
        # Solo retornar si tiene al menos nombre
        if libro.get('nombre'):
            return libro
        return None
    
    def upload_from_scraper_data(self, productos_info, search_term):
        """
        Subir libros directamente desde los datos del scraper
        
        Args:
            productos_info (list): Lista de diccionarios con informacion de productos
            search_term (str): Termino de busqueda usado
        """
        if not productos_info:
            print("No hay datos de productos para subir")
            return
        
        print(" Subiendo " + str(len(productos_info)) + " libros directamente desde el scraper")
        
        libros_subidos = 0
        for producto in productos_info:
            doc_id = self.upload_book(producto, search_term)
            if doc_id:
                libros_subidos += 1
        
        print(" Subida completada: " + str(libros_subidos) + "/" + str(len(productos_info)) + " libros")
    
def main():
    """Funcion principal para probar el uploader"""
    uploader = FirebaseUploader()
    
    # Ejemplo de uso:
    # 1. Desde archivo de texto
    # uploader.upload_books_from_file("book_images_HISTORIA_DE_MEXICO/libros_HISTORIA_DE_MEXICO.txt", "HISTORIA DE MEXICO")
    
    # 2. Desde datos del scraper (integrar en buscalibreUpdating.py)
    # uploader.upload_from_scraper_data(productos_info, search_term)
    
    print("Para usar este script:")
    print("1. Las credenciales de Firebase estn configuradas automticamente")
    print("2. Ejecuta el scraper para generar datos")
    print("3. Usa upload_books_from_file() o upload_from_scraper_data()")

if __name__ == "__main__":
    main()