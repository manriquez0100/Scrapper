"""Scraper visible de libros Prime en Amazon México.

Lee los resultados directamente en amazon.com.mx, conserva sólo las fichas con
la insignia Prime y publica cada libro en Firebase al terminar de leerlo.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import sys
import tempfile
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
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from default_queries import DEFAULT_QUERIES
from firestore_catalog import catalog_writer, persist_catalog_books


AMAZON_HOME = "https://www.amazon.com.mx/"
AMAZON_DOMAIN = "amazon.com.mx"
_search_semaphore = asyncio.Semaphore(1)


def _profile_copy(user_data_dir: Path, profile: str) -> Path:
    """Clona sólo el perfil solicitado para no bloquear el Edge del usuario."""
    source_profile = user_data_dir / profile
    if not source_profile.is_dir():
        raise RuntimeError(f"No se encontró el perfil de Edge: {source_profile}")
    temporary_root = Path(tempfile.mkdtemp(prefix="amazon-edge-profile-"))
    try:
        local_state = user_data_dir / "Local State"
        if local_state.is_file():
            shutil.copy2(local_state, temporary_root / "Local State")
        shutil.copytree(
            source_profile,
            temporary_root / profile,
            ignore=shutil.ignore_patterns(
                "Cache", "Code Cache", "GPUCache", "GrShaderCache", "DawnCache",
                "Singleton*", "LOCK", "Lockfile",
            ),
        )
        return temporary_root
    except Exception:
        shutil.rmtree(temporary_root, ignore_errors=True)
        raise


def _setup_edge(user_data_dir: Optional[Path], profile: str, use_profile: bool):
    """Abre Microsoft Edge visible; clona el perfil si está en uso."""
    options = EdgeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    temporary_profile: Optional[Path] = None
    if use_profile:
        if not user_data_dir or not user_data_dir.is_dir():
            raise RuntimeError("No se encontró el directorio User Data de Microsoft Edge.")
        temporary_profile = _profile_copy(user_data_dir, profile)
        options.add_argument(f"--user-data-dir={temporary_profile}")
        options.add_argument(f"--profile-directory={profile}")
    try:
        return webdriver.Edge(options=options), temporary_profile
    except WebDriverException as error:
        if temporary_profile:
            shutil.rmtree(temporary_profile, ignore_errors=True)
        raise RuntimeError(f"No se pudo abrir Microsoft Edge: {str(error).splitlines()[0]}") from error


def _compact(value: Any) -> str:
    return " ".join(str(value or "").split())


def _is_blocked(driver) -> bool:
    page = _compact(driver.page_source).lower()
    return any(marker in page for marker in (
        "enter the characters you see below", "robot check", "captcha", "automated access",
    ))


def _find_search_box(driver, wait: WebDriverWait):
    """Obtiene el buscador visible de la portada de Amazon México."""
    for selector in ("#twotabsearchtextbox", "input[name='field-keywords']", "input[type='search']"):
        try:
            return wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
        except TimeoutException:
            continue
    return None


def _search_like_a_person(driver, query: str) -> bool:
    """Abre Amazon y escribe la búsqueda carácter por carácter."""
    driver.get(AMAZON_HOME)
    wait = WebDriverWait(driver, 20)
    search_box = _find_search_box(driver, wait)
    if not search_box:
        return False
    search_box.click()
    for character in query.strip():
        search_box.send_keys(character)
        time.sleep(0.06)
    search_box.submit()
    return True


def _has_prime(element) -> bool:
    """Amazon renders Prime as an icon, image alt text, or accessibility label."""
    try:
        # A result card is a WebElement, while product validation passes the
        # WebDriver itself. Both must inspect the rendered HTML.
        if hasattr(element, "page_source"):
            markup = element.page_source.lower()
            text = _compact(element.find_element(By.TAG_NAME, "body").text).lower()
        else:
            markup = (element.get_attribute("innerHTML") or "").lower()
            text = _compact(element.text).lower()
    except Exception:
        return False
    return bool(
        re.search(r"(?:a-icon-prime|prime-logo|\bprime\b)", markup)
        or re.search(r"\bprime\b", text)
    )


def _product_has_prime(driver) -> bool:
    """Confirma Prime en zonas de entrega/compra, no en el menú global."""
    for selector in (
        "#prime-badge", "i.a-icon-prime", "[aria-label*='Prime']",
        "#deliveryBlock_feature_div", "#mir-layout-DELIVERY_BLOCK",
        "#deliveryBlockMessage", "#shipsFromSoldBy_feature_div",
    ):
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for element in elements:
                if "prime" in (_compact(element.text) + " " + (element.get_attribute("aria-label") or "")).lower():
                    return True
                markup = (element.get_attribute("outerHTML") or "").lower()
                if "a-icon-prime" in markup or "prime-logo" in markup:
                    return True
        except Exception:
            continue
    return False


def _apply_prime_filter(driver) -> bool:
    """Selecciona Prime en los refinamientos visibles de Amazon, si existe."""
    try:
        refinements = driver.find_element(By.CSS_SELECTOR, "#s-refinements")
    except Exception:
        return False
    for link in refinements.find_elements(By.CSS_SELECTOR, "a"):
        label = _compact(link.text).lower()
        href = link.get_attribute("href") or ""
        # Evita enlaces de membresía o ayuda: debe ser una opción de filtro.
        if label not in {"prime", "prime elegible"} and "p_85" not in href:
            continue
        try:
            previous_url = driver.current_url
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", link)
            driver.execute_script("arguments[0].click();", link)
            WebDriverWait(driver, 12).until(
                lambda browser: browser.current_url != previous_url
                or "p_85" in browser.current_url
            )
            print("[INFO] Filtro Prime aplicado desde Amazon.")
            return True
        except Exception:
            continue
    print("[INFO] Amazon no mostró un filtro Prime seleccionable; se usarán insignias visibles.")
    return False


def _prime_result_urls(driver, max_results: int, amazon_prime_filter: bool = False) -> List[str]:
    """Extrae URLs Prime, por filtro de Amazon o por insignia de tarjeta."""
    urls: List[str] = []
    unlabelled_urls: List[str] = []
    cards = driver.find_elements(By.CSS_SELECTOR, "div[data-component-type='s-search-result']")
    prime_cards = 0
    for card in cards:
        has_visible_prime = _has_prime(card)
        if has_visible_prime or amazon_prime_filter:
            prime_cards += 1
        try:
            link = card.find_element(By.CSS_SELECTOR, "h2 a.a-link-normal, a.a-link-normal.s-no-outline")
            href = link.get_attribute("href") or ""
        except Exception:
            continue
        href = href.split("?")[0]
        if AMAZON_DOMAIN not in href or "/dp/" not in href or href in urls or href in unlabelled_urls:
            continue
        if has_visible_prime or amazon_prime_filter:
            urls.append(href)
            if len(urls) >= max_results:
                break
        else:
            unlabelled_urls.append(href)
    # Amazon a veces omite el distintivo en la tarjeta. En ese caso se entra a
    # la ficha y se exige la confirmación Prime en su bloque de compra.
    if not urls and unlabelled_urls:
        urls = unlabelled_urls[:max_results]
        print("[INFO] Sin insignias en tarjetas; verificando Prime dentro de cada ficha.")
    status = "filtrados por Amazon Prime" if amazon_prime_filter else "con etiqueta Prime visible"
    print(f"[INFO] Resultados leídos: {len(cards)} | {status}: {prime_cards}")
    return urls


def _price_from_page(driver) -> tuple[float, str]:
    whole = ""
    fraction = ""
    for selector in (".priceToPay .a-price-whole", "#priceblock_ourprice", "#priceblock_dealprice", ".a-price .a-price-whole"):
        try:
            whole = _compact(driver.find_element(By.CSS_SELECTOR, selector).text)
            if whole:
                break
        except Exception:
            continue
    for selector in (".priceToPay .a-price-fraction", ".a-price .a-price-fraction"):
        try:
            fraction = _compact(driver.find_element(By.CSS_SELECTOR, selector).text)
            if fraction:
                break
        except Exception:
            continue
    raw = re.sub(r"[^0-9]", "", whole)
    if not raw:
        return 0.0, "No disponible"
    cents = re.sub(r"[^0-9]", "", fraction)[:2]
    value = float(f"{raw}.{cents or '0'}")
    return value, f"$ {value:,.0f}"


def _text(driver, selectors: tuple[str, ...], default: str = "No disponible") -> str:
    for selector in selectors:
        try:
            text = _compact(driver.find_element(By.CSS_SELECTOR, selector).text)
            if text:
                return text
        except Exception:
            continue
    return default


def _pages_from_text(text: str) -> str:
    match = re.search(r"(?:número de páginas|páginas)\s*[:\-]?\s*(\d{1,5})", text, re.IGNORECASE)
    return match.group(1) if match else "No disponible"


def _read_prime_book(driver, url: str, margin: float, amazon_prime_filter: bool = False) -> Optional[Dict[str, Any]]:
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
        # Si la interfaz de Amazon ya filtró por Prime, esa selección es la
        # fuente de verdad. De otra forma se exige una insignia en la ficha.
        if _is_blocked(driver) or (not amazon_prime_filter and not _product_has_prime(driver)):
            return None

        title = _text(driver, ("#productTitle",), "")
        if not title:
            return None
        cost, cost_text = _price_from_page(driver)
        # Mantiene la misma terminación comercial aplicada en los otros scrapers.
        final_price = max(0, int(round(cost + max(margin, 0))))
        if final_price and final_price % 10 == 0:
            final_price -= 1
        body = _compact(driver.find_element(By.TAG_NAME, "body").text)
        image = ""
        try:
            image = driver.find_element(By.CSS_SELECTOR, "#landingImage, #imgBlkFront").get_attribute("src") or ""
        except Exception:
            pass
        return {
            "title": title,
            "author": _text(driver, ("#bylineInfo", ".author a")),
            "price": f"$ {final_price:,.0f}" if final_price else "No disponible",
            "price_original": cost_text,
            "currency": "MXN",
            "availability": bool(cost),
            "url": driver.current_url.split("?")[0],
            "image_url": image,
            "editorial": "No disponible",
            "pages": _pages_from_text(body),
            "description": _text(driver, ("#bookDescription_feature_div", "#productDescription")),
            "delivery_estimate": _text(driver, ("#mir-layout-DELIVERY_BLOCK", "#deliveryBlockMessage")),
            "delivery_dates": [],
            "condition": "Nuevo",
            "seller_name": _text(driver, ("#sellerProfileTriggerId", "#merchant-info a")),
            "seller_reputation": "No disponible",
            "seller_sales": "No disponible",
            "seller_url": "",
            "source": "amazon",
            "badge": "Prime",
        }
    except Exception as error:
        print(f"No se pudo leer la publicación de Amazon: {error}")
        return None
    finally:
        if len(driver.window_handles) > 1:
            try:
                driver.close()
                driver.switch_to.window(original_window)
            except Exception:
                pass


def search_amazon_sync(
    query: str, max_results: int = 5, ganancia_envio: float = 200,
    on_result: Optional[Callable[[Dict[str, Any]], None]] = None,
    user_data_dir: Optional[Path] = None, edge_profile: str = "Default",
    use_edge_profile: bool = False,
) -> Dict[str, Any]:
    """Busca y devuelve exclusivamente libros Prime de Amazon México."""
    driver, temporary_profile = _setup_edge(user_data_dir, edge_profile, use_edge_profile)
    results: List[Dict[str, Any]] = []
    try:
        if not _search_like_a_person(driver, query):
            return {"results": [], "error": "No se encontró el buscador de Amazon"}
        try:
            WebDriverWait(driver, 20).until(
                lambda browser: bool(browser.find_elements(By.CSS_SELECTOR, "div[data-component-type='s-search-result']"))
            )
        except TimeoutException:
            return {"results": [], "error": "No se encontraron resultados de Amazon"}
        if _is_blocked(driver):
            return {"results": [], "error": "Amazon mostró una verificación CAPTCHA"}
        amazon_prime_filter = _apply_prime_filter(driver)
        if amazon_prime_filter:
            try:
                WebDriverWait(driver, 15).until(
                    lambda browser: bool(browser.find_elements(By.CSS_SELECTOR, "div[data-component-type='s-search-result']"))
                )
            except TimeoutException:
                return {"results": [], "error": "Amazon no cargó resultados tras aplicar Prime"}
        for url in _prime_result_urls(driver, max(max_results, 1), amazon_prime_filter):
            book = _read_prime_book(driver, url, ganancia_envio, amazon_prime_filter)
            if not book:
                continue
            results.append(book)
            if on_result:
                on_result(book)
            time.sleep(0.8)
        return {"results": results}
    except Exception as error:
        return {"results": [], "error": str(error)}
    finally:
        driver.quit()
        if temporary_profile:
            shutil.rmtree(temporary_profile, ignore_errors=True)


async def search_amazon(query: str, **kwargs: Any) -> Dict[str, Any]:
    async with _search_semaphore:
        return await asyncio.to_thread(search_amazon_sync, query, **kwargs)


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description="Busca libros Prime en Amazon México usando Microsoft Edge.")
    parser.add_argument("queries", nargs="*", help="Libros, autores o temas a buscar.")
    parser.add_argument("--limit", type=int, default=20, help="Máximo de consultas predeterminadas.")
    parser.add_argument("--max-results", type=int, default=5, help="Máximo de libros Prime por consulta.")
    parser.add_argument("--ganancia-envio", type=float, default=200.0, help="Margen agregado al costo en MXN.")
    parser.add_argument("--usar-perfil-edge", action="store_true", help="Usa el perfil autenticado de Edge; ciérralo antes de ejecutarlo.")
    parser.add_argument("--edge-user-data-dir", type=Path, help="Directorio User Data de Edge.")
    parser.add_argument("--edge-profile", default="Default", help="Perfil de Edge a utilizar.")
    args = parser.parse_args()
    user_data_dir = args.edge_user_data_dir or Path(os.getenv("LOCALAPPDATA", "")) / "Microsoft/Edge/User Data"
    queries = (args.queries or DEFAULT_QUERIES)[:max(args.limit, 1)]
    searches = []
    for index, query in enumerate(queries, 1):
        print(f"[{index}/{len(queries)}] Buscando libros Prime: {query}")
        saved_count = 0

        def save_book(book: Dict[str, Any]) -> None:
            nonlocal saved_count
            if not getattr(catalog_writer, "enabled", False):
                print("[AVISO] Firebase no está disponible; no se guardó la ficha.")
                return
            saved_count += persist_catalog_books([book], query)
            print(f"[OK] Publicado en Firebase: {book.get('title', 'Libro sin título')}")

        result = asyncio.run(search_amazon(
            query, max_results=max(args.max_results, 1), ganancia_envio=max(args.ganancia_envio, 0),
            on_result=save_book, user_data_dir=user_data_dir, edge_profile=args.edge_profile,
            use_edge_profile=args.usar_perfil_edge,
        ))
        searches.append({"query": query, "saved_to_firebase": saved_count, **result})
    print(json.dumps({"searches": searches}, ensure_ascii=False, indent=2))
    if not any(item.get("results") for item in searches):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
