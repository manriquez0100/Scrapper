"""
MercadoLibre Book Scraper - Optimizado
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
    print(" PIL no disponible - generación de imágenes publicitarias desactivada")

# Importar Firebase
sys.path.append('../implemented_firestore')
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    from config import SERVICE_ACCOUNT_KEY_PATH, PROJECT_ID
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    print(" Firebase no disponible")

# -----------------------------------------------
# CONFIGURACIÓN
# -----------------------------------------------
NUMERO_PRODUCTOS = 1  # Solo procesamos una URL directa
ganancia_envio = 150  # Ganancia fija por envío para d el precio final

tiempoEntrega = "✓ ENTREGA DE 3 A 7 DÍAS A PARTIR DE LA FECHA DE COMPRA"
#tiempoEntrega = "Entrega en 2-3 semanas a partir de fecha de compra."  # Texto fijo para beneficios

# Control de funcionalidades
DESCARGAR_IMAGENES = True
ABRIR_ENLACES = True
GENERAR_ANUNCIOS_FACEBOOK = True

# Configuración de carpetas
CARPETA_BASE = "busquedas"
CARPETA_IMAGENES = os.path.join(CARPETA_BASE, "book_images_mercadolibre")


class FacebookAdGenerator:
    """Generador de anuncios de Facebook con diseño verde profesional para MercadoLibre"""
    
    def __init__(self):
        if not PIL_AVAILABLE:
            raise ImportError("PIL/Pillow no disponible")
        
        self.width = 900
        self.height = 630
        
        # Esquemas de colores verdes elegantes
        self.color_schemes = [
            {
                'bg': '#f0f8f0',
                'accent': '#e8f5e8',
                'text': '#1a4a1a',
                'price': '#2d6930',
                'button': '#4a8c4a',
                'secondary': '#5a8c5a',
                'border': '#c8e6c8'
            },
            {
                'bg': '#f5fff5',
                'accent': '#e0f2e0',
                'text': '#0d3d0d',
                'price': '#1e5d1e',
                'button': '#2e7d2e',
                'secondary': '#4a7d4a',
                'border': '#b8e2b8'
            }
        ]
    
    def add_modern_elements(self, image, colors, book_info):
        """Añade elementos visuales modernos distribuidos en la imagen"""
        draw = ImageDraw.Draw(image)
        
        try:
            detail_font = ImageFont.truetype("arial.ttf", 11)
        except:
            detail_font = ImageFont.load_default()
        
        # Badge "NUEVO" en la esquina superior derecha
        badge_width = 80
        badge_height = 25
        badge_x = self.width - badge_width - 20
        badge_y = 20
        
        draw.rounded_rectangle(
            [badge_x, badge_y, badge_x + badge_width, badge_y + badge_height],
            radius=8, fill=colors['button']
        )
        draw.text((badge_x + 25, badge_y + 5), "NUEVO", font=detail_font, fill='white')
        
        # Estrellas de rating en la parte inferior
        star_y = self.height - 120
        star_size = 20
        star_spacing = 25
        start_x = 50
        
        # Dibujar 5 estrellas
        for i in range(5):
            star_x = start_x + (i * star_spacing)
            # Estrella llena (amarilla)
            self.draw_star(draw, star_x, star_y, star_size, '#FFD700')
        
        # Texto de rating
        rating_text = "4.5/5 (128 reseñas)"
        rating_x = start_x + (5 * star_spacing) + 10
        draw.text((rating_x, star_y + 2), rating_text, font=detail_font, fill=colors['secondary'])
        
        return image
    
    def draw_star(self, draw, x, y, size, color):
        """Dibuja una estrella de 5 puntas"""
        import math
        
        # Calcular puntos de la estrella
        points = []
        for i in range(10):
            angle = i * math.pi / 5 - math.pi / 2
            if i % 2 == 0:
                # Punto exterior
                radius = size // 2
            else:
                # Punto interior
                radius = size // 4
            
            point_x = x + size // 2 + radius * math.cos(angle)
            point_y = y + size // 2 + radius * math.sin(angle)
            points.append((point_x, point_y))
        
        # Dibujar la estrella
        draw.polygon(points, fill=color, outline='#DAA520')
    
    def hex_to_rgb(self, hex_color):
        """Convierte color hexadecimal a RGB"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def wrap_text(self, text, max_width, font):
        """Divide texto en líneas que caben en el ancho especificado"""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            # Crear imagen temporal para medir
            temp_img = Image.new('RGB', (1, 1))
            temp_draw = ImageDraw.Draw(temp_img)
            bbox = temp_draw.textbbox((0, 0), test_line, font=font)
            
            if bbox[2] - bbox[0] <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    lines.append(word)
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines
    
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
        """Crea un fondo limpio con header de librería"""
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
    
    def generate_ad(self, book_data, output_path):
        """Genera anuncio publicitario completo estilo BuscaLibre para MercadoLibre"""
        try:
            colors = random.choice(self.color_schemes)
            image, draw = self.create_clean_background(colors)
            
            # Configurar fuentes
            try:
                title_font = ImageFont.truetype("arial.ttf", 22)
                subtitle_font = ImageFont.truetype("arial.ttf", 16)
                price_font = ImageFont.truetype("arial.ttf", 32)
                old_price_font = ImageFont.truetype("arial.ttf", 18)
                detail_font = ImageFont.truetype("arial.ttf", 12)
                small_font = ImageFont.truetype("arial.ttf", 11)
                button_font = ImageFont.truetype("arial.ttf", 16)
            except:
                title_font = subtitle_font = price_font = old_price_font = detail_font = small_font = button_font = ImageFont.load_default()
            
            # Layout rediseñado - Portada grande a la izquierda
            header_height = 70
            content_start_y = header_height + 15
            
            # ÁREA DE PORTADA (lado izquierdo) - 50% del ancho optimizado
            cover_area_width = int(self.width * 0.50)
            cover_x = 30
            cover_y = content_start_y + 20
            cover_max_size = min(cover_area_width - 40, 380)  # Portada optimizada
            
            # ÁREA DE INFORMACIÓN (lado derecho) - 50% del ancho restante
            info_x = cover_area_width + 15
            info_width = self.width - info_x - 20
            
            # Procesar imagen de portada PROMINENTE
            if book_data.get('url_imagen'):
                cover_image = self.download_image(book_data['url_imagen'])
                if cover_image:
                    # Redimensionar manteniendo aspecto - IMAGEN GRANDE
                    cover_image = cover_image.convert('RGBA')
                    
                    # Calcular tamaño manteniendo proporción
                    original_w, original_h = cover_image.size
                    if original_w > original_h:
                        new_width = cover_max_size
                        new_height = int((original_h * cover_max_size) / original_w)
                    else:
                        new_height = cover_max_size
                        new_width = int((original_w * cover_max_size) / original_h)
                    
                    cover_image = cover_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    
                    # Centrar la portada en su área
                    final_cover_x = cover_x + (cover_area_width - new_width) // 2
                    final_cover_y = cover_y + 20
                    
                    # Marco elegante para la portada
                    frame_padding = 8
                    frame_color = colors['accent']
                    
                    # Sombra profunda para dar profundidad
                    shadow_offset = 12
                    shadow = Image.new('RGBA', (new_width + shadow_offset*2, new_height + shadow_offset*2), 
                                     (0, 0, 0, 40))
                    shadow = shadow.filter(ImageFilter.GaussianBlur(8))
                    image.paste(shadow, (final_cover_x + shadow_offset, final_cover_y + shadow_offset), shadow)
                    
                    # Marco de fondo
                    frame_bg = Image.new('RGBA', (new_width + frame_padding*2, new_height + frame_padding*2), 
                                        (*self.hex_to_rgb(frame_color), 255))
                    image.paste(frame_bg, (final_cover_x - frame_padding, final_cover_y - frame_padding), frame_bg)
                    
                    # Pegar la imagen de portada
                    image.paste(cover_image, (final_cover_x, final_cover_y), cover_image)
                    
                    # Brillo sutil en la portada
                    highlight = Image.new('RGBA', (new_width//3, new_height//2), (255, 255, 255, 25))
                    highlight = highlight.filter(ImageFilter.GaussianBlur(15))
                    image.paste(highlight, (final_cover_x + 10, final_cover_y + 10), highlight)
            
            # Título del libro - más prominente
            title = book_data.get('nombre', 'Libro Disponible')
            title_lines = self.wrap_text(title, info_width - 20, title_font)
            
            y_pos = content_start_y + 15
            for i, line in enumerate(title_lines[:3]):  # Máximo 3 líneas
                text_color = colors['text'] if i == 0 else colors['secondary']
                font_to_use = title_font if i == 0 else subtitle_font
                draw.text((info_x, y_pos), line, font=font_to_use, fill=text_color)
                y_pos += 38 if i == 0 else 32
            
            # Autor con más espacio
            autor = book_data.get('autor', '')
            if autor and autor != 'No disponible':
                y_pos += 15
                draw.text((info_x, y_pos), f"por {autor}", font=subtitle_font, 
                         fill=colors['secondary'])
                y_pos += 40
            
            # Separador visual
            draw.rectangle([info_x, y_pos, info_x + info_width - 40, y_pos + 2], fill=colors['accent'])
            y_pos += 25
            
            # Sección de precios expandida
            precio = book_data.get('precio_con_envio', 'Consultar precio')
            
            # Etiqueta "Precio especial" más visible
            special_bg_width = 160
            special_bg_height = 25
            draw.rounded_rectangle([info_x, y_pos, info_x + special_bg_width, y_pos + special_bg_height], 
                                 radius=8, fill=colors['price'])
            draw.text((info_x + 8, y_pos + 4), "PRECIO ", font=detail_font, fill='#ffffff')
            y_pos += 40
            
            # Precio principal más destacado
            price_color = colors['price']
            draw.text((info_x, y_pos), f"${precio}", font=price_font, fill=price_color)
            
            # Precio tachado al lado
            try:
                precio_num = float(str(precio).replace('$', '').replace(',', '').strip())
                original_price = f"${precio_num * 1.4:,.0f}"
                price_bbox = draw.textbbox((info_x, y_pos), f"${precio}", font=price_font)
                strike_x = price_bbox[2] + 20
                draw.text((strike_x, y_pos + 15), original_price, font=old_price_font, fill=colors['secondary'])
                
                # Línea tachada
                strike_bbox = draw.textbbox((strike_x, y_pos + 15), original_price, font=old_price_font)
                draw.line([(strike_x, strike_bbox[1] + 12), (strike_bbox[2], strike_bbox[1] + 12)], 
                         fill=colors['secondary'], width=2)
            except:
                pass
            
            y_pos += 80
            
            # Beneficios expandidos con iconos
            benefits = [
                "✓ Envío GRATIS a todo el país.",
                #"✓ Libro nuevo y sellado.", 
                tiempoEntrega
            ]
            
            for benefit in benefits:
                # Fondo sutil para cada beneficio
                benefit_bbox = draw.textbbox((info_x, y_pos), benefit, font=small_font)
                benefit_bg_width = benefit_bbox[2] - benefit_bbox[0] + 10
                draw.rounded_rectangle([info_x, y_pos, info_x + benefit_bg_width, y_pos + 22], 
                                     radius=5, fill=colors['accent'], outline=colors['border'])
                draw.text((info_x + 5, y_pos + 3), benefit, font=small_font, fill=colors['text'])
                y_pos += 28
            
            # Botón de compra más grande y llamativo
            button_text = "DISPONIBLE"
            button_y = self.height - 100
            button_width = 280
            button_height = 55
            
            # Sombra del botón
            shadow_button = Image.new('RGBA', (button_width + 10, button_height + 10), (0, 0, 0, 50))
            shadow_button = shadow_button.filter(ImageFilter.GaussianBlur(8))
            image.paste(shadow_button, (info_x + 5, button_y + 5), shadow_button)
            
            # Gradiente del botón
            button_gradient = Image.new('RGBA', (button_width, button_height), 
                                       (*self.hex_to_rgb(colors['button']), 255))
            
            # Pegar el botón
            image.paste(button_gradient, (info_x, button_y), button_gradient)
            
            # Texto del botón centrado
            button_bbox = draw.textbbox((0, 0), button_text, font=button_font)
            button_text_width = button_bbox[2] - button_bbox[0]
            button_text_height = button_bbox[3] - button_bbox[1]
            
            text_x = info_x + (button_width - button_text_width) // 2
            text_y = button_y + (button_height - button_text_height) // 2
            
            draw.text((text_x, text_y), button_text, font=button_font, fill='white')
            
            # Detalles adicionales
            if book_data.get('num_paginas'):
                detail_y = button_y - 35
                detail_text = f"📖 {book_data['num_paginas']} páginas"
                draw.text((info_x, detail_y), detail_text, font=small_font, fill=colors['secondary'])
            
            if book_data.get('editorial'):
                detail_y = button_y - 50
                detail_text = f"📚 {book_data['editorial']}"
                draw.text((info_x, detail_y), detail_text, font=small_font, fill=colors['secondary'])
            
            # Guardar imagen
            image.save(output_path, 'PNG', quality=95, optimize=True)
            print(f" Anuncio Facebook generado: {output_path}")
            return True
            
        except Exception as e:
            print(f" Error generando anuncio Facebook: {e}")
            return False


def configurar_selenium(headless=False):
    """Configura el driver de Selenium optimizado para velocidad"""
    chrome_options = Options()
    
    # Configuración anti-detección para MercadoLibre
    if headless:
        chrome_options.add_argument("--headless=new")  # Nuevo modo headless de Chrome
    chrome_options.add_argument("--disable-images")  # No cargar imágenes para velocidad
    # chrome_options.add_argument("--disable-javascript")  # COMENTADO: Necesario para MercadoLibre
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-plugins")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    
    # Anti-detección mejorada
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Estrategia de carga de página optimizada
    chrome_options.add_argument("--page-load-strategy=normal")
    
    # User agent más reciente
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    
    # Configuraciones adicionales para evitar detección
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")
    chrome_options.add_argument("--lang=es-MX")
    
    # Preferencias adicionales
    prefs = {
        "profile.default_content_setting_values": {
            "notifications": 2
        }
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Scripts anti-detección
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
        driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['es-MX', 'es']})")
        
        return driver
    except Exception as e:
        print(f" Error configurando Selenium: {e}")
        return None


def extract_json_data(driver):
    """Extrae datos de JSON-LD de la página - versión mejorada para schema.org Product"""
    try:
        json_scripts = driver.find_elements(By.CSS_SELECTOR, 'script[type="application/ld+json"]')
        print(f" Encontrados {len(json_scripts)} scripts JSON-LD")
        
        all_products = []
        
        for i, script in enumerate(json_scripts):
            try:
                json_text = script.get_attribute('innerHTML')
                if not json_text or not json_text.strip():
                    continue
                    
                data = json.loads(json_text)
                print(f" Script {i+1}: tipo={type(data).__name__}")
                
                products = _extract_products_from_json(data)
                if products:
                    all_products.extend(products)
                    for p in products:
                        print(f"  Producto encontrado: {p.get('name', 'sin nombre')[:60]}")
                        
            except json.JSONDecodeError as e:
                print(f" Error JSON en script {i+1}: {e}")
                continue
            except Exception as e:
                print(f" Error procesando script {i+1}: {e}")
                continue
                
        if all_products:
            # Devolver el más completo (con más campos)
            best = max(all_products, key=lambda x: len([v for v in x.values() if v]))
            print(f" JSON-LD: mejor producto con {len([v for v in best.values() if v])} campos")
            return best
            
        print(" No se encontraron datos de producto en JSON-LD")
        return None
    except Exception as e:
        print(f" Error extrayendo JSON-LD: {e}")
        return None


def _extract_products_from_json(data):
    """Extrae productos de estructuras JSON-LD variadas (dict, list, @graph)"""
    products = []
    
    def process_item(item):
        if not isinstance(item, dict):
            return
        # Buscar tipo Product o que tenga 'name' y 'offers'
        item_type = item.get('@type', '').lower()
        if item_type == 'product' or ('name' in item and ('offers' in item or 'image' in item)):
            # Normalizar campos
            product = {}
            product['name'] = item.get('name', '')
            product['description'] = item.get('description', '')
            product['sku'] = item.get('sku', '')
            product['image'] = item.get('image', '')
            product['url'] = item.get('url', '')
            product['brand'] = item.get('brand', {}).get('name', '') if isinstance(item.get('brand'), dict) else str(item.get('brand', ''))
            
            # Offers
            offers = item.get('offers', {})
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            if isinstance(offers, dict):
                product['price'] = offers.get('price', '')
                product['priceCurrency'] = offers.get('priceCurrency', 'MXN')
                product['availability'] = offers.get('availability', '')
                product['seller'] = offers.get('seller', {}).get('name', '') if isinstance(offers.get('seller'), dict) else ''
            
            # AggregateRating
            agg = item.get('aggregateRating', {})
            if isinstance(agg, dict):
                product['ratingValue'] = agg.get('ratingValue', '')
                product['reviewCount'] = agg.get('reviewCount', '')
            
            # Dimensiones
            for dim in ['weight', 'width', 'height', 'depth']:
                if dim in item:
                    product[dim] = item[dim]
            
            if product.get('name'):
                products.append(product)
        
        # Recursivamente buscar en @graph, @list, itemListElement
        for key in ['@graph', '@list', 'itemListElement', 'hasPart', 'isPartOf']:
            val = item.get(key)
            if isinstance(val, list):
                for sub in val:
                    process_item(sub)
            elif isinstance(val, dict):
                process_item(val)
    
    if isinstance(data, dict):
        process_item(data)
    elif isinstance(data, list):
        for item in data:
            process_item(item)
    
    return products


def extract_meta_data(driver):
    """Extrae datos de meta tags de Twitter/OpenGraph - versión mejorada"""
    try:
        meta_data = {}
        
        # Definir todos los meta tags a buscar con prioridad
        meta_selectors = {
            'title': [
                'meta[property="og:title"]',
                'meta[name="twitter:title"]',
                'meta[itemprop="name"]',
            ],
            'description': [
                'meta[property="og:description"]',
                'meta[name="twitter:description"]',
                'meta[name="description"]',
                'meta[itemprop="description"]',
            ],
            'image': [
                'meta[property="og:image"]',
                'meta[property="og:image:secure_url"]',
                'meta[name="twitter:image"]',
                'meta[name="twitter:image:src"]',
                'meta[itemprop="image"]',
            ],
            'price': [
                'meta[property="og:price:amount"]',
                'meta[property="product:price:amount"]',
                'meta[name="twitter:data1"]',
            ],
            'priceCurrency': [
                'meta[property="og:price:currency"]',
                'meta[property="product:price:currency"]',
                'meta[name="twitter:data2"]',
            ],
            'availability': [
                'meta[property="og:availability"]',
                'meta[property="product:availability"]',
            ],
            'sku': [
                'meta[property="og:sku"]',
                'meta[property="product:sku"]',
            ],
            'brand': [
                'meta[property="og:brand"]',
                'meta[property="product:brand"]',
            ],
        }
        
        for field, selectors in meta_selectors.items():
            for selector in selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        content = elements[0].get_attribute('content')
                        if content and content.strip():
                            meta_data[field] = content.strip()
                            print(f" Meta {field}: {content[:80]}...")
                            break
                except:
                    continue
        
        # También buscar en data-testid attributes para precio
        try:
            price_elements = driver.find_elements(By.CSS_SELECTOR, '[data-testid="price"] .andes-money-amount__fraction, .ui-pdp-price .andes-money-amount__fraction')
            for el in price_elements:
                text = el.text.strip()
                if text and 'price' not in meta_data:
                    meta_data['price'] = text.replace(',', '')
                    print(f" Meta price (DOM): {meta_data['price']}")
                    break
        except:
            pass
        
        print(f" Meta datos extraídos: {len(meta_data)} campos")
        return meta_data
    except Exception as e:
        print(f" Error extrayendo meta datos: {e}")
        return {}


def parse_description(description_text):
    """Parsea la descripción para extraer información específica de libros"""
    info = {}
    
    if not description_text:
        return info
    
    # Patrones para libros de MercadoLibre
    patterns = {
        'num_paginas': r'N[úu]mero de p[áa]ginas?\s*[:\-]?\s*(\d+)',
        'genero': r'G[ée]nero\s*[:\-]?\s*([^|.]+)',
        'subgenero': r'Subg[ée]nero\s*[:\-]?\s*([^|.]+)',
        'isbn': r'ISBN\s*[:\-]?\s*(\d[\d\-]{10,})',
        'volumen': r'Volumen del libro\s*[:\-]?\s*([^|.]+)',
        'autor': r'Autor\s*[:\-]?\s*([^|.]+)',
        'editorial': r'Editorial\s*[:\-]?\s*([^|.]+)',
        'idioma': r'Idioma\s*[:\-]?\s*([^|.]+)',
        'anio_publicacion': r'A[ñn]o de publicaci[óo]n\s*[:\-]?\s*(\d{4})',
        'tipo_tapa': r'Tipo de tapa\s*[:\-]?\s*([^|.]+)',
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, description_text, re.IGNORECASE)
        if match:
            info[key] = match.group(1).strip()
    
    # También buscar en formato JSON-LD description si viene estructurada
    if 'description' not in info and description_text:
        # Limpiar descripción para guardar
        info['descripcion_limpia'] = description_text[:500]
    
    return info


def extraer_informacion_libro(url, driver):
    """Extrae información completa del libro desde MercadoLibre - versión mejorada"""
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
        'fuente': 'mercadolibre.com.mx',
        'isbn': '',
        'genero': '',
        'subgenero': '',
        'volumen': '',
        'idioma': '',
        'anio_publicacion': '',
        'tipo_tapa': '',
        'rating': '',
        'review_count': '',
        'sku': '',
        'peso': '',
        'ancho': '',
        'alto': '',
    }
    
    try:
        print(f" Procesando: {url}")
        driver.get(url)
        
        # Verificar si fue redirected a página de verificación
        current_url = driver.current_url
        if "account-verification" in current_url or "captcha" in current_url:
            print(" MercadoLibre ha detectado el bot - intentando navegar directamente")
            driver.execute_script(f"window.location.href = '{url}'")
            time.sleep(3)
            current_url = driver.current_url
            
        print(f" URL actual: {current_url}")
        
        # Esperar a elementos específicos críticos - selectores modernos
        try:
            WebDriverWait(driver, 15).until(
                EC.any_of(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'h1.ui-pdp-title')),
                    EC.presence_of_element_located((By.CSS_SELECTOR, '.ui-pdp-price')),
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="price"]')),
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'meta[property="og:title"]')),
                    EC.presence_of_element_located((By.TAG_NAME, "title"))
                )
            )
            print(" Página cargada correctamente")
        except TimeoutException:
            print(" Timeout esperando elementos, continuando...")
        
        # Delay para permitir que JavaScript/React termine de hidratar
        time.sleep(4)
        
        # PRIORIDAD 1: JSON-LD (más estructurado y confiable)
        json_data = extract_json_data(driver)
        if json_data:
            print(" Datos JSON-LD encontrados")
            libro_info['nombre'] = json_data.get('name', '') or libro_info['nombre']
            libro_info['descripcion'] = json_data.get('description', '') or libro_info['descripcion']
            libro_info['sku'] = json_data.get('sku', '') or libro_info['sku']
            libro_info['rating'] = str(json_data.get('ratingValue', '')) or libro_info['rating']
            libro_info['review_count'] = str(json_data.get('reviewCount', '')) or libro_info['review_count']
            libro_info['peso'] = str(json_data.get('weight', '')) or libro_info['peso']
            libro_info['ancho'] = str(json_data.get('width', '')) or libro_info['ancho']
            libro_info['alto'] = str(json_data.get('height', '')) or libro_info['alto']
            
            # Imagen
            imagen_url = json_data.get('image', '')
            if imagen_url:
                if isinstance(imagen_url, list):
                    imagen_url = imagen_url[0] if imagen_url else ''
                libro_info['url_imagen'] = imagen_url
            
            # Precio desde offers
            offers = json_data.get('offers', {})
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            if isinstance(offers, dict):
                precio = offers.get('price', '')
                if precio:
                    libro_info['precio_original'] = str(precio)
                libro_info['priceCurrency'] = offers.get('priceCurrency', 'MXN')
                libro_info['availability'] = offers.get('availability', '')
            
            # Brand
            brand = json_data.get('brand', {})
            if isinstance(brand, dict):
                libro_info['editorial'] = brand.get('name', '') or libro_info['editorial']
        
        # PRIORIDAD 2: Meta tags (OpenGraph/Twitter) - muy confiables en ML moderno
        meta_data = extract_meta_data(driver)
        if meta_data:
            print(" Meta datos encontrados")
            
            # Título
            if not libro_info['nombre'] and meta_data.get('title'):
                libro_info['nombre'] = meta_data['title']
            
            # Imagen
            if not libro_info['url_imagen'] and meta_data.get('image'):
                libro_info['url_imagen'] = meta_data['image']
            
            # Precio
            if not libro_info['precio_original'] and meta_data.get('price'):
                libro_info['precio_original'] = meta_data['price'].replace(',', '')
            
            if meta_data.get('priceCurrency'):
                libro_info['priceCurrency'] = meta_data['priceCurrency']
            
            # Descripción y parsing de detalles del libro
            if meta_data.get('description'):
                parsed_info = parse_description(meta_data['description'])
                libro_info.update(parsed_info)
                libro_info['descripcion'] = meta_data['description']
            
            # Otros campos
            for field in ['availability', 'sku', 'brand']:
                if meta_data.get(field) and not libro_info.get(field):
                    libro_info[field] = meta_data[field]
        
        # PRIORIDAD 3: Selectores DOM modernos (fallback)
        # Título
        if not libro_info['nombre']:
            title_selectors = [
                'h1.ui-pdp-title',
                'h1[data-testid="product-title"]',
                'h1[class*="ui-pdp-title"]',
                '.ui-pdp-title',
                'meta[property="og:title"]',
                'meta[name="twitter:title"]',
                'title'
            ]
            
            for selector in title_selectors:
                try:
                    if selector.startswith('meta'):
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            title_text = elements[0].get_attribute('content')
                    else:
                        title_element = driver.find_element(By.CSS_SELECTOR, selector)
                        title_text = title_element.text.strip()
                    
                    if title_text and len(title_text) > 5:
                        libro_info['nombre'] = title_text
                        print(f" Título extraído ({selector}): {title_text[:60]}...")
                        break
                except:
                    continue
        
        # Imagen
        if not libro_info['url_imagen']:
            image_selectors = [
                '.ui-pdp-gallery img',
                '.ui-pdp-gallery__figure img',
                '[data-testid="gallery"] img',
                '[data-testid="product-image"]',
                '.ui-pdp-media__image',
                'meta[property="og:image"]',
                'meta[name="twitter:image"]',
            ]
            
            for selector in image_selectors:
                try:
                    if selector.startswith('meta'):
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            img_url = elements[0].get_attribute('content')
                    else:
                        img_element = driver.find_element(By.CSS_SELECTOR, selector)
                        img_url = img_element.get_attribute('src') or img_element.get_attribute('data-src')
                    
                    if img_url and 'http' in img_url:
                        libro_info['url_imagen'] = img_url
                        print(f" Imagen extraída ({selector}): {img_url[:80]}...")
                        break
                except:
                    continue
        
        # Precio - selectores modernos
        if not libro_info['precio_original']:
            price_selectors = [
                '.ui-pdp-price .andes-money-amount__fraction',
                '[data-testid="price"] .andes-money-amount__fraction',
                '.ui-pdp-price__main .andes-money-amount__fraction',
                '[class*="price"] .andes-money-amount__fraction',
                '.price-tag .andes-money-amount__fraction',
            ]
            
            for selector in price_selectors:
                try:
                    price_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for el in price_elements:
                        text = el.text.strip()
                        if text and re.search(r'\d', text):
                            price_clean = re.sub(r'[^\d.,]', '', text.replace('.', '').replace(',', ''))
                            if price_clean:
                                libro_info['precio_original'] = price_clean
                                print(f" Precio extraído ({selector}): {price_clean}")
                                break
                    if libro_info['precio_original']:
                        break
                except:
                    continue
        
        # También buscar centavos si existen
        if libro_info['precio_original']:
            try:
                cents_selectors = [
                    '.ui-pdp-price .andes-money-amount__cents',
                    '[data-testid="price"] .andes-money-amount__cents',
                    '.andes-money-amount__cents',
                ]
                for selector in cents_selectors:
                    try:
                        cents_el = driver.find_element(By.CSS_SELECTOR, selector)
                        cents_text = cents_el.text.strip()
                        if cents_text and cents_text.isdigit():
                            libro_info['precio_original'] += f".{cents_text}"
                            break
                    except:
                        continue
            except:
                pass
        
        # Envío / Shipping
        shipping_selectors = [
            '.ui-pdp-media__shipping',
            '.ui-pdp-shipping',
            '[data-testid="shipping"]',
            '.shipping-info',
            '.ui-pdp-delivery',
            '[class*="shipping"]',
        ]
        
        for selector in shipping_selectors:
            try:
                shipping_element = driver.find_element(By.CSS_SELECTOR, selector)
                shipping_text = shipping_element.text.strip()
                if shipping_text and ('gratis' in shipping_text.lower() or 'envío' in shipping_text.lower() or 'entrega' in shipping_text.lower()):
                    libro_info['tiempo_entrega'] = shipping_text
                    print(f" Envío: {shipping_text[:80]}")
                    break
            except:
                continue
        
        # Descripción completa (para parsing adicional)
        if not libro_info['descripcion']:
            desc_selectors = [
                '.ui-pdp-description__content',
                '.ui-pdp-description',
                '[data-testid="description"]',
                '.ui-pdp-collapsable__content',
            ]
            for selector in desc_selectors:
                try:
                    desc_element = driver.find_element(By.CSS_SELECTOR, selector)
                    desc_text = desc_element.text.strip()
                    if desc_text and len(desc_text) > 20:
                        parsed_info = parse_description(desc_text)
                        libro_info.update(parsed_info)
                        libro_info['descripcion'] = desc_text
                        print(f" Descripción extraída ({selector}): {len(desc_text)} chars")
                        break
                except:
                    continue
        
        # Especificaciones técnicas / atributos
        try:
            spec_selectors = [
                '.ui-pdp-specs__table tr',
                '.andes-table tr',
                '[data-testid="specs"] tr',
                '.ui-vpp-striped-specs tr',
            ]
            for selector in spec_selectors:
                try:
                    rows = driver.find_elements(By.CSS_SELECTOR, selector)
                    for row in rows:
                        text = row.text.lower()
                        if 'autor' in text or 'author' in text:
                            cells = row.find_elements(By.TAG_NAME, 'td')
                            if len(cells) > 1 and not libro_info['autor']:
                                libro_info['autor'] = cells[1].text.strip()
                        elif 'editorial' in text or 'publisher' in text:
                            cells = row.find_elements(By.TAG_NAME, 'td')
                            if len(cells) > 1 and not libro_info['editorial']:
                                libro_info['editorial'] = cells[1].text.strip()
                        elif 'página' in text or 'page' in text:
                            cells = row.find_elements(By.TAG_NAME, 'td')
                            if len(cells) > 1 and not libro_info['num_paginas']:
                                libro_info['num_paginas'] = cells[1].text.strip()
                        elif 'isbn' in text:
                            cells = row.find_elements(By.TAG_NAME, 'td')
                            if len(cells) > 1 and not libro_info['isbn']:
                                libro_info['isbn'] = cells[1].text.strip()
                        elif 'idioma' in text or 'language' in text:
                            cells = row.find_elements(By.TAG_NAME, 'td')
                            if len(cells) > 1 and not libro_info['idioma']:
                                libro_info['idioma'] = cells[1].text.strip()
                        elif 'año' in text or 'year' in text:
                            cells = row.find_elements(By.TAG_NAME, 'td')
                            if len(cells) > 1 and not libro_info['anio_publicacion']:
                                libro_info['anio_publicacion'] = cells[1].text.strip()
                        elif 'tapa' in text or 'cover' in text or 'binding' in text:
                            cells = row.find_elements(By.TAG_NAME, 'td')
                            if len(cells) > 1 and not libro_info['tipo_tapa']:
                                libro_info['tipo_tapa'] = cells[1].text.strip()
                except:
                    continue
        except:
            pass
        
        # 4. CALCULAR PRECIO CON ENVÍO
        try:
            precio_original = libro_info.get('precio_original', '0')
            if precio_original:
                # Limpiar: quitar puntos de miles, comas decimales
                precio_clean = re.sub(r'[^\d.,]', '', str(precio_original))
                precio_clean = precio_clean.replace('.', '').replace(',', '.')
                precio_numerico = float(precio_clean)
                
                # Si ya tiene envío gratis (precio final), no sumar
                tiene_envio_gratis = False
                if libro_info.get('tiempo_entrega'):
                    tiene_envio_gratis = 'gratis' in libro_info['tiempo_entrega'].lower()
                
                if not tiene_envio_gratis:
                    precio_con_envio = precio_numerico + ganancia_envio
                else:
                    precio_con_envio = precio_numerico
                
                precio_final = int(precio_con_envio)
                if precio_final % 10 != 9:
                    precio_final = (precio_final // 10) * 10 + 9
                
                libro_info['precio_con_envio'] = str(precio_final)
                print(f" Precio calculado: ${precio_numerico:,.0f} + ${ganancia_envio if not tiene_envio_gratis else 0} = ${precio_final:,.0f}")
            
        except Exception as e:
            print(f" Error calculando precio: {e}")
            libro_info['precio_con_envio'] = libro_info.get('precio_original', '0')
        
        # Debug: Intentar extraer título de última instancia
        if not libro_info['nombre']:
            try:
                page_title = driver.title.strip()
                if page_title and len(page_title) > 10:
                    # Limpiar título de página (quita " | MercadoLibre" etc)
                    page_title = re.sub(r'\s*\|\s*MercadoLibre.*$', '', page_title)
                    libro_info['nombre'] = page_title
                    print(f" Título extraído del page title: {page_title[:60]}...")
                else:
                    libro_info['nombre'] = "Producto MercadoLibre"
                    print(" No se pudo extraer título, usando valor por defecto")
            except:
                libro_info['nombre'] = "Producto MercadoLibre"
        
        print(" Información extraída:")
        for key, value in libro_info.items():
            if value:
                print(f"   {key}: {str(value)[:80]}{'...' if len(str(value)) > 80 else ''}")
        
        print(f"🔗 URL actual: {driver.current_url}")
        
        return libro_info
        
    except Exception as e:
        print(f" Error procesando {url}: {e}")
        import traceback
        traceback.print_exc()
        return libro_info


def configurar_firebase():
    """Configura Firebase para almacenamiento de datos"""
    if not FIREBASE_AVAILABLE:
        print(" Firebase no disponible - saltando configuración")
        return None
    
    try:
        if not firebase_admin._apps:
            if not os.path.exists(SERVICE_ACCOUNT_KEY_PATH):
                print(f" Archivo de credenciales no encontrado: {SERVICE_ACCOUNT_KEY_PATH}")
                return None
            
            cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
            firebase_admin.initialize_app(cred, {
                'projectId': PROJECT_ID,
            })
            print(" Firebase inicializado correctamente")
        
        db = firestore.client()
        return db
        
    except Exception as e:
        print(f" Error configurando Firebase: {e}")
        return None


def insertar_en_firebase(db, libro_info):
    """Inserta información del libro en Firebase con batch operations"""
    if not db:
        print(" Base de datos no disponible - saltando inserción")
        return False
    
    try:
        precio_numerico = libro_info.get('precio_con_envio', '0')
        precio_clean = re.sub(r'[^\d.]', '', str(precio_numerico))
        
        book_data = {
            'contacto': '',
            'disponible': 'true',
            'link': libro_info.get('url_libro', ''),
            'portada': libro_info.get('url_imagen', ''),
            'precio': precio_clean,
            'rating': '4.8',
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
        
        print(f" Libro insertado en Firebase con ID: {doc_ref.id}")
        return True
        
    except Exception as e:
        print(f" Error insertando en Firebase: {e}")
        return False


def main():
    """Función principal del scraper de MercadoLibre optimizado"""
    print(" Iniciando MercadoLibre Book Scraper (OPTIMIZADO)")
    print("=" * 60)
    
    # Configurar carpetas
    os.makedirs(CARPETA_IMAGENES, exist_ok=True)
    
    # Configurar Selenium - SIN headless para debugging
    print(" Configurando navegador optimizado...")
    driver = configurar_selenium(headless=False)
    if not driver:
        print(" No se pudo configurar el navegador")
        return
    
    # Configurar Firebase
    print(" Configurando Firebase...")
    db = configurar_firebase()
    
    # Configurar generador de anuncios
    fb_generator = None
    if GENERAR_ANUNCIOS_FACEBOOK and PIL_AVAILABLE:
        try:
            fb_generator = FacebookAdGenerator()
            print(" Generador de anuncios Facebook configurado")
        except ImportError:
            print(" No se pudo configurar el generador de anuncios")
    
    try:
        # URL proporcionada por el usuario
        print("\n Usando URL proporcionada:")
        url_input = "https://www.mercadolibre.com.mx/libro-efectos-de-la-meditacion-en-la-psique-y-el-cerebro/up/MLMU4003431988#polycard_client=search-desktop&be_origin=backend&overlay_label=not_apply&search_layout=grid&position=1&type=product&tracking_id=50cdde02-d2ac-4146-a26f-032a2c6d2c5f&wid=MLM2727152537&sid=search"
        print(f"URL: {url_input}")
        
        # Opción para cambiar URL si es necesario
        cambiar = input("\n¿Usar otra URL? (Enter para continuar, o pega nueva URL): ").strip()
        if cambiar and cambiar.lower() not in ['enter', '']:
            url_input = cambiar
        
        if 'mercadolibre.com' not in url_input:
            print("La URL debe ser de MercadoLibre")
            return
        
        print(f"\n Procesando: {url_input}")
        
        # Extraer información
        libro_info = extraer_informacion_libro(url_input, driver)
        
        if not libro_info.get('nombre'):
            print(" No se pudo extraer información del libro")
            return
        
        print(f"\n Libro procesado: {libro_info['nombre']}")
        
        # Guardar en archivo de texto
        output_file = os.path.join(CARPETA_IMAGENES, "libro_mercadolibre.txt")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("INFORMACIÓN DEL LIBRO - MERCADOLIBRE (OPTIMIZADO)\n")
            f.write("=" * 60 + "\n\n")
            for key, value in libro_info.items():
                if value:
                    f.write(f"{key.replace('_', ' ').title()}: {value}\n")
            f.write(f"\nFecha de extracción: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        print(f" Información guardada en: {output_file}")
        
        # Descargar imagen de portada
        if DESCARGAR_IMAGENES and libro_info.get('url_imagen'):
            try:
                print(" Descargando imagen de portada...")
                response = requests.get(libro_info['url_imagen'], timeout=10)
                if response.status_code == 200:
                    image_path = os.path.join(CARPETA_IMAGENES, "portada_libro.jpg")
                    with open(image_path, 'wb') as f:
                        f.write(response.content)
                    print(f" Imagen descargada: {image_path}")
            except Exception as e:
                print(f" Error descargando imagen: {e}")
        
        # Generar anuncio de Facebook
        if GENERAR_ANUNCIOS_FACEBOOK and fb_generator:
            try:
                print(" Generando anuncio de Facebook...")
                ad_path = os.path.join(CARPETA_IMAGENES, "fb_ad_mercadolibre.png")
                if fb_generator.generate_ad(libro_info, ad_path):
                    print(f" Anuncio generado: {ad_path}")
            except Exception as e:
                print(f" Error generando anuncio: {e}")
        
        # Insertar en Firebase
        if db:
            print(" Insertando en Firebase...")
            insertar_en_firebase(db, libro_info)
        
        print(f"\n Proceso completado exitosamente!")
        print(f" Archivos guardados en: {CARPETA_IMAGENES}")
        print(f" Tiempo de ejecución optimizado")
        
    except KeyboardInterrupt:
        print("\nProceso cancelado por el usuario")
    except Exception as e:
        print(f"\n Error inesperado: {e}")
    finally:
        if driver:
            driver.quit()
            print(" Navegador cerrado")


if __name__ == "__main__":
    main()