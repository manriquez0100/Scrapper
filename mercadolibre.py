"""Scraper público de libros de Mercado Libre México, sin API ni inicio de sesión."""
from __future__ import annotations

import argparse
import io
import json
import logging
import os
import re
import sys
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from urllib.parse import urlsplit, urlunsplit

import requests
from PIL import Image, ImageDraw, ImageFont
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

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


def abrir_chrome_y_extraer(url: str, user_data_dir: Optional[Path] = None, profile: str = "Default", usar_perfil: bool = False) -> Dict[str, str]:
    """Abre una publicación en Chrome visible; la consulta pública no requiere login."""
    _validar_url_producto(url)
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
    args = parser.parse_args()
    url = (args.url or "").strip()
    while not url:
        url = input("URL del libro de Mercado Libre: ").strip()
    try:
        _validar_url_producto(url)
        data = extraer_desde_html(args.html.read_text(encoding="utf-8"), url) if args.html else abrir_chrome_y_extraer(
            url, args.chrome_user_data_dir, args.chrome_profile, args.usar_perfil_chrome
        )
        image = generar_imagen_resultado(data, args.output)
        print(json.dumps(data, ensure_ascii=False, indent=2)); print(f"Imagen generada: {image.resolve()}")
        LOGGER.info("Imagen generada: %s", image.resolve())
    except (MercadoLibreError, OSError, WebDriverException) as exc:
        LOGGER.exception("Error al procesar %s: %s", _url_segura_para_log(url), exc)
        raise SystemExit(f"Error: {exc}") from exc


if __name__ == "__main__":
    main()
