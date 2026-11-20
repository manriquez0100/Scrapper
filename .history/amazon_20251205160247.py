#!/usr/bin/env python3
"""
AMAZON.PY - ARCHIVO NO FUNCIONAL

NOTA: Este archivo requiere módulos que fueron eliminados:
- triple_mexico_ecommerce_scraper
- whatsapp_formatter
- customer_display
- scraper/amazon_scraper

Para scraping funcional, use: buscalibre.py

Uso de buscalibre.py:
    .venv/Scripts/python.exe buscalibre.py

"""

import json
import sys
import os

print("❌ ERROR: Este archivo (amazon.py) no está funcional")
print("📌 Los módulos necesarios fueron eliminados")
print("")
print("✅ Use el archivo funcional: buscalibre.py")
print("   Comando: .venv/Scripts/python.exe buscalibre.py")
print("")
sys.exit(1)

def execute_improved_scraper():
    """Execute the improved scraper with all latest features."""
    
    print("=" * 120)
    print("📚 BUSCADOR DE LIBROS MÉXICO - VERSIÓN MEJORADA")
    print("=" * 120)
    print("🎯 MEJORAS IMPLEMENTADAS:")
    print("   ✅ Amazon: Tiempo de entrega fijo 7-10 días para clientes")
    print("   ✅ Imágenes de portadas de libros")
    print("   ✅ Costo de servicio: $149 MXN")
    print("   ✅ Ordenado: Mayor a menor precio")
    print("   ✅ Sección empleados: URLs completas")
    print("   ✅ Sección clientes: Sin URLs, sin reseñas")
    print("=" * 120)
    print()
    
    # Initialize scraper
    scraper = TripleMexicoEcommerceScraper()
    
    # Get search term
    if len(sys.argv) > 1:
        # Command line argument
        search_term = " ".join(sys.argv[1:])
        print(f"📖 Buscando: '{search_term}'")
    else:
        try:
            search_term = input("🔍 Ingrese el nombre del libro a buscar: ").strip()
            if not search_term:
                print("❌ Debe ingresar un término de búsqueda")
                return
            print(f"\n📖 Buscando: '{search_term}'")
        except EOFError:
            print("❌ No se pudo leer el término de búsqueda")
            return

    print(" Buscando en Amazon Prime México...")
    print("⏳ Esto puede tomar unos momentos...")
    print()

    try:
        # Amazon-only: search and extract
        search_results = scraper.search_all(search_term, max_results=10)
        
        # Verificar que tenemos resultados
        if not search_results or not isinstance(search_results, dict):
            print("❌ No se obtuvieron resultados válidos de Amazon")
            print("💡 Amazon puede estar bloqueando las solicitudes. Intente nuevamente en unos minutos.")
            return
        
        amazon_urls = search_results.get('amazon', [])
        if not amazon_urls:
            print("❌ No se encontraron libros en Amazon México")
            print("💡 Intente con otro término de búsqueda")
            return
        
        print(f"✅ Encontrados {len(amazon_urls)} URLs de Amazon")
        
        results = scraper.extract_product_data_from_all(search_results, max_extracts_per_platform=10)
        print("🔄 Mostrando resultados con mejoras...")
        print()
        scraper.customer_display.display_two_part_results(results)
        
        # NEW: Generate WhatsApp/Messenger package with images
        print("\n" + "📱" * 120)
        print("🔥 GENERANDO FORMATO ESPECIAL PARA WHATSAPP/MESSENGER CON IMÁGENES")
        print("📱" * 120)
        
        # Create chat formatter and generate package
        chat_formatter = WhatsAppChatFormatter()
        chat_package = chat_formatter.create_chat_package(results, search_term)
        
        if chat_package:
            print("\n" + "✅" * 120)
            print("🎉 PAQUETE DE CHAT GENERADO EXITOSAMENTE!")
            print("✅" * 120)
            
            # Show what was generated
            images_with_urls = sum(1 for msg in chat_package if msg.get('image_url'))
            total_books = len(chat_package)
            
            print(f"📊 ESTADÍSTICAS:")
            print(f"   📚 Libros procesados: {total_books}")
            print(f"   🖼️  URLs de imágenes: {images_with_urls}")
            print(f"   � Formato: URLs en lugar de archivos descargados")
            print(f"   📋 Archivos generados:")
            print(f"      • INSTRUCCIONES_CHAT_{search_term.replace(' ', '_')}.txt")
            print(f"      • RESUMEN_CHAT_{search_term.replace(' ', '_')}.txt")
            
            print(f"\n🎯 CÓMO USAR EN WHATSAPP/MESSENGER:")
            print("   1️⃣ Abre el archivo INSTRUCCIONES_CHAT_...")
            print("   2️⃣ Para cada libro:")
            print("      📎 Adjunta la imagen JPG correspondiente")  
            print("      📝 Copia y pega el texto del libro")
            print("   3️⃣ Envía mensaje por mensaje")
            print("\n💡 RESULTADO: El cliente verá imagen + información como en el ejemplo")
            
            # Show preview of first book for demonstration
            if chat_package:
                first_book = chat_package[0]
                print(f"\n🔍 VISTA PREVIA - LIBRO 1:")
                print("─" * 60)
                print(f"📎 URL IMAGEN: {first_book.get('image_url', 'Sin imagen')}")
                print("📝 TEXTO A COPIAR:")
                print(first_book['message_text'])
                print("─" * 60)
            
            print("✅" * 120)
        else:
            print("❌ No se pudo generar el paquete de chat")
        
        # Save enhanced results
        filename = f"enhanced_results_{search_term.replace(' ', '_')}.json"
        
        # Prepare enhanced data for JSON
        all_products = []
        for platform_key, platform_data in results.items():
            products = platform_data.get('products', [])
            platform_name = platform_data.get('platform', platform_key)
            
            for product in products:
                product['platform'] = platform_name
                raw_price = product.get('price', '')
                numeric_price = scraper.customer_display.extract_numeric_price(raw_price)
                product['total_price_numeric'] = numeric_price + 149 if numeric_price > 0 else 0
                
                # Add delivery info for customer section
                if "Amazon" in platform_name:
                    product['customer_delivery'] = "Llega en 7 a 10 días"
                else:
                    product['customer_delivery'] = scraper.customer_display.format_arrival_time(
                        product.get('availability', ''), platform_name
                    )
                
                all_products.append(product)
        
        # Sort by price (highest to lowest)
        all_products.sort(key=lambda x: x.get('total_price_numeric', 0), reverse=True)
        
        enhanced_data = {
            'search_term': search_term,
            'timestamp': '2025-10-11',
            'improvements': {
                'amazon_delivery_fixed': '7-10 days',
                'book_covers_included': True,
                'service_fee': 149,
                'price_sorting': 'highest_to_lowest',
                'two_part_display': True
            },
            'summary': {
                'total_books': len(all_products),
                'amazon_books': len([p for p in all_products if 'Amazon' in p.get('platform', '')]),
                'mercado_libre_books': len([p for p in all_products if 'Mercado Libre' in p.get('platform', '')]),
                'buscalibre_books': len([p for p in all_products if 'Buscalibre' in p.get('platform', '')])
            },
            'books': all_products,
            'raw_platform_data': results
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(enhanced_data, f, ensure_ascii=False, indent=2)
        
        print(f"\\n💾 Resultados guardados en: {filename}")
        
        # Final summary
        print(f"\\n{'='*120}")
        print("✅ EJECUCIÓN COMPLETADA CON ÉXITO")
        print(f"📚 {len(all_products)} libros encontrados y ordenados por precio")
        print("🎯 Todas las mejoras implementadas correctamente")
        print(f"{'='*120}")
        
    except KeyboardInterrupt:
        print("\\n⚠️  Búsqueda interrumpida por el usuario")
    except Exception as e:
        print(f"❌ Error durante la búsqueda: {e}")
        print("💡 Intente ejecutar nuevamente")

if __name__ == "__main__":
    execute_improved_scraper()