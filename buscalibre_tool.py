"""Buscalibre search tool - thin wrapper around buscalibreUpdating_11.py"""

import sys
import os
import asyncio
import re
from typing import Callable, List, Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Concurrency control: only 1 Selenium search at a time
_search_semaphore = asyncio.Semaphore(1)

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager


def setup_chrome_driver():
    chrome_options = Options()
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    chrome_options.add_argument('--start-maximized')
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver


def extraer_url_libro(producto):
    try:
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
                if url and ('libro-' in url or 'product' in url):
                    return url
            except:
                continue
        return None
    except:
        return None


def extraer_entrega_buscalibre(driver: webdriver.Chrome) -> Dict[str, Any]:
    """Extract the delivery estimate published on the Buscalibre product page."""
    selectors = [
        ".tiempoEnvio",
        "[class*='tiempoEnvio']",
        "[id*='tiempoEnvio']",
        ".tiempo-envio",
        ".shipping-time",
        ".delivery-time",
        ".envio-tiempo",
        "[class*='shipping']",
        "[class*='delivery']",
        "[data-testid*='delivery']",
        "[data-testid*='shipping']",
    ]
    delivery_keywords = ("entrega", "envío", "envio", "recibe", "llega", "despacho")

    for selector in selectors:
        try:
            for element in driver.find_elements(By.CSS_SELECTOR, selector):
                delivery_text = " ".join(element.text.split())
                if len(delivery_text) < 4 or not any(
                    keyword in delivery_text.lower() for keyword in delivery_keywords
                ):
                    continue

                dates = re.findall(
                    r"\b\d{1,2}\s+de\s+"
                    r"(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
                    r"septiembre|octubre|noviembre|diciembre)(?:\s+de\s+\d{4})?\b",
                    delivery_text,
                    flags=re.IGNORECASE,
                )
                return {
                    "delivery_estimate": delivery_text,
                    "delivery_dates": dates,
                }
        except Exception:
            continue

    return {"delivery_estimate": "No disponible", "delivery_dates": []}


def extraer_detalle_libro(driver, url_libro, numero_producto, ganancia_envio: float = 200):
    if not url_libro:
        return None
    try:
        ventana_original = driver.current_window_handle
        driver.execute_script(f"window.open('{url_libro}', '_blank');")
        driver.switch_to.window(driver.window_handles[-1])
        
        import time
        time.sleep(2)
        
        info_completa = {}
        
        selectores_nombre = [
            "p.tituloProducto", ".tituloProducto", "p[class*='tituloProducto']",
            "[class*='tituloProducto']", "h1.titulo-libro", "h1[class*='titulo']",
            ".nombre-producto h1", ".product-title h1",
            "h1:not([class*='opinion']):not([class*='review']):not([class*='comentario'])",
            ".libro-info h1", ".producto-titulo", "h1",
            ".titulo:not([class*='opinion']):not([class*='review'])", 
            ".title:not([class*='opinion']):not([class*='review'])",
            ".product-title", ".libro-titulo",
            "[class*='titulo']:not([class*='opinion']):not([class*='review'])",
            "[class*='title']:not([class*='opinion']):not([class*='review'])",
            ".nombre-libro"
        ]
        for selector in selectores_nombre:
            try:
                nombre_element = driver.find_element(By.CSS_SELECTOR, selector)
                nombre = nombre_element.text.strip()
                if (nombre and len(nombre) > 3 and 
                    not any(palabra in nombre.lower() for palabra in [
                        'opinion', 'review', 'comentario', 'reseña', 'crítica', 
                        'valoración', 'calificación', 'rating', 'puntuación'
                    ]) and
                    not nombre.lower().startswith('opiniones') and
                    not nombre.lower().startswith('reseña') and
                    len(nombre) < 200):
                    info_completa['nombre'] = nombre
                    break
            except:
                continue
        if 'nombre' not in info_completa:
            info_completa['nombre'] = f"Libro #{numero_producto}"
        
        selectores_precio_actual = [
            ".precio", ".price", ".product-price", ".costo", "[class*='precio']",
            "[class*='price']", ".valor", ".amount", ".box-precio-v2 strong"
        ]
        selectores_precio_original = [
            ".precio tachado", ".precio .original", ".precio .price--original",
            ".precio anterior", "[class*='precio-original']", "[class*='original-price']",
            ".price--before", ".price-original", ".price-before-discount"
        ]
        selectores_descuento = [
            "[class*='descuento']", "[class*='discount']", ".percent-descuento",
            "[class*='percent']", ".badge-descuento", ".badge-descuento",
            ".descuento-porcentaje", "span[class*='des']"
        ]
        
        precio_actual_encontrado = False
        for selector in selectores_precio_actual:
            try:
                precio_element = driver.find_element(By.CSS_SELECTOR, selector)
                precio_texto = precio_element.text.strip()
                if precio_texto and ('$' in precio_texto or '€' in precio_texto or any(c.isdigit() for c in precio_texto)):
                    info_completa['precio_actual'] = precio_texto
                    import re
                    precio_numerico = re.search(r'[\d,]+\.?\d*', precio_texto)
                    if precio_numerico:
                        precio_valor = float(precio_numerico.group().replace(',', ''))
                        precio_actual_encontrado = True
                        # Calcular precio con envio
                        precio_actualizado = precio_valor + ganancia_envio
                        unidad = int(precio_actualizado) % 10
                        if 1 <= unidad <= 5:
                            precio_actualizado = int(precio_actualizado // 10) * 10 - 1
                        elif unidad == 6 or unidad == 7:
                            precio_actualizado = int(precio_actualizado // 10) * 10 + 9
                        elif unidad == 8:
                            precio_actualizado = int(precio_actualizado // 10) * 10 + 9
                        elif unidad == 0:
                            precio_actualizado = precio_actualizado - 1
                        info_completa['precio_con_envio'] = f"$ {precio_actualizado:,.0f}"
                        # También guardamos el precio actual como precio_original si aún no está establecido
                        if 'precio_original' not in info_completa:
                            info_completa['precio_original'] = precio_texto
                    break
            except:
                continue
        
        # Buscar precio original (antes de descuentos) si no fue encontrado
        if not precio_actual_encontrado or 'precio_original' not in info_completa or info_completa.get('precio_original') == "Precio no disponible":
            for selector in selectores_precio_original:
                try:
                    precio_original_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in precio_original_elements:
                        precio_texto = elem.text.strip()
                        if precio_texto and ('$' in precio_texto or '€' in precio_texto or any(c.isdigit() for c in precio_texto)):
                            info_completa['precio_original'] = precio_texto
                            import re
                            precio_numerico = re.search(r'[\d,]+\.?\d*', precio_texto)
                            if precio_numerico:
                                # Guardar el valor numérico original sin markup
                                info_completa['precio_original_numerico'] = float(precio_numerico.group().replace(',', ''))
                            break
                    if 'precio_original' in info_completa:
                        break
                except:
                    continue
        
        # Extraer porcentaje de descuento
        for selector in selectores_descuento:
            try:
                descuento_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in descuento_elements:
                    descuento_texto = elem.text.strip()
                    # Buscar porcentaje en el texto
                    import re
                    porcentaje_match = re.search(r'(\d+(\.\d+)?)%?', descuento_texto)
                    if porcentaje_match:
                        info_completa['descuento_porcentaje'] = float(porcentaje_match.group(1))
                        # Si hay descuento, el precio_actual es el precio con descuento
                        # Podríamos calcular el precio original si no existe
                        if 'precio_original' not in info_completa or info_completa.get('precio_original') == "Precio no disponible":
                            # Precio original = precio_actual / (1 - descuento/100)
                            if 'precio_actual_numerico' in info_completa and info_completa['precio_actual_numerico']:
                                precio_actual_valor = info_completa['precio_actual_numerico']
                                descuento = info_completa['descuento_porcentaje']
                                if descuento and descuento < 100:
                                    precio_original_calc = precio_actual_valor / (1 - descuento/100)
                                    info_completa['precio_original'] = f"$ {precio_original_calc:,.0f}"
                                    info_completa['precio_original_numerico'] = precio_original_calc
                        break
            except:
                continue
            if 'descuento_porcentaje' in info_completa:
                break
        
        # Si aún no tenemos precio_original, usar precio_actual como fallback
        if 'precio_original' not in info_completa:
            info_completa['precio_original'] = info_completa.get('precio_actual', "Precio no disponible")
        if 'precio_original_numerico' not in info_completa and 'precio_actual_numerico' in info_completa:
            info_completa['precio_original_numerico'] = info_completa['precio_actual_numerico']
        
        if 'precio_original' not in info_completa or info_completa.get('precio_original') == "Precio no disponible":
            info_completa['precio_original'] = "Precio no disponible"
            info_completa['precio_con_envio'] = "Precio no disponible"
        
        selectores_imagen = [
            ".imagen-producto img", ".product-image img", ".libro-imagen img",
            ".cover img", ".portada img", "img[src*='cover']", "img[src*='libro']",
            ".imagen-grande img", "img[alt*='portada']"
        ]
        url_imagen_hq = None
        for selector in selectores_imagen:
            try:
                img_element = driver.find_element(By.CSS_SELECTOR, selector)
                url_imagen_hq = img_element.get_attribute('src') or img_element.get_attribute('data-src')
                if url_imagen_hq and ('jpg' in url_imagen_hq.lower() or 'png' in url_imagen_hq.lower() or 'jpeg' in url_imagen_hq.lower()):
                    if any(size in url_imagen_hq for size in ['large', 'big', 'full', 'original', '_l', '_xl']):
                        info_completa['url_imagen_hq'] = url_imagen_hq
                        break
                    elif not info_completa.get('url_imagen_hq'):
                        info_completa['url_imagen_hq'] = url_imagen_hq
            except:
                continue
        
        selectores_ficha = [
            ".ficha .row", ".metadata .row", ".book-details .row",
            ".product-details .row", "[class*='ficha'] .row", "[class*='metadata'] .row"
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
                        if any(palabra in texto_fila for palabra in ['autor', 'author', 'writer', 'escritor']):
                            try:
                                valor_elementos = fila.find_elements(By.CSS_SELECTOR, ".col-xs-7 .box, .col-md-7 .box, .value, .data")
                                if valor_elementos:
                                    valor_autor_element = valor_elementos[0]
                                    link_autor = valor_autor_element.find_elements(By.CSS_SELECTOR, "a.color-primary, a[href*='autor'], a[href*='author']")
                                    if link_autor:
                                        valor_autor = link_autor[0].text.strip()
                                    else:
                                        valor_autor = valor_autor_element.text.strip()
                                    if valor_autor and len(valor_autor) > 1 and valor_autor.lower() != "autor":
                                        autor = valor_autor
                            except:
                                pass
                        if any(palabra in texto_fila for palabra in ['editorial', 'editor', 'publisher']):
                            try:
                                valor_elementos = fila.find_elements(By.CSS_SELECTOR, ".col-xs-7 .box, .col-md-7 .box, .value, .data")
                                if valor_elementos:
                                    valor_editorial = valor_elementos[0].text.strip()
                                    if valor_editorial and len(valor_editorial) > 1 and valor_editorial != "Editorial":
                                        editorial = valor_editorial
                            except:
                                pass
                        if any(palabra in texto_fila for palabra in ['páginas', 'paginas', 'pages', 'número de páginas', 'num páginas']):
                            try:
                                valor_elementos = fila.find_elements(By.CSS_SELECTOR, ".col-xs-7 .box, .col-md-7 .box, .value, .data")
                                if valor_elementos:
                                    valor_paginas = valor_elementos[0].text.strip()
                                    if valor_paginas and any(c.isdigit() for c in valor_paginas):
                                        num_paginas = valor_paginas
                            except:
                                pass
                    except:
                        continue
                if autor != "No disponible" and editorial != "No disponible" and num_paginas != "No disponible":
                    break
            except:
                continue
        info_completa['autor'] = autor
        info_completa['editorial'] = editorial
        info_completa['num_paginas'] = num_paginas
        
        try:
            selectores_desc = [".descripcion", ".description", ".product-description", "[class*='descripcion']", "[class*='description']"]
            for sel in selectores_desc:
                try:
                    elem = driver.find_element(By.CSS_SELECTOR, sel)
                    desc = elem.text.strip()
                    if desc and len(desc) > 10:
                        info_completa['descripcion'] = desc[:500]
                        break
                except:
                    continue
        except:
            pass
        if 'descripcion' not in info_completa:
            info_completa['descripcion'] = "No disponible"

        info_completa.update(extraer_entrega_buscalibre(driver))
        
        info_completa['url_libro'] = url_libro
        
        driver.close()
        driver.switch_to.window(ventana_original)
        return info_completa
    except Exception as e:
        print(f"Error extrayendo detalle: {e}")
        try:
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
        except:
            pass
        return None


def search_buscalibre_sync(
    query: str,
    max_results: int = 5,
    ganancia_envio: float = 200,
    on_result: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """Search BuscaLibre and optionally publish each completed product immediately."""
    driver = setup_chrome_driver()
    results = []
    try:
        driver.get("https://www.buscalibre.com.mx/")
        import time
        time.sleep(2)
        
        wait = WebDriverWait(driver, 15)
        search_box = None
        for by, selector in [(By.ID, "inputSearch"), (By.NAME, "q"), (By.CSS_SELECTOR, "input[type='search']"), (By.CSS_SELECTOR, "input[placeholder*='Buscar']"), (By.XPATH, "//input[contains(@class, 'search')]")]:
            try:
                search_box = wait.until(EC.presence_of_element_located((by, selector)))
                break
            except TimeoutException:
                continue
        
        if not search_box:
            return {"results": [], "error": "Search box not found"}
        
        search_box.click()
        time.sleep(0.5)
        for char in query:
            search_box.send_keys(char)
            time.sleep(0.05)
        time.sleep(0.5)
        
        try:
            search_btn = wait.until(EC.element_to_be_clickable((By.ID, "botonBuscarHeader")))
            search_btn.click()
        except:
            search_box.submit()
        
        time.sleep(3)
        
        productos = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".box-producto")))
        productos = productos[:max_results]
        
        for i, producto in enumerate(productos, 1):
            try:
                url = extraer_url_libro(producto)
                if not url:
                    continue
                detail = extraer_detalle_libro(driver, url, i, ganancia_envio)
                if not detail:
                    continue
                available = detail.get('precio_con_envio', 'No disponible') != 'No disponible'
                book = {
                    "title": detail.get('nombre', 'No disponible'),
                    "author": detail.get('autor', 'No disponible'),
                    "price": detail.get('precio_con_envio', 'No disponible'),
                    "price_original": detail.get('precio_original', 'No disponible'),
                    "currency": "MXN",
                    "availability": available,
                    "url": detail.get('url_libro', ''),
                    "image_url": detail.get('url_imagen_hq', ''),
                    "editorial": detail.get('editorial', 'No disponible'),
                    "pages": detail.get('num_paginas', 'No disponible'),
                    "description": detail.get('descripcion', 'No disponible'),
                    "delivery_estimate": detail.get('delivery_estimate', 'No disponible'),
                    "delivery_dates": detail.get('delivery_dates', []),
                }
                results.append(book)

                # The product page has now been read completely.  Notify the
                # caller before moving to the next page so catalog persistence
                # never has to wait for the entire search batch.
                if on_result:
                    try:
                        on_result(book)
                    except Exception as callback_error:
                        print(f"Error publishing product {i}: {callback_error}")
                time.sleep(1)
            except Exception as e:
                print(f"Error extracting product {i}: {e}")
                continue
    except Exception as e:
        return {"results": [], "error": str(e)}
    finally:
        driver.quit()
    return {"results": results}


async def search_buscalibre(
    query: str,
    max_results: int = 5,
    ganancia_envio: float = 200,
    on_result: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    async with _search_semaphore:
        try:
            # Add 120 second timeout to prevent hanging
            return await asyncio.wait_for(
                asyncio.to_thread(search_buscalibre_sync, query, max_results, ganancia_envio, on_result),
                timeout=120.0
            )
        except asyncio.TimeoutError:
            return {"results": [], "error": "Search timed out after 120 seconds"}
        except Exception as e:
            return {"results": [], "error": f"Search error: {str(e)}"}


if __name__ == "__main__":
    import json
    result = asyncio.run(search_buscalibre("El Kybalion", max_results=3))
    print(json.dumps(result, ensure_ascii=False, indent=2))
