"""Customer Display - Formatea y muestra información de productos para clientes"""

import re
from datetime import datetime, timedelta

class CustomerDisplay:
    def __init__(self):
        self.service_fee = 149
    
    def extract_numeric_price(self, price_str):
        """Extraer precio numérico de string"""
        if not price_str:
            return 0
        
        numbers = re.findall(r'[\d,]+\.?\d*', str(price_str))
        if numbers:
            try:
                return float(numbers[0].replace(',', ''))
            except:
                return 0
        return 0
    
    def format_arrival_time(self, availability, platform):
        """Formatear tiempo de llegada"""
        if "Amazon" in platform:
            return "Llega en 7 a 10 días"
        return availability if availability else "Consultar disponibilidad"
    
    def display_two_part_results(self, results):
        """Mostrar resultados en dos partes: Empleados y Clientes"""
        
        all_products = []
        for platform_key, platform_data in results.items():
            products = platform_data.get('products', [])
            for product in products:
                product['platform'] = platform_data.get('platform', platform_key)
                product['total_price'] = self.extract_numeric_price(product.get('price', '')) + self.service_fee
                all_products.append(product)
        
        all_products.sort(key=lambda x: x.get('total_price', 0), reverse=True)
        
        if not all_products:
            print("❌ No se encontraron productos")
            return
        
        # SECCIÓN EMPLEADOS
        print("\n" + "="*120)
        print("👨‍💼 SECCIÓN EMPLEADOS - INFORMACIÓN COMPLETA")
        print("="*120)
        
        for i, product in enumerate(all_products, 1):
            print(f"\n📦 PRODUCTO #{i}")
            print("-" * 120)
            print(f"📕 Título: {product.get('title', 'N/A')}")
            print(f"💰 Precio: {product.get('price', 'N/A')}")
            print(f"💵 Precio Total (+ $149 servicio): ${product.get('total_price', 0):.2f}")
            print(f"🏪 Plataforma: {product.get('platform', 'N/A')}")
            print(f"⭐ Rating: {product.get('rating', 'N/A')}")
            print(f"📦 Disponibilidad: {product.get('availability', 'N/A')}")
            print(f"🔗 URL: {product.get('url', 'N/A')}")
            if product.get('image_url'):
                print(f"🖼️  Imagen: {product.get('image_url')}")
        
        # SECCIÓN CLIENTES
        print("\n" + "="*120)
        print("👤 SECCIÓN CLIENTES - INFORMACIÓN SIMPLIFICADA")
        print("="*120)
        
        for i, product in enumerate(all_products, 1):
            delivery = self.format_arrival_time(product.get('availability', ''), product.get('platform', ''))
            
            print(f"\n📖 Libro #{i}")
            print("-" * 120)
            print(f"📕 {product.get('title', 'N/A')}")
            print(f"💵 Precio Final: ${product.get('total_price', 0):.2f} MXN")
            print(f"🚚 {delivery}")
            if product.get('image_url'):
                print(f"🖼️  [Ver portada del libro]")
        
        print("\n" + "="*120)
        print(f"✅ Total de productos encontrados: {len(all_products)}")
        print("="*120)
