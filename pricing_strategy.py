"""
Módulo de pricing inteligente para libros.

Implementa estrategias de pricing psicológico y maximización de ganancias
para sustituir o complementar la lógica actual de ganancia_envio fija.

Sustituye el modelo de: precio_actual = precio_original + ganancia_envio_fija
Con un modelo inteligente que evalúa precios psicológicos, márgenes y
competitividad para seleccionar el precio óptimo de venta.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Tuple, Optional, List


# Umbrales psicológicos de precio (rangos comerciales comunes)
PRICE_BRACKETS = [
    (0, 50, 5),    # $0-50 -> incrementos de $5
    (50, 100, 10), # $50-100 -> incrementos de $10
    (100, 200, 20),# $100-200 -> incrementos de $20
    (200, 500, 50),# $200-500 -> incrementos de $50
    (500, 1000, 100), # $500-1000 -> incrementos de $100
    (1000, float('inf'), 200), # $1000+ -> incrementos de $200
]


def _get_price_bracket(price: float) -> Tuple[int, int]:
    """Determina el umbral psicológico y el incremento para un precio dado."""
    for min_val, max_val, increment in PRICE_BRACKETS:
        if min_val <= price < max_val:
            return min_val, increment
    return PRICE_BRACKETS[-1][0], PRICE_BRACKETS[-1][2]


def _charm_price(price: float, ending: str = ".99") -> float:
    """
    Aplica pricing charm (encanto) al precio.
    
    Strategias:
    - ".99" : el más común ( $399 en lugar de $400 )
    - ".90" : para rangos medios ( $190 en lugar de $200 )
    - "9"   : terminaciones simples ( $399, $49, etc.)
    
    Returns el precio ajustado con la terminación especificada.
    """
    if ending == ".99":
        return math.ceil(price) - 0.01
    elif ending == ".90":
        return round(price / 10) * 10 - 0.10
    elif ending == "9":
        # Redondear al número terminado en 9 más cercano
        return math.ceil(price / 10) * 10 - 1
    return price


def _round_commercial(price: float, bracket_min: float, bracket_increment: float) -> float:
    """
    Redondeo comercial: ajusta el precio al umbral psicológico más cercano
    dentro de su rango, evitando precios "raros" como $427 o $463.
    """
    # Calcular la posición dentro del bracket
    if price < bracket_min:
        return bracket_min
    
    # Redondear al múltiplo del increment dentro del bracket
    relative = price - bracket_min
    units = round(relative / bracket_increment)
    result = bracket_min + (units * bracket_increment)
    
    # Asegurar que no exceda el tope del bracket
    max_val = bracket_min + bracket_increment  # próximo bracket
    if result >= max_val:
        result = max_val - bracket_increment
    
    return round(result, 2)


def calculate_smart_price(
    original_price: float,
    ganancia_envio: float = 200.0,
    min_margin: Optional[float] = None,
    max_margin: Optional[float] = None,
    psychological: bool = True,
    prefer_psychological: bool = True,
    min_profit_ratio: float = 0.15,
    max_profit_ratio: float = 0.50,
) -> Dict[str, Any]:
    """
    Calcula un precio de venta inteligente para un libro.
    
    Esta función sustituye la lógica simple de:
        precio_actual = precio_original + ganancia_envio
    
    Con una estrategia que considera:
    - Márgenes mínimos y máximos configurables
    - Precios psicológicos (charm pricing, brackets)
    - Balance entre rentabilidad y conversión
    - Precios competitivos vs precio original
    
    Args:
        original_price: Precio original del libro (antes de márgenes)
        ganancia_envio: Margen fijo por envío por defecto (200 MXN)
        min_margin: Ganancia mínima absoluta (si None, se calcula por ratio)
        max_margin: Ganancia máxima absoluta (si None, no hay límite superior)
        psychological: Aplicar pricing psicológico
        prefer_psychological: Preferir precios psicológicos sobre puros matemáticos
        min_profit_ratio: Ratio mínimo de ganancia sobre el precio original (15%)
        max_profit_ratio: Ratio máximo de ganancia sobre el precio original (50%)
    
    Returns:
        Diccionario con:
        - "precio_venta": precio final sugerido
        - "precio_original": precio original ingresado
        - "ganancia_envio": margen de envío aplicado
        - "estrategia": descripción de la estrategia aplicada
        - "es_precio_psicologico": booleano indicando si se usó pricing psicológico
        - "candidatos": lista de precios candidatos evaluados
        - "margen_bruto": margen en monto absoluto
        - "margen_porcentaje": margen como porcentaje del precio original
    
    Raises:
        ValueError: Si original_price es negativo o cero
    """
    
    if original_price <= 0:
        raise ValueError("El precio original debe ser un valor positivo")
    
    # 1. Calcular precio objetivo inicial (costo + margen)
    precio_base = original_price + ganancia_envio
    
    # 2. Determinar márgenes mín/máx en ratio si no se proporcionan absolutamente
    if min_margin is None:
        min_margin = original_price * min_profit_ratio
    if max_margin is None:
        max_margin = original_price * max_profit_ratio
    
    # 3. Calcular rango de precios viable
    precio_minimo = original_price + min_margin  # costo + ganancia mínima
    precio_maximo = original_price + max_margin  # costo + ganancia máxima
    
    # 4. Generar candidatos de precios
    candidatos: List[Dict[str, Any]] = []
    
    # Candidato A: Precio base matemático puro
    candidatos.append({
        "precio": precio_base,
        "origen": "base_matematica",
        "margen_absoluto": ganancia_envio,
        "margen_porcentaje": (ganancia_envio / original_price) * 100,
        "es_psicologico": False,
    })
    
    # Candidato B: Precio base con margen mínimo
    if precio_base < precio_minimo:
        candidatos.append({
            "precio": precio_minimo,
            "origen": "minimo_viable",
            "margen_absoluto": min_margin,
            "margen_porcentaje": min_profit_ratio * 100,
            "es_psicologico": psychological,
        })
    
    # Candidato C: Precio base con margen máximo
    if precio_base > precio_maximo:
        candidatos.append({
            "precio": precio_maximo,
            "origen": "maximo_establecido",
            "margen_absoluto": max_margin,
            "margen_porcentaje": max_profit_ratio * 100,
            "es_psicologico": psychological,
        })
    
    # Candidatos de pricing psicológico
    if psychological:
        # 1. Charm pricing .99
        precio_encanto_99 = _charm_price(precio_base, ".99")
        if precio_minimo <= precio_encanto_99 <= precio_maximo:
            margen = precio_encanto_99 - original_price
            candidatos.append({
                "precio": precio_encanto_99,
                "origen": "charm_99",
                "margen_absoluto": margen,
                "margen_porcentaje": (margen / original_price) * 100,
                "es_psicologico": True,
                "tipo_psicologico": "charm_99",
            })
        
        # 2. Charm pricing .90
        precio_encanto_90 = _charm_price(precio_base, ".90")
        if precio_minimo <= precio_encanto_90 <= precio_maximo:
            margen = precio_encanto_90 - original_price
            candidatos.append({
                "precio": precio_encanto_90,
                "origen": "charm_90",
                "margen_absoluto": margen,
                "margen_porcentaje": (margen / original_price) * 100,
                "es_psicologico": True,
                "tipo_psicologico": "charm_90",
            })
        
        # 3. Redondeo comercial al bracket inmediato
        bracket_min, bracket_inc = _get_price_bracket(precio_base)
        precio_comercial = _round_commercial(precio_base, bracket_min, bracket_inc)
        if precio_minimo <= precio_comercial <= precio_maximo and precio_comercial != precio_base:
            margen = precio_comercial - original_price
            candidatos.append({
                "precio": precio_comercial,
                "origen": "redondeo_bracket",
                "margen_absoluto": margen,
                "margen_porcentaje": (margen / original_price) * 100,
                "es_psicologico": True,
                "tipo_psicologico": "bracket",
                "bracket_min": bracket_min,
                "bracket_inc": bracket_inc,
            })
        
        # 4. Precio psicológico: evitar cruzar umbrales importantes
        # Si precio_base está cerca de un umbral (ej. $400, $500), bajar un nivel
        umbrales_importantes = [50, 100, 200, 500, 1000]
        for umbral in umbrales_importantes:
            if abs(precio_base - umbral) < 15:  # Está a menos de $15 del umbral
                # Intentar precio un nivel abajo (ej. $399 en vez de $400)
                precio_nivel_abajo = umbral - 1
                if precio_minimo <= precio_nivel_abajo <= precio_maximo:
                    margen = precio_nivel_abajo - original_price
                    candidatos.append({
                        "precio": precio_nivel_abajo,
                        "origen": "umbral_psicologico",
                        "margen_absoluto": margen,
                        "margen_porcentaje": (margen / original_price) * 100,
                        "es_psicologico": True,
                        "tipo_psicologico": "avoid_threshold",
                        "umbral_evitado": umbral,
                    })
    
    # 5. Filtrar candidatos por restricciones de rentabilidad
    candidatos_validados = []
    for c in candidatos:
        margen = c["margen_absoluto"]
        ratio_margen = margen / original_price if original_price > 0 else 0
        
        # Verificar margen mínimo
        if margen < min_margin:
            continue
        
        # Verificar margen máximo
        if margen > max_margin:
            # Ajustar precio al máximo permitido
            precio_ajustado = original_price + max_margin
            if precio_minimo <= precio_ajustado <= precio_maximo:
                candidatos_validados.append({
                    "precio": precio_ajustado,
                    "origen": "max_margin_clamped",
                    "margen_absoluto": max_margin,
                    "margen_porcentaje": max_profit_ratio * 100,
                    "es_psicologico": psychological,
                    "motivo": "Clampado por margen máximo",
                })
                continue
            else:
                continue
        
        # Verificar que no sea inferior al costo
        if precio_ajustado := c["precio"] < precio_minimo:
            continue
        
        # Verificar que no sea irrealísticamente alto (más del 100% sobre precio original)
        if c["precio"] > original_price * 2.0:
            continue
        
        candidatos_validados.append(c)
    
    if not candidatos_validados:
        # Fallback: precio base matemático si todos fueron filtrados
        return {
            "precio_venta": precio_base,
            "precio_original": original_price,
            "ganancia_envio": ganancia_envio,
            "estrategia": "fallback_precio_base",
            "es_precio_psicologico": False,
            "candidatos": candidatos,
            "margen_bruto": ganancia_envio,
            "margen_porcentaje": (ganancia_envio / original_price) * 100,
        }
    
    # 6. Seleccionar el mejor candidato
    # Critério de selección priorizado:
    # 1. Maximizar margen (dentro de los límites)
    # 2. Preferir pricing psicológico si mejora o iguala la rentabilidad
    # 3. Evitar umbrales psicológicos innecesarios
    # 4. Precio más cercano al base matemático (menor desviación)
    
    # Separar candidatos psicológicos de los puros
    psicologicos = [c for c in candidatos_validados if c.get("es_psicologico")]
    puros = [c for c in candidatos_validados if not c.get("es_psicologico")]
    
    seleccionado = None
    estrategia = "desconocido"
    
    # Preferir pricing psicológico si existe y es competitivo
    if psicologicos and prefer_psychological:
        # Entre los psicológicos, preferir el que tenga mejor ratio margen/percepción
        # Pero nunca sacrificar margen significativo
        # Ordenar: primero por margen (mayor es mejor), luego por cercanía al base
        psicologicos_ordenados = sorted(
            psicologicos,
            key=lambda c: (-c["margen_absoluto"], abs(c["precio"] - precio_base))
        )
        seleccionado = psicologicos_ordenados[0]
        tipo = seleccionado.get("tipo_psicologico", "desconocido")
        estrategia = f"precio_psicologico_{tipo}"
    elif puros:
        # Usar precio puro matemático
        seleccionado = puros[0]
        estrategia = "precio_matematico_base"
    elif psicologicos:
        # Usar el mejor psicológicoa a pesar de prefer_psychological=False
        psicologicos_ordenados = sorted(
            psicologicos,
            key=lambda c: (-c["margen_absoluto"], abs(c["precio"] - precio_base))
        )
        seleccionado = psicologicos_ordenados[0]
        tipo = seleccionado.get("tipo_psicologico", "desconocido")
        estrategia = f"precio_psicologico_{tipo}"
    else:
        # Último recurso
        seleccionado = candidatos_validados[0]
        estrategia = "desconocido"
    
    # 7. Avoid visually flat prices such as $840 when lowering one peso still
    # respects the configured margin. This is applied after choosing the best
    # candidate so the commercial rules above remain the source of truth.
    selected_price = float(seleccionado["precio"])
    rounded_price = round(selected_price)
    if (
        psychological
        and abs(selected_price - rounded_price) < 0.001
        and rounded_price % 10 == 0
        # A one-peso charm adjustment may sit one peso below the configured
        # floor, but must never fall below cost.
        and (rounded_price - 1) >= original_price
        and (rounded_price - 1 - original_price) >= (min_margin - 1)
    ):
        adjusted_price = float(rounded_price - 1)
        adjusted_margin = adjusted_price - original_price
        seleccionado = {
            **seleccionado,
            "precio": adjusted_price,
            "margen_absoluto": adjusted_margin,
            "margen_porcentaje": (adjusted_margin / original_price) * 100,
            "es_psicologico": True,
            "tipo_psicologico": "terminacion_9",
        }
        estrategia = "precio_psicologico_terminacion_9"

    # 8. Información del ajuste
    es_precio_psicologico = seleccionado.get("es_psicologico", False)
    
    resultado = {
        "precio_venta": seleccionado["precio"],
        "precio_original": original_price,
        "ganancia_envio": ganancia_envio,
        "estrategia": estrategia,
        "es_precio_psicologico": es_precio_psicologico,
        "candidatos": candidatos_validados,
        "margen_bruto": seleccionado["margen_absoluto"],
        "margen_porcentaje": round(seleccionado["margen_porcentaje"], 2),
    }
    
    # Agregar información adicional sobre el ajuste
    if es_precio_psicologico:
        resultado["ajuste_detalle"] = {
            "tipo": seleccionado.get("tipo_psicologico"),
            "precio_base_calculado": round(precio_base, 2),
            "precio_ajustado": round(seleccionado["precio"], 2),
            "ganancia_cambiada": round(seleccionado["margen_absoluto"] - ganancia_envio, 2),
            "margen_original": round(ganancia_envio, 2),
            "margen_nuevo": round(seleccionado["margen_absoluto"], 2),
        }
    
    return resultado


def get_price_tier_info(price: float) -> Dict[str, Any]:
    """
    Devuelve información sobre el rango/tier psicológico de un precio.
    
    Útil para reportes y entendimiento del mercado.
    """
    bracket_min, bracket_inc = _get_price_bracket(price)
    max_bracket = bracket_min + bracket_inc
    
    # Determinar nombre aproximado del tier
    if price < 50:
        tier = "económico"
    elif price < 100:
        tier = "bajo"
    elif price < 200:
        tier = "medio"
    elif price < 500:
        tier = "alto"
    elif price < 1000:
        tier = "premium"
    else:
        tier = "lujo"
    
    return {
        "precio": price,
        "tier": tier,
        "bracket_activo": (bracket_min, max_bracket),
        "incremento_sugerido": bracket_inc,
        "precio_rounded_psicologico": _charm_price(price, ".99"),
    }


# Ejemplos y pruebas
if __name__ == "__main__":
    # Ejemplos de uso
    casos_prueba = [
        230.0,  # Libro común
        350.0,  # Libro de texto/o de lujo
        89.0,   # Libro de bolsillo
        670.0,  # Libro especial/coleccionable
    ]
    
    print("=" * 70)
    print("EJEMPLOS DE PRICING INTELIGENTE")
    print("=" * 70)
    
    for precio_original in casos_prueba:
        resultado = calculate_smart_price(
            original_price=precio_original,
            ganancia_envio=200.0,
            psychological=True,
            prefer_psychological=True,
        )
        
        print(f"\n📚 Libro: ${precio_original:,.0f}")
        print(f"   Precio de venta: ${resultado['precio_venta']:,.2f}")
        print(f"   Margen: ${resultado['margen_bruto']:,.2f} ({resultado['margen_porcentaje']}%)")
        print(f"   Estrategia: {resultado['estrategia']}")
        if resultado.get("es_precio_psicologico"):
            print(f"   ✅ Precio psicológico aplicado")
        print(f"   Precio original: ${resultado['precio_original']:,.2f}")
    
    print("\n" + "=" * 70)
    print("INFORMACIÓN DE TIERS PSICOLÓGICOS")
    print("=" * 70)
    
    for precio_prueba in [49.99, 129.99, 299.50, 599.00, 1299.00]:
        info = get_price_tier_info(precio_prueba)
        print(f"\n${precio_prueba:,.2f} -> Tier: {info['tier']}, Bracket: ${info['bracket_activo'][0]:,.0f} - ${info['bracket_activo'][1]:,.0f}")
        print(f"   Psicológico .99: ${info['precio_rounded_psicologico']:,.2f}")
