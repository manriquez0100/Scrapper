import time
import random
import pyautogui
import requests
import os
import re
import time
import random
import pyautogui
import requests
import os
import re
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime, timedelta

# Importar Firebase
import sys
sys.path.append('implemented_firestore')
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    from config import SERVICE_ACCOUNT_KEY_PATH, PROJECT_ID
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    print("⚠️ Firebase no disponible")

# -----------------------------------------------
# CONFIGURACIÓN
# -----------------------------------------------
search_term = "Lir. Bioquímica"
  # Término de búsqueda
NUMERO_PRODUCTOS = 10  # Número de productos a extraer
ganancia_envio = 120  # Ganancia fija por envío para calcular el precio final

DESCARGAR_IMAGENES = True  # Parámetro para activar/desactivar descarga de imágenes
ABRIR_ENLACES = True  # Parámetro para activar/desactivar apertura de enlaces
NAVEGAR_A_DETALLE = True  # True para extraer info adicional navegando a cada libro

# -----------------------------------------------
# FUNCIONES AUXILIARES PARA SIMULAR UN HUMANO
# -----------------------------------------------
CARPETA_IMAGENES = "busquedas/book_images"+"_"+search_term.replace(" ", "_")  # Carpeta donde guardar las imágenes


def initialize_firebase():
    """Inicializar Firebase Admin SDK"""
    if not FIREBASE_AVAILABLE:
        return None
    
    try:
        if not firebase_admin._apps:
            # Usar el archivo de credenciales desde implemented_firestore
            cred_path = os.path.join('implemented_firestore', SERVICE_ACCOUNT_KEY_PATH)
            if os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                print("🔥 Firebase inicializado correctamente")
            else:
                print(f"❌ No se encontró archivo de credenciales: {cred_path}")
                return None
        
        db = firestore.client()
        return db
    except Exception as e:
        print(f"❌ Error inicializando Firebase: {e}")
        return None

def insert_book_to_firebase(db, libro_info):
    """Insertar libro individual en Firebase Firestore"""
    if not db or not FIREBASE_AVAILABLE:
        return None
    
    try:
        # Preparar datos para Firebase según la estructura existente
        book_data = {
            'contacto': '',
            'disponible': 'true',
            'link': libro_info.get('url_libro', ''),
            'portada': libro_info.get('url_imagen', ''),
            'precio': str(libro_info.get('precio_con_envio', '').replace('$', '').replace(',', '').strip()),
            'rating': '4.5',
            'textFromQuery': search_term,
            'titulo': libro_info.get('nombre', ''),
            'autor': libro_info.get('autor', ''),
            'editorial': libro_info.get('editorial', ''),
            'num_paginas': libro_info.get('num_paginas', ''),
            'tiempo_entrega': libro_info.get('tiempo_entrega', ''),
            'precio_original': libro_info.get('precio_original', ''),
            'fecha_agregado': datetime.now(),
            'fuente': 'buscalibre.com.mx'
        }
        
        # Agregar a la colección 'books'
        doc_ref = db.collection('books').add(book_data)
        doc_id = doc_ref[1].id
        
        print(f"🔥 Libro insertado en Firebase con ID: {doc_id}")
        print(f"   portada: {libro_info.get('url_imagen', '')}")
        return doc_id
        
    except Exception as e:
        print(f"❌ Error insertando en Firebase: {e}")
        return None

def calcular_tiempo_entrega():
    """Calcula el tiempo de entrega de 3 a 4 semanas a partir de la fecha actual."""
    fecha_actual = datetime.now()
    fecha_minima = fecha_actual + timedelta(weeks=3)
    fecha_maxima = fecha_actual + timedelta(weeks=4)
    
    # Formatear las fechas en español
    meses = {
        1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
        5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
        9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
    }
    
    fecha_min_str = f"{fecha_minima.day} de {meses[fecha_minima.month]} de {fecha_minima.year}"
    fecha_max_str = f"{fecha_maxima.day} de {meses[fecha_maxima.month]} de {fecha_maxima.year}"
    
    return f"Entre el {fecha_min_str} y el {fecha_max_str}"

def extraer_url_libro(producto):
    """
    Extrae la URL del libro desde el elemento producto.
    
    Args:
        producto: Elemento WebDriver del producto
    
    Returns:
        str: URL del libro o None si no se encuentra
    """
    try:
        # Buscar el enlace principal del producto (varios selectores posibles)
        selectores = [
            "a[href*='/libro-']",
            "h3.nombre a",
            ".imagen a",
            "a[href*='/product']",
            ".box-producto a"
        ]
        
        for selector in selectores:
            try:
                enlace = producto.find_element(By.CSS_SELECTOR, selector)
                url = enlace.get_attribute('href')
                
                # Verificar que la URL sea válida
                if url and ('libro-' in url or 'product' in url):
                    return url
            except NoSuchElementException:
                continue
                
        return None
        
    except Exception as e:
        print(f"⚠️ Error extrayendo URL: {e}")
        return None

def abrir_libro_en_nueva_pestana(driver, url_libro, numero_producto):
    """
    Abre un libro en una nueva pestaña del navegador.
    
    Args:
        driver: Instancia del WebDriver
        url_libro (str): URL del libro a abrir
        numero_producto (int): Número del producto para logging
    
    Returns:
        bool: True si se abrió exitosamente, False en caso contrario
    """
    if not ABRIR_ENLACES or not url_libro:
        return False
        
    try:
        # Abrir nueva pestaña usando JavaScript
        driver.execute_script(f"window.open('{url_libro}', '_blank');")
        #print(f"🌐 Libro #{numero_producto} abierto en nueva pestaña")
        
        # Pausa para evitar sobrecarga
        human_pause(0.5, 1)
        
        return True
        
    except Exception as e:
        print(f"❌ Error al abrir libro #{numero_producto}: {e}")
        return False

def extraer_detalle_libro(driver, url_libro, numero_producto):
    """
    Navega a la página de detalle del libro y extrae toda la información incluyendo nombre, precio, imagen de alta calidad, autor y descripción.
    
    Args:
        driver: Instancia del WebDriver
        url_libro (str): URL del libro
        numero_producto (int): Número del producto
    
    Returns:
        dict: Información completa del libro extraída de la página individual
    """
    if not url_libro:
        return None
        
    try:
        #print(f"📖 Extrayendo información completa del libro #{numero_producto}...")
        
        # Guardar la ventana original
        ventana_original = driver.current_window_handle
        
        # Abrir en nueva pestaña
        driver.execute_script(f"window.open('{url_libro}', '_blank');")
        
        # Cambiar a la nueva pestaña
        driver.switch_to.window(driver.window_handles[-1])
        
        # Esperar que cargue la página
        human_pause(2, 4)
        
        # Extraer información completa del detalle
        info_completa = {}
        
        # EXTRAER NOMBRE DEL LIBRO
        try:
            selectores_nombre = [
                "p.tituloProducto",                  # Selector específico para buscalibre
                ".tituloProducto",                   # Clase tituloProducto
                "p[class*='tituloProducto']",        # P con clase que contenga tituloProducto
                "[class*='tituloProducto']",         # Cualquier elemento con tituloProducto
                "h1.titulo-libro",
                "h1[class*='titulo']",
                ".nombre-producto h1",
                ".product-title h1",
                "h1:not([class*='opinion']):not([class*='review']):not([class*='comentario'])",
                ".libro-info h1",
                ".producto-titulo",
                "h1",
                ".titulo:not([class*='opinion']):not([class*='review'])", 
                ".title:not([class*='opinion']):not([class*='review'])",
                ".product-title",
                ".libro-titulo",
                "[class*='titulo']:not([class*='opinion']):not([class*='review'])",
                "[class*='title']:not([class*='opinion']):not([class*='review'])",
                ".nombre-libro"
            ]
            
            for selector in selectores_nombre:
                try:
                    nombre_element = driver.find_element(By.CSS_SELECTOR, selector)
                    nombre = nombre_element.text.strip()
                    
                    # Validaciones adicionales para filtrar contenido no deseado
                    if (nombre and len(nombre) > 3 and 
                        not any(palabra in nombre.lower() for palabra in [
                            'opinion', 'review', 'comentario', 'reseña', 'crítica', 
                            'valoración', 'calificación', 'rating', 'puntuación'
                        ]) and
                        not nombre.lower().startswith('opiniones') and
                        not nombre.lower().startswith('reseña') and
                        len(nombre) < 200):  # Evitar textos muy largos
                        
                        info_completa['nombre'] = nombre
                        ##print(f"📚 Nombre extraído con {selector}: {nombre[:80]}...")
                        break
                except:
                    continue
                    
            if 'nombre' not in info_completa:
                info_completa['nombre'] = f"Libro #{numero_producto}"
                print(f"⚠️ No se pudo extraer nombre, usando valor por defecto")
        except Exception as e:
            info_completa['nombre'] = f"Libro #{numero_producto}"
            print(f"⚠️ Error extrayendo nombre: {e}")
        
        # EXTRAER PRECIO ORIGINAL
        try:
            selectores_precio = [
                ".precio",
                ".price", 
                ".product-price",
                ".costo",
                "[class*='precio']",
                "[class*='price']",
                ".valor",
                ".amount",
                ".box-precio-v2 strong"
            ]
            
            for selector in selectores_precio:
                try:
                    precio_element = driver.find_element(By.CSS_SELECTOR, selector)
                    precio_texto = precio_element.text.strip()
                    # Validar que contenga números y símbolos de moneda
                    if precio_texto and ('$' in precio_texto or '€' in precio_texto or any(c.isdigit() for c in precio_texto)):
                        info_completa['precio_original'] = precio_texto
                        ##print(f"💰 Precio extraído: {precio_texto}")
                        
                        # Calcular precio con envío
                        precio_numerico = re.search(r'[\d,]+\.?\d*', precio_texto)
                        if precio_numerico:
                            precio_valor = float(precio_numerico.group().replace(',', ''))
                            precio_actualizado = precio_valor + ganancia_envio
                            
                            # Aplicar nueva estrategia de precios basada en la unidad
                            unidad = int(precio_actualizado) % 10
                            
                            if unidad >= 1 and unidad <= 5:
                                # Unidades 1-5: bajar a la decena anterior terminada en 9
                                # Ej: 201,202,203,204,205 -> 199
                                precio_actualizado = int(precio_actualizado // 10) * 10 - 1
                            elif unidad == 6 or unidad == 7:
                                # Unidades 6,7: subir a 9
                                # Ej: 206,207 -> 209
                                precio_actualizado = int(precio_actualizado // 10) * 10 + 9
                            elif unidad == 8:
                                # Unidad 8: subir a 9
                                # Ej: 208 -> 209
                                precio_actualizado = int(precio_actualizado // 10) * 10 + 9
                            elif unidad == 0:
                                # Unidad 0: bajar a 9 de la decena anterior
                                # Ej: 200 -> 199
                                precio_actualizado = precio_actualizado - 1
                            # Si ya termina en 9, no cambiar
                            
                            info_completa['precio_con_envio'] = f"$ {precio_actualizado:,.0f}"
                            ##print(f"📦 Precio con envío (+$100): $ {precio_actualizado:,.2f}")
                        ##else:
                        ##    info_completa['precio_con_envio'] = precio_texto
                        break
                except:
                    continue
                    
            ##if 'precio_original' not in info_completa:
            ##    info_completa['precio_original'] = "Precio no disponible"
            ##    info_completa['precio_con_envio'] = "Precio no disponible"
            ##    print(f"⚠️ No se pudo extraer precio")
        except Exception as e:
            info_completa['precio_original'] = "Precio no disponible"
            info_completa['precio_con_envio'] = "Precio no disponible"
            print(f"⚠️ Error extrayendo precio: {e}")
        
        # EXTRAER IMAGEN DE ALTA CALIDAD
        try:
            selectores_imagen = [
                ".imagen-producto img",
                ".product-image img", 
                ".libro-imagen img",
                ".cover img",
                ".portada img",
                "img[src*='cover']",
                "img[src*='libro']",
                ".imagen-grande img",
                "img[alt*='portada']"
            ]
            
            url_imagen_hq = None
            for selector in selectores_imagen:
                try:
                    img_element = driver.find_element(By.CSS_SELECTOR, selector)
                    url_imagen_hq = img_element.get_attribute('src') or img_element.get_attribute('data-src')
                    
                    # Verificar que sea una URL válida y de buena calidad
                    if url_imagen_hq and ('jpg' in url_imagen_hq.lower() or 'png' in url_imagen_hq.lower() or 'jpeg' in url_imagen_hq.lower()):
                        # Buscar la versión de mayor resolución
                        if any(size in url_imagen_hq for size in ['large', 'big', 'full', 'original', '_l', '_xl']):
                            info_completa['url_imagen_hq'] = url_imagen_hq
                            print(f"🖼️ Imagen de alta calidad encontrada: {url_imagen_hq[:60]}...")
                            break
                        elif not info_completa.get('url_imagen_hq'):
                            info_completa['url_imagen_hq'] = url_imagen_hq
                except:
                    continue
                    
            if not info_completa.get('url_imagen_hq'):
                print(f"⚠️ No se encontró imagen de alta calidad para libro #{numero_producto}")
        except Exception as e:
            print(f"⚠️ Error extrayendo imagen: {e}")
        
        # EXTRAER AUTOR, EDITORIAL Y NÚMERO DE PÁGINAS
        try:
            # Buscar en la sección de metadatos/ficha del libro
            selectores_ficha = [
                ".ficha .row",
                ".metadata .row", 
                ".book-details .row",
                ".product-details .row",
                "[class*='ficha'] .row",
                "[class*='metadata'] .row"
            ]
            
            autor = "No disponible"
            editorial = "No disponible"
            num_paginas = "No disponible"
            
            for selector_ficha in selectores_ficha:
                try:
                    filas = driver.find_elements(By.CSS_SELECTOR, selector_ficha)
                    
                    for fila in filas:
                        try:
                            texto_fila = fila.text.lower()
                            
                            # Buscar autor
                            if any(palabra in texto_fila for palabra in ['autor', 'author', 'writer', 'escritor']):
                                try:
                                    # Buscar el valor en la segunda columna de la fila
                                    valor_elementos = fila.find_elements(By.CSS_SELECTOR, ".col-xs-7 .box, .col-md-7 .box, .value, .data")
                                    if valor_elementos:
                                        # Extraer texto limpio del autor (sin iconos ni enlaces)
                                        valor_autor_element = valor_elementos[0]
                                        # Buscar el enlace del autor primero
                                        link_autor = valor_autor_element.find_elements(By.CSS_SELECTOR, "a.color-primary, a[href*='autor'], a[href*='author']")
                                        if link_autor:
                                            valor_autor = link_autor[0].text.strip()
                                        else:
                                            valor_autor = valor_autor_element.text.strip()
                                        
                                        if valor_autor and len(valor_autor) > 1 and valor_autor.lower() != "autor":
                                            autor = valor_autor
                                            #print(f"👤 Autor extraído: {autor}")
                                except:
                                    pass
                            
                            # Buscar editorial
                            if any(palabra in texto_fila for palabra in ['editorial', 'editor', 'publisher']):
                                try:
                                    # Buscar el valor en la segunda columna de la fila
                                    valor_elementos = fila.find_elements(By.CSS_SELECTOR, ".col-xs-7 .box, .col-md-7 .box, .value, .data")
                                    if valor_elementos:
                                        valor_editorial = valor_elementos[0].text.strip()
                                        if valor_editorial and len(valor_editorial) > 1 and valor_editorial != "Editorial":
                                            editorial = valor_editorial
                                            #print(f"🏢 Editorial extraída: {editorial}")
                                except:
                                    pass
                            
                            # Buscar número de páginas
                            if any(palabra in texto_fila for palabra in ['páginas', 'paginas', 'pages', 'número de páginas', 'num páginas']):
                                try:
                                    # Buscar el valor en la segunda columna de la fila
                                    valor_elementos = fila.find_elements(By.CSS_SELECTOR, ".col-xs-7 .box, .col-md-7 .box, .value, .data")
                                    if valor_elementos:
                                        valor_paginas = valor_elementos[0].text.strip()
                                        # Validar que contenga números
                                        if valor_paginas and any(c.isdigit() for c in valor_paginas):
                                            num_paginas = valor_paginas
                                            #print(f"📄 Número de páginas extraído: {num_paginas}")
                                except:
                                    pass
                                    
                        except:
                            continue
                            
                    # Si ya encontramos todos los datos, salir del bucle
                    if autor != "No disponible" and editorial != "No disponible" and num_paginas != "No disponible":
                        break
                        
                except:
                    continue
            
            info_completa['autor'] = autor
            info_completa['editorial'] = editorial
            info_completa['num_paginas'] = num_paginas
            
        except Exception as e:
            info_completa['autor'] = "No disponible"
            info_completa['editorial'] = "No disponible"
            info_completa['num_paginas'] = "No disponible"
            print(f"⚠️ Error extrayendo autor/editorial/páginas: {e}")
        
        # EXTRAER DESCRIPCIÓN
        try:
            selectores_desc = [".descripcion", ".resumen", "[class*='descripcion']", "[class*='resumen']", ".synopsis", ".summary"]
            for selector in selectores_desc:
                try:
                    descripcion = driver.find_element(By.CSS_SELECTOR, selector).text.strip()
                    if descripcion:
                        info_completa['descripcion'] = descripcion[:200] + "..." if len(descripcion) > 200 else descripcion
                        ##print(f"📝 Descripción extraída: {descripcion[:50]}...")
                        break
                except:
                    continue
            if 'descripcion' not in info_completa:
                info_completa['descripcion'] = "No disponible"
        except:
            info_completa['descripcion'] = "No disponible"
        
        # EXTRAER INFORMACIÓN DE ENVÍO REAL DESDE tiempoEnvio
        try:
            selectores_envio = [
                ".tiempoEnvio",
                "[class*='tiempoEnvio']",
                "[id*='tiempoEnvio']",
                ".tiempo-envio",
                ".shipping-time",
                ".delivery-time",
                ".envio-tiempo",
                "[class*='tiempo-envio']",
                "[class*='shipping']",
                "[class*='delivery']"
            ]
            
            tiempo_envio_real = None
            for selector in selectores_envio:
                try:
                    envio_element = driver.find_element(By.CSS_SELECTOR, selector)
                    tiempo_envio_real = envio_element.text.strip()
                    if tiempo_envio_real and len(tiempo_envio_real) > 5:  # Validar que tenga contenido útil
                        info_completa['tiempo_entrega'] = tiempo_envio_real
                        break
                except:
                    continue
                    
            if not tiempo_envio_real:
                # Fallback: usar el cálculo original si no se encuentra tiempoEnvio
                info_completa['tiempo_entrega'] = calcular_tiempo_entrega()
                print(f"⚠️ No se encontró tiempoEnvio, usando cálculo por defecto")
        except Exception as e:
            info_completa['tiempo_entrega'] = calcular_tiempo_entrega()
            print(f"⚠️ Error extrayendo tiempo de envío: {e}, usando cálculo por defecto")
        
        ##print(f"✅ Información completa extraída para libro #{numero_producto}")
        
        # Solo cerrar si no es la única pestaña
        if len(driver.window_handles) > 1:
            driver.close()
            # Volver a la ventana original
            driver.switch_to.window(ventana_original)
        
        return info_completa
        
    except Exception as e:
        print(f"❌ Error al extraer información completa del libro #{numero_producto}: {e}")
        
        # Asegurarse de volver a la ventana original
        try:
            if len(driver.window_handles) > 1:
                driver.close()
            driver.switch_to.window(ventana_original)
        except:
            pass
        
        return None

def crear_carpeta_imagenes():
    """Crea la carpeta para guardar las imágenes si no existe."""
    if not os.path.exists(CARPETA_IMAGENES):
        os.makedirs(CARPETA_IMAGENES)
        print(f"📁 Carpeta '{CARPETA_IMAGENES}' creada")
    return CARPETA_IMAGENES

def limpiar_nombre_archivo(nombre):
    """Limpia el nombre del archivo para que sea válido en el sistema de archivos."""
    # Remover caracteres especiales y limitar longitud
    nombre_limpio = re.sub(r'[<>:"/\\|?*]', '', nombre)
    nombre_limpio = re.sub(r'\s+', '_', nombre_limpio.strip())
    return nombre_limpio[:50]  # Limitar a 50 caracteres

def descargar_imagen(url_imagen, nombre_libro, numero_producto):
    """
    Descarga una imagen de libro desde una URL.
    
    Args:
        url_imagen (str): URL de la imagen a descargar
        nombre_libro (str): Nombre del libro para el archivo
        numero_producto (int): Número del producto
    
    Returns:
        str: Ruta del archivo descargado o None si falló
    """
    if not DESCARGAR_IMAGENES or not url_imagen:
        return None
    
    try:
        # Crear carpeta si no existe
        carpeta = crear_carpeta_imagenes()
        
        # Limpiar nombre del archivo
        nombre_limpio = limpiar_nombre_archivo(nombre_libro)
        
        # Obtener extensión de la imagen
        parsed_url = urlparse(url_imagen)
        extension = os.path.splitext(parsed_url.path)[1]
        if not extension:
            extension = '.jpg'  # Extensión por defecto
        
        # Crear nombre del archivo
        nombre_archivo = f"libro_{numero_producto:02d}_{nombre_limpio}{extension}"
        ruta_archivo = os.path.join(carpeta, nombre_archivo)
        
        # Configurar headers para parecer un navegador real
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'es-MX,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # Descargar la imagen
        ##print(f"📸 Descargando imagen del libro #{numero_producto}...")
        response = requests.get(url_imagen, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Guardar la imagen
        with open(ruta_archivo, 'wb') as f:
            f.write(response.content)
        
        #print(f"✅ Imagen guardada: {ruta_archivo}")
        return ruta_archivo
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error de red al descargar imagen #{numero_producto}: {e}")
        return None
    except Exception as e:
        print(f"❌ Error al guardar imagen #{numero_producto}: {e}")
        return None

def human_pause(a=0.1, b=0.4):
    """Pausa aleatoria entre acciones."""
    time.sleep(random.uniform(a, b))

def human_type(text):
    """Escribe un texto carácter por carácter como un humano."""
    for char in text:
        pyautogui.write(char)
        human_pause(0.05, 0.18)  # simula velocidad de tecleo

def human_mouse_move(x, y):
    """Mueve el mouse en una trayectoria suave y no robótica."""
    pyautogui.moveTo(
        x,
        y,
        duration=random.uniform(0.4, 0.9),
        tween=pyautogui.easeInOutQuad
    )

# -----------------------------------------------
# CONFIGURACIÓN DEL NAVEGADOR
# -----------------------------------------------

def setup_chrome_driver():
    """Configura y retorna una instancia de Chrome WebDriver con opciones anti-detección."""
    chrome_options = Options()
    
    # Opciones para parecer un navegador real
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # User agent realista
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # Tamaño de ventana
    chrome_options.add_argument('--start-maximized')
    
    # Configurar el servicio
    service = Service(ChromeDriverManager().install())
    
    # Crear driver
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # Eliminar la propiedad webdriver para evitar detección
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

# -----------------------------------------------
# CONFIGURACIÓN
# -----------------------------------------------

# Parámetro: Número de productos a extraer


# -----------------------------------------------
# INICIO DEL AUTOMATION
# -----------------------------------------------

print("🚀 Iniciando navegador Chrome...")
driver = setup_chrome_driver()

# Inicializar Firebase
print("🔥 Inicializando conexión a Firebase...")
db_firebase = initialize_firebase()
if db_firebase:
    print("✅ Firebase listo para insertar datos")
else:
    print("⚠️ Firebase no disponible - solo se guardará en archivo")

try:
    # Navegar directamente a Buscalibre México
    url = "https://www.buscalibre.com.mx/"
    print(f"📍 Navegando a {url}")
    driver.get(url)
    
    # Pausa para que cargue la página
    human_pause(2, 4)
    print("✅ Página cargada exitosamente")


    # -----------------------------------------------
    # LLEGAR AL BUSCADOR DE BUSCALIBRE
    # -----------------------------------------------
    
    print("🔍 Buscando el campo de búsqueda...")
    
    # Usar WebDriverWait para esperar que el elemento esté presente
    wait = WebDriverWait(driver, 15)
    
    try:
        # Intentar encontrar el campo de búsqueda con varios selectores posibles
        search_box = None
        selectors = [
            (By.ID, "inputSearch"),
            (By.NAME, "q"),
            (By.CSS_SELECTOR, "input[type='search']"),
            (By.CSS_SELECTOR, "input[placeholder*='Buscar']"),
            (By.XPATH, "//input[contains(@class, 'search')]")
        ]
        
        for by, selector in selectors:
            try:
                search_box = wait.until(EC.presence_of_element_located((by, selector)))
                print(f"✅ Campo de búsqueda encontrado usando {by}: {selector}")
                break
            except TimeoutException:
                continue
        
        if search_box is None:
            raise Exception("❌ No se pudo encontrar el campo de búsqueda con ningún selector")
        
        # Scroll suave hacia el elemento
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", search_box)
        human_pause(1, 2)
        
        # Hacer clic en el campo de búsqueda
        search_box.click()
        human_pause(0.5, 1)
        
        print("✅ Campo de búsqueda listo para escribir")
        
        # Escribir texto de forma muy humana
        
        print(f"⌨️  Escribiendo '{search_term}' de forma humana...")
        search_text = search_term
        
        for char in search_text:
            search_box.send_keys(char)
            # Pausas variables para simular velocidad de tecleo humano
            # Algunas teclas más rápidas, otras más lentas
            if char == ' ':
                human_pause(0.15, 0.30)  # Espacio ligeramente más largo
            elif char in 'aeiou':
                human_pause(0.08, 0.15)  # Vocales más rápidas
            else:
                human_pause(0.12, 0.22)  # Consonantes velocidad normal
            
            # Ocasionalmente una pausa más larga (como si estuviera pensando)
            if random.random() < 0.15:
                human_pause(0.3, 0.6)
        
        print("✅ Texto escrito exitosamente en el campo de búsqueda")
        
        # Pausa humana antes de dar clic (como si estuviera revisando lo que escribió)
        human_pause(0.8, 1.5)
        
        # Buscar el botón de búsqueda por su ID específico
        print("� Buscando el botón 'Buscar'...")
        
        try:
            search_button = wait.until(EC.element_to_be_clickable((By.ID, "botonBuscarHeader")))
            print("✅ Botón 'Buscar' encontrado")
            
            # Scroll suave hacia el botón (si es necesario)
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", search_button)
            human_pause(0.5, 0.8)
            
            # Hacer clic en el botón
            search_button.click()
            print("✅ Clic en botón 'Buscar' realizado exitosamente")
            
            # Esperar a que carguen los resultados
            print("⏳ Esperando que carguen los resultados...")
            human_pause(3, 5)
            print("✅ Búsqueda completada")
            
            # EXTRAER INFORMACIÓN COMPLETA DESDE PÁGINAS INDIVIDUALES
            #print(f"\n📚 Extrayendo información completa desde páginas individuales de los primeros {NUMERO_PRODUCTOS} productos...")
            #print(f"🎯 Fuente de datos: Páginas individuales de cada libro (mayor precisión)")
            
            if DESCARGAR_IMAGENES:
                crear_carpeta_imagenes()
                print(f"📁 Las imágenes se guardarán en la carpeta: {CARPETA_IMAGENES}")
                print(f"🖼️ Imágenes de alta calidad desde páginas individuales")
                
                # Limpiar archivo de texto anterior (si existe)
                try:
                    archivo_txt = os.path.join(CARPETA_IMAGENES, f"libros_{search_term.replace(' ', '_')}.txt")
                    if os.path.exists(archivo_txt):
                        os.remove(archivo_txt)
                    print(f"📄 La información se guardará en: libros_{search_term.replace(' ', '_')}.txt")
                except Exception as e:
                    print(f"⚠️ Error preparando archivo de texto: {e}")
            
            try:
                # Esperar a que se carguen los productos
                productos = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".box-producto")))
                
                # Limitar al número configurado
                productos_a_extraer = productos[:NUMERO_PRODUCTOS]
                
                print(f"\n✅ Se encontraron {len(productos)} productos. Extrayendo {len(productos_a_extraer)}...\n")
                
                # Calcular tiempo de entrega (una sola vez para todos)
                tiempo_entrega = calcular_tiempo_entrega()
                
                # Lista para almacenar información de todos los productos
                productos_info = []
                
                # Iterar sobre cada producto
                for i, producto in enumerate(productos_a_extraer, 1):
                    try:
                        # Extraer URL del libro PRIMERO
                        url_libro = extraer_url_libro(producto)
                        
                        if not url_libro:
                            print(f"❌ No se pudo extraer URL para producto #{i}, saltando...")
                            continue
                        
                        ##print(f"🔗 URL encontrada para libro #{i}: {url_libro}")
                        
                        # Extraer TODA la información desde la página individual
                        info_completa = extraer_detalle_libro(driver, url_libro, i)
                        
                        if not info_completa:
                            print(f"❌ No se pudo extraer información para libro #{i}, saltando...")
                            continue
                        
                        # Usar información extraída de la página individual
                        nombre = info_completa.get('nombre', f'Libro #{i}')
                        precio_texto = info_completa.get('precio_original', 'Precio no disponible')
                        precio_final = info_completa.get('precio_con_envio', 'Precio no disponible')
                        tiempo_entrega = info_completa.get('tiempo_entrega', calcular_tiempo_entrega())
                        url_imagen_final = info_completa.get('url_imagen_hq')
                        
                        # Descargar la imagen si está disponible
                        archivo_imagen = None
                        if url_imagen_final and DESCARGAR_IMAGENES:
                            archivo_imagen = descargar_imagen(url_imagen_final, nombre, i)
                        
                        # Abrir enlace del libro (opcional)
                        enlace_abierto = False
                        if url_libro and ABRIR_ENLACES:
                            enlace_abierto = abrir_libro_en_nueva_pestana(driver, url_libro, i)
                        
                        # Almacenar información del producto
                        info_producto = {
                            'numero': i,
                            'nombre': nombre,
                            'precio_original': precio_texto,
                            'precio_con_envio': precio_final,
                            'url_imagen': url_imagen_final,
                            'archivo_imagen': archivo_imagen,
                            'url_libro': url_libro,
                            'enlace_abierto': enlace_abierto,
                            'tiempo_entrega': tiempo_entrega,
                            'autor': info_completa.get('autor', 'No disponible'),
                            'descripcion': info_completa.get('descripcion', 'No disponible')
                        }
                        productos_info.append(info_producto)
                        
                        # Preparar información adicional opcional
                        info_adicional = ""
                        if info_completa.get('autor') != "No disponible":
                            info_adicional += f"👤 Autor: {info_completa['autor']}\n"
                        if info_completa.get('editorial') != "No disponible":
                            info_adicional += f"🏢 Editorial: {info_completa['editorial']}\n"
                        if info_completa.get('num_paginas') != "No disponible":
                            info_adicional += f"📄 Páginas: {info_completa['num_paginas']}\n"
                        
                        # INSERTAR EN FIREBASE
                        if db_firebase:
                            libro_firebase = {
                                'nombre': nombre,
                                'autor': info_completa.get('autor', 'No disponible'),
                                'editorial': info_completa.get('editorial', 'No disponible'),
                                'num_paginas': info_completa.get('num_paginas', 'No disponible'),
                                'precio_con_envio': precio_final,
                                'precio_original': precio_texto,
                                'tiempo_entrega': tiempo_entrega,
                                'url_libro': url_libro,
                                'url_imagen': url_imagen_final
                            }
                            insert_book_to_firebase(db_firebase, libro_firebase)
                        
                        # Mostrar información del producto

                        ##Utiliza el Nombre, Autor, editorial, paginas, precio total con envío y tiempo de entrega para insertarla en firebase usando el método de inserció de la clase main.py en la carpeta implemented_firestore.

                        info_texto = f"""{"="*70}
                        📖 LIBRO #{i}
                        {"="*70}
                        📕 Nombre: {nombre}
                        {info_adicional}
                        💵 Precio total con envío: {precio_final}
                        🚚 Tiempo de entrega: 2 a 3 semanas a partir de la fecha de compra.
                        {"="*70}

                        """
                        
#📖 LIBRO #{i}
#{"="*70}
#📕 Nombre: {nombre}
#{info_adicional}💰 Precio original: {precio_texto}
#💵 Precio con envío (+$100): {precio_final}
#🚚 Tiempo de entrega: 2 a 3 semanas a partir de la fecha de compra.
#{"="*70}

#"""                        
                        
                        # Mostrar en pantalla
                        print(info_texto.strip())
                        
                        # Guardar en archivo de texto
                        try:
                            carpeta = crear_carpeta_imagenes()  # Usar la misma carpeta que las imágenes
                            archivo_txt = os.path.join(carpeta, f"libros_{search_term.replace(' ', '_')}.txt")
                            
                            # Escribir o agregar al archivo
                            with open(archivo_txt, 'a', encoding='utf-8') as f:
                                f.write(info_texto)
                            
                            if i == 1:  # Solo mostrar el mensaje la primera vez
                                print(f"📄 Guardando información en: {archivo_txt}")
                                
                        except Exception as e:
                            print(f"⚠️ Error guardando archivo de texto: {e}")
                        
                        # Pausa entre productos
                        human_pause(1, 2)
                        
                    except Exception as e:
                        print(f"⚠️ Error extrayendo producto #{i}: {e}\n")
                        continue
                
              
                
            except Exception as e:
                print(f"❌ Error al extraer productos: {e}")
            
        except TimeoutException:
            print("❌ No se pudo encontrar el botón 'Buscar' con id 'botonBuscarHeader'")
        except Exception as e:
            print(f"⚠️  Error al hacer clic en el botón: {e}")
        
        print("\n✅ Precio y disponibilidad puede variar con los días.")

        with open(archivo_txt, 'a', encoding='utf-8') as f:
            f.write("\n✅ Precio y disponibilidad puede variar con los días.")
                            
        print("💡 El navegador permanecerá abierto para que veas los resultados.")
        print("   Puedes interactuar manualmente con la página.")
        
        # Mantener el navegador abierto
        print("\n⏳ Presiona Ctrl+C en la terminal para cerrar el navegador...")
        while True:
            time.sleep(1)
            
    except TimeoutException:
        print("❌ Timeout: La página tardó demasiado en cargar el campo de búsqueda")
        print("💡 Intenta verificar tu conexión a internet o si buscalibre.com.mx está disponible")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
    
except KeyboardInterrupt:
    print("\n⚠️  Interrupción detectada por el usuario")
except Exception as e:
    print(f"❌ Error al iniciar el navegador: {e}")
finally:
    print("🔒 Cerrando navegador...")
    try:
        # Cerrar pestañas adicionales si se abrieron
        if ABRIR_ENLACES and len(driver.window_handles) > 1:
            ventana_principal = driver.window_handles[0]
            for handle in driver.window_handles[1:]:
                driver.switch_to.window(handle)
                driver.close()
            driver.switch_to.window(ventana_principal)
        
        driver.quit()
    except:
        pass
    print("✅ Navegador cerrado")
