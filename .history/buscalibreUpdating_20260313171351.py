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

# -----------------------------------------------
# CONFIGURACIÓN
# -----------------------------------------------
search_term = "la tecnica metamorfica"
DESCARGAR_IMAGENES = True  # Parámetro para activar/desactivar descarga de imágenes
CARPETA_IMAGENES = "book_images"  # Carpeta donde guardar las imágenes

# -----------------------------------------------
# FUNCIONES AUXILIARES PARA SIMULAR UN HUMANO
# -----------------------------------------------
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
        print(f"📸 Descargando imagen del libro #{numero_producto}...")
        response = requests.get(url_imagen, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Guardar la imagen
        with open(ruta_archivo, 'wb') as f:
            f.write(response.content)
        
        print(f"✅ Imagen guardada: {ruta_archivo}")
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
NUMERO_PRODUCTOS = 10

# -----------------------------------------------
# INICIO DEL AUTOMATION
# -----------------------------------------------

print("🚀 Iniciando navegador Chrome...")
driver = setup_chrome_driver()

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
            
            # EXTRAER MÚLTIPLES PRODUCTOS CON IMÁGENES
            print(f"\n📚 Extrayendo datos y descargando imágenes de los primeros {NUMERO_PRODUCTOS} productos...")
            
            if DESCARGAR_IMAGENES:
                crear_carpeta_imagenes()
                print(f"📁 Las imágenes se guardarán en la carpeta: {CARPETA_IMAGENES}")
            
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
                        # Extraer nombre
                        nombre = producto.find_element(By.CSS_SELECTOR, "h3.nombre").text.strip()
                        
                        # Extraer precio
                        precio_texto = producto.find_element(By.CSS_SELECTOR, ".box-precio-v2 strong").text.strip()
                        
                        # Calcular precio con envío
                        precio_numerico = re.search(r'[\d,]+\.?\d*', precio_texto)
                        if precio_numerico:
                            precio_valor = float(precio_numerico.group().replace(',', ''))
                            precio_actualizado = precio_valor + 100
                            precio_final = f"$ {precio_actualizado:,.2f}"
                        else:
                            precio_final = precio_texto
                        
                        # Extraer URL de imagen
                        url_imagen = None
                        archivo_imagen = None
                        try:
                            img_element = producto.find_element(By.CSS_SELECTOR, ".imagen img")
                            url_imagen = img_element.get_attribute('src') or img_element.get_attribute('data-src')
                            
                            if url_imagen and DESCARGAR_IMAGENES:
                                # Descargar imagen
                                archivo_imagen = descargar_imagen(url_imagen, nombre, i)
                                
                        except NoSuchElementException:
                            print(f"⚠️ No se encontró imagen para el producto #{i}")
                        
                        # Almacenar información del producto
                        info_producto = {
                            'numero': i,
                            'nombre': nombre,
                            'precio_original': precio_texto,
                            'precio_con_envio': precio_final,
                            'url_imagen': url_imagen,
                            'archivo_imagen': archivo_imagen,
                            'tiempo_entrega': tiempo_entrega
                        }
                        productos_info.append(info_producto)
                        
                        # Mostrar información del producto
                        print("="*70)
                        print(f"📖 LIBRO #{i}")
                        print("="*70)
                        print(f"📕 Nombre: {nombre}")
                        print(f"💰 Precio original: {precio_texto}")
                        print(f"💵 Precio con envío (+$100): {precio_final}")
                        print(f"🚚 Tiempo de entrega: {tiempo_entrega}")
                        
                        if url_imagen:
                            print(f"🖼️ URL imagen: {url_imagen}")
                            if archivo_imagen:
                                print(f"📁 Imagen guardada: {archivo_imagen}")
                            else:
                                print("❌ No se pudo descargar la imagen")
                        else:
                            print("❌ No se encontró imagen")
                        
                        print("="*70 + "\n")
                        
                        # Pausa entre productos para no sobrecargar el servidor
                        if DESCARGAR_IMAGENES:
                            human_pause(1, 2)
                        
                    except Exception as e:
                        print(f"⚠️ Error extrayendo producto #{i}: {e}\n")
                        continue
                
                # Resumen final
                print(f"\n🎉 EXTRACCIÓN COMPLETADA")
                print("="*70)
                print(f"📊 Productos procesados: {len(productos_info)}")
                
                if DESCARGAR_IMAGENES:
                    imagenes_descargadas = sum(1 for p in productos_info if p['archivo_imagen'])
                    print(f"📸 Imágenes descargadas: {imagenes_descargadas}/{len(productos_info)}")
                    print(f"📁 Ubicación de imágenes: {os.path.abspath(CARPETA_IMAGENES)}")
                
                print("="*70)
                
            except Exception as e:
                print(f"❌ Error al extraer productos: {e}")
            
        except TimeoutException:
            print("❌ No se pudo encontrar el botón 'Buscar' con id 'botonBuscarHeader'")
        except Exception as e:
            print(f"⚠️  Error al hacer clic en el botón: {e}")
        
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
        driver.quit()
    except:
        pass
    print("✅ Navegador cerrado")
