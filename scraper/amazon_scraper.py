"""Amazon Scraper con Selenium - Más robusto contra anti-bot"""

import time
import random
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

class AmazonScraper:
    def __init__(self, country='MX'):
        self.country = country
        if country == 'MX':
            self.base_url = 'https://www.amazon.com.mx'
        else:
            self.base_url = 'https://www.amazon.com'
        
        self.driver = None
        self._setup_driver()
    
    def _setup_driver(self):
        """Configurar Chrome con anti-detección"""
        options = Options()
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        # options.add_argument('--headless')  # Comentado para ver qué pasa
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--start-maximized')
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    def __del__(self):
        """Cerrar navegador"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
    
    def search_books_by_name(self, book_name, max_results=10):
        """Buscar libros en Amazon"""
        search_url = f"{self.base_url}/s?k={book_name.replace(' ', '+')}&i=stripbooks"
        
        try:
            print(f"   🌐 Navegando a Amazon...")
            self.driver.get(search_url)
            time.sleep(random.uniform(4, 6))
            
            # Guardar screenshot para debug
            self.driver.save_screenshot('amazon_search_debug.png')
            
            product_links = []
            
            # Probar múltiples selectores
            products = self.driver.find_elements(By.CSS_SELECTOR, 'div[data-asin]:not([data-asin=""])')
            if not products:
                products = self.driver.find_elements(By.CSS_SELECTOR, '.s-result-item')
            if not products:
                products = self.driver.find_elements(By.CSS_SELECTOR, '[data-component-type="s-search-result"]')
            
            print(f"   📦 {len(products)} productos en página")
            
            for product in products[:max_results * 2]:
                try:
                    link_elem = product.find_element(By.CSS_SELECTOR, 'h2 a')
                    href = link_elem.get_attribute('href')
                    
                    if href and ('/dp/' in href or '/gp/product/' in href):
                        asin_match = re.search(r'/dp/([A-Z0-9]{10})', href)
                        if not asin_match:
                            asin_match = re.search(r'/gp/product/([A-Z0-9]{10})', href)
                        
                        if asin_match:
                            asin = asin_match.group(1)
                            clean_url = f"{self.base_url}/dp/{asin}"
                            if clean_url not in product_links:
                                product_links.append(clean_url)
                                
                            if len(product_links) >= max_results:
                                break
                except:
                    continue
            
            print(f"   ✅ {len(product_links)} URLs extraídas")
            return product_links
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return []
    
    def get_product_info(self, url):
        """Obtener info de producto"""
        try:
            time.sleep(random.uniform(2, 4))
            self.driver.get(url)
            time.sleep(random.uniform(2, 3))
            
            title = ''
            try:
                title_elem = self.driver.find_element(By.ID, 'productTitle')
                title = title_elem.text.strip()
            except:
                pass
            
            price = ''
            try:
                price_whole = self.driver.find_element(By.CSS_SELECTOR, '.a-price-whole')
                price_fraction = self.driver.find_element(By.CSS_SELECTOR, '.a-price-fraction')
                price = f"${price_whole.text}{price_fraction.text}"
            except:
                try:
                    price_elem = self.driver.find_element(By.CSS_SELECTOR, '.a-price .a-offscreen')
                    price = price_elem.get_attribute('textContent')
                except:
                    pass
            
            image_url = ''
            try:
                img_elem = self.driver.find_element(By.ID, 'landingImage')
                image_url = img_elem.get_attribute('src')
            except:
                try:
                    img_elem = self.driver.find_element(By.CSS_SELECTOR, 'img[data-a-dynamic-image]')
                    image_url = img_elem.get_attribute('src')
                except:
                    pass
            
            rating = ''
            try:
                rating_elem = self.driver.find_element(By.CSS_SELECTOR, '.a-icon-alt')
                rating = rating_elem.text.strip()
            except:
                pass
            
            availability = 'Disponible'
            try:
                avail_elem = self.driver.find_element(By.ID, 'availability')
                availability = avail_elem.text.strip()
            except:
                pass
            
            if not title:
                return None
            
            return {
                'title': title,
                'price': price if price else 'Precio no disponible',
                'rating': rating,
                'availability': availability,
                'url': url,
                'image_url': image_url
            }
            
        except Exception as e:
            return None
