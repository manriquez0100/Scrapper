"""WhatsApp Formatter - Crea mensajes formateados para WhatsApp/Messenger"""

import re

class WhatsAppChatFormatter:
    def __init__(self):
        self.service_fee = 149
    
    def create_chat_package(self, results, search_term):
        """Crear paquete de mensajes para WhatsApp/Messenger"""
        
        all_products = []
        for platform_key, platform_data in results.items():
            products = platform_data.get('products', [])
            for product in products:
                all_products.append(product)
        
        if not all_products:
            return None
        
        messages = []
        for i, product in enumerate(all_products, 1):
            price = self._extract_price(product.get('price', ''))
            total_price = price + self.service_fee
            
            message_text = f"""📖 Libro #{i}

📕 {product.get('title', 'N/A')}

💵 Precio Final: ${total_price:.2f} MXN
🚚 Llega en 7 a 10 días

¿Te interesa? 😊"""
            
            messages.append({
                'number': i,
                'message_text': message_text,
                'image_url': product.get('image_url', ''),
                'product_url': product.get('url', '')
            })
        
        self._save_instructions(messages, search_term)
        self._save_summary(messages, search_term)
        
        return messages
    
    def _extract_price(self, price_str):
        """Extraer precio numérico"""
        if not price_str:
            return 0
        numbers = re.findall(r'[\d,]+\.?\d*', str(price_str))
        if numbers:
            try:
                return float(numbers[0].replace(',', ''))
            except:
                return 0
        return 0
    
    def _save_instructions(self, messages, search_term):
        """Guardar archivo de instrucciones"""
        filename = f"INSTRUCCIONES_CHAT_{search_term.replace(' ', '_')}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("📱 INSTRUCCIONES PARA ENVIAR EN WHATSAPP/MESSENGER\n")
            f.write("="*80 + "\n\n")
            f.write(f"Búsqueda: {search_term}\n")
            f.write(f"Total de libros: {len(messages)}\n\n")
            
            for msg in messages:
                f.write(f"\n{'─'*80}\n")
                f.write(f"LIBRO #{msg['number']}\n")
                f.write(f"{'─'*80}\n\n")
                f.write(f"📎 PASO 1: Adjuntar imagen desde URL:\n")
                f.write(f"{msg['image_url']}\n\n")
                f.write(f"📝 PASO 2: Copiar y pegar este texto:\n\n")
                f.write(msg['message_text'])
                f.write("\n\n")
    
    def _save_summary(self, messages, search_term):
        """Guardar archivo de resumen"""
        filename = f"RESUMEN_CHAT_{search_term.replace(' ', '_')}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("📊 RESUMEN DE MENSAJES GENERADOS\n")
            f.write("="*80 + "\n\n")
            f.write(f"Búsqueda: {search_term}\n")
            f.write(f"Total de mensajes: {len(messages)}\n")
            f.write(f"Imágenes con URL: {sum(1 for m in messages if m['image_url'])}\n\n")
            
            for msg in messages:
                f.write(f"\nLibro #{msg['number']}:\n")
                f.write(f"  - Tiene imagen: {'Sí' if msg['image_url'] else 'No'}\n")
                f.write(f"  - URL producto: {msg['product_url'][:50]}...\n")
