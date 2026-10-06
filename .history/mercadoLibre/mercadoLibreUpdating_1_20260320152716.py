"""
MercadoLibre Book Scraper
Extrae información de libros desde URLs directas de MercadoLibre
Genera imágenes publicitarias y almacena en Firebase
"""

import os
import re
import sys
import time
import json
import random
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# Imports para generación de imágenes de Facebook
try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
    import io
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("⚠️ PIL no disponible - generación de imágenes publicitarias desactivada")

# Importar Firebase
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
NUMERO_PRODUCTOS = 1  # Solo procesamos una URL directa
ganancia_envio = 100  # Ganancia fija por envío para calcular el precio final

# URLs de ejemplo para testing
EXAMPLE_URLs = [
    "https://www.mercadolibre.com.mx/libro-harry-potter-y-la-piedra-filosofal-de-j-k-rowling/p/MLM21072952"
]

# Control de funcionalidades
DESCARGAR_IMAGENES = True  # Parámetro para activar/desactivar descarga de imágenes
ABRIR_ENLACES = True  # Parámetro para activar/desactivar apertura de enlaces
GENERAR_ANUNCIOS_FACEBOOK = True  # Parámetro para activar/desactivar generación de imágenes publicitarias

# Configuración de carpetas
CARPETA_BASE = "busquedas"
CARPETA_IMAGENES = os.path.join(CARPETA_BASE, "book_images_mercadolibre")


class FacebookAdGenerator:
    """Generador de anuncios de Facebook con diseño verde profesional para MercadoLibre"""
    
    def __init__(self):
        if not PIL_AVAILABLE:
            raise ImportError("PIL/Pillow no disponible")
        
        self.width = 900  # Optimizado para contenido
        self.height = 630
        
        # Esquemas de colores verdes elegantes
        self.color_schemes = [
            {
                'bg': '#f0f8f0',  # Verde muy claro de fondo
                'accent': '#e8f5e8',  # Verde suave para acentos
                'text': '#1a4a1a',  # Verde oscuro para texto
                'price': '#2d6930',  # Verde medio para precios
                'button': '#4a8c4a',  # Verde vibrante para botones
                'secondary': '#5a8c5a',  # Verde medio para texto secundario
                'border': '#c8e6c8'  # Verde claro para bordes
            },
            {
                'bg': '#f5fff5',  # Verde muy suave
                'accent': '#e0f2e0',  # Verde claro acentuado
                'text': '#0d3d0d',  # Verde muy oscuro
                'price': '#1e5d1e',  # Verde bosque para precios
                'button': '#2e7d2e',  # Verde medio para botones
                'secondary': '#4a7d4a',  # Verde gris para secundario
                'border': '#b8e2b8'  # Verde pastel para bordes
            },
            {
                'bg': '#edf7ed',  # Verde menta claro
                'accent': '#ddf0dd',  # Verde menta medio
                'text': '#0a330a',  # Verde intenso para texto
                'price': '#146914',  # Verde oscuro para precios
                'button': '#359935',  # Verde brillante para botones
                'secondary': '#4d8a4d',  # Verde medio para secundario
                'border': '#a6d6a6'  # Verde suave para bordes
            }
        ]
    
    def download_image(self, url, timeout=10):
        """Descarga imagen desde URL"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=timeout)
            if response.status_code == 200:
                return Image.open(io.BytesIO(response.content))
            return None
        except Exception as e:
            print(f"Error descargando imagen: {e}")
            return None
    
    def create_clean_background(self, colors):
        """Crea un fondo limpio estilo MercadoLibre con header de librería"""
        image = Image.new('RGB', (self.width, self.height), colors['bg'])
        draw = ImageDraw.Draw(image)
        
        # Header con nombre de la librería
        try:
            header_font = ImageFont.truetype("arial.ttf", 24)
        except:
            header_font = ImageFont.load_default()
        
        header_text = "LOS LIBROS DE LA BUENA MEMORIA"
        header_bbox = draw.textbbox((0, 0), header_text, font=header_font)
        header_width = header_bbox[2] - header_bbox[0]
        header_x = (self.width - header_width) // 2
        
        # Fondo del header
        draw.rectangle([0, 0, self.width, 50], fill=colors['accent'])
        draw.line([(0, 50), (self.width, 50)], fill=colors['border'], width=2)
        
        # Texto del header
        draw.text((header_x, 15), header_text, fill=colors['text'], font=header_font)
        
        return image, draw
    
    def add_modern_elements(self, draw, colors, x, y, width):
        """Añade elementos modernos estilo MercadoLibre"""
        # Badge de "Envío gratis"
        badge_width = 120
        badge_height = 25
        badge_x = x + width - badge_width
        badge_y = y
        
        draw.rounded_rectangle(
            [badge_x, badge_y, badge_x + badge_width, badge_y + badge_height],
            radius=12, fill=colors['button']
        )
        
        try:
            badge_font = ImageFont.truetype("arial.ttf", 12)
        except:
            badge_font = ImageFont.load_default()
        
        badge_text = "ENVÍO GRATIS"
        badge_bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
        badge_text_width = badge_bbox[2] - badge_bbox[0]
        badge_text_x = badge_x + (badge_width - badge_text_width) // 2
        
        draw.text((badge_text_x, badge_y + 6), badge_text, fill='white', font=badge_font)
        
        # Estrellas de rating (5 estrellas)
        star_size = 16
        stars_y = y + 160
        
        for i in range(5):
            star_x = x + (i * (star_size + 2))
            # Dibujar estrella simple
            points = []
            for j in range(5):
                angle = j * 2 * 3.14159 / 5 - 3.14159 / 2
                points.append((star_x + star_size//2 + (star_size//3) * 0.6 * 
                              (1 if j % 2 == 0 else 0.4) * (1 if j % 2 == 0 else -1) * 
                              (0.9 if j % 2 == 0 else 1), 
                              stars_y + star_size//2 + (star_size//3) * 0.6 * 
                              (1 if j % 2 == 0 else 0.4) * (0.9 if j % 2 == 0 else 1)))
            
            # Estrella simple como círculo
            draw.ellipse([star_x, stars_y, star_x + star_size, stars_y + star_size], 
                        fill='#FFD700')
        
        return y + 190
    
    def generate_ad(self, book_data, output_path):
        """Genera anuncio publicitario completo"""
        try:
            # Seleccionar esquema de color aleatorio
            colors = random.choice(self.color_schemes)
            
            # Crear fondo
            image, draw = self.create_clean_background(colors)
            
            content_start_y = 60
            
            # ÁREA DE PORTADA (lado izquierdo) - 50% del ancho optimizado
            cover_area_width = int(self.width * 0.50)
            cover_x = 30
            cover_y = content_start_y + 20
            cover_max_size = min(cover_area_width - 40, 380)  # Portada optimizada
            
            # ÁREA DE INFORMACIÓN (lado derecho) - 50% del ancho restante
            info_x = cover_area_width + 15
            info_width = self.width - info_x - 20
            
            # Descargar y procesar portada
            cover_image = None
            if book_data.get('url_imagen'):
                cover_image = self.download_image(book_data['url_imagen'])
            
            if cover_image:
                # Redimensionar portada manteniendo proporción
                cover_image.thumbnail((cover_max_size, cover_max_size), Image.Resampling.LANCZOS)
                
                # Centrar portada en su área
                cover_paste_x = cover_x + (cover_area_width - cover_image.width) // 2
                cover_paste_y = cover_y + 20
                
                # Sombra para la portada
                shadow_offset = 5
                shadow = Image.new('RGBA', (cover_image.width + shadow_offset, 
                                          cover_image.height + shadow_offset), 
                                 (0, 0, 0, 50))
                image.paste(shadow, (cover_paste_x + shadow_offset, cover_paste_y + shadow_offset), shadow)
                
                # Pegar portada
                if cover_image.mode != 'RGB':
                    cover_image = cover_image.convert('RGB')
                image.paste(cover_image, (cover_paste_x, cover_paste_y))
            
            # INFORMACIÓN DEL LIBRO (lado derecho)
            current_y = content_start_y + 20
            
            # Añadir elementos modernos
            current_y = self.add_modern_elements(draw, colors, info_x, current_y, info_width)
            
            # Título del libro
            try:
                title_font = ImageFont.truetype("arial.ttf", 20)
            except:
                title_font = ImageFont.load_default()
            
            title = book_data.get('nombre', 'Título no disponible')[:60] + "..." if len(book_data.get('nombre', '')) > 60 else book_data.get('nombre', 'Título no disponible')
            
            # Dividir título en líneas
            words = title.split()
            lines = []
            current_line = []
            
            for word in words:
                test_line = ' '.join(current_line + [word])
                bbox = draw.textbbox((0, 0), test_line, font=title_font)
                if bbox[2] - bbox[0] <= info_width - 10:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                        current_line = [word]
                    else:
                        lines.append(word)
            
            if current_line:
                lines.append(' '.join(current_line))
            
            for line in lines[:3]:  # Máximo 3 líneas
                draw.text((info_x, current_y), line, fill=colors['text'], font=title_font)
                current_y += 25
            
            current_y += 10
            
            # Autor
            if book_data.get('autor'):
                try:
                    author_font = ImageFont.truetype("arial.ttf", 16)
                except:
                    author_font = ImageFont.load_default()
                
                autor_text = f"Autor: {book_data['autor']}"
                draw.text((info_x, current_y), autor_text, fill=colors['secondary'], font=author_font)
                current_y += 25
            
            # Editorial y páginas
            if book_data.get('editorial') or book_data.get('num_paginas'):
                try:
                    detail_font = ImageFont.truetype("arial.ttf", 14)
                except:
                    detail_font = ImageFont.load_default()
                
                details = []
                if book_data.get('editorial'):
                    details.append(f"Editorial: {book_data['editorial']}")
                if book_data.get('num_paginas'):
                    details.append(f"Páginas: {book_data['num_paginas']}")
                
                detail_text = " | ".join(details)
                draw.text((info_x, current_y), detail_text, fill=colors['secondary'], font=detail_font)
                current_y += 30
            
            # Precio con descuento
            try:
                price_font = ImageFont.truetype("arial.ttf", 28)
                old_price_font = ImageFont.truetype("arial.ttf", 18)
            except:
                price_font = ImageFont.load_default()
                old_price_font = ImageFont.load_default()
            
            precio_actual = book_data.get('precio_con_envio', book_data.get('precio_original', '0'))
            precio_original = book_data.get('precio_original', '0')
            
            # Precio actual
            precio_text = f"${precio_actual}"
            draw.text((info_x, current_y), precio_text, fill=colors['price'], font=price_font)
            
            # Precio original tachado (si hay descuento)
            if precio_original and precio_original != precio_actual:
                bbox = draw.textbbox((0, 0), precio_text, font=price_font)
                old_price_x = info_x + bbox[2] - bbox[0] + 15
                old_price_text = f"${precio_original}"
                draw.text((old_price_x, current_y + 5), old_price_text, fill=colors['secondary'], font=old_price_font)
                
                # Línea tachada
                old_bbox = draw.textbbox((old_price_x, current_y + 5), old_price_text, font=old_price_font)
                draw.line([(old_price_x, current_y + 15), (old_bbox[2], current_y + 15)], fill=colors['secondary'], width=2)
            
            current_y += 50
            
            # Tiempo de entrega
            if book_data.get('tiempo_entrega'):
                try:
                    delivery_font = ImageFont.truetype("arial.ttf", 14)
                except:
                    delivery_font = ImageFont.load_default()
                
                entrega_text = f"⚡ {book_data['tiempo_entrega']}"
                draw.text((info_x, current_y), entrega_text, fill=colors['button'], font=delivery_font)
                current_y += 30
            
            # Botón de llamada a la acción
            button_width = min(info_width - 20, 250)
            button_height = 40
            button_x = info_x
            button_y = current_y
            
            # Fondo del botón
            draw.rounded_rectangle(
                [button_x, button_y, button_x + button_width, button_y + button_height],
                radius=8, fill=colors['button']
            )
            
            # Texto del botón
            try:
                button_font = ImageFont.truetype("arial.ttf", 16)
            except:
                button_font = ImageFont.load_default()
            
            button_text = "AGREGAR AL CARRITO"
            button_bbox = draw.textbbox((0, 0), button_text, font=button_font)
            button_text_width = button_bbox[2] - button_bbox[0]
            button_text_x = button_x + (button_width - button_text_width) // 2
            
            draw.text((button_text_x, button_y + 12), button_text, fill='white', font=button_font)
            
            # Guardar imagen
            image.save(output_path, 'PNG', quality=95, optimize=True)
            print(f"✅ Anuncio Facebook generado: {output_path}")
            return True
            
        except Exception as e:
            print(f"❌ Error generando anuncio Facebook: {e}")
            return False


def configurar_selenium():
    """Configura el driver de Selenium optimizado para velocidad"""
    chrome_options = Options()
    
    # Optimizaciones de rendimiento
    chrome_options.add_argument("--headless")  # Modo headless para mayor velocidad
    chrome_options.add_argument("--disable-images")  # No cargar imágenes
    chrome_options.add_argument("--disable-javascript")  # Deshabilitar JS si no es necesario
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-plugins")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    
    # Estrategia de carga de página optimizada
    chrome_options.add_argument("--page-load-strategy=eager")
    
    # User agent realista
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )
    
    # Configuraciones adicionales
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--window-size=1920,1080")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Ejecutar script para ocultar webdriver
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver
    except Exception as e:
        print(f"❌ Error configurando Selenium: {e}")
        return None


def extract_json_data(driver):
    """Extrae datos de JSON-LD de la página"""
    try:
        # Buscar script con JSON-LD estructurado
        json_scripts = driver.find_elements(By.CSS_SELECTOR, 'script[type="application/ld+json"]')
        
        for script in json_scripts:
            try:
                json_text = script.get_attribute('innerHTML')
                data = json.loads(json_text)
                
                if isinstance(data, dict) and 'name' in data:
                    return data
            except json.JSONDecodeError:
                continue
                
        return None
    except Exception as e:
        print(f"Error extrayendo JSON-LD: {e}")
        return None


def extract_meta_data(driver):
    """Extrae datos de meta tags de Twitter/OpenGraph"""
    try:
        meta_data = {}
        
        # Twitter meta tags
        twitter_title = driver.find_elements(By.CSS_SELECTOR, 'meta[name="twitter:title"]')
        if twitter_title:
            meta_data['title'] = twitter_title[0].get_attribute('content')
        
        twitter_description = driver.find_elements(By.CSS_SELECTOR, 'meta[name="twitter:description"]')
        if twitter_description:
            meta_data['description'] = twitter_description[0].get_attribute('content')
        
        twitter_image = driver.find_elements(By.CSS_SELECTOR, 'meta[name="twitter:image"]')
        if twitter_image:
            meta_data['image'] = twitter_image[0].get_attribute('content')
        
        # OpenGraph meta tags
        og_title = driver.find_elements(By.CSS_SELECTOR, 'meta[property="og:title"]')
        if og_title and 'title' not in meta_data:
            meta_data['title'] = og_title[0].get_attribute('content')
        
        og_image = driver.find_elements(By.CSS_SELECTOR, 'meta[property="og:image"]')
        if og_image and 'image' not in meta_data:
            meta_data['image'] = og_image[0].get_attribute('content')
        
        return meta_data
    except Exception as e:
        print(f"Error extrayendo meta datos: {e}")
        return {}


def parse_description(description_text):
    """Parsea la descripción para extraer información específica"""
    info = {}
    
    if not description_text:
        return info
    
    # Buscar número de páginas
    pages_match = re.search(r'Número de páginas:\s*(\d+)', description_text)
    if pages_match:
        info['num_paginas'] = pages_match.group(1)
    
    # Buscar género
    genre_match = re.search(r'Género:\s*([^|.]+)', description_text)
    if genre_match:
        info['genero'] = genre_match.group(1).strip()
    
    # Buscar ISBN
    isbn_match = re.search(r'ISBN:\s*(\d+)', description_text)
    if isbn_match:
        info['isbn'] = isbn_match.group(1)
    
    # Buscar volumen
    volume_match = re.search(r'Volumen del libro:\s*([^|.]+)', description_text)
    if volume_match:
        info['volumen'] = volume_match.group(1).strip()
    
    return info


def extraer_informacion_libro(url, driver):
    """Extrae información completa del libro desde MercadoLibre"""
    libro_info = {
        'nombre': '',
        'autor': '',
        'editorial': '',
        'num_paginas': '',
        'precio_original': '',
        'precio_con_envio': '',
        'url_imagen': '',
        'descripcion': '',
        'tiempo_entrega': '',
        'url_libro': url,
        'fuente': 'mercadolibre.com.mx'
    }
    
    try:
        print(f"🔍 Procesando: {url}")
        driver.get(url)
        
        # Esperar a elementos específicos críticos
        try:
            WebDriverWait(driver, 5).until(
                EC.any_of(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="price"]')),
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'meta[name="twitter:title"]')),
                    EC.presence_of_element_located((By.TAG_NAME, "title"))
                )
            )
        except TimeoutException:
            print("⚠️ Timeout esperando elementos, continuando...")
        
        # Delay mínimo optimizado
        time.sleep(1)
        
        # 1. INTENTAR JSON-LD (más confiable)
        json_data = extract_json_data(driver)
        if json_data:
            print("✅ Datos JSON-LD encontrados")
            libro_info['nombre'] = json_data.get('name', '')
            
            if 'offers' in json_data and json_data['offers']:
                offers = json_data['offers']
                if isinstance(offers, dict):
                    libro_info['precio_original'] = str(offers.get('price', ''))
                elif isinstance(offers, list) and offers:
                    libro_info['precio_original'] = str(offers[0].get('price', ''))
            
            if 'image' in json_data:
                imagen_url = json_data['image']
                if isinstance(imagen_url, list):
                    imagen_url = imagen_url[0] if imagen_url else ''
                libro_info['url_imagen'] = imagen_url
        
        # 2. EXTRAER META DATOS (complementario)
        meta_data = extract_meta_data(driver)
        if meta_data:
            print("✅ Meta datos encontrados")
            
            if not libro_info['nombre'] and meta_data.get('title'):
                libro_info['nombre'] = meta_data['title']
            
            if not libro_info['url_imagen'] and meta_data.get('image'):
                libro_info['url_imagen'] = meta_data['image']
            
            # Parsear descripción para obtener más detalles
            if meta_data.get('description'):
                parsed_info = parse_description(meta_data['description'])
                libro_info.update(parsed_info)
                libro_info['descripcion'] = meta_data['description']
        
        # 3. EXTRAER DATOS ADICIONALES DE LA PÁGINA
        try:
            # Buscar precio en el DOM con selectores optimizados
            price_selectors = [
                '[data-testid="price"] .price-fraction',  # Selector más confiable primero
                '.price-tag-amount .price-tag-fraction',
                '[class*="price-tag-fraction"]',
                '.price-tag .price-tag-fraction',
                '[class*="price"] [class*="fraction"]'
            ]
            
            for selector in price_selectors:
                try:
                    price_element = driver.find_element(By.CSS_SELECTOR, selector)
                    price_text = price_element.text.strip()
                    if price_text and not libro_info['precio_original']:
                        # Limpiar y extraer número
                        price_clean = re.sub(r'[^\d.,]', '', price_text)
                        libro_info['precio_original'] = price_clean
                        print(f"✅ Precio extraído: {price_clean}")
                        break
                except:
                    continue
            
            # Buscar información de envío
            shipping_selectors = [
                '[class*="shipping"] [class*="text"]',
                '.shipping-info',
                '[data-testid="shipping"]'
            ]
            
            for selector in shipping_selectors:
                try:
                    shipping_element = driver.find_element(By.CSS_SELECTOR, selector)
                    shipping_text = shipping_element.text.strip()
                    if 'gratis' in shipping_text.lower() or 'envío' in shipping_text.lower():
                        libro_info['tiempo_entrega'] = shipping_text
                        break
                except:
                    continue
                    
            # Intentar extraer autor de la página si no está en meta datos
            if not libro_info['autor']:
                author_selectors = [
                    '[class*="author"]',
                    '[class*="seller-name"]',
                    '.product-seller'
                ]
                
                for selector in author_selectors:
                    try:
                        author_element = driver.find_element(By.CSS_SELECTOR, selector)
                        author_text = author_element.text.strip()
                        if author_text and len(author_text) < 100:  # Filtro básico
                            libro_info['autor'] = author_text
                            break
                    except:
                        continue
            
        except Exception as e:
            print(f"⚠️ Error extrayendo datos adicionales: {e}")
        
        # 4. CALCULAR PRECIO CON ENVÍO
        try:
            precio_original = libro_info.get('precio_original', '0')
            if precio_original:
                # Limpiar precio y convertir a número
                precio_numerico = float(re.sub(r'[^\d.]', '', str(precio_original)))
                precio_con_envio = precio_numerico + ganancia_envio
                
                # Aplicar estrategia de precios terminados en 9
                precio_final = int(precio_con_envio)
                if precio_final % 10 != 9:
                    precio_final = (precio_final // 10) * 10 + 9
                
                libro_info['precio_con_envio'] = str(precio_final)
                print(f"✅ Precio calculado: ${precio_numerico} + ${ganancia_envio} = ${precio_final}")
            
        except Exception as e:
            print(f"⚠️ Error calculando precio: {e}")
            libro_info['precio_con_envio'] = libro_info.get('precio_original', '0')
        
        # Validación final
        if not libro_info['nombre']:
            libro_info['nombre'] = "Producto MercadoLibre"
        
        print("📊 Información extraída:")
        for key, value in libro_info.items():
            if value:
                print(f"   {key}: {value[:100]}{'...' if len(str(value)) > 100 else ''}")
        
        return libro_info
        
    except Exception as e:
        print(f"❌ Error procesando {url}: {e}")
        return libro_info


def configurar_firebase():
    """Configura Firebase para almacenamiento de datos"""
    if not FIREBASE_AVAILABLE:
        print("⚠️ Firebase no disponible - saltando configuración")
        return None
    
    try:
        if not firebase_admin._apps:
            if not os.path.exists(SERVICE_ACCOUNT_KEY_PATH):
                print(f"❌ Archivo de credenciales no encontrado: {SERVICE_ACCOUNT_KEY_PATH}")
                return None
            
            cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
            firebase_admin.initialize_app(cred, {
                'projectId': PROJECT_ID,
            })
            print("✅ Firebase inicializado correctamente")
        
        db = firestore.client()
        return db
        
    except Exception as e:
        print(f"❌ Error configurando Firebase: {e}")
        return None


def insertar_en_firebase(db, libro_info):
    """Inserta información del libro en Firebase con batch operations"""
    if not db:
        print("⚠️ Base de datos no disponible - saltando inserción")
        return False
    
    try:
        # Preparar datos para Firebase
        precio_numerico = libro_info.get('precio_con_envio', '0')
        precio_clean = re.sub(r'[^\d.]', '', str(precio_numerico))
        
        book_data = {
            'contacto': '',
            'disponible': 'true',
            'link': libro_info.get('url_libro', ''),
            'portada': libro_info.get('url_imagen', ''),
            'precio': precio_clean,
            'rating': '4.8',  # Rating por defecto para MercadoLibre
            'textFromQuery': 'mercadolibre_direct',
            'titulo': libro_info.get('nombre', ''),
            'autor': libro_info.get('autor', ''),
            'editorial': libro_info.get('editorial', ''),
            'num_paginas': libro_info.get('num_paginas', ''),
            'tiempo_entrega': libro_info.get('tiempo_entrega', 'Consultar disponibilidad'),
            'precio_original': libro_info.get('precio_original', ''),
            'descripcion': libro_info.get('descripcion', ''),
            'fuente': 'mercadolibre.com.mx',
            'fecha_agregado': datetime.now(),
        }
        
        # Insertar en Firestore con batch operations
        batch = db.batch()
        collection_ref = db.collection('libros_mercadolibre')
        doc_ref = collection_ref.document()  # Auto-generate ID
        batch.set(doc_ref, book_data)
        batch.commit()
        
        print(f"✅ Libro insertado en Firebase con ID: {doc_ref.id}")
        return True
        
    except Exception as e:
        print(f"❌ Error insertando en Firebase: {e}")
        return False


def main():
    """Función principal del scraper de MercadoLibre"""
    print("🚀 Iniciando MercadoLibre Book Scraper")
    print("=" * 50)
    
    # Configurar carpetas
    os.makedirs(CARPETA_IMAGENES, exist_ok=True)
    
    # Configurar Selenium
    print("🔧 Configurando navegador...")
    driver = configurar_selenium()
    if not driver:
        print("❌ No se pudo configurar el navegador")
        return
    
    # Configurar Firebase
    print("🔧 Configurando Firebase...")
    db = configurar_firebase()
    
    # Configurar generador de anuncios
    fb_generator = None
    if GENERAR_ANUNCIOS_FACEBOOK and PIL_AVAILABLE:
        try:
            fb_generator = FacebookAdGenerator()
            print("✅ Generador de anuncios Facebook configurado")
        except ImportError:
            print("⚠️ No se pudo configurar el generador de anuncios")
    
    try:
        # Usar URL del ejemplo HTML directamente
        print("\n📝 Usando URL del ejemplo HTML:")
        url_input = "https://www.mercadolibre.com.mx/libro-harry-potter-y-la-piedra-filosofal-de-j-k-rowling/p/MLM21072952"
        print(f"URL: {url_input}")
        
        # Opción para cambiar URL si es necesario
        cambiar = input("\n¿Usar otra URL? (Enter para continuar, o pega nueva URL): ").strip()
        if cambiar:
            url_input = cambiar
        
        if 'mercadolibre.com' not in url_input:
            print("❌ La URL debe ser de MercadoLibre")
            return
        
        print(f"\n🎯 Procesando: {url_input}")
        
        # Extraer información
        libro_info = extraer_informacion_libro(url_input, driver)
        
        if not libro_info.get('nombre'):
            print("❌ No se pudo extraer información del libro")
            return
        
        print(f"\n✅ Libro procesado: {libro_info['nombre']}")
        
        # Guardar en archivo de texto
        output_file = os.path.join(CARPETA_IMAGENES, "libro_mercadolibre.txt")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("INFORMACIÓN DEL LIBRO - MERCADOLIBRE\n")
            f.write("=" * 50 + "\n\n")
            for key, value in libro_info.items():
                if value:
                    f.write(f"{key.replace('_', ' ').title()}: {value}\n")
            f.write(f"\nFecha de extracción: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        print(f"📄 Información guardada en: {output_file}")
        
        # Descargar imagen de portada
        if DESCARGAR_IMAGENES and libro_info.get('url_imagen'):
            try:
                print("📸 Descargando imagen de portada...")
                response = requests.get(libro_info['url_imagen'], timeout=10)
                if response.status_code == 200:
                    image_path = os.path.join(CARPETA_IMAGENES, "portada_libro.jpg")
                    with open(image_path, 'wb') as f:
                        f.write(response.content)
                    print(f"✅ Imagen descargada: {image_path}")
            except Exception as e:
                print(f"⚠️ Error descargando imagen: {e}")
        
        # Generar anuncio de Facebook
        if GENERAR_ANUNCIOS_FACEBOOK and fb_generator:
            try:
                print("🎨 Generando anuncio de Facebook...")
                ad_path = os.path.join(CARPETA_IMAGENES, "fb_ad_mercadolibre.png")
                if fb_generator.generate_ad(libro_info, ad_path):
                    print(f"✅ Anuncio generado: {ad_path}")
            except Exception as e:
                print(f"⚠️ Error generando anuncio: {e}")
        
        # Insertar en Firebase
        if db:
            print("💾 Insertando en Firebase...")
            insertar_en_firebase(db, libro_info)
        
        print(f"\n🎉 Proceso completado exitosamente!")
        print(f"📁 Archivos guardados en: {CARPETA_IMAGENES}")
        
    except KeyboardInterrupt:
        print("\n⏹️ Proceso cancelado por el usuario")
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
    finally:
        if driver:
            driver.quit()
            print("🔒 Navegador cerrado")


if __name__ == "__main__":
    main()