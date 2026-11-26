"""Script para poblar automáticamente la base de datos de BuscaLibre con múltiples temas y pricing inteligente.

Este script utiliza el mismo método de simulación de interacción humana:
- Abre buscalibre.com
- Escribe la consulta carácter a carácter (como un humano)
- Presiona enter para buscar
- Extrae el título, precio original, precio con descuento, y porcentaje de descuento
- Aplica pricing inteligente para determinar el precio de venta óptimo
- Solo guarda en la base de datos si hay resultados Y no son duplicados
- Incluye campo precioOriginal para adaptar precios fuera de BuscaLibre

Uso:
    python poblar.py "Tema 1" "Tema 2" "Tema 3" ...

Omitiendo los argumentos, usará una lista por defecto de 20 temas populares.
"""

import asyncio
import argparse
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, Optional

# Permite ejecutar este archivo directamente desde la carpeta ``scrappers``.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from buscalibre_tool import search_buscalibre
from firestore_catalog import (
    persist_catalog_books,
    catalog_document_id,
    prepare_catalog_book_document,
)
from pricing_strategy import calculate_smart_price


from default_queries import DEFAULT_QUERIES

def parse_mxn(value: Any) -> float:
    """Parse common BuscaLibre price formats without silently inflating them."""
    raw = re.sub(r"[^0-9,.-]", "", str(value or "")).replace("-", "")
    if not raw:
        return 0.0
    if "," in raw and "." in raw:
        # The final separator is normally the decimal separator.
        decimal = "," if raw.rfind(",") > raw.rfind(".") else "."
        thousands = "." if decimal == "," else ","
        raw = raw.replace(thousands, "").replace(decimal, ".")
    elif raw.count(",") == 1 and len(raw.rsplit(",", 1)[1]) == 2:
        raw = raw.replace(",", ".")
    else:
        raw = raw.replace(",", "")
        # A single dot followed by exactly three digits is a thousands mark.
        if raw.count(".") == 1 and len(raw.rsplit(".", 1)[1]) == 3:
            raw = raw.replace(".", "")
        elif raw.count(".") > 1:
            groups = raw.split(".")
            # e.g. "8.917.27" -> "8917.27"; otherwise dots are
            # thousands separators and can be removed safely.
            raw = "".join(groups[:-1]) + (f".{groups[-1]}" if len(groups[-1]) == 2 else groups[-1])
    try:
        return round(float(raw), 2)
    except ValueError:
        return 0.0


def clean_text(value: Any, fallback: str = "") -> str:
    text = " ".join(str(value or "").split()).strip()
    return fallback if not text or text.lower() in {"no disponible", "n/a", "none"} else text


def category_for_query(query: str) -> str:
    normalized = unicodedata.normalize("NFKD", query).encode("ascii", "ignore").decode().lower()
    groups = {
        "Ciencia ficción": ("ciencia ficcion", "asimov", "fantasia", "robot", "dune"),
        "Historia": ("historia", "arqueologia", "egipto", "medieval", "revolucion"),
        "Arte y diseño": ("arte", "diseno", "arquitectura", "fotografia", "tipografia"),
        "Ciencias y tecnología": ("ciencia", "matematic", "tecnologia", "inteligencia artificial", "programacion", "game design"),
        "Filosofía y sociedad": ("filosofia", "sociologia", "feminismo", "politica", "geopolitica"),
        "Literatura": ("novela", "literatura", "poesia", "cuento", "thriller"),
    }
    return next((category for category, terms in groups.items() if any(term in normalized for term in terms)), "Libros seleccionados")


def quality_score(book: Dict[str, Any]) -> int:
    fields = ("author", "editorial", "pages", "description", "image_url", "delivery_estimate")
    return sum(bool(clean_text(book.get(field))) for field in fields)


def enrich_book(book: Dict[str, Any], query: str, sale_price: float, source_price: float) -> Dict[str, Any]:
    """Return the complete storefront payload, preserving scraper provenance."""
    description = clean_text(book.get("description"), "Descripción no disponible.")
    return {
        **book,
        "title": clean_text(book.get("title"), "Libro sin título"),
        "author": clean_text(book.get("author"), "Autor no disponible"),
        "price": sale_price,
        "priceText": f"$ {sale_price:,.0f}",
        "price_original": book.get("price_original") or f"$ {source_price:,.0f}",
        "category": category_for_query(query),
        "format": clean_text(book.get("format") or book.get("formato"), "No disponible"),
        "pages": book.get("pages") or book.get("num_paginas") or 0,
        "description": description[:700],
        "stock": 1,
        "badge": "Selección de la casa" if quality_score(book) >= 5 else "Recién encontrado",
        "qualityScore": quality_score(book),
        "source": "buscalibre",
    }


def check_book_exists(db, book_id: str) -> bool:
    """Verificar si un libro ya existe en Firestore por su ID."""
    try:
        doc_ref = db.collection("books").document(book_id)
        doc = doc_ref.get()
        return doc.exists
    except Exception:
        # Si hay error de conexión, asumimos que no existe para no perder datos
        return False


def main():
    parser = argparse.ArgumentParser(description="Puebla el catálogo de libros con fichas enriquecidas.")
    parser.add_argument("queries", nargs="*", help="Temas o títulos a buscar.")
    parser.add_argument("--limit", type=int, default=20, help="Máximo de consultas a procesar (predeterminado: 20).")
    parser.add_argument("--max-results", type=int, default=5, help="Resultados por consulta (predeterminado: 5).")
    parser.add_argument("--dry-run", action="store_true", help="Busca y valida, pero no escribe en Firestore.")
    args = parser.parse_args()

    if args.queries:
        queries = args.queries
    else:
        queries = DEFAULT_QUERIES
        print(f"[*] Sin argumentos proporcionados. Usando {len(queries)} temas por defecto.")

    queries = queries[:max(args.limit, 1)]

    # Inicializar Firestore
    from firestore_catalog import catalog_writer

    if args.dry_run:
        print("[*] Modo simulación: no se escribirá ningún libro en Firestore.")
        firestore_available = False
    elif not catalog_writer.enabled:
        print("[!] Firestore deshabilitado. Ejecutando búsqueda pero sin guardar en BD.")
        print("[*] Los resultados se mostrarán pero no se insertarán en la base.")
        firestore_available = False
    else:
        catalog_writer.initialize_firebase()
        db = catalog_writer.db
        firestore_available = True

    print("[*] Iniciando poblar automático de BuscaLibre con pricing inteligente")
    print(f"[+] Total de temas a procesar: {len(queries)}")
    print("-" * 60)

    total_saved = 0
    total_skipped = 0  # Contador de libros duplicados
    total_searched = 0

    for i, query in enumerate(queries, 1):
        total_searched += 1
        print(f"\n[{i}/{len(queries)}] Buscando: '{query}'")

        immediate_saved = 0

        def save_after_detail(book: Dict[str, Any]) -> None:
            """Persist a product as soon as Selenium finishes its detail page."""
            nonlocal immediate_saved
            if not firestore_available:
                return
            saved = persist_catalog_books([book], query)
            immediate_saved += saved
            print(
                f"   [OK] Guardado inmediato: "
                f"{clean_text(book.get('title'), 'Libro sin título')}"
            )

        # Ejecutar la búsqueda en BuscaLibre (mismo metodo que el backend)
        result = asyncio.run(
            search_buscalibre(
                query,
                max_results=max(args.max_results, 1),
                ganancia_envio=200.0,
                on_result=save_after_detail if firestore_available else None,
            )
        )

        # Verificar si hay errores o no hay resultados
        if result.get("error"):
            print(f"[!] Error en la busqueda: {result['error']}")
            continue

        books = result.get("results", [])
        print(f"[+] Encontrados {len(books)} libros")
        if immediate_saved:
            print(f"[+] Libros guardados durante la lectura: {immediate_saved}")

        if not books:
            print(f"[!] No se encontraron resultados para '{query}'. Sin guardar en BD.")
            continue

        # Procesar cada libro encontrado
        for book in books:
            # Generar el ID documental usando la misma función que el backend
            book_id = catalog_document_id(book)

            # Verificar si ya existe en la base de datos
            if firestore_available and check_book_exists(db, book_id):
                # The shared persistence layer performs the full idempotent
                # upsert, including refreshed metadata and price history.
                print("   [ACTUALIZAR] Libro existente: se actualizarán precio y ficha.")

            # Obtener el precio original del libro
            precio_original = 0.0
            precio_original_texto = book.get("price_original")
            if precio_original_texto:
                import re
                # Normalizar: quitar símbolo de moneda y espacios
                texto_limpio = str(precio_original_texto).replace("$", "").strip()
                
                # Detectar formato: si tiene periodos y comas, tratar como número localizable
                # Formatos comunes:
                # - "8.917.27" (periodos como separadores de miles, formato mexicano)
                # - "1,299.50" (comas como separadores de miles, punto decimal)
                # - "239.25" (solo decimal, sin separadores de miles)
                # - "$ 499" (con símbolo de moneda)
                
                # Paso 1: Remover el símbolo $ si está presente
                # Ya lo hice arriba, pero por seguridad:
                texto_limpio = texto_limpio.replace("$", "").strip()
                
                # Paso 2: Verificar si el formato usa periodos como separadores de miles
                # Si hay 2 o más periodos y el último grupo tiene 2 dígitos, es probable que sea "8.917.27"
                # Si hay 1 periodo y el último grupo tiene 2-3 dígitos, podría ser decimal
                # Si hay comas, es formato EE.UU. "1,299.50"
                
                # Contar periodos y comas
                count_periods = texto_limpio.count(".")
                count_commas = texto_limpio.count(",")
                
                if count_periods >= 2 and count_commas == 0:
                    # Formato probable: "8.917.27" - quitar todos los periodos (mil separadores)
                    texto_numerico = texto_limpio.replace(".", "")
                elif count_commas >= 1 and count_periods == 1:
                    # Formato EE.UU.: "1,299.50" - quitar coma, mantener punto decimal
                    texto_numerico = texto_limpio.replace(",", "")
                elif count_periods == 1 and count_commas == 0:
                    # Formato decimal simple: "239.25" - mantener como está
                    texto_numerico = texto_limpio
                else:
                    # Formato desconocido - quitar todos los caracteres no numéricos excepto un punto
                    texto_numerico = re.sub(r"[^\d.]", "", texto_limpio)
                
                # Paso 3: Convertir a float, manejando múltiples periodos
                # Si aún queda más de un periodo, quitar todos menos el último
                if texto_numerico.count(".") > 1:
                    # Encontrar el último periodo y quitar los anteriores
                    last_dot = texto_numerico.rfind(".")
                    texto_numerico = texto_numerico[:last_dot] + texto_numerico[last_dot+1:]
                
                try:
                    precio_original = float(texto_numerico)
                except ValueError:
                    # Último intento: quitar todos los periodos y convertir
                    try:
                        precio_original = float(texto_numerico.replace(".", ""))
                    except ValueError:
                        precio_original = 0.0

            # The scraper's displayed price is the most reliable cost basis;
            # price_original is only a fallback when it is unavailable.
            precio_base = parse_mxn(book.get("price")) or parse_mxn(book.get("price_original"))
            if precio_base <= 0:
                print(f"[!] Se omite '{book.get('title', 'Desconocido')}': no tiene un precio válido.")
                total_skipped += 1
                continue
            precio_original = precio_base

            # Aplicar pricing inteligente en lugar de simple ganancia_envio fija
            # Usamos la estrategia de pricing con:
            # - precio original del libro
            # - ganancia_envio base de 200 MXN
            # - ratio de margen del 15-50% sobre el precio original
            # - pricing psicológico preferente
            try:
                pricing_result = calculate_smart_price(
                    original_price=precio_original,
                    ganancia_envio=100.0,  # Base nueva: $100 mínimo por libro
                    min_margin=100.0,      # Ganancia mínima absoluta asegurada
                    psychological=True,
                    prefer_psychological=True,
                )
            except ValueError as e:
                print(f"[!] Error en pricing para '{book.get('title', 'Desconocido')}': {e}")
                pricing_result = {
                    "precio_venta": precio_original + 200.0,
                    "precio_original": precio_original,
                    "ganancia_envio": 200.0,
                    "estrategia": "error_fallback",
                    "es_precio_psicologico": False,
                    "candidatos": [],
                    "margen_bruto": 200.0,
                    "margen_porcentaje": (200.0 / precio_original * 100) if precio_original > 0 else 0,
                }

            # Usar el precio de venta calculado
            precio_venta = pricing_result.get("precio_venta", precio_original + 200.0)
            estrategia = pricing_result.get("estrategia", "desconocido")
            es_psicologico = pricing_result.get("es_precio_psicologico", False)
            margen_bruto = pricing_result.get("margen_bruto", 200.0)

            # Preparar el documento para persistir
            # El precio de venta se guardará en el campo appropriate
            # Usamos la estructura que espera el firestore_catalog
            enriched_book = enrich_book(book, query, float(precio_venta), precio_original)
            # Keep pricing analytics for future reporting without exposing
            # internal costs in the storefront.
            enriched_book["pricing_strategy"] = estrategia
            enriched_book["is_psychological_price"] = es_psicologico
            enriched_book["smart_price_original"] = precio_original
            enriched_book["smart_price_margin"] = margen_bruto
            enriched_book["smart_price_percent"] = pricing_result.get("margen_porcentaje", 0)
            doc = prepare_catalog_book_document(enriched_book, query)

            print(f"[*] Guardando libro: '{doc.get('title', 'Desconocido')}'")
            print(f"   Precio inteligente: ${precio_venta:,.2f} (estrat: {estrategia})")
            print(f"   Margen: ${margen_bruto:,.2f} ({pricing_result.get('margen_porcentaje', 0)}%)")

            # Persistir en Firestore usando la misma funcion que el backend
            # Solo si Firestore está disponible
            if firestore_available:
                saved = persist_catalog_books([enriched_book], query)
                total_saved += saved
            else:
                saved = 0
                print("[!] Firestore deshabilitado, libro no guardado en BD")
            # Ajustar el contador ya que persist_catalog_books puede guardar 0 o 1
            # Si Firestore no está disponible, saved será 0

    print("-" * 60)
    print(f"[+] Proceso completado!")
    print(f"[+] Temas buscados: {total_searched}")
    print(f"[+] Libros guardados nuevos: {total_saved}")
    if total_skipped > 0:
        print(f"[+] Libros duplicados (ya existían): {total_skipped}")
    print("=" * 60)


if __name__ == "__main__":
    main()
