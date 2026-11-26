"""Scraper de libros para Mercado Libre México mediante navegación visible.

El flujo replica el de BuscaLibre: abre la página principal, escribe la
consulta de forma gradual, abre cada publicación y extrae su ficha completa.
No utiliza API privada ni requiere una cuenta de Mercado Libre.
"""

from __future__ import annotations

import asyncio
import argparse
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# Los módulos compartidos permanecen en la raíz del backend.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from mercadolibre import _detectar_captcha_o_login, extraer_desde_html, setup_chrome_driver
from default_queries import DEFAULT_QUERIES
from firestore_catalog import catalog_writer, persist_catalog_books


MERCADOLIBRE_HOME = "https://www.mercadolibre.com.mx/"
_search_semaphore = asyncio.Semaphore(1)


def _pause(minimum: float, maximum: float) -> None:
    """Aplica una pausa variable para reducir la cadencia de consultas."""
    time.sleep(random.uniform(minimum, maximum))


def _enter_search_query(search_box, query: str) -> None:
    """Introduce una búsqueda despacio y con descansos breves entre palabras."""
    for character in query.strip():
        search_box.send_keys(character)
        if character.isspace():
            _pause(0.18, 0.55)
        elif random.random() < 0.09:
            _pause(0.35, 0.95)
        else:
            _pause(0.07, 0.24)
    _pause(0.6, 1.8)
    search_box.send_keys(Keys.ENTER)


def _setup_driver(
    debugger_address: Optional[str],
    user_data_dir: Optional[Path],
    chrome_profile: str,
    use_chrome_profile: bool,
    browser: str,
):
    """Abre un perfil autenticado sólo cuando se solicita explícitamente."""
    if browser == "edge":
        options = EdgeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        if use_chrome_profile:
            if not user_data_dir or not user_data_dir.is_dir():
                raise RuntimeError("No se encontró el directorio de datos de Edge indicado.")
            options.add_argument(f"--user-data-dir={user_data_dir}")
            options.add_argument(f"--profile-directory={chrome_profile}")
        try:
            return webdriver.Edge(options=options)
        except WebDriverException as error:
            detail = str(error).splitlines()[0]
            raise RuntimeError(f"No se pudo abrir Microsoft Edge para el scraper: {detail}") from error
    if debugger_address:
        return setup_chrome_driver(debugger_address)
    if not use_chrome_profile:
        return setup_chrome_driver()
    if not user_data_dir or not user_data_dir.is_dir():
        raise RuntimeError("No se encontró el directorio de datos de Chrome indicado.")

    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(f"--user-data-dir={user_data_dir}")
    options.add_argument(f"--profile-directory={chrome_profile}")
    try:
        driver = webdriver.Chrome(options=options)
    except WebDriverException as error:
        raise RuntimeError(
            "No se pudo abrir el perfil de Chrome. Cierra todas las ventanas de Chrome "
            "o usa una instancia iniciada con --remote-debugging-port=9222."
        ) from error
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver


def _parse_price(value: Any) -> float:
    """Convierte los formatos de precio usuales de Mercado Libre a MXN."""
    raw = re.sub(r"[^0-9,.-]", "", str(value or ""))
    if not raw:
        return 0.0
    if "," in raw and "." in raw:
        decimal = "," if raw.rfind(",") > raw.rfind(".") else "."
        raw = raw.replace("." if decimal == "," else ",", "").replace(decimal, ".")
    else:
        raw = raw.replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return 0.0


def _sale_price(cost: float, margin: float) -> float:
    """Aplica margen y una terminación comercial, por ejemplo 840 -> 839."""
    price = cost + max(margin, 0)
    rounded = int(round(price))
    unit = rounded % 10
    if unit == 0:
        return float(rounded - 1)
    if 1 <= unit <= 5:
        return float((rounded // 10) * 10 - 1)
    if unit >= 6:
        return float((rounded // 10) * 10 + 9)
    return float(rounded)


def _find_search_box(driver, wait: WebDriverWait):
    selectors = (
        "input.nav-search-input",
        "input[name='as_word']",
        "input[placeholder*='Buscar']",
        "input[type='search']",
    )
    for selector in selectors:
        try:
            return wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
        except TimeoutException:
            continue
    return None


def _result_urls(driver, max_results: int) -> List[str]:
    """Extrae URLs únicas de las tarjetas que Mercado Libre acaba de mostrar."""
    urls: List[str] = []
    selectors = (
        "a.poly-component__title",
        ".poly-card a[href*='/MLM-']",
        ".ui-search-layout__item a[href*='/MLM-']",
        "a[href*='/MLM-']",
        "a[href*='/up/']",
    )
    for selector in selectors:
        try:
            anchors = driver.find_elements(By.CSS_SELECTOR, selector)
            for anchor in anchors:
                href = (anchor.get_attribute("href") or "").split("?")[0]
                if not href or href in urls or "mercadolibre.com.mx" not in href:
                    continue
                urls.append(href)
                if len(urls) >= max_results:
                    return urls
        except Exception:
            continue
    return urls


def _pages_from_text(text: str) -> str:
    patterns = (
        r"(?:N[uú]mero de p[aá]ginas|P[aá]ginas)\s*[:\-]?\s*(\d{1,5})",
        r"(\d{1,5})\s+p[aá]ginas",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return "No disponible"


def _delivery_from_page(driver, fallback: str) -> str:
    """Lee el bloque de envío de la ficha, evitando texto de recomendaciones."""
    selectors = (
        ".ui-pdp-shipping__container",
        ".ui-pdp-shipping",
        "[data-testid*='shipping']",
        "[class*='shipping']",
    )
    for selector in selectors:
        try:
            for element in driver.find_elements(By.CSS_SELECTOR, selector):
                text = " ".join(element.text.split())
                if 5 <= len(text) <= 180 and any(word in text.lower() for word in ("llega", "envío", "envio", "entrega")):
                    return text
        except Exception:
            continue
    fallback = " ".join(fallback.split())
    # The generic HTML parser can merge the shipping copy with suggested
    # products; an absent value is safer than showing another book's shipping.
    if len(fallback) > 180 or fallback.count("$") > 1:
        return "No disponible"
    return fallback or "No disponible"


def _seller_from_page(driver) -> Dict[str, str]:
    """Extract seller identity and reputation published on the product page."""
    sections = (
        ".ui-pdp-seller__header",
        ".ui-pdp-seller",
        ".ui-seller-data-header",
        ".ui-pdp-seller__info",
    )
    name_selectors = (
        "a.ui-pdp-seller__link-trigger",
        "a.ui-seller-data-header__title",
        "a[href*='/perfil/']",
        "a[href*='/perfil/']",
    )
    for selector in sections:
        try:
            for section in driver.find_elements(By.CSS_SELECTOR, selector):
                section_text = " ".join(section.text.split())
                if not section_text:
                    continue
                seller_name = ""
                seller_url = ""
                for name_selector in name_selectors:
                    try:
                        link = section.find_element(By.CSS_SELECTOR, name_selector)
                        seller_name = " ".join(link.text.split())
                        seller_url = link.get_attribute("href") or ""
                        if seller_name:
                            break
                    except Exception:
                        continue
                lines = [" ".join(line.split()) for line in section.text.splitlines()]
                reputation_lines = [
                    line for line in lines
                    if any(marker in line.lower() for marker in (
                        "reputación", "reputacion", "mercado líder", "mercado lider", "ventas", "vende",
                    ))
                ]
                sales_match = re.search(r"(\d[\d.,]*\+?\s*(?:ventas|vendidos))", section_text, re.IGNORECASE)
                return {
                    "seller_name": seller_name or "No disponible",
                    "seller_reputation": " | ".join(reputation_lines)[:400] or "No disponible",
                    "seller_sales": sales_match.group(1) if sales_match else "No disponible",
                    "seller_url": seller_url,
                }
        except Exception:
            continue
    return {
        "seller_name": "No disponible",
        "seller_reputation": "No disponible",
        "seller_sales": "No disponible",
        "seller_url": "",
    }


def _read_product_page(driver, url: str, margin: float) -> Optional[Dict[str, Any]]:
    """Abre una ficha en una pestaña temporal y la normaliza para el catálogo."""
    original_window = driver.current_window_handle
    try:
        driver.execute_script("window.open(arguments[0], '_blank');", url)
        driver.switch_to.window(driver.window_handles[-1])
        try:
            WebDriverWait(driver, 20).until(
                lambda browser: browser.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            pass

        if _detectar_captcha_o_login(driver):
            return None

        data = extraer_desde_html(driver.page_source, driver.current_url)
        title = " ".join(data.get("nombre", "").split())
        if not title:
            return None
        cost = _parse_price(data.get("precio"))
        final_price = _sale_price(cost, margin) if cost else 0.0
        body_text = driver.find_element(By.TAG_NAME, "body").text
        pages = _pages_from_text(body_text)
        if pages == "No disponible":
            pages = _pages_from_text(data.get("descripcion", ""))
        delivery = _delivery_from_page(driver, data.get("envio", ""))
        seller = _seller_from_page(driver)
        return {
            "title": title,
            "author": data.get("autor", "No disponible"),
            "price": f"$ {final_price:,.0f}" if final_price else "No disponible",
            "price_original": f"$ {cost:,.0f}" if cost else "No disponible",
            "currency": data.get("moneda", "MXN") or "MXN",
            "availability": bool(cost),
            "url": driver.current_url,
            "image_url": data.get("url_imagen", ""),
            "editorial": data.get("editorial", "No disponible"),
            "pages": pages,
            "description": data.get("descripcion", "No disponible"),
            "delivery_estimate": delivery,
            "delivery_dates": [],
            "condition": data.get("condicion", "No disponible"),
            **seller,
            "source": "mercadolibre",
        }
    except Exception as error:
        print(f"No se pudo leer la publicación de Mercado Libre: {error}")
        return None
    finally:
        if len(driver.window_handles) > 1:
            try:
                driver.close()
                driver.switch_to.window(original_window)
            except Exception:
                pass


def search_mercadolibre_sync(
    query: str,
    max_results: int = 5,
    ganancia_envio: float = 200,
    on_result: Optional[Callable[[Dict[str, Any]], None]] = None,
    debugger_address: Optional[str] = None,
    user_data_dir: Optional[Path] = None,
    chrome_profile: str = "Default",
    use_chrome_profile: bool = False,
    browser: str = "edge",
) -> Dict[str, Any]:
    """Busca libros escribiendo la consulta en Mercado Libre y lee cada ficha."""
    driver = _setup_driver(debugger_address, user_data_dir, chrome_profile, use_chrome_profile, browser)
    results: List[Dict[str, Any]] = []
    try:
        driver.get(MERCADOLIBRE_HOME)
        wait = WebDriverWait(driver, 20)
        search_box = _find_search_box(driver, wait)
        if not search_box:
            return {"results": [], "error": "Search box not found"}

        search_box.click()
        _pause(0.35, 1.1)
        _enter_search_query(search_box, query)

        try:
            wait.until(lambda browser: bool(_result_urls(browser, 1)))
        except TimeoutException:
            return {"results": [], "error": "Search results not found"}
        if _detectar_captcha_o_login(driver):
            return {"results": [], "error": "Captcha or login wall detected"}

        for url in _result_urls(driver, max(max_results, 1)):
            _pause(1.8, 4.5)
            book = _read_product_page(driver, url, ganancia_envio)
            if not book:
                continue
            results.append(book)
            if on_result:
                try:
                    on_result(book)
                except Exception as callback_error:
                    print(f"No se pudo publicar el libro recién leído: {callback_error}")
            _pause(2.2, 5.5)
        return {"results": results}
    except Exception as error:
        return {"results": [], "error": str(error)}
    finally:
        if not getattr(driver, "_mercadolibre_attached_browser", False):
            driver.quit()


async def search_mercadolibre(
    query: str,
    max_results: int = 5,
    ganancia_envio: float = 200,
    on_result: Optional[Callable[[Dict[str, Any]], None]] = None,
    debugger_address: Optional[str] = None,
    user_data_dir: Optional[Path] = None,
    chrome_profile: str = "Default",
    use_chrome_profile: bool = False,
    browser: str = "edge",
) -> Dict[str, Any]:
    """Versión asíncrona protegida para consumir desde FastAPI."""
    async with _search_semaphore:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    search_mercadolibre_sync,
                    query,
                    max_results,
                    ganancia_envio,
                    on_result,
                    debugger_address,
                    user_data_dir,
                    chrome_profile,
                    use_chrome_profile,
                    browser,
                ),
                timeout=180.0,
            )
        except asyncio.TimeoutError:
            return {"results": [], "error": "Search timed out after 180 seconds"}
        except Exception as error:
            return {"results": [], "error": f"Search error: {error}"}


def main() -> None:
    """Ejecuta una búsqueda manual desde la terminal para verificar el scraper."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description="Busca libros en Mercado Libre México con navegación visible.")
    parser.add_argument("queries", nargs="*", help="Libros, autores o temas a buscar.")
    parser.add_argument("--limit", type=int, default=20, help="Máximo de consultas predeterminadas a procesar.")
    parser.add_argument("--max-results", type=int, default=5, help="Máximo de publicaciones a leer por consulta.")
    parser.add_argument("--ganancia-envio", type=float, default=200.0, help="Margen agregado al precio en MXN.")
    parser.add_argument("--browser", choices=("chrome", "edge"), default="edge", help="Navegador a usar (por defecto: edge).")
    parser.add_argument("--chrome-debugger-address", help="Chrome remoto, por ejemplo 127.0.0.1:9222.")
    parser.add_argument("--usar-perfil-navegador", "--usar-perfil-chrome", dest="use_browser_profile", action="store_true", help="Usa el perfil autenticado del navegador; ciérralo antes de ejecutarlo.")
    parser.add_argument(
        "--chrome-user-data-dir",
        type=Path,
        help="Directorio User Data del navegador; se infiere según --browser si se omite.",
    )
    parser.add_argument("--chrome-profile", default="Default", help="Perfil del navegador a usar (por defecto: Default).")
    args = parser.parse_args()
    default_user_data = "Microsoft/Edge/User Data" if args.browser == "edge" else "Google/Chrome/User Data"
    user_data_dir = args.chrome_user_data_dir or (Path(os.getenv("LOCALAPPDATA", "")) / default_user_data)
    queries = args.queries or DEFAULT_QUERIES
    queries = queries[:max(args.limit, 1)]
    searches = []
    for index, query in enumerate(queries, 1):
        print(f"[{index}/{len(queries)}] Buscando: {query}")

        saved_count = 0

        def save_book(book: Dict[str, Any]) -> None:
            """Publica cada ficha al catálogo sin esperar al resto de resultados."""
            nonlocal saved_count
            if not getattr(catalog_writer, "enabled", False):
                print("[AVISO] Firebase no está disponible; no se guardó la ficha.")
                return
            saved = persist_catalog_books([{**book, "source": "mercadolibre"}], query)
            saved_count += saved
            print(f"[OK] Publicado en Firebase: {book.get('title', 'Libro sin título')}")

        result = asyncio.run(
            search_mercadolibre(
                query,
                max_results=max(args.max_results, 1),
                ganancia_envio=max(args.ganancia_envio, 0),
                on_result=save_book,
                debugger_address=args.chrome_debugger_address,
                user_data_dir=user_data_dir,
                chrome_profile=args.chrome_profile,
                use_chrome_profile=args.use_browser_profile,
                browser=args.browser,
            )
        )
        searches.append({"query": query, "saved_to_firebase": saved_count, **result})
        if "captcha" in str(result.get("error", "")).lower():
            print("[AVISO] Mercado Libre solicitó verificación; se detiene el lote para no insistir.")
            break
        if index < len(queries):
            pause_seconds = random.uniform(15, 35)
            print(f"[PAUSA] Esperando {pause_seconds:.0f}s antes de la siguiente consulta.")
            time.sleep(pause_seconds)
    print(json.dumps({"searches": searches}, ensure_ascii=False, indent=2))
    if not any(search.get("results") for search in searches):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
