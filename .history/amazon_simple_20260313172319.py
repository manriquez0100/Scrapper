#!/usr/bin/env python3
"""
Amazon Simple Scraper
Script simple para buscar libros en Amazon México y obtener precios
"""

import requests
from bs4 import BeautifulSoup
import time
import random

def search_amazon_books(search_term):
    """Buscar libros en Amazon México"""
    
    # URL de búsqueda en Amazon México
    base_url = "https://www.amazon.com.mx"
    search_url = f"{base_url}/s?k={search_term.replace(' ', '+')}&i=stripbooks"
    
    # Headers para parecer un navegador real
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'es-MX,es;q=0.9,en;q=0.8',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    print(f"🔍 Buscando '{search_term}' en Amazon México...")
    print(f"📍 URL: {search_url}\n")
    
    try:
        # Pausa para no parecer bot
        time.sleep(random.uniform(1, 3))
        
        # Hacer request
        response = requests.get(search_url, headers=headers, timeout=15)
        
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Amazon devolvió código: {response.status_code}")
            print("💡 Intenta nuevamente en unos minutos")
            return []
        
        # Parsear HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Encontrar productos - Intentar múltiples selectores
        products = []
        
        # Selector 1: data-component-type
        results = soup.find_all('div', {'data-component-type': 's-search-result'})
        
        # Selector 2: Si no hay resultados, buscar por clase
        if not results:
            results = soup.find_all('div', {'class': 's-result-item'})
        
        # Selector 3: Buscar cualquier div con data-asin
        if not results:
            results = soup.find_all('div', attrs={'data-asin': True})
            results = [r for r in results if r.get('data-asin') and r.get('data-asin') != '']
        
        print(f"✅ Encontrados {len(results)} resultados\n")
        
        # Debug: guardar HTML para análisis
        if len(results) == 0:
            with open('amazon_debug.html', 'w', encoding='utf-8') as f:
                f.write(str(soup.prettify()))
            print("📝 HTML guardado en amazon_debug.html para análisis\n")
        
        print("="*100)
        
        for idx, result in enumerate(results[:10], 1):  # Primeros 10 resultados
            try:
                # Título
                title_tag = result.find('h2', {'class': 'a-size-mini'})
                if not title_tag:
                    title_tag = result.find('span', {'class': 'a-size-medium a-color-base a-text-normal'})
                
                title = title_tag.get_text(strip=True) if title_tag else "Sin título"
                
                # Precio
                price = "Sin precio"
                
                # Intentar diferentes selectores de precio
                price_whole = result.find('span', {'class': 'a-price-whole'})
                price_fraction = result.find('span', {'class': 'a-price-fraction'})
                
                if price_whole:
                    price = f"${price_whole.get_text(strip=True)}"
                    if price_fraction:
                        price += price_fraction.get_text(strip=True)
                    price = price.replace('\xa0', ' ').replace('..', '')
                else:
                    # Buscar precio alternativo
                    price_tag = result.find('span', {'class': 'a-price'})
                    if price_tag:
                        price_span = price_tag.find('span', {'class': 'a-offscreen'})
                        if price_span:
                            price = price_span.get_text(strip=True)
                
                # URL del producto
                link_tag = result.find('a', {'class': 'a-link-normal s-no-outline'})
                if not link_tag:
                    link_tag = result.find('a', {'class': 'a-link-normal s-underline-text s-underline-link-text s-link-style a-text-normal'})
                
                url = ""
                if link_tag and link_tag.get('href'):
                    url = base_url + link_tag['href']
                
                # Almacenar producto
                product = {
                    'numero': idx,
                    'titulo': title,
                    'precio': price,
                    'url': url
                }
                products.append(product)
                
                # Mostrar producto
                print(f"📖 LIBRO #{idx}")
                print(f"   Título: {title[:80]}{'...' if len(title) > 80 else ''}")
                print(f"   💰 Precio: {price}")
                if url:
                    print(f"   🔗 URL: {url[:70]}...")
                print("-"*100)
                
            except Exception as e:
                print(f"⚠️  Error procesando resultado #{idx}: {e}")
                continue
        
        print("="*100)
        print(f"\n✅ Total de productos extraídos: {len(products)}")
        
        return products
        
    except requests.exceptions.Timeout:
        print("❌ Timeout: Amazon tardó demasiado en responder")
        return []
    except requests.exceptions.RequestException as e:
        print(f"❌ Error de conexión: {e}")
        return []
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        return []

def main():
    """Función principal"""
    print("="*100)
    print("🛒 AMAZON MÉXICO - BUSCADOR DE LIBROS")
    print("="*100)
    print()
    
    # Buscar "harry potter"
    search_term = "harry potter"
    products = search_amazon_books(search_term)
    
    if products:
        print(f"\n💾 Se encontraron {len(products)} productos con precios")
        print("\n📋 RESUMEN:")
        for p in products:
            print(f"   {p['numero']}. {p['titulo'][:50]}... - {p['precio']}")
    else:
        print("\n❌ No se pudieron obtener productos")
        print("💡 Posibles causas:")
        print("   - Amazon está bloqueando las solicitudes")
        print("   - Problema de conexión a internet")
        print("   - Cambios en la estructura HTML de Amazon")

if __name__ == "__main__":
    main()
