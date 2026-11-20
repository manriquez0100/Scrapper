
"""
AMAZON MEXICO SCRAPER (SOLO AMAZON FUNCIONAL)
==============================================================
"""


from scraper.amazon_scraper import AmazonScraper
from customer_display import CustomerDisplay

class TripleMexicoEcommerceScraper:
    def __init__(self):
        self.amazon_scraper = AmazonScraper(country='MX')
        self.customer_display = CustomerDisplay()

    def search_all(self, product_name, max_results=4):
        """Buscar solo en Amazon México (estado funcional restaurado)"""
        print("\n1️⃣ Searching Amazon Mexico (Prime books only)...")
        amazon_results = self.amazon_scraper.search_books_by_name(product_name, max_results=max_results)
        return {'amazon': amazon_results}

    def extract_product_data_from_all(self, search_results, max_extracts_per_platform=3):
        """Extraer datos solo de Amazon México (estado funcional restaurado)"""
        amazon_data = []
        for url in search_results.get('amazon', [])[:max_extracts_per_platform]:
            product_info = self.amazon_scraper.get_product_info(url)
            if product_info:
                amazon_data.append(product_info)
        
        return {
            'amazon': {
                'products': amazon_data,
                'platform': 'Amazon México'
            }
        }
        all_products = (
            results['amazon_mexico']['products'] + 
            results['mercado_libre']['products'] +
            results['buscalibre']['products']
        )
        
        if all_products:
            unified_filename = f"mexico_ecommerce_{product_name.replace(' ', '_')}_unified.json"
            try:
                with open(unified_filename, 'w', encoding='utf-8') as f:
                    json.dump({
                        'search_term': product_name,
                        'total_products': len(all_products),
                        'amazon_mexico_count': len(results['amazon_mexico']['products']),
                        'mercado_libre_count': len(results['mercado_libre']['products']),
                        'buscalibre_count': len(results['buscalibre']['products']),
                        'products': all_products
                    }, f, indent=2, ensure_ascii=False)
                print(f"\\n💾 Unified results saved to: {unified_filename}")
            except Exception as e:
                print(f"Error saving unified results: {e}")

def main():
    print("AMAZON MEXICO SCRAPER (SOLO AMAZON FUNCIONAL)")
    print("="*70)
    scraper = TripleMexicoEcommerceScraper()
    product_name = input("Enter a product name to search on Amazon Mexico: ").strip()
    if not product_name:
        product_name = "laptop"
        print(f"Using default search: '{product_name}'")
    try:
        search_results = scraper.search_all(product_name, max_results=10)
        complete_results = scraper.extract_product_data_from_all(search_results, max_extracts_per_platform=3)
        scraper.customer_display.display_customer_products(complete_results)
        print(f"\n{'='*80}")
        print("INFORMACIÓN TÉCNICA (PARA DESARROLLO)")
        print(f"{'='*80}")
        # Optionally display technical details here
        print(complete_results)
    except Exception as e:
        print(f"\nError during execution: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()