"""Scraper público de libros de Mercado Libre México, sin API ni inicio de sesión."""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import logging
import os
import re
import sys
import time
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlsplit, urlunsplit, quote

import requests
from PIL import Image, ImageDraw, ImageFont
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

OUTPUT_DIR = Path(__file__).parent / "busquedas" / "book_images_mercadolibre"
LOG_FILE = Path(__file__).parent / "logs" / "mercadolibre.log"
REQUEST_TIMEOUT = 20
LOGGER = logging.getLogger("mercadolibre")


class MercadoLibreError(RuntimeError):
    """Error recuperable al cargar o interpretar una publicación."""


def configurar_log() -> None:
    """Registra errores en UTF-8 sin depender de la codificación de la terminal."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8")],
        force=True,
    )


def _url_segura_para_log(url: str) -> str:
    """No guarda parámetros ni fragmentos que puedan identificar una sesión."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _validar_url_producto(url: str) -> None:
    parts = urlsplit(url)
    if not re.fullmatch(r"(?:www\.)?mercadolibre\.com(?:\.mx)?", parts.netloc, re.I):
        raise MercadoLibreError("La URL debe pertenecer a Mercado Libre.")
    # /gz/cart es una página de carrito, no una ficha de producto para extraer.
    if "/up/" not in parts.path.lower() and not re.search(r"\bMLM\d+\b", parts.path, re.I):
        raise MercadoLibreError("La URL debe ser la ficha de un producto (por ejemplo, una URL que contenga '/up/').")


def _conectar_a_chrome_abierto(debugger_address: str) -> webdriver.Chrome:
    """Attach to a Chrome explicitly opened with remote debugging enabled."""
    address = debugger_address.removeprefix("http://").removeprefix("https://").rstrip("/")
    try:
        response = requests.get(f"http://{address}/json/version", timeout=3)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise MercadoLibreError(
            "No hay un Chrome disponible para adjuntar en "
            f"{address}. Inícialo con --remote-debugging-port antes de usar --usar-chrome-abierto."
        ) from exc
    options = Options()
    options.debugger_address = address
    try:
        driver = webdriver.Chrome(options=options)
        # It is important not to call quit() on a browser that belongs to the user.
        setattr(driver, "_mercadolibre_attached_browser", True)
        return driver
    except WebDriverException as exc:
        raise MercadoLibreError(f"No fue posible adjuntarse al Chrome abierto: {exc.msg}") from exc


class _ProductHTMLParser(HTMLParser):
    """Recolecta metadatos, JSON-LD y texto sin dependencias adicionales."""
    def __init__(self) -> None:
        super().__init__()
        self.meta: Dict[str, str] = {}
        self.json_ld: list[str] = []
        self.text: list[str] = []
        self._in_json, self._in_script, self._script_parts = False, False, []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        attr = {key.lower(): value or "" for key, value in attrs}
        if tag == "meta":
            key = attr.get("property") or attr.get("name")
            if key and attr.get("content"):
                self.meta[key.lower()] = attr["content"].strip()
        elif tag == "script":
            self._in_script = True
            if attr.get("type", "").lower() == "application/ld+json":
                self._in_json, self._script_parts = True, []

    def handle_data(self, data: str) -> None:
        if self._in_json:
            self._script_parts.append(data)
        elif not self._in_script and (clean := " ".join(data.split())):
            self.text.append(clean)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_json:
            self.json_ld.append("".join(self._script_parts))
            self._in_json = False
        if tag == "script":
            self._in_script = False


def _first_string(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return next((found for item in value if (found := _first_string(item))), "")
    if isinstance(value, dict):
        return _first_string(value.get("url") or value.get("contentUrl"))
    return ""


def _find_product(value: Any) -> Optional[Dict[str, Any]]:
    if isinstance(value, dict):
        kind = value.get("@type", "")
        if kind == "Product" or (isinstance(kind, list) and "Product" in kind):
            return value
        for child in value.values():
            if found := _find_product(child):
                return found
    if isinstance(value, list):
        for child in value:
            if found := _find_product(child):
                return found
    return None


def _details(description: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    labels = {
        "autor": r"Autor\s*[:|-]?\s*([^|.]+)",
        "editorial": r"Editorial\s*[:|-]?\s*([^|.]+)",
        "idioma": r"Idioma\s*[:|-]?\s*([^|.]+)",
        "anio_publicacion": r"Año de publicación\s*[:|-]?\s*(\d{4})",
        "tipo_tapa": r"(?:Tapa del libro|Tipo de tapa)\s*[:|-]?\s*([^|.]+)",
    }
    for key, pattern in labels.items():
        if match := re.search(pattern, description, re.IGNORECASE):
            result[key] = match.group(1).strip()
    return result


def _shipping_text(page_text: str) -> str:
    """Obtiene sólo el resumen de entrega, sin arrastrar el resto de la ficha."""
    match = re.search(r"(?:Envío gratis|Llega|Entrega)[^.]{0,180}", page_text, re.IGNORECASE)
    if not match:
        return "No disponible"
    value = match.group(0)
    for marker in ("Más detalles", "Retira", "Comprar ahora", "Agregar al carrito", "Vendido por"):
        value = value.split(marker, 1)[0]
    return value.strip(" -·")[:140] or "No disponible"


def extraer_desde_html(html: str, url: str) -> Dict[str, str]:
    """Extrae los datos estables del HTML recibido desde la URL del libro."""
    parser = _ProductHTMLParser()
    parser.feed(html)
    product: Dict[str, Any] = {}
    for raw in parser.json_ld:
        try:
            product = _find_product(json.loads(raw)) or product
        except json.JSONDecodeError:
            pass
    meta = parser.meta
    description = product.get("description") or meta.get("og:description") or meta.get("twitter:description") or ""
    offers = product.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    title = (product.get("name") or meta.get("twitter:title") or meta.get("og:title") or "").strip()
    title = re.sub(r"\s*-\s*\$[\d,.]+$", "", title)
    if not title and (match := re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)):
        title = re.sub(r"<[^>]+>", " ", match.group(1)).strip()
    price = re.sub(r"[^0-9.,]", "", str(offers.get("price", "")))
    if not price and (match := re.search(r"og:title[^>]*content=\"[^\"]*?\$\s*([\d,.]+)", html, re.I)):
        price = match.group(1)
    text = " ".join(parser.text)
    condition = re.search(r"\b(Nuevo|Usado|Reacondicionado)\b", text, re.I)
    details = _details(unescape(description))
    image = _first_string(product.get("image")) or meta.get("og:image") or meta.get("twitter:image") or ""
    return {
        "nombre": unescape(title), "precio": price, "moneda": (offers.get("priceCurrency") if isinstance(offers, dict) else "") or "MXN",
        "url_imagen": image, "descripcion": unescape(description), "condicion": condition.group(1).capitalize() if condition else "No disponible",
        "envio": _shipping_text(text), "url_libro": url,
        "autor": details.get("autor", "No disponible"), "editorial": details.get("editorial", "No disponible"),
        "idioma": details.get("idioma", "No disponible"), "anio_publicacion": details.get("anio_publicacion", "No disponible"),
        "tipo_tapa": details.get("tipo_tapa", "No disponible"),
    }


def abrir_chrome_y_extraer(
    url: str,
    user_data_dir: Optional[Path] = None,
    profile: str = "Default",
    usar_perfil: bool = False,
    debugger_address: Optional[str] = None,
) -> Dict[str, str]:
    """Abre una publicación en Chrome visible; la consulta pública no requiere login."""
    _validar_url_producto(url)
    if debugger_address:
        if usar_perfil:
            raise MercadoLibreError("Use sólo una opción: --usar-chrome-abierto o --usar-perfil-chrome.")
        driver = _conectar_a_chrome_abierto(debugger_address)
        LOGGER.info("Adjuntado al Chrome abierto en %s.", debugger_address)
    else:
        options = Options()
        options.add_argument("--start-maximized")  # Deliberadamente no se usa --headless.
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        if usar_perfil:
            if not user_data_dir:
                raise MercadoLibreError("Indica el directorio de datos de Chrome para usar un perfil.")
            if not user_data_dir.is_dir():
                raise MercadoLibreError(f"No existe el directorio de perfil de Chrome: {user_data_dir}")
            options.add_argument(f"--user-data-dir={user_data_dir}")
            options.add_argument(f"--profile-directory={profile}")
            LOGGER.info("Abriendo Chrome con el perfil '%s'.", profile)
        else:
            LOGGER.info("Abriendo Chrome en modo público; no se solicita ni se usa una cuenta.")
        try:
            driver = webdriver.Chrome(options=options)
        except WebDriverException as exc:
            original_message = str(exc)
            LOGGER.exception("Chrome no pudo iniciarse con el perfil '%s': %s", profile, original_message)
            message = original_message.splitlines()[0]
            if usar_perfil and any(marker in original_message.lower() for marker in ("user data directory", "singleton", "devtoolsactiveport", "chrome failed to start")):
                message = ("El perfil de Chrome está ocupado. Ciérralo antes de usar --usar-perfil-chrome, "
                           "o ejecuta sin esa opción para consultar la publicación pública sin iniciar sesión.")
            raise MercadoLibreError(f"No fue posible abrir Chrome: {message}") from exc
    try:
        LOGGER.info("Cargando publicación: %s", _url_segura_para_log(url))
        driver.get(url)
        try:
            WebDriverWait(driver, 20).until(lambda browser: browser.execute_script("return document.readyState") == "complete")
        except TimeoutException:
            pass
        data = extraer_desde_html(driver.page_source, driver.current_url)
        if not data["nombre"]:
            raise MercadoLibreError("No se encontró un producto en la página cargada.")
        LOGGER.info("Extracción terminada: %s", _url_segura_para_log(driver.current_url))
        return data
    finally:
        if not getattr(driver, "_mercadolibre_attached_browser", False):
            driver.quit()


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    for name in (["arialbd.ttf", "Arial Bold.ttf"] if bold else ["arial.ttf", "Arial.ttf"]):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _lines(text: str, max_width: int, font: ImageFont.ImageFont, draw: ImageDraw.ImageDraw) -> Iterable[str]:
    line = ""
    for word in str(text or "No disponible").split():
        candidate = f"{line} {word}".strip()
        if not line or draw.textlength(candidate, font=font) <= max_width:
            line = candidate
        else:
            yield line
            line = word
    if line:
        yield line


def generar_imagen_resultado(data: Dict[str, str], output: Path) -> Path:
    """Crea una tarjeta PNG con portada y datos extraídos, sin datos inventados."""
    canvas = Image.new("RGB", (1200, 630), "#f5f5f5")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, 1200, 88), fill="#ffe600")
    draw.text((48, 25), "Mercado Libre · Libro encontrado", font=_font(34, True), fill="#333333")
    cover = Image.new("RGB", (340, 430), "#ffffff")
    if data.get("url_imagen"):
        try:
            response = requests.get(data["url_imagen"], timeout=REQUEST_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            image = Image.open(io.BytesIO(response.content)).convert("RGB")
            image.thumbnail((300, 390))
            cover.paste(image, ((340 - image.width) // 2, (430 - image.height) // 2))
        except (requests.RequestException, OSError):
            pass
    canvas.paste(cover, (48, 140)); draw.rectangle((48, 140, 388, 570), outline="#dddddd", width=2)
    x, y, width = 440, 135, 710
    for line in list(_lines(data.get("nombre", ""), width, _font(32, True), draw))[:3]:
        draw.text((x, y), line, font=_font(32, True), fill="#222222"); y += 42
    y += 12
    price_text = f"$ {data['precio']} {data.get('moneda') or 'MXN'}" if data.get("precio") else "Precio no disponible"
    draw.text((x, y), price_text, font=_font(38, True), fill="#00a650"); y += 66
    values = [("Autor", data.get("autor")), ("Estado", data.get("condicion")), ("Envío", data.get("envio")), ("Editorial", data.get("editorial")), ("Año", data.get("anio_publicacion")), ("Tapa", data.get("tipo_tapa"))]
    for label, value in values:
        for line in _lines(f"{label}: {value or 'No disponible'}", width, _font(22), draw):
            draw.text((x, y), line, font=_font(22), fill="#222222"); y += 28
        y += 8
        if y > 575: break
    output.parent.mkdir(parents=True, exist_ok=True); canvas.save(output, "PNG")
    return output


# =============================================================================
# SEARCH FUNCTIONALITY - Nueva funcionalidad de búsqueda por palabras clave
# =============================================================================

SEARCH_URL = "https://listado.mercadolibre.com.mx/{slug}"

# Concurrency control: only 1 Selenium search at a time
_search_semaphore = asyncio.Semaphore(1)


def _build_search_url(query: str) -> str:
    """Construye la URL de búsqueda pública con el formato del sitio de Mercado Libre."""
    normalized = " ".join(query.split())
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-") or "libros"
    return SEARCH_URL.format(slug=quote(slug))


def setup_chrome_driver(debugger_address: Optional[str] = None):
    """Configura el driver de Chrome para scraping."""
    if debugger_address:
        return _conectar_a_chrome_abierto(debugger_address)
    chrome_options = Options()
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    chrome_options.add_argument('--start-maximized')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver


def extraer_resultados_busqueda(driver, max_results: int = 5) -> List[Dict[str, Any]]:
    """Extrae la lista de resultados de la página de búsqueda."""
    results = []
    try:
        wait = WebDriverWait(driver, 15)
        # Esperar a que carguen los productos - selectores actualizados basados en diagnóstico real
        container_selectors = [
            "[class*='poly-card']",
            ".poly-card",
            ".ui-search-layout__item",
            "li.ui-search-layout__item",
            ".ui-search-result__wrapper",
            "[data-id]",
            ".shops__item",
        ]
        
        productos = []
        for selector in container_selectors:
            try:
                productos = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector)))
                if productos:
                    LOGGER.info(f"Contenedor de productos encontrado con: {selector} ({len(productos)} elementos)")
                    break
            except TimeoutException:
                continue
        
        if not productos:
            LOGGER.warning("No se encontraron contenedores de productos con ningún selector")
            return results
        
        # Filtrar solo visibles
        productos_visibles = [p for p in productos if p.is_displayed()]
        LOGGER.info(f"Productos visibles: {len(productos_visibles)} de {len(productos)}")
        
        for i, producto in enumerate(productos_visibles[:max_results]):
            try:
                data = extraer_dato_producto_lista(producto)
                if data:
                    results.append(data)
            except Exception as e:
                LOGGER.warning(f"Error extrayendo producto {i}: {e}")
                continue
    except TimeoutException:
        LOGGER.warning("Timeout esperando resultados de búsqueda")
    except Exception as e:
        LOGGER.warning(f"Error extrayendo resultados: {e}")
    return results


def _detectar_captcha_o_login(driver) -> bool:
    """Detecta si hay captcha, muro de login o verificación de cuenta en la página."""
    captcha_indicators = [
        "abuse-captcha-container",
        "abuse-china-wall",
        "recaptcha",
        "g-recaptcha",
        "#/captcha/wall",
        "account-verification",
        "andes-button--loud",  # Botón de verificación
    ]
    for indicator in captcha_indicators:
        try:
            if driver.find_elements(By.CSS_SELECTOR, indicator):
                return True
        except:
            continue
    # Verificar en URL
    current_url = driver.current_url.lower()
    if any(x in current_url for x in ["/captcha/", "recaptcha", "account-verification", "gz/account"]):
        return True
    page_source_lower = driver.page_source.lower()
    if any(x in page_source_lower for x in ["recaptcha", "verificación de cuenta", "verifica tu cuenta", "para continuar, verifica"]):
        return True
    return False


def extraer_dato_producto_lista(producto) -> Optional[Dict[str, Any]]:
    """Extrae datos básicos de un producto en la lista de resultados."""
    try:
        # Intentar obtener el link del producto - selectores actualizados
        url = None
        for selector in ["a[href*='MLM']", "a.poly-component__title", "a[href*='/up/']", ".poly-card__title a", ".ui-search-link"]:
            try:
                enlace = producto.find_element(By.CSS_SELECTOR, selector)
                url = enlace.get_attribute('href')
                if url and ('up/' in url or 'MLM' in url):
                    break
            except:
                continue
        
        # Título - selectores actualizados
        title = None
        for selector in [".poly-component__title", "h3", "[class*='title']", "a[class*='title']", ".poly-card__title", ".ui-search-item__title"]:
            try:
                elem = producto.find_element(By.CSS_SELECTOR, selector)
                title = elem.text.strip()
                if title and len(title) > 3:
                    break
            except:
                continue
        
        # Precio - selectores actualizados
        price = None
        for selector in [".poly-price__current", "[class*='price']", ".andes-money-amount", ".ui-search-price"]:
            try:
                elem = producto.find_element(By.CSS_SELECTOR, selector)
                price_text = elem.text.strip()
                if '$' in price_text or any(c.isdigit() for c in price_text):
                    price = price_text
                    break
            except:
                continue
        
        # Imagen
        image_url = None
        for selector in ["img.poly-component__picture", "img[class*='picture']", "img.ui-search-result-image", "img[class*='image']", "img"]:
            try:
                img_elem = producto.find_element(By.CSS_SELECTOR, selector)
                image_url = img_elem.get_attribute('src') or img_elem.get_attribute('data-src')
                if image_url and ('http' in image_url):
                    break
            except:
                continue
        
        # Estado/Condición
        condition = "No disponible"
        for selector in [".poly-component__condition", ".ui-search-item__condition", "[class*='condition']", ".ui-search-item__status"]:
            try:
                elem = producto.find_element(By.CSS_SELECTOR, selector)
                condition = elem.text.strip()
                if condition:
                    break
            except:
                continue
        
        # Envío - selector actualizado
        shipping = "No disponible"
        for selector in ["[class*='shipping']", ".poly-component__shipping", ".ui-search-item__shipping", "[class*='envio']", ".ui-search-item__delivery"]:
            try:
                elem = producto.find_element(By.CSS_SELECTOR, selector)
                shipping = elem.text.strip()
                if shipping:
                    break
            except:
                continue
        
        if not title or not url:
            return None
            
        return {
            "title": title,
            "url": url,
            "price": price,
            "image_url": image_url,
            "condition": condition,
            "shipping": shipping,
        }
    except Exception as e:
        LOGGER.warning(f"Error extrayendo dato de producto: {e}")
        return None


def extraer_detalle_completo(driver, url: str) -> Optional[Dict[str, Any]]:
    """Extrae información completa del producto abriendo su página de detalle."""
    if not url:
        return None
    try:
        ventana_original = driver.current_window_handle
        driver.execute_script(f"window.open('{url}', '_blank');")
        driver.switch_to.window(driver.window_handles[-1])
        
        time.sleep(2)
        
        # Usar el parser existente
        html = driver.page_source
        data = extraer_desde_html(html, driver.current_url)
        
        driver.close()
        driver.switch_to.window(ventana_original)
        return data
    except Exception as e:
        LOGGER.warning(f"Error extrayendo detalle completo: {e}")
        try:
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
        except:
            pass
        return None


def search_mercadolibre_sync(
    query: str,
    max_results: int = 5,
    ganancia_envio: float = 200,
    detailed: bool = False,
    debugger_address: Optional[str] = None,
) -> Dict[str, Any]:
    """Búsqueda síncrona en MercadoLibre."""
    driver = setup_chrome_driver(debugger_address)
    try:
        search_url = _build_search_url(query)
        LOGGER.info(f"Buscando en MercadoLibre: {search_url}")
        driver.get(search_url)
        
        # Wait for page to load and handle potential redirects
        time.sleep(3)
        
        # Check for verification/account pages and try to handle them
        max_wait = 30
        start_time = time.time()
        while time.time() - start_time < max_wait:
            current_url = driver.current_url.lower()
            LOGGER.debug(f"Current URL: {driver.current_url}")
            
            if "/gz/account-verification" in current_url or "account-verification" in current_url:
                LOGGER.warning("Detected account verification page, waiting for manual resolution...")
                # Wait for user to manually resolve or for redirect
                time.sleep(5)
                continue
            
            if "/captcha/" in driver.current_url or "recaptcha" in driver.current_url.lower():
                LOGGER.warning("Detected captcha page")
                break
                
            # Check if we have results
            try:
                productos = driver.find_elements(By.CSS_SELECTOR, "[class*='poly-card'], .poly-card, .ui-search-layout__item")
                visible_products = [p for p in productos if p.is_displayed()]
                if visible_products:
                    LOGGER.info(f"Found {len(visible_products)} products on page")
                    break
            except:
                pass
            
            time.sleep(2)
        
        # Detectar captcha o muro de login
        if _detectar_captcha_o_login(driver):
            LOGGER.error("Detectado captcha o muro de login en MercadoLibre. Use --usar-chrome-abierto con su sesión autenticada.")
            return {"results": [], "error": "Captcha/login wall detected. Use authenticated Chrome session via --usar-chrome-abierto."}
        
        # Si estamos adjuntos a Chrome existente (CDP), no podemos abrir pestañas nuevas
        if debugger_address and detailed:
            LOGGER.warning("CDP attach detectado: deshabilitando detailed=True (no se pueden abrir pestañas nuevas en Chrome adjunto)")
            detailed = False
        
        results = extraer_resultados_busqueda(driver, max_results)
        
        if not results:
            LOGGER.warning("Búsqueda completada pero sin resultados extraídos")
            return {"results": [], "error": "No results extracted"}
        
        # Si se solicita detalle completo, abrir cada producto
        if detailed and results:
            detailed_results = []
            for result in results:
                detail = extraer_detalle_completo(driver, result["url"])
                if detail:
                    # Calcular precio con ganancia
                    if detail.get("precio") and detail["precio"] != "No disponible":
                        try:
                            precio_valor = float(re.sub(r'[^0-9.,]', '', detail["precio"]).replace(',', ''))
                            precio_actualizado = precio_valor + ganancia_envio
                            unidad = int(precio_actualizado) % 10
                            if 1 <= unidad <= 5:
                                precio_actualizado = int(precio_actualizado // 10) * 10 - 1
                            elif unidad >= 6:
                                precio_actualizado = int(precio_actualizado // 10) * 10 + 9
                            detail['precio_con_envio'] = f"$ {precio_actualizado:,.0f}"
                        except:
                            detail['precio_con_envio'] = detail.get("precio", "No disponible")
                    detailed_results.append(detail)
                time.sleep(1)
            results = detailed_results
        
        # Normalizar resultados al formato estándar
        normalized_results = []
        for r in results:
            if isinstance(r, dict) and "title" in r:
                normalized_results.append({
                    "title": r.get("title", r.get("nombre", "No disponible")),
                    "author": r.get("author", r.get("autor", "No disponible")),
                    "price": r.get("price", r.get("precio_con_envio", r.get("precio", "No disponible"))),
                    "price_original": r.get("precio_original", r.get("precio", "No disponible")),
                    "currency": "MXN",
                    "availability": True,
                    "url": r.get("url", r.get("url_libro", "")),
                    "image_url": r.get("image_url", r.get("url_imagen", "")),
                    "editorial": r.get("editorial", "No disponible"),
                    "pages": r.get("num_paginas", r.get("anio_publicacion", "No disponible")),
                    "description": r.get("descripcion", "No disponible"),
                    "delivery_estimate": r.get("delivery_estimate", r.get("envio", "No disponible")),
                    "delivery_dates": r.get("delivery_dates", []),
                    "condition": r.get("condicion", r.get("condition", "No disponible")),
                    "source": "mercadolibre"
                })
        
        return {"results": normalized_results}
    except Exception as e:
        LOGGER.error(f"Error en búsqueda MercadoLibre: {e}")
        return {"results": [], "error": str(e)}
    finally:
        if not getattr(driver, "_mercadolibre_attached_browser", False):
            driver.quit()


async def search_mercadolibre(
    query: str,
    max_results: int = 5,
    ganancia_envio: float = 200,
    detailed: bool = True,
    debugger_address: Optional[str] = None,
) -> Dict[str, Any]:
    """Búsqueda asíncrona en MercadoLibre con control de concurrencia."""
    async with _search_semaphore:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(search_mercadolibre_sync, query, max_results, ganancia_envio, detailed, debugger_address),
                timeout=180.0
            )
        except asyncio.TimeoutError:
            return {"results": [], "error": "Search timed out after 180 seconds"}
        except Exception as e:
            return {"results": [], "error": f"Search error: {str(e)}"}


def main() -> None:
    configurar_log()
    # Git Bash/Windows puede usar cp1252; nunca debe abortar al imprimir el JSON.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description="Extrae un libro público de Mercado Libre y genera una imagen.")
    parser.add_argument("url", nargs="?", help="URL de la publicación")
    parser.add_argument("--html", type=Path, help="Procesa un HTML local para pruebas; no abre Chrome.")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR / "resultado_mercadolibre.png")
    parser.add_argument(
        "--chrome-user-data-dir", type=Path,
        default=Path(os.getenv("CHROME_USER_DATA_DIR", Path(os.getenv("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data")),
        help="Directorio User Data de Chrome, usado sólo junto con --usar-perfil-chrome.",
    )
    parser.add_argument("--chrome-profile", default=os.getenv("CHROME_PROFILE", "Default"), help="Nombre del perfil de Chrome; por defecto, Default.")
    parser.add_argument(
        "--usar-perfil-chrome", action="store_true",
        help="Usa la sesión de Chrome. Requiere cerrar Chrome por completo antes de ejecutar.",
    )
    parser.add_argument(
        "--usar-chrome-abierto", action="store_true",
        help="Se adjunta al Chrome ya abierto en el puerto de depuración indicado; no abre ni cierra Chrome.",
    )
    parser.add_argument(
        "--chrome-debugger-address",
        default=os.getenv("MELI_CHROME_DEBUGGER_ADDRESS", "127.0.0.1:9222"),
        help="Dirección de depuración del Chrome abierto; por defecto 127.0.0.1:9222.",
    )
    args = parser.parse_args()
    url = (args.url or "").strip()
    while not url:
        url = input("URL del libro de Mercado Libre: ").strip()
    try:
        _validar_url_producto(url)
        data = extraer_desde_html(args.html.read_text(encoding="utf-8"), url) if args.html else abrir_chrome_y_extraer(
            url,
            args.chrome_user_data_dir,
            args.chrome_profile,
            args.usar_perfil_chrome,
            args.chrome_debugger_address if args.usar_chrome_abierto else None,
        )
        image = generar_imagen_resultado(data, args.output)
        print(json.dumps(data, ensure_ascii=False, indent=2)); print(f"Imagen generada: {image.resolve()}")
        LOGGER.info("Imagen generada: %s", image.resolve())
    except (MercadoLibreError, OSError, WebDriverException) as exc:
        LOGGER.exception("Error al procesar %s: %s", _url_segura_para_log(url), exc)
        raise SystemExit(f"Error: {exc}") from exc


if __name__ == "__main__":
    main()
