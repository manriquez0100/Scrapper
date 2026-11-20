"""
Price Management Module
Módulo para gestión y actualización de precios
Utilizado en BuscaLibre y MercadoLibre scrapers
"""

import re
import random


class PriceManager:
    """Clase para gestionar cálculos y actualizaciones de precios"""
    
    def __init__(self, ganancia_envio=100, strategy="smart_ending"):
        """
        Inicializa el gestor de precios
        
        Args:
            ganancia_envio (int): Ganancia fija por envío
            strategy (str): Estrategia de precios ('smart_ending', 'round', 'exact')
        """
        self.ganancia_envio = ganancia_envio
        self.strategy = strategy
    
    def clean_price(self, precio_str):
        """
        Limpia y convierte string de precio a número
        
        Args:
            precio_str: String con precio (ej: "$1,234.56", "1234", "$ 1.234,56")
            
        Returns:
            float: Precio como número decimal
        """
        if not precio_str:
            return 0.0
        
        # Convertir a string por si es número
        precio_str = str(precio_str)
        
        # Remover símbolos de moneda, espacios y caracteres no numéricos excepto . y ,
        precio_clean = re.sub(r'[^\d.,]', '', precio_str)
        
        # Manejar diferentes formatos (1,234.56 vs 1.234,56)
        if ',' in precio_clean and '.' in precio_clean:
            # Formato: 1,234.56 (punto decimal)
            if precio_clean.rindex(',') < precio_clean.rindex('.'):
                precio_clean = precio_clean.replace(',', '')
            # Formato: 1.234,56 (coma decimal)
            else:
                precio_clean = precio_clean.replace('.', '').replace(',', '.')
        elif ',' in precio_clean:
            # Solo comas - puede ser separador de miles o decimal
            parts = precio_clean.split(',')
            if len(parts) == 2 and len(parts[1]) <= 2:
                # Probablemente decimal: 1234,56
                precio_clean = precio_clean.replace(',', '.')
            else:
                # Separador de miles: 1,234,567
                precio_clean = precio_clean.replace(',', '')
        
        try:
            return float(precio_clean)
        except ValueError:
            print(f"⚠️ Error convirtiendo precio: {precio_str}")
            return 0.0
    
    def calculate_final_price(self, precio_original):
        """
        Calcula precio final con ganancia y estrategia
        
        Args:
            precio_original: Precio original (string o número)
            
        Returns:
            dict: {
                'precio_original': float,
                'ganancia_envio': float, 
                'precio_con_envio': float,
                'precio_final': float,
                'strategy_applied': str
            }
        """
        precio_base = self.clean_price(precio_original)
        
        if precio_base <= 0:
            return {
                'precio_original': 0,
                'ganancia_envio': 0,
                'precio_con_envio': 0,
                'precio_final': 0,
                'strategy_applied': 'error'
            }
        
        precio_con_envio = precio_base + self.ganancia_envio
        precio_final = self.apply_pricing_strategy(precio_con_envio)
        
        return {
            'precio_original': precio_base,
            'ganancia_envio': self.ganancia_envio,
            'precio_con_envio': precio_con_envio,
            'precio_final': precio_final,
            'strategy_applied': self.strategy
        }
    
    def apply_pricing_strategy(self, precio):
        """
        Aplica estrategia de precios al precio calculado
        
        Args:
            precio (float): Precio base
            
        Returns:
            float: Precio con estrategia aplicada
        """
        if self.strategy == "smart_ending":
            return self.smart_ending_strategy(precio)
        elif self.strategy == "round":
            return self.round_strategy(precio)
        elif self.strategy == "exact":
            return precio
        else:
            return self.smart_ending_strategy(precio)  # Default
    
    def smart_ending_strategy(self, precio):
        """
        Estrategia de precios terminados en 9
        Ej: 156.7 -> 159, 203.2 -> 209
        
        Args:
            precio (float): Precio original
            
        Returns:
            float: Precio terminado en 9
        """
        precio_int = int(precio)
        
        # Si ya termina en 9, mantenerlo
        if precio_int % 10 == 9:
            return float(precio_int)
        
        # Redondear al siguiente 9
        precio_final = (precio_int // 10) * 10 + 9
        
        # Si el precio final es menor que el original, sumar 10
        if precio_final < precio:
            precio_final += 10
        
        return float(precio_final)
    
    def round_strategy(self, precio):
        """
        Estrategia de redondeo estándar
        
        Args:
            precio (float): Precio original
            
        Returns:
            float: Precio redondeado
        """
        return round(precio)
    
    def format_price(self, precio, currency="$", thousands_sep=","):
        """
        Formatea precio para mostrar
        
        Args:
            precio: Precio a formatear
            currency: Símbolo de moneda
            thousands_sep: Separador de miles
            
        Returns:
            str: Precio formateado (ej: "$1,259")
        """
        if precio <= 0:
            return f"{currency}0"
        
        precio_int = int(precio)
        precio_str = f"{precio_int:,}".replace(",", thousands_sep)
        return f"{currency}{precio_str}"
    
    def calculate_discount_percentage(self, precio_original, precio_final):
        """
        Calcula porcentaje de descuento aparente
        
        Args:
            precio_original (float): Precio original
            precio_final (float): Precio final
            
        Returns:
            float: Porcentaje de descuento
        """
        if precio_original <= 0:
            return 0
        
        # Simular precio "anterior" más alto para marketing
        precio_referencia = precio_original * 1.4
        descuento = ((precio_referencia - precio_final) / precio_referencia) * 100
        return max(0, round(descuento))
    
    def generate_pricing_summary(self, libro_info):
        """
        Genera resumen completo de precios para un libro
        
        Args:
            libro_info (dict): Información del libro con precio_original
            
        Returns:
            dict: Resumen completo de precios
        """
        precio_data = self.calculate_final_price(libro_info.get('precio_original', 0))
        
        precio_referencia = precio_data['precio_original'] * 1.4
        descuento = self.calculate_discount_percentage(precio_data['precio_original'], precio_data['precio_final'])
        
        summary = {
            **precio_data,
            'precio_referencia': precio_referencia,
            'descuento_porcentaje': descuento,
            'precio_original_formatted': self.format_price(precio_data['precio_original']),
            'precio_final_formatted': self.format_price(precio_data['precio_final']),
            'precio_referencia_formatted': self.format_price(precio_referencia),
            'ganancia_total': precio_data['precio_final'] - precio_data['precio_original']
        }
        
        return summary


# Funciones de conveniencia para usar directamente
def update_book_prices(libro_info, ganancia_envio=100, strategy="smart_ending"):
    """
    Función de conveniencia para actualizar precios de un libro
    
    Args:
        libro_info (dict): Información del libro
        ganancia_envio (int): Ganancia por envío
        strategy (str): Estrategia de precios
        
    Returns:
        dict: libro_info actualizado con precios calculados
    """
    price_manager = PriceManager(ganancia_envio, strategy)
    pricing_summary = price_manager.generate_pricing_summary(libro_info)
    
    # Actualizar libro_info con precios calculados
    libro_info.update({
        'precio_con_envio': str(pricing_summary['precio_final']),
        'precio_referencia': str(pricing_summary['precio_referencia']),
        'descuento_porcentaje': pricing_summary['descuento_porcentaje'],
        'ganancia_total': pricing_summary['ganancia_total'],
        'precio_original_formatted': pricing_summary['precio_original_formatted'],
        'precio_final_formatted': pricing_summary['precio_final_formatted'],
        'strategy_applied': pricing_summary['strategy_applied']
    })
    
    return libro_info


def batch_update_prices(libros_list, ganancia_envio=100, strategy="smart_ending"):
    """
    Actualiza precios para una lista de libros
    
    Args:
        libros_list (list): Lista de diccionarios con información de libros
        ganancia_envio (int): Ganancia por envío
        strategy (str): Estrategia de precios
        
    Returns:
        list: Lista de libros con precios actualizados
    """
    price_manager = PriceManager(ganancia_envio, strategy)
    
    updated_libros = []
    for libro in libros_list:
        updated_libro = update_book_prices(libro, ganancia_envio, strategy)
        updated_libros.append(updated_libro)
    
    return updated_libros


# Configuraciones predefinidas
PRICING_CONFIGS = {
    'conservative': {'ganancia_envio': 50, 'strategy': 'round'},
    'standard': {'ganancia_envio': 100, 'strategy': 'smart_ending'},
    'aggressive': {'ganancia_envio': 200, 'strategy': 'smart_ending'},
    'premium': {'ganancia_envio': 300, 'strategy': 'smart_ending'}
}


def apply_pricing_config(libro_info, config_name='standard'):
    """
    Aplica configuración de precios predefinida
    
    Args:
        libro_info (dict): Información del libro
        config_name (str): Nombre de la configuración
        
    Returns:
        dict: libro_info con precios actualizados
    """
    config = PRICING_CONFIGS.get(config_name, PRICING_CONFIGS['standard'])
    return update_book_prices(libro_info, **config)


if __name__ == "__main__":
    # Ejemplos de uso
    print("🧪 Testing Price Manager...")
    
    # Ejemplo 1: Libro básico
    libro_test = {
        'nombre': 'Test Book',
        'precio_original': '468.3',
        'autor': 'Test Author'
    }
    
    resultado = update_book_prices(libro_test, ganancia_envio=100)
    print(f"📚 Libro: {resultado['nombre']}")
    print(f"💰 Precio original: {resultado['precio_original_formatted']}")
    print(f"✨ Precio final: {resultado['precio_final_formatted']}")
    print(f"📈 Estrategia: {resultado['strategy_applied']}")
    print(f"🎯 Ganancia: ${resultado['ganancia_total']:.0f}")
    
    # Ejemplo 2: Diferentes formatos de precio
    formatos_test = ['$1,234.56', '1.234,56', '1234', '$1234.00']
    pm = PriceManager()
    
    print("\n🔧 Testing price formats:")
    for formato in formatos_test:
        cleaned = pm.clean_price(formato)
        print(f"   {formato} -> {cleaned}")