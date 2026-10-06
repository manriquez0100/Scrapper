#!/usr/bin/env python3
"""
Amazon Scraper con Selenium
Scraper robusto para Amazon México usando Selenium
"""

import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def setup_chrome():
    """Configurar Chrome con opciones anti-detección"""
    options = Options()
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    options.add_argument('--start-maximized')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

def search_amazon_books(search_term="harry potter"):
    """Buscar libros en Amazon México"""
    
    print("="*100)
    print("🛒 AMAZON MÉXICO - BUSCADOR DE LIBROS")
    print("="*100)
    print(f"\n🔍 Buscando: '{search_term}'")
    
    driver = setup_chrome()
    
    try:
        # Construir URL de búsqueda
        base_url = "https://www.amazon.com.mx"
        search_url = f"{base_url}/s?k={search_term.replace(' ', '+')}&i=stripbooks"
        
        print(f"📍 Navegando a Amazon México...")
        driver.get(search_url)
        
        # Esperar a que cargue
        time.sleep(random.uniform(3, 5))
        print("✅ Página cargada\n")
        
        # Esperar a que aparezcan los resultados
        wait = WebDriverWait(driver, 15)
        
        # Buscar productos
        print("🔎 Buscando productos en la página...")
        
        try:
            # Intentar múltiples selectores
            products = []
            
            # Selector 1
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-component-type="s-search-result"]')))
                products = driver.find_elements(By.CSS_SELECTOR, '[data-component-type="s-search-result"]')
            except:
                pass
            
            # Selector 2: Si no funcionó el primero
            if not products:
                try:
                    products = driver.find_elements(By.CSS_SELECTOR, 'div[data-asin]:not([data-asin=""])')
                except:
                    pass
            
            # Selector 3: Más genérico
            if not products:
                products = driver.find_elements(By.CSS_SELECTOR, '.s-result-item')
            
            print(f"✅ Encontrados {len(products)} productos\n")
            print("="*100)
            
            results = []
            
            for idx, product in enumerate(products[:10], 1):  # Primeros 10
                try:
                    # Título
                    try:
                        title_elem = product.find_element(By.CSS_SELECTOR, 'h2 a span')
                        title = title_elem.text.strip()
                    except:
                        title = "Sin título"
                    
                    # Precio
                    precio = "Sin precio"
                    try:
                        # Intentar precio completo
                        price_whole = product.find_element(By.CSS_SELECTOR, '.a-price-whole')
                        price_fraction = product.find_element(By.CSS_SELECTOR, '.a-price-fraction')
                        precio = f"${price_whole.text}{price_fraction.text}"
                    except:
                        try:
                            # Precio alternativo
                            price_elem = product.find_element(By.CSS_SELECTOR, '.a-price .a-offscreen')
                            precio = price_elem.get_attribute('textContent')
                        except:
                            pass
                    
                    # URL
                    url = ""
                    try:
                        link_elem = product.find_element(By.CSS_SELECTOR, 'h2 a')
                        url = link_elem.get_attribute('href')
                    except:
                        pass
                    
                    # Guardar resultado
                    result = {
                        'numero': idx,
                        'titulo': title,
                        'precio': precio,
                        'url': url
                    }
                    results.append(result)
                    
                    # Mostrar
                    print(f"📖 LIBRO #{idx}")
                    print(f"   Título: {title[:80]}{'...' if len(title) > 80 else ''}")
                    print(f"   💰 Precio: {precio}")
                    if url:
                        print(f"   🔗 URL: {url[:70]}...")
                    print("-"*100)
                    
                except Exception as e:
                    print(f"⚠️  Error procesando producto #{idx}: {e}")
                    continue
            
            print("="*100)
            print(f"\n✅ RESUMEN: Se encontraron {len(results)} productos con información\n")
            
            if results:
                print("📋 LISTA DE PRODUCTOS Y PRECIOS:")
                for r in results:
                    print(f"   {r['numero']}. {r['titulo'][:60]}... - {r['precio']}")
            
            # Mantener navegador abierto para ver resultados
            print("\n💡 El navegador permanecerá abierto.")
            print("   Presiona Ctrl+C en la terminal cuando termines...")
            
            while True:
                time.sleep(1)
            
        except Exception as e:
            print(f"❌ Error buscando productos: {e}")
            print("\n💡 Guardando captura de pantalla para análisis...")
            driver.save_screenshot('amazon_error.png')
            print("📸 Captura guardada: amazon_error.png")
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrumpido por el usuario")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n🔒 Cerrando navegador...")
        driver.quit()
        print("✅ Navegador cerrado")

if __name__ == "__main__":
    search_amazon_books("harry potter")
