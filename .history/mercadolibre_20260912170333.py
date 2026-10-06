import time
import random
import requests
import os
import re
import math
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime, timedelta

# Imports para generación de imágenes de Facebook
try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
    import io
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("⚠️ PIL no disponible - generación de imágenes publicitarias desactivada")

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
search_term = ""  # Término de búsqueda (se solicitará por teclado)
#informacionEntrega = "✓ ENTREGA DE 3 A 7 DÍAS A PARTIR DE LA FECHA DE COMPRA"
informacionEntrega = "✓ ENTREGA DE 3 A 4 DÍAs A PARTIR DE LA FECHA DE COMPRA"

informacionEstado = "✓ Nuevo."
NUMERO_PRODUCTOS = 20  # Número de productos a extraer
ganancia_envio = 150  # Ganancia fija por envío para calcular el precio final

DESCARGAR_IMAGENES = True  # Parámetro para activar/desactivar descarga de imágenes
ABRIR_ENLACES = True  # Parámetro para activar/desactivar apertura de enlaces
NAVEGAR_A_DETALLE = True  # True para extraer info adicional navegando a cada libro
GENERAR_ANUNCIOS_FACEBOOK = True  # Parámetro para activar/desactivar generación de imágenes publicitarias

# FUNCIONES AUXILIARES PARA SIMULAR UN HUMANO
# -----------------------------------------------
CARPETA_IMAGENES = ""  # Se define dinámicamente por cada búsqueda


class FacebookAdGenerator:
    """Generador de piezas publicitarias limpias y consistentes para Facebook."""

    def __init__(self, output_dir="busquedas"):
        self.output_dir = output_dir
        # El formato horizontal funciona bien en el feed y conserva la portada legible.
        self.width = 900
        self.height = 630

        # Paletas sobrias: alto contraste, fondos neutros y un solo color de acción.
        self.color_schemes = [
            {
                'bg': '#F6F7F8',
                'surface': '#FFFFFF',
                'header': '#132238',
                'text': '#172033',
                'secondary': '#627085',
                'accent': '#DDE8E8',
                'price': '#176B63',
                'button': '#176B63',
                'border': '#D9E0E7'
            },
            {
                'bg': '#F8F7F4',
                'surface': '#FFFFFF',
                'header': '#2B2F36',
                'text': '#252A33',
                'secondary': '#6E7178',
                'accent': '#EEE7DB',
                'price': '#8A5A2B',
                'button': '#8A5A2B',
                'border': '#E3DDD3'
            },
            {
                'bg': '#F4F6FA',
                'surface': '#FFFFFF',
                'header': '#1E2D4A',
                'text': '#18233A',
                'secondary': '#65738B',
                'accent': '#E2E9F5',
                'price': '#315C9B',
                'button': '#315C9B',
                'border': '#D8E0EC'
            }
        ]

    def download_image(self, url, timeout=10):
        """Descarga y valida una portada sin propagar errores de red."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=timeout)
            if response.status_code == 200:
                image = Image.open(io.BytesIO(response.content))
                image.load()
                return image
            return None
        except Exception as e:
            print(f"Error descargando imagen: {e}")
            return None

    def create_clean_background(self, colors):
        """Crea la base editorial con una cabecera sobria y aire visual."""
        image = Image.new('RGB', (self.width, self.height), colors['bg'])
        draw = ImageDraw.Draw(image)

        header_height = 74
        draw.rectangle([0, 0, self.width, header_height], fill=colors['header'])
        draw.rectangle([0, header_height - 3, self.width, header_height], fill=colors['price'])
        brand_font = self.get_default_font(24, bold=True)
        label_font = self.get_default_font(11)
        draw.text((34, 19), "LOS LIBROS DE LA BUENA MEMORIA", font=brand_font, fill='#FFFFFF')
        draw.text((36, 48), "Selección editorial · compra con confianza", font=label_font, fill='#C9D3E0')
        return image

    def hex_to_rgb(self, hex_color):
        """Convierte color hexadecimal a RGB"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def wrap_text(self, text, max_width, font):
        """Divide texto en líneas sin cortar palabras."""
        words = str(text).split()
        lines = []
        current_line = []
        for word in words:
            test_line = ' '.join(current_line + [word])
            if self.text_width(test_line, font) <= max_width:
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

    def text_width(self, text, font):
        bbox = font.getbbox(text)
        return bbox[2] - bbox[0]

    def get_default_font(self, size, bold=False):
        """Obtiene una tipografía legible; prioriza familias modernas del sistema."""
        try:
            font_paths = (
                ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/calibrib.ttf",
                 "C:/Windows/Fonts/arialbd.ttf"] if bold else
                ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/calibri.ttf",
                 "C:/Windows/Fonts/arial.ttf"]
            )
            for font_path in font_paths:
                if os.path.exists(font_path):
                    return ImageFont.truetype(font_path, size)
            return ImageFont.load_default()
        except Exception:
            return ImageFont.load_default()

    def draw_card(self, image, box, fill, border, radius=16):
        """Dibuja una tarjeta con sombra suave sin ensuciar la composición."""
        shadow = Image.new('RGBA', image.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_box = [box[0] + 3, box[1] + 5, box[2] + 3, box[3] + 5]
        shadow_draw.rounded_rectangle(shadow_box, radius=radius, fill=(20, 32, 51, 24))
        shadow = shadow.filter(ImageFilter.GaussianBlur(7))
        image.paste(shadow, (0, 0), shadow)
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle(box, radius=radius, fill=fill, outline=border, width=1)

    def paste_cover(self, image, cover_image, box, colors):
        """Ajusta la portada a su tarjeta conservando proporciones y calidad."""
        draw = ImageDraw.Draw(image)
        inner = [box[0] + 24, box[1] + 24, box[2] - 24, box[3] - 24]
        if not cover_image:
            draw.rounded_rectangle(inner, radius=8, fill=colors['accent'])
            placeholder_font = self.get_default_font(18, bold=True)
            label = "PORTADA\nNO DISPONIBLE"
            draw.multiline_text((inner[0] + 28, (inner[1] + inner[3]) // 2 - 24), label,
                                font=placeholder_font, fill=colors['secondary'], spacing=5)
            return

        cover = cover_image.convert('RGBA')
        available_w, available_h = inner[2] - inner[0], inner[3] - inner[1]
        scale = min(available_w / cover.width, available_h / cover.height)
        new_size = (max(1, int(cover.width * scale)), max(1, int(cover.height * scale)))
        cover = cover.resize(new_size, Image.Resampling.LANCZOS)
        x = inner[0] + (available_w - new_size[0]) // 2
        y = inner[1] + (available_h - new_size[1]) // 2
        cover_shadow = Image.new('RGBA', (new_size[0] + 12, new_size[1] + 12), (0, 0, 0, 0))
        ImageDraw.Draw(cover_shadow).rounded_rectangle([6, 6, new_size[0] + 4, new_size[1] + 4],
                                                        radius=4, fill=(15, 23, 38, 55))
        cover_shadow = cover_shadow.filter(ImageFilter.GaussianBlur(5))
        image.paste(cover_shadow, (x - 6, y - 3), cover_shadow)
        image.paste(cover, (x, y), cover)

    def generate_ad(self, book_info, scheme_index=0):
        """Genera una pieza publicitaria sobria a partir de la información disponible."""
        if not PIL_AVAILABLE:
            print("⚠️ PIL no disponible - no se puede generar imagen publicitaria")
            return None
        try:
            colors = self.color_schemes[scheme_index % len(self.color_schemes)]
            image = self.create_clean_background(colors)
            draw = ImageDraw.Draw(image)
            cover_box = [34, 101, 349, 570]
            info_box = [375, 101, 866, 570]
            self.draw_card(image, cover_box, colors['surface'], colors['border'])
            self.draw_card(image, info_box, colors['surface'], colors['border'])

            cover_image = self.download_image(book_info['url_imagen']) if book_info.get('url_imagen') else None
            self.paste_cover(image, cover_image, cover_box, colors)

            title_font = self.get_default_font(29, bold=True)
            author_font = self.get_default_font(17)
            price_font = self.get_default_font(42, bold=True)
            detail_font = self.get_default_font(14)
            label_font = self.get_default_font(12, bold=True)
            info_x, content_width = 407, 425
            y_pos = 139

            draw.text((info_x, y_pos), "LIBRO DISPONIBLE", font=label_font, fill=colors['price'])
            y_pos += 31
            title = str(book_info.get('nombre') or 'Libro disponible')
            title_lines = self.wrap_text(title, content_width, title_font)
            visible_title = title_lines[:3]
            if len(title_lines) > 3:
                visible_title[-1] = visible_title[-1].rstrip(' .') + '…'
            for line in visible_title:
                draw.text((info_x, y_pos), line, font=title_font, fill=colors['text'])
                y_pos += 37

            autor = str(book_info.get('autor') or '').strip()
            if autor and autor.lower() != 'no disponible':
                y_pos += 9
                author_lines = self.wrap_text(f"Por {autor}", content_width, author_font)
                for line in author_lines[:2]:
                    draw.text((info_x, y_pos), line, font=author_font, fill=colors['secondary'])
                    y_pos += 24

            y_pos = max(y_pos + 17, 285)
            draw.line([(info_x, y_pos), (info_x + content_width, y_pos)], fill=colors['border'], width=1)
            y_pos += 21
            draw.text((info_x, y_pos), "PRECIO FINAL", font=label_font, fill=colors['secondary'])
            y_pos += 21
            precio = str(book_info.get('precio_con_envio') or 'Consultar precio')
            draw.text((info_x, y_pos), precio, font=price_font, fill=colors['price'])

            benefits = ["Envío gratis a todo el país", informacionEstado, informacionEntrega]
            price_bbox = draw.textbbox((info_x, y_pos), precio, font=price_font)
            benefit_y = price_bbox[3] + 13
            for benefit in benefits:
                text = str(benefit).replace('✓', '').strip()
                draw.ellipse([info_x, benefit_y + 5, info_x + 8, benefit_y + 13], fill=colors['price'])
                lines = self.wrap_text(text, content_width - 20, detail_font)
                visible_lines = lines[:2]
                draw.multiline_text((info_x + 18, benefit_y), '\n'.join(visible_lines),
                                    font=detail_font, fill=colors['text'], spacing=2)
                benefit_y += 21 * len(visible_lines) + 5

            button_y = max(510, benefit_y + 5)
            button_box = [info_x, button_y, info_x + 238, button_y + 40]
            draw.rounded_rectangle(button_box, radius=8, fill=colors['button'])
            button_text = "DISPONIBLE"
            button_font = self.get_default_font(15, bold=True)
            button_x = info_x + (238 - self.text_width(button_text, button_font)) // 2
            draw.text((button_x, button_y + 11), button_text, font=button_font, fill='#FFFFFF')

            footer_font = self.get_default_font(11)
            footer_text = "Precio y disponibilidad sujetos a cambios."
            draw.text((34, 594), footer_text, font=footer_font, fill=colors['secondary'])

            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)
            filename = f"fb_ad_{book_info.get('numero', 'book')}_{title[:15]}.png"
            filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
            filepath = os.path.join(self.output_dir, filename)
            image.save(filepath, 'PNG', quality=95, optimize=True)
            print(f"🎨 Imagen publicitaria guardada: {filepath}")
            return filepath
        except Exception as e:
            print(f"❌ Error generando imagen publicitaria: {e}")
            import traceback
            traceback.print_exc()
            return None




# -----------------------------------------------
# CONFIGURACIÓN Y UTILIDADES
# -----------------------------------------------

WAIT_TIMEOUT = 15
DETAIL_TIMEOUT = 15
MAX_RETRIES = 2
REQUEST_TIMEOUT = 20

# Una sesión HTTP reutilizable evita abrir una conexión nueva por cada imagen.
HTTP_SESSION = requests.Session()
HTTP_SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
})


def human_pause(a=0.15, b=0.45):
    """Pausa aleatoria entre acciones."""
    time.sleep(random.uniform(a, b))


def limpiar_nombre_archivo(nombre):
    """Genera un nombre de archivo seguro para Windows."""
    nombre = str(nombre or "libro")
    nombre = re.sub(r'[<>:"/\\|?*]', '', nombre)
    nombre = re.sub(r'\s+', '_', nombre.strip())
    nombre = nombre.rstrip(". ")
    if not nombre:
        nombre = "libro"
    # Windows tiene nombres reservados.
    if nombre.upper() in {"CON", "PRN", "AUX", "NUL"}:
        nombre = f"_{nombre}"
    return nombre[:80]


def normalizar_url(url):
    """Convierte URLs relativas de Buscalibre en URLs absolutas."""
    if not url:
        return None
    url = str(url).strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return "https://www.buscalibre.com.mx" + url
    return url


def extraer_numero_precio(texto):
    """
    Extrae un precio de textos como:
    '$ 399.00', '$399', '$1,299.90', 'MXN 1,299'.
    Para México se prioriza el último separador cuando parece decimal.
    """
    if not texto:
        return None

    texto = str(texto).replace("\xa0", " ").strip()
    # Buscar candidatos con separadores de miles/decimales.
    candidatos = re.findall(r"\d[\d.,]*", texto)
    if not candidatos:
        return None

    candidato = max(candidatos, key=lambda x: len(re.sub(r"\D", "", x)))

    try:
        if "," in candidato and "." in candidato:
            # El separador que aparece al final suele ser el decimal.
            if candidato.rfind(",") > candidato.rfind("."):
                candidato = candidato.replace(".", "").replace(",", ".")
            else:
                candidato = candidato.replace(",", "")
        elif "," in candidato:
            partes = candidato.split(",")
            # 1,299 -> miles; 299,90 -> decimal.
            if len(partes[-1]) == 2:
                candidato = "".join(partes[:-1]) + "." + partes[-1]
            else:
                candidato = candidato.replace(",", "")
        elif candidato.count(".") > 1:
            candidato = candidato.replace(".", "")
        elif "." in candidato:
            parte_decimal = candidato.split(".")[-1]
            if len(parte_decimal) == 3:
                candidato = candidato.replace(".", "")

        valor = float(candidato)
        return valor if valor > 0 else None
    except (ValueError, TypeError):
        return None


def calcular_precio_final(precio_original):
    """Suma el costo/ganancia de envío y aplica la regla de redondeo existente."""
    precio_valor = extraer_numero_precio(precio_original)
    if precio_valor is None:
        return "Precio no disponible"

    precio_actualizado = precio_valor + ganancia_envio
    unidad = int(precio_actualizado) % 10

    if 1 <= unidad <= 5:
        precio_actualizado = int(precio_actualizado // 10) * 10 - 1
    elif 6 <= unidad <= 9:
        precio_actualizado = int(precio_actualizado // 10) * 10 + 9
    elif unidad == 0:
        precio_actualizado -= 1

    return f"$ {int(precio_actualizado):,}"


def calcular_tiempo_entrega():
    """Fallback de entrega cuando Buscalibre no muestra la fecha/tiempo."""
    fecha_actual = datetime.now()
    fecha_minima = fecha_actual + timedelta(weeks=3)
    fecha_maxima = fecha_actual + timedelta(weeks=4)

    meses = {
        1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
        5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
        9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
    }

    fecha_min_str = f"{fecha_minima.day} de {meses[fecha_minima.month]} de {fecha_minima.year}"
    fecha_max_str = f"{fecha_maxima.day} de {meses[fecha_maxima.month]} de {fecha_maxima.year}"
    return f"Entre el {fecha_min_str} y el {fecha_max_str}"


# -----------------------------------------------
# FIREBASE
# -----------------------------------------------

def initialize_firebase():
    """Inicializa Firebase Admin SDK de forma segura."""
    if not FIREBASE_AVAILABLE:
        return None

    try:
        if not firebase_admin._apps:
            cred_path = SERVICE_ACCOUNT_KEY_PATH

            # Acepta tanto una ruta absoluta/relativa ya completa como
            # una ruta cuyo archivo vive dentro de implemented_firestore.
            if not os.path.isabs(cred_path) and not os.path.exists(cred_path):
                cred_path = os.path.join("implemented_firestore", cred_path)

            if not os.path.exists(cred_path):
                print(f"❌ No se encontró archivo de credenciales: {cred_path}")
                return None

            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            print("🔥 Firebase inicializado correctamente")

        return firestore.client()

    except Exception as e:
        print(f"❌ Error inicializando Firebase: {e}")
        return None


def _limpiar_precio_para_firebase(precio):
    """Guarda el precio como texto numérico sin símbolos cuando es posible."""
    valor = extraer_numero_precio(precio)
    if valor is None:
        return str(precio or "")
    return str(int(valor)) if float(valor).is_integer() else str(valor)


def insert_book_to_firebase(db, libro_info):
    """
    Inserta o actualiza un libro por URL.

    Mejora importante:
    - evita duplicar el mismo libro cada vez que se vuelve a buscar;
    - conserva la estructura 'books' que ya utiliza tu aplicación.
    """
    if not db or not FIREBASE_AVAILABLE:
        return None

    try:
        url_libro = libro_info.get("url_libro", "").strip()
        if not url_libro:
            return None

        book_data = {
            "contacto": "",
            "disponible": "true",
            "link": url_libro,
            "portada": libro_info.get("url_imagen", ""),
            "precio": _limpiar_precio_para_firebase(
                libro_info.get("precio_con_envio", "")
            ),
            "rating": str(libro_info.get("rating", "4.5")),
            "textFromQuery": search_term,
            "titulo": libro_info.get("nombre", ""),
            "autor": libro_info.get("autor", ""),
            "editorial": libro_info.get("editorial", ""),
            "num_paginas": libro_info.get("num_paginas", ""),
            "isbn10": libro_info.get("isbn10", ""),
            "isbn13": libro_info.get("isbn13", ""),
            "idioma": libro_info.get("idioma", ""),
            "descripcion": libro_info.get("descripcion", ""),
            "tiempo_entrega": libro_info.get("tiempo_entrega", ""),
            "precio_original": libro_info.get("precio_original", ""),
            "fecha_actualizacion": datetime.now(),
            # Se conserva este campo para no romper documentos/consultas
            # que ya dependan de la estructura anterior.
            "fecha_agregado": datetime.now(),
            "fuente": "buscalibre.com.mx",
        }

        # Buscar por URL para no crear copias idénticas.
        query = db.collection("books").where("link", "==", url_libro).limit(1)
        docs = list(query.stream())

        if docs:
            doc_ref = docs[0].reference
            doc_ref.set(book_data, merge=True)
            print(f"♻️ Libro actualizado en Firebase: {doc_ref.id}")
            return doc_ref.id

        doc_ref = db.collection("books").add(book_data)[1]
        print(f"🔥 Libro insertado en Firebase con ID: {doc_ref.id}")
        return doc_ref.id

    except Exception as e:
        print(f"❌ Error insertando/actualizando Firebase: {e}")
        return None


# -----------------------------------------------
# EXTRACCIÓN DE URLS Y METADATOS
# -----------------------------------------------

def extraer_url_libro(producto):
    """Extrae la URL principal de un resultado de Buscalibre."""
    selectores = [
        "a[href*='/libro-']",
        "h3.nombre a",
        ".imagen a",
        "a[href*='/product']",
        ".box-producto a",
    ]

    try:
        for selector in selectores:
            try:
                enlaces = producto.find_elements(By.CSS_SELECTOR, selector)
                for enlace in enlaces:
                    url = normalizar_url(enlace.get_attribute("href"))
                    if url and (
                        "buscalibre.com.mx" in url
                        and ("libro-" in url or "/product" in url)
                    ):
                        return url
            except (NoSuchElementException, StaleElementReferenceException):
                continue
    except Exception as e:
        print(f"⚠️ Error extrayendo URL del producto: {e}")

    return None


def _texto_elemento(driver, selectores, min_len=1, max_len=None):
    """Devuelve el primer texto útil encontrado entre varios selectores."""
    for selector in selectores:
        try:
            elementos = driver.find_elements(By.CSS_SELECTOR, selector)
            for elemento in elementos:
                texto = elemento.text.strip()
                if len(texto) >= min_len and (max_len is None or len(texto) <= max_len):
                    return texto
        except Exception:
            continue
    return None


def _atributo_elemento(driver, selectores, atributos=("src", "data-src", "data-original")):
    """Devuelve el primer atributo útil encontrado."""
    for selector in selectores:
        try:
            elementos = driver.find_elements(By.CSS_SELECTOR, selector)
            for elemento in elementos:
                for atributo in atributos:
                    valor = elemento.get_attribute(atributo)
                    if valor:
                        valor = normalizar_url(valor)
                        if valor:
                            return valor
        except Exception:
            continue
    return None


def _extraer_isbn(texto):
    """Extrae ISBN-13 o ISBN-10 de un texto."""
    if not texto:
        return None, None

    texto = str(texto)

    # ISBN-13, permitiendo guiones/espacios.
    for candidato in re.findall(r"(?:97[89][-\s]?\d(?:[-\s]?\d){9,11})", texto):
        limpio = re.sub(r"[-\s]", "", candidato)
        if len(limpio) == 13 and limpio.isdigit():
            return None, limpio

    # ISBN-10, incluyendo X.
    for candidato in re.findall(r"\b(?:\d[-\s]?){9}[\dXx]\b", texto):
        limpio = re.sub(r"[-\s]", "", candidato).upper()
        if len(limpio) == 10:
            return limpio, None

    return None, None


def _normalizar_isbn(isbn):
    if not isbn:
        return ""
    isbn = re.sub(r"[^0-9Xx]", "", str(isbn)).upper()
    return isbn


def extraer_isbn_detalle(driver):
    """
    Busca ISBN en metadatos visibles y en meta tags.
    Devuelve (isbn10, isbn13).
    """
    candidatos = []

    # Texto visible de zonas típicas.
    selectores = [
        ".ficha",
        ".metadata",
        ".book-details",
        ".product-details",
        "[class*='ficha']",
        "[class*='metadata']",
        "body",
    ]

    for selector in selectores:
        try:
            elementos = driver.find_elements(By.CSS_SELECTOR, selector)
            for elemento in elementos[:3]:
                texto = elemento.text.strip()
                if texto:
                    candidatos.append(texto)
        except Exception:
            pass

    # Meta tags y JSON-LD simplificado.
    for selector in [
        "meta[name='isbn']",
        "meta[property='book:isbn']",
        "meta[itemprop='isbn']",
        "[itemprop='isbn']",
    ]:
        try:
            elementos = driver.find_elements(By.CSS_SELECTOR, selector)
            for elemento in elementos:
                valor = (
                    elemento.get_attribute("content")
                    or elemento.get_attribute("value")
                    or elemento.text
                )
                if valor:
                    candidatos.append(valor)
        except Exception:
            pass

    isbn10 = ""
    isbn13 = ""

    for candidato in candidatos:
        i10, i13 = _extraer_isbn(candidato)
        if i10 and not isbn10:
            isbn10 = _normalizar_isbn(i10)
        if i13 and not isbn13:
            isbn13 = _normalizar_isbn(i13)
        if isbn10 and isbn13:
            break

    return isbn10, isbn13


def _extraer_dato_ficha(driver, etiquetas):
    """
    Busca un dato en filas de fichas sin depender de una sola estructura HTML.
    """
    filas_selectores = [
        ".ficha .row",
        ".metadata .row",
        ".book-details .row",
        ".product-details .row",
        "[class*='ficha'] .row",
        "[class*='metadata'] .row",
        "tr",
        "li",
    ]

    etiquetas = [e.lower() for e in etiquetas]

    for selector in filas_selectores:
        try:
            filas = driver.find_elements(By.CSS_SELECTOR, selector)
            for fila in filas:
                texto = " ".join(fila.text.split())
                texto_lower = texto.lower()

                if not any(etiqueta in texto_lower for etiqueta in etiquetas):
                    continue

                # Preferir enlaces/elementos de valor.
                valores = fila.find_elements(
                    By.CSS_SELECTOR,
                    ".value, .data, .box, td:nth-child(2), "
                    ".col-xs-7, .col-md-7, a"
                )

                for valor_elemento in valores:
                    valor = " ".join(valor_elemento.text.split())
                    if valor and not any(
                        valor.lower() == etiqueta for etiqueta in etiquetas
                    ):
                        return valor

                # Fallback: quitar la etiqueta del texto.
                partes = re.split(r"[:\n]", texto, maxsplit=1)
                if len(partes) == 2:
                    valor = partes[1].strip()
                    if valor:
                        return valor

        except Exception:
            continue

    return "No disponible"


# -----------------------------------------------
# DETALLE DE LIBRO
# -----------------------------------------------

def extraer_detalle_libro(driver, url_libro, numero_producto):
    """
    Abre el libro en una pestaña temporal, espera contenido real y extrae
    información bibliográfica/comercial. Siempre intenta restaurar la pestaña
    original aunque falle una extracción.
    """
    if not url_libro:
        return None

    ventana_original = None
    ventana_detalle = None

    try:
        ventana_original = driver.current_window_handle
        ventanas_antes = set(driver.window_handles)

        # Evitar interpolar la URL directamente en JavaScript.
        driver.execute_script("window.open(arguments[0], '_blank');", url_libro)

        WebDriverWait(driver, 5).until(
            lambda d: len(d.window_handles) > len(ventanas_antes)
        )

        ventanas_nuevas = [h for h in driver.window_handles if h not in ventanas_antes]
        ventana_detalle = ventanas_nuevas[-1] if ventanas_nuevas else driver.window_handles[-1]
        driver.switch_to.window(ventana_detalle)

        # Cargar la URL explícitamente también permite detectar redirecciones.
        try:
            WebDriverWait(driver, DETAIL_TIMEOUT).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            print(f"⚠️ La página #{numero_producto} tardó en completar carga.")

        # Esperar a que exista al menos un h1 o el contenedor de producto.
        try:
            WebDriverWait(driver, DETAIL_TIMEOUT).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    "h1, .tituloProducto, [class*='tituloProducto'], .product-title"
                ))
            )
        except TimeoutException:
            print(f"⚠️ No apareció el título del libro #{numero_producto}.")

        human_pause(0.6, 1.2)

        info = {
            "nombre": f"Libro #{numero_producto}",
            "precio_original": "Precio no disponible",
            "precio_con_envio": "Precio no disponible",
            "url_imagen_hq": None,
            "autor": "No disponible",
            "editorial": "No disponible",
            "num_paginas": "No disponible",
            "descripcion": "No disponible",
            "tiempo_entrega": calcular_tiempo_entrega(),
            "isbn10": "",
            "isbn13": "",
            "idioma": "",
            "rating": "",
        }

        # ---------- TÍTULO ----------
        nombre = _texto_elemento(
            driver,
            [
                "p.tituloProducto",
                ".tituloProducto",
                "p[class*='tituloProducto']",
                "[class*='tituloProducto']",
                "h1.titulo-libro",
                "h1[class*='titulo']",
                ".nombre-producto h1",
                ".product-title h1",
                ".libro-info h1",
                ".producto-titulo",
                ".libro-titulo",
                ".nombre-libro",
                "h1",
            ],
            min_len=4,
            max_len=250,
        )

        if nombre:
            palabras_excluidas = [
                "opinion", "review", "comentario", "reseña", "crítica",
                "valoración", "calificación", "rating", "puntuación",
            ]
            if not any(p in nombre.lower() for p in palabras_excluidas):
                info["nombre"] = nombre

        # ---------- PRECIO ----------
        precio_texto = _texto_elemento(
            driver,
            [
                ".box-precio-v2 strong",
                ".precio",
                ".price",
                ".product-price",
                ".costo",
                "[class*='precio']",
                "[class*='price']",
                ".valor",
                ".amount",
            ],
            min_len=1,
            max_len=150,
        )

        if precio_texto and extraer_numero_precio(precio_texto) is not None:
            info["precio_original"] = precio_texto
            info["precio_con_envio"] = calcular_precio_final(precio_texto)

        # ---------- IMAGEN ----------
        info["url_imagen_hq"] = _atributo_elemento(
            driver,
            [
                ".imagen-producto img",
                ".product-image img",
                ".libro-imagen img",
                ".cover img",
                ".portada img",
                ".imagen-grande img",
                "img[alt*='portada']",
                "img[src*='cover']",
                "img[src*='libro']",
                "img",
            ],
        )

        # ---------- FICHA ----------
        info["autor"] = _extraer_dato_ficha(
            driver, ["autor", "author", "writer", "escritor"]
        )
        info["editorial"] = _extraer_dato_ficha(
            driver, ["editorial", "publisher", "editor"]
        )
        info["num_paginas"] = _extraer_dato_ficha(
            driver, ["páginas", "paginas", "pages", "número de páginas", "num páginas"]
        )
        info["idioma"] = _extraer_dato_ficha(
            driver, ["idioma", "language", "lengua"]
        )

        # ---------- ISBN ----------
        isbn10, isbn13 = extraer_isbn_detalle(driver)
        info["isbn10"] = isbn10
        info["isbn13"] = isbn13

        # ---------- DESCRIPCIÓN ----------
        descripcion = _texto_elemento(
            driver,
            [
                ".descripcion",
                ".resumen",
                "[class*='descripcion']",
                "[class*='resumen']",
                ".synopsis",
                ".summary",
            ],
            min_len=10,
            max_len=10000,
        )
        if descripcion:
            info["descripcion"] = (
                descripcion[:500] + "..." if len(descripcion) > 500 else descripcion
            )

        # ---------- RATING ----------
        rating_texto = _texto_elemento(
            driver,
            [
                "[class*='rating']",
                "[class*='valoracion']",
                "[class*='calificacion']",
            ],
            min_len=1,
            max_len=50,
        )
        if rating_texto:
            match = re.search(r"\d+(?:[.,]\d+)?", rating_texto)
            if match:
                info["rating"] = match.group(0).replace(",", ".")

        # ---------- ENVÍO ----------
        tiempo_envio = _texto_elemento(
            driver,
            [
                ".tiempoEnvio",
                "[class*='tiempoEnvio']",
                "[id*='tiempoEnvio']",
                ".tiempo-envio",
                ".shipping-time",
                ".delivery-time",
                ".envio-tiempo",
                "[class*='tiempo-envio']",
                "[class*='shipping']",
                "[class*='delivery']",
            ],
            min_len=6,
            max_len=300,
        )
        if tiempo_envio:
            info["tiempo_entrega"] = " ".join(tiempo_envio.split())

        print(
            f"   📚 {info['nombre'][:70]}"
            f" | ISBN13: {info['isbn13'] or 'no encontrado'}"
        )

        return info

    except Exception as e:
        print(f"❌ Error al extraer libro #{numero_producto}: {e}")
        return None

    finally:
        # Limpieza robusta: nunca dejar la pestaña de detalle abierta por error.
        try:
            if ventana_detalle and ventana_detalle in driver.window_handles:
                driver.switch_to.window(ventana_detalle)
                driver.close()
        except Exception:
            pass

        try:
            if ventana_original and ventana_original in driver.window_handles:
                driver.switch_to.window(ventana_original)
        except Exception:
            pass


# -----------------------------------------------
# IMÁGENES
# -----------------------------------------------

def crear_carpeta_imagenes():
    """Crea la carpeta de salida."""
    if not CARPETA_IMAGENES:
        return None

    os.makedirs(CARPETA_IMAGENES, exist_ok=True)
    return CARPETA_IMAGENES


def actualizar_contexto_busqueda(nuevo_termino):
    """Actualiza término y carpeta de salida."""
    global search_term, CARPETA_IMAGENES

    search_term = " ".join(nuevo_termino.strip().split())
    carpeta_termino = limpiar_nombre_archivo(search_term).replace(" ", "_")
    CARPETA_IMAGENES = os.path.join("busquedas", f"book_images_{carpeta_termino}")


def descargar_imagen(url_imagen, nombre_libro, numero_producto):
    """Descarga una portada con reintentos y validación básica."""
    if not DESCARGAR_IMAGENES or not url_imagen:
        return None

    carpeta = crear_carpeta_imagenes()
    if not carpeta:
        return None

    nombre_limpio = limpiar_nombre_archivo(nombre_libro)
    extension = os.path.splitext(urlparse(url_imagen).path)[1].lower()

    if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
        extension = ".jpg"

    ruta_archivo = os.path.join(
        carpeta,
        f"libro_{numero_producto:02d}_{nombre_limpio}{extension}"
    )

    if os.path.exists(ruta_archivo) and os.path.getsize(ruta_archivo) > 0:
        return ruta_archivo

    headers = {
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": "https://www.buscalibre.com.mx/",
    }

    for intento in range(1, MAX_RETRIES + 2):
        try:
            response = HTTP_SESSION.get(
                url_imagen,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "").lower()
            if not content_type.startswith("image/"):
                print(f"⚠️ La URL no devolvió una imagen: {url_imagen}")
                return None

            with open(ruta_archivo, "wb") as f:
                f.write(response.content)

            if os.path.getsize(ruta_archivo) == 0:
                os.remove(ruta_archivo)
                return None

            return ruta_archivo

        except requests.RequestException as e:
            print(f"⚠️ Error descargando imagen #{numero_producto}, intento {intento}: {e}")
            if intento <= MAX_RETRIES:
                human_pause(0.8, 1.5)

        except OSError as e:
            print(f"❌ Error guardando imagen #{numero_producto}: {e}")
            return None

    return None


# -----------------------------------------------
# CHROME
# -----------------------------------------------

def setup_chrome_driver():
    """Configura Chrome con opciones estables para Selenium."""
    chrome_options = Options()

    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option(
        "excludeSwitches",
        ["enable-automation"]
    )
    chrome_options.add_experimental_option(
        "useAutomationExtension",
        False
    )
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--lang=es-MX")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # Mantener esta mejora de compatibilidad con páginas que inspeccionan webdriver.
    try:
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
    except Exception:
        pass

    driver.set_page_load_timeout(40)
    driver.set_script_timeout(20)

    return driver


def cerrar_pestanas_extra(driver):
    """Cierra pestañas secundarias y deja activa la primera."""
    try:
        handles = driver.window_handles
        if not handles:
            return

        principal = handles[0]

        for handle in handles[1:]:
            try:
                driver.switch_to.window(handle)
                driver.close()
            except Exception:
                pass

        if principal in driver.window_handles:
            driver.switch_to.window(principal)

    except Exception:
        pass


# -----------------------------------------------
# BÚSQUEDA
# -----------------------------------------------

def realizar_busqueda(driver, termino):
    """
    Ejecuta una búsqueda en Buscalibre y devuelve URLs únicas.
    Primero recopila las URLs y después visita los detalles.
    Esto evita problemas de elementos 'stale' al cambiar de página.
    """
    url_inicio = "https://www.buscalibre.com.mx/"

    driver.get(url_inicio)
    human_pause(1.5, 3)

    wait = WebDriverWait(driver, WAIT_TIMEOUT)

    search_selectors = [
        (By.ID, "inputSearch"),
        (By.NAME, "q"),
        (By.CSS_SELECTOR, "input[type='search']"),
        (By.CSS_SELECTOR, "input[placeholder*='Buscar']"),
        (By.XPATH, "//input[contains(@class, 'search')]"),
    ]

    search_box = None

    for by, selector in search_selectors:
        try:
            search_box = wait.until(
                EC.element_to_be_clickable((by, selector))
            )
            break
        except TimeoutException:
            continue

    if search_box is None:
        raise RuntimeError("No se encontró el campo de búsqueda de Buscalibre.")

    try:
        search_box.clear()
    except Exception:
        pass

    search_box.click()

    # No usamos pyautogui: Selenium es suficiente y evita depender de esa librería.
    search_box.send_keys(termino)
    human_pause(0.4, 0.9)

    search_button = None
    button_selectors = [
        (By.ID, "botonBuscarHeader"),
        (By.CSS_SELECTOR, "button[type='submit']"),
        (By.CSS_SELECTOR, "input[type='submit']"),
    ]

    for by, selector in button_selectors:
        try:
            search_button = wait.until(
                EC.element_to_be_clickable((by, selector))
            )
            break
        except TimeoutException:
            continue

    if search_button:
        search_button.click()
    else:
        # Fallback: Enter en el campo.
        search_box.send_keys("\n")

    human_pause(2.5, 4)

    try:
        wait.until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, ".box-producto")
            )
        )
    except TimeoutException:
        print("⚠️ No aparecieron productos dentro del tiempo esperado.")
        return []

    productos = driver.find_elements(By.CSS_SELECTOR, ".box-producto")

    urls = []
    urls_vistas = set()

    for producto in productos:
        url_libro = extraer_url_libro(producto)
        if url_libro and url_libro not in urls_vistas:
            urls_vistas.add(url_libro)
            urls.append(url_libro)

        if len(urls) >= NUMERO_PRODUCTOS:
            break

    print(
        f"✅ Resultados encontrados: {len(productos)} | "
        f"URLs únicas seleccionadas: {len(urls)}"
    )

    return urls


# -----------------------------------------------
# ARCHIVO TXT
# -----------------------------------------------

def preparar_archivo_txt():
    carpeta = crear_carpeta_imagenes()
    if not carpeta:
        return None

    nombre = f"libros_{limpiar_nombre_archivo(search_term).replace(' ', '_')}.txt"
    ruta = os.path.join(carpeta, nombre)

    try:
        if os.path.exists(ruta):
            os.remove(ruta)
        return ruta
    except OSError as e:
        print(f"⚠️ No se pudo preparar TXT: {e}")
        return None


def guardar_libro_txt(archivo_txt, libro, numero):
    if not archivo_txt:
        return

    info_adicional = ""

    if libro.get("autor") != "No disponible":
        info_adicional += f"👤 Autor: {libro.get('autor')}\n"

    if libro.get("editorial") != "No disponible":
        info_adicional += f"🏢 Editorial: {libro.get('editorial')}\n"

    if libro.get("num_paginas") != "No disponible":
        info_adicional += f"📄 Páginas: {libro.get('num_paginas')}\n"

    if libro.get("isbn13"):
        info_adicional += f"🔢 ISBN-13: {libro.get('isbn13')}\n"
    elif libro.get("isbn10"):
        info_adicional += f"🔢 ISBN-10: {libro.get('isbn10')}\n"

    info_texto = f"""
{"=" * 70}
📖 LIBRO #{numero}
{"=" * 70}
📕 Nombre: {libro.get('nombre', 'No disponible')}
{info_adicional}💵 Precio original: {libro.get('precio_original', 'No disponible')}
💵 Precio total con envío: {libro.get('precio_con_envio', 'No disponible')}
🚚 Tiempo de entrega: {libro.get('tiempo_entrega', calcular_tiempo_entrega())}
🔗 URL: {libro.get('url_libro', '')}
{"=" * 70}

"""

    try:
        with open(archivo_txt, "a", encoding="utf-8") as f:
            f.write(info_texto)
    except OSError as e:
        print(f"⚠️ Error guardando TXT: {e}")


# -----------------------------------------------
# ANUNCIOS
# -----------------------------------------------

def generar_anuncio(ad_generator, libro, numero):
    if not GENERAR_ANUNCIOS_FACEBOOK or not PIL_AVAILABLE:
        return None

    try:
        ad_info = {
            "numero": numero,
            "nombre": libro.get("nombre", ""),
            "autor": libro.get("autor", ""),
            "precio_con_envio": libro.get("precio_con_envio", ""),
            "url_imagen": libro.get("url_imagen", ""),
        }

        return ad_generator.generate_ad(
            ad_info,
            scheme_index=max(0, numero - 1)
        )

    except Exception as e:
        print(f"⚠️ Error generando anuncio para libro #{numero}: {e}")
        return None


# -----------------------------------------------
# PROCESAMIENTO DE UNA BÚSQUEDA
# -----------------------------------------------

def procesar_busqueda(driver, db_firebase, termino):
    actualizar_contexto_busqueda(termino)

    print("\n" + "=" * 75)
    print(f"🔎 BUSCANDO: {search_term}")
    print("=" * 75)

    archivo_txt = preparar_archivo_txt()

    if DESCARGAR_IMAGENES:
        print(f"📁 Carpeta de imágenes: {CARPETA_IMAGENES}")

    urls_libros = realizar_busqueda(driver, search_term)

    if not urls_libros:
        print("❌ No se encontraron libros.")
        if archivo_txt:
            with open(archivo_txt, "w", encoding="utf-8") as f:
                f.write(f"No se encontraron resultados para: {search_term}\n")
        return []

    productos_info = []
    ad_generator = (
        FacebookAdGenerator(output_dir=CARPETA_IMAGENES)
        if GENERAR_ANUNCIOS_FACEBOOK and PIL_AVAILABLE
        else None
    )

    for i, url_libro in enumerate(urls_libros, 1):
        print(f"\n📖 Procesando libro #{i}/{len(urls_libros)}")

        try:
            info_completa = extraer_detalle_libro(
                driver,
                url_libro,
                i
            )

            if not info_completa:
                print(f"❌ No se pudo extraer libro #{i}")
                continue

            nombre = info_completa.get("nombre", f"Libro #{i}")
            url_imagen = info_completa.get("url_imagen_hq")

            archivo_imagen = None
            if url_imagen:
                archivo_imagen = descargar_imagen(
                    url_imagen,
                    nombre,
                    i
                )

            libro = {
                "numero": i,
                "nombre": nombre,
                "precio_original": info_completa.get(
                    "precio_original",
                    "Precio no disponible"
                ),
                "precio_con_envio": info_completa.get(
                    "precio_con_envio",
                    "Precio no disponible"
                ),
                "url_imagen": url_imagen,
                "archivo_imagen": archivo_imagen,
                "url_libro": url_libro,
                "tiempo_entrega": info_completa.get(
                    "tiempo_entrega",
                    calcular_tiempo_entrega()
                ),
                "autor": info_completa.get("autor", "No disponible"),
                "editorial": info_completa.get("editorial", "No disponible"),
                "num_paginas": info_completa.get("num_paginas", "No disponible"),
                "descripcion": info_completa.get("descripcion", "No disponible"),
                "isbn10": info_completa.get("isbn10", ""),
                "isbn13": info_completa.get("isbn13", ""),
                "idioma": info_completa.get("idioma", ""),
                "rating": info_completa.get("rating", ""),
            }

            productos_info.append(libro)

            # Firebase.
            if db_firebase:
                insert_book_to_firebase(db_firebase, libro)

            # Facebook.
            if ad_generator:
                ad_path = generar_anuncio(
                    ad_generator,
                    libro,
                    i
                )
                if ad_path:
                    libro["imagen_publicitaria"] = ad_path

            # TXT.
            guardar_libro_txt(
                archivo_txt,
                libro,
                i
            )

            print(
                f"   💵 {libro['precio_con_envio']} | "
                f"👤 {libro['autor']} | "
                f"🔢 {libro['isbn13'] or libro['isbn10'] or 'ISBN no encontrado'}"
            )

            human_pause(0.8, 1.5)

        except Exception as e:
            print(f"⚠️ Error procesando libro #{i}: {e}")
            continue

    if archivo_txt:
        try:
            with open(archivo_txt, "a", encoding="utf-8") as f:
                f.write(
                    "\n✅ Precio y disponibilidad pueden variar con los días.\n"
                )
        except OSError:
            pass

    print("\n" + "-" * 75)
    print(f"✅ Búsqueda terminada. Libros procesados: {len(productos_info)}")
    print("-" * 75)

    return productos_info


# -----------------------------------------------
# MAIN
# -----------------------------------------------

def main():
    print("🚀 Iniciando navegador Chrome...")

    driver = None

    try:
        driver = setup_chrome_driver()

        print("🔥 Inicializando conexión a Firebase...")
        db_firebase = initialize_firebase()

        if db_firebase:
            print("✅ Firebase listo")
        else:
            print("⚠️ Firebase no disponible - se continuará con archivos locales")

        print(
            "\n💬 Escribe un término de búsqueda y presiona Enter. "
            "Escribe 'salir' para terminar."
        )

        while True:
            try:
                termino_ingresado = input("\n🔎 Término de búsqueda: ").strip()
            except EOFError:
                break

            if not termino_ingresado:
                print("⚠️ Debes ingresar un término válido.")
                continue

            if termino_ingresado.lower() in {"salir", "exit", "q"}:
                print("👋 Saliendo por solicitud del usuario.")
                break

            try:
                procesar_busqueda(
                    driver,
                    db_firebase,
                    termino_ingresado
                )
            except TimeoutException:
                print(
                    "❌ Timeout durante la búsqueda. "
                    "Se intentará continuar con el siguiente término."
                )
            except Exception as e:
                print(f"❌ Error inesperado en la búsqueda: {e}")
                import traceback
                traceback.print_exc()

            # Dejar el navegador limpio para la siguiente búsqueda.
            try:
                cerrar_pestanas_extra(driver)
            except Exception:
                pass

            print(
                "\n💡 Extracción completada. "
                "Puedes ingresar otro término o escribir 'salir'."
            )

    except KeyboardInterrupt:
        print("\n⚠️ Interrupción detectada por el usuario.")

    except Exception as e:
        print(f"❌ Error al iniciar el navegador: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if driver:
            print("🔒 Cerrando navegador...")
            try:
                driver.quit()
            except Exception:
                pass
            print("✅ Navegador cerrado")


if __name__ == "__main__":
    main()
