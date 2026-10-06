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

# Importar Firebase uploader
try:
    from firebase_uploader import FirebaseUploader
    FIREBASE_AVAILABLE = True
    print("🔥 Firebase uploader disponible")
except ImportError:
    FIREBASE_AVAILABLE = False
    print("⚠️  Firebase uploader no disponible")

# -----------------------------------------------
# CONFIGURACIÓN
# -----------------------------------------------
search_term = "HISTORIA DE MEXICO"  # Término de búsqueda
NUMERO_PRODUCTOS = 5  # Número de productos a extraer
ganancia_envio = 100  # Ganancia fija por envío para calcular el precio final

DESCARGAR_IMAGENES = True  # Parámetro para activar/desactivar descarga de imágenes
ABRIR_ENLACES = True  # Parámetro para activar/desactivar apertura de enlaces
NAVEGAR_A_DETALLE = True  # True para extraer info adicional navegando a cada libro
SUBIR_A_FIREBASE = True  # Nuevo: Subir datos a Firebase

# -----------------------------------------------
# FUNCIONES AUXILIARES PARA SIMULAR UN HUMANO
# -----------------------------------------------
CARPETA_IMAGENES = "busquedas/book_images"+"_"+search_term.replace(" ", "_")  # Carpeta donde guardar las imágenes

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
    
    fecha_min_str = f"{fecha_minima.day} de {meses[fecha_minima.month]}"
    fecha_max_str = f"{fecha_maxima.day} de {meses[fecha_maxima.month]}"
    
    return f"Entre el {fecha_min_str} y el {fecha_max_str}"

def pausa_humana(min_tiempo=0.5, max_tiempo=2.0):
    """Simula una pausa humana aleatoria"""
    tiempo = random.uniform(min_tiempo, max_tiempo)
    time.sleep(tiempo)

def escribir_como_humano(elemento, texto):
    """Simula escritura humana con velocidad variable"""
    elemento.clear()
    pausa_humana(0.2, 0.5)
    for char in texto:
        elemento.send_keys(char)
        time.sleep(random.uniform(0.05, 0.15))

def setup_chrome_driver():
    """Configurar Chrome driver con opciones optimizadas"""
    chrome_options = Options()
    
    # Opciones para parecer más humano
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # User agent más realista
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # Ejecutar script para ocultar que es un navegador automatizado
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

def crear_carpeta_imagenes(carpeta):
    """Crear carpeta para guardar imágenes si no existe"""
    if not os.path.exists(carpeta):
        os.makedirs(carpeta)
        print(f"📁 Carpeta creada: {carpeta}")

def descargar_imagen(url_imagen, nombre_archivo, carpeta):
    """Descargar imagen desde URL"""
    try:
        # Headers para simular navegador real
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url_imagen, headers=headers)
        response.raise_for_status()
        
        # Crear ruta completa del archivo
        ruta_archivo = os.path.join(carpeta, nombre_archivo)
        
        with open(ruta_archivo, 'wb') as file:
            file.write(response.content)
        
        print(f"🖼️ Imagen descargada: {nombre_archivo}")
        return True
    
    except Exception as e:
        print(f"❌ Error descargando imagen {nombre_archivo}: {e}")
        return False

def extraer_url_libro(driver, producto):
    """Extraer URL del libro desde el elemento producto"""
    try:
        # Buscar el enlace al libro
        link_element = producto.find_element(By.CSS_SELECTOR, "a[href*='/libro/']")
        url_relativa = link_element.get_attribute('href')
        
        # Si la URL es relativa, convertirla a absoluta
        if url_relativa.startswith('/'):
            url_completa = f"https://www.buscalibre.com.mx{url_relativa}"
        else:
            url_completa = url_relativa
        
        return url_completa
    
    except:
        return None

def abrir_libro_en_nueva_pestana(driver, url_libro):
    """Abrir el libro en una nueva pestaña usando JavaScript"""
    try:
        driver.execute_script(f"window.open('{url_libro}', '_blank');")
        pausa_humana(1, 2)
        
        # Cambiar a la nueva pestaña
        driver.switch_to.window(driver.window_handles[-1])
        
        # Esperar a que la página cargue
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        return True
    except Exception as e:
        print(f"❌ Error abriendo libro en nueva pestaña: {e}")
        return False

def extraer_detalle_libro(driver, libro_data):
    """Extraer información detallada del libro desde su página individual"""
    try:
        # Extraer nombre del libro usando el selector específico
        try:
            nombre_elemento = driver.find_element(By.CSS_SELECTOR, "p.tituloProducto")
            libro_data['nombre'] = nombre_elemento.text.strip()
        except NoSuchElementException:
            # Fallback a otros selectores si el principal no funciona
            try:
                nombre_elemento = driver.find_element(By.CSS_SELECTOR, "h1.product-title, .product-name, h1")
                libro_data['nombre'] = nombre_elemento.text.strip()
            except:
                print("⚠️ No se pudo encontrar el nombre del libro")
        
        # Extraer precio
        try:
            precio_elemento = driver.find_element(By.CSS_SELECTOR, ".precio, .price, .precio-actual")
            precio_texto = precio_elemento.text.strip()
            libro_data['precio_original'] = precio_texto
            
            # Extraer precio numérico
            precio_match = re.search(r'[\d,]+\.?\d*', precio_texto)
            if precio_match:
                precio_numerico = float(precio_match.group().replace(',', ''))
                libro_data['precio_numerico'] = precio_numerico
                libro_data['precio_con_envio'] = f"${precio_numerico + ganancia_envio:.0f}"
                
                # Aplicar estrategia de precios: si termina en 0, restar 1
                precio_final = precio_numerico + ganancia_envio
                if precio_final % 10 == 0 and precio_final > 10:
                    precio_final -= 1
                    libro_data['precio_con_envio'] = f"${precio_final:.0f}"
        except:
            print("⚠️ No se pudo encontrar el precio")
        
        # Extraer imagen de la página de detalle
        try:
            imagen_elemento = driver.find_element(By.CSS_SELECTOR, ".book-cover img, .product-image img, #imagenProducto img")
            url_imagen = imagen_elemento.get_attribute('src')
            if url_imagen:
                libro_data['url_imagen'] = url_imagen
        except:
            print("⚠️ No se pudo encontrar la imagen en la página de detalle")
        
        # Extraer información de la sección de metadata (.ficha .row)
        try:
            ficha_rows = driver.find_elements(By.CSS_SELECTOR, ".ficha .row")
            for row in ficha_rows:
                text_content = row.text.strip().lower()
                
                # Buscar autor (puede estar como enlace o texto)
                if any(keyword in text_content for keyword in ['autor', 'writer', 'by']):
                    try:
                        # Intentar encontrar un enlace dentro de la fila
                        autor_link = row.find_element(By.TAG_NAME, "a")
                        autor_text = autor_link.text.strip()
                        if autor_text and len(autor_text) > 1:
                            libro_data['autor'] = autor_text
                    except:
                        # Si no hay enlace, extraer el texto después de los dos puntos
                        if ':' in row.text:
                            autor_text = row.text.split(':', 1)[1].strip()
                            if autor_text:
                                libro_data['autor'] = autor_text
                
                # Buscar editorial
                if 'editorial' in text_content or 'publisher' in text_content:
                    if ':' in row.text:
                        editorial_text = row.text.split(':', 1)[1].strip()
                        if editorial_text:
                            libro_data['editorial'] = editorial_text
                
                # Buscar número de páginas
                if 'páginas' in text_content or 'pages' in text_content:
                    pages_match = re.search(r'\d+', row.text)
                    if pages_match:
                        libro_data['num_paginas'] = pages_match.group()
        
        except Exception as e:
            print(f"⚠️ Error extrayendo metadata: {e}")
        
        # Calcular tiempo de entrega
        libro_data['tiempo_entrega'] = calcular_tiempo_entrega()
        
        # Agregar URL del libro
        libro_data['url_libro'] = driver.current_url
        
        return True
        
    except Exception as e:
        print(f"❌ Error extrayendo detalles del libro: {e}")
        return False

def main():
    """Función principal"""
    print("🚀 Iniciando scraper de BuscaLibre con integración Firebase...")
    
    # Inicializar Firebase uploader si está disponible
    firebase_uploader = None
    if FIREBASE_AVAILABLE and SUBIR_A_FIREBASE:
        firebase_uploader = FirebaseUploader()
    
    # Configurar carpeta de imágenes
    if DESCARGAR_IMAGENES:
        crear_carpeta_imagenes(CARPETA_IMAGENES)
    
    driver = None
    productos_info = []  # Lista para almacenar info de todos los productos
    
    try:
        # Configurar driver
        print("⚙️ Configurando navegador...")
        driver = setup_chrome_driver()
        
        # Navegar a BuscaLibre
        print("🌐 Navegando a BuscaLibre...")
        driver.get("https://www.buscalibre.com.mx/")
        pausa_humana(2, 4)
        
        # Buscar cuadro de búsqueda
        print("🔍 Buscando cuadro de búsqueda...")
        search_box = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "txtBusqueda"))
        )
        
        # Escribir término de búsqueda
        print(f"✍️ Escribiendo '{search_term}'...")
        escribir_como_humano(search_box, search_term)
        pausa_humana(0.5, 1.5)
        
        # Hacer clic en buscar
        print("🔍 Iniciando búsqueda...")
        boton_buscar = driver.find_element(By.ID, "btnBuscar")
        boton_buscar.click()
        
        # Esperar resultados
        print("⏳ Esperando resultados...")
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".box-producto"))
        )
        pausa_humana(2, 3)
        
        # Extraer información de productos
        productos = driver.find_elements(By.CSS_SELECTOR, ".box-producto")[:NUMERO_PRODUCTOS]
        print(f"📚 Encontrados {len(productos)} libros")
        
        for i, producto in enumerate(productos, 1):
            try:
                print(f"\n{'='*70}")
                print(f"📖 PROCESANDO LIBRO #{i}")
                print('='*70)
                
                libro_data = {}
                
                # Extraer URL del libro
                url_libro = extraer_url_libro(driver, producto)
                if not url_libro:
                    print("⚠️ No se pudo extraer URL del libro")
                    continue
                
                print(f"🔗 URL del libro: {url_libro}")
                libro_data['url_libro'] = url_libro
                
                if NAVEGAR_A_DETALLE and ABRIR_ENLACES:
                    # Abrir libro en nueva pestaña y extraer información detallada
                    if abrir_libro_en_nueva_pestana(driver, url_libro):
                        extraer_detalle_libro(driver, libro_data)
                        
                        # Descargar imagen desde la página de detalle
                        if DESCARGAR_IMAGENES and libro_data.get('url_imagen'):
                            nombre_archivo = f"libro_{i}_{libro_data.get('nombre', 'sin_titulo')[:30].replace(' ', '_')}.jpg"
                            # Limpiar nombre de archivo de caracteres especiales
                            nombre_archivo = re.sub(r'[^\w\-_\.]', '', nombre_archivo)
                            descargar_imagen(libro_data['url_imagen'], nombre_archivo, CARPETA_IMAGENES)
                        
                        # Cerrar pestaña actual y volver a la de resultados
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                        pausa_humana(1, 2)
                
                # Mostrar información extraída
                print(f"📕 Nombre: {libro_data.get('nombre', 'No disponible')}")
                print(f"👤 Autor: {libro_data.get('autor', 'No disponible')}")
                print(f"🏢 Editorial: {libro_data.get('editorial', 'No disponible')}")
                print(f"📄 Páginas: {libro_data.get('num_paginas', 'No disponible')}")
                print(f"💰 Precio original: {libro_data.get('precio_original', 'No disponible')}")
                print(f"💵 Precio con envío: {libro_data.get('precio_con_envio', 'No disponible')}")
                print(f"🚚 Tiempo de entrega: {libro_data.get('tiempo_entrega', 'No disponible')}")
                
                # Agregar a la lista de productos
                productos_info.append(libro_data)
                
            except Exception as e:
                print(f"❌ Error procesando libro {i}: {e}")
        
        # Guardar información en archivo de texto
        if productos_info:
            archivo_txt = os.path.join(CARPETA_IMAGENES, f"libros_{search_term.replace(' ', '_')}.txt")
            
            with open(archivo_txt, 'w', encoding='utf-8') as f:
                f.write(f"INFORMACIÓN DE LIBROS - {search_term.upper()}\n")
                f.write(f"Fecha de extracción: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
                f.write(f"Total de libros encontrados: {len(productos_info)}\n")
                f.write("="*70 + "\n\n")
                
                for i, libro in enumerate(productos_info, 1):
                    f.write(f"📖 LIBRO #{i}\n")
                    f.write("="*70 + "\n")
                    f.write(f"📕 Nombre: {libro.get('nombre', 'No disponible')}\n")
                    f.write(f"👤 Autor: {libro.get('autor', 'No disponible')}\n")
                    f.write(f"🏢 Editorial: {libro.get('editorial', 'No disponible')}\n")
                    f.write(f"📄 Páginas: {libro.get('num_paginas', 'No disponible')}\n")
                    f.write(f"💰 Precio original: {libro.get('precio_original', 'No disponible')}\n")
                    f.write(f"💵 Precio con envío: {libro.get('precio_con_envio', 'No disponible')}\n")
                    f.write(f"🚚 Tiempo de entrega: {libro.get('tiempo_entrega', 'No disponible')}\n")
                    f.write(f"🔗 URL: {libro.get('url_libro', 'No disponible')}\n")
                    f.write("\n" + "="*70 + "\n\n")
            
            print(f"\n💾 Información guardada en: {archivo_txt}")
        
        # Subir a Firebase si está habilitado
        if firebase_uploader and productos_info:
            print("\n🔥 Subiendo libros a Firebase...")
            firebase_uploader.upload_from_scraper_data(productos_info, search_term)
        
        print(f"\n🎉 Proceso completado exitosamente!")
        print(f"📚 Total de libros procesados: {len(productos_info)}")
        if DESCARGAR_IMAGENES:
            print(f"📁 Imágenes guardadas en: {CARPETA_IMAGENES}")
        
    except Exception as e:
        print(f"❌ Error en el proceso: {e}")
        
    finally:
        if driver:
            print("🔄 Cerrando navegador...")
            pausa_humana(2, 3)
            driver.quit()

if __name__ == "__main__":
    main()