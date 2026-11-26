"""Persist scraper results in the Firestore catalog without blocking customer replies."""

from __future__ import annotations

import hashlib
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

# Nombres de meses en español para formatear la fecha de llegada
MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

logger = logging.getLogger(__name__)
LOG_FILE = Path(__file__).with_name("firebase_catalog.log")


def _configure_catalog_logger() -> None:
    """Write an audit trail that remains available for background Uvicorn runs."""
    if any(
        isinstance(handler, logging.FileHandler)
        and Path(handler.baseFilename) == LOG_FILE
        for handler in logger.handlers
    ):
        return
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


_configure_catalog_logger()


def _clean_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return " ".join(str(value).split()).strip() or default


def _money_value(value: Any) -> float:
    """Turn scraper price strings such as '$ 1,299' into a Firestore number."""
    if isinstance(value, (int, float)):
        return float(value)
    digits = re.sub(r"[^0-9.]", "", _clean_text(value))
    try:
        return float(digits) if digits else 0.0
    except ValueError:
        return 0.0


def _pages_value(value: Any) -> int:
    match = re.search(r"\d+", _clean_text(value))
    return int(match.group()) if match else 0


def _positive_int(value: Any, default: int = 0) -> int:
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return default


def _format_price(value: float) -> str:
    return f"$ {value:,.0f}" if value > 0 else "No disponible"


def _cover_tone(title: str) -> str:
    tones = ("midnight", "terracotta", "ochre", "jungle", "clay", "ocean")
    return tones[int(hashlib.sha256(title.encode("utf-8")).hexdigest(), 16) % len(tones)]


def _formato_llegada() -> str:
    """Retorna la fecha de llegada formateada: 'dd de Mes'"""
    return f"{((datetime.now().date() + timedelta(days=7)).day):02d} de {MESES[(datetime.now().date() + timedelta(days=7)).month - 1] if (datetime.now().date() + timedelta(days=7)).month > 0 else ''}"


def _transformar_llegada(raw: str) -> str:
    """Transforma 'Envío rápido' a 'Envío rápido (llega el dd de Mes)'"""
    if raw and ('rápido' in raw.lower() or 'envío rápido' in raw.lower()):
        return f"Envío rápido (llega el {_formato_llegada()})"
    return raw or '15 a 20 días háb.'


def prepare_catalog_book_document(book: Dict[str, Any], search_query: str) -> Dict[str, Any]:
    """Normalize a BuscaLibre/MercadoLibre result into the shared catalog schema."""
    title = _clean_text(book.get("title") or book.get("nombre"), "Libro sin título")
    raw_price = book.get("price") or book.get("precio_con_envio")
    price_value = _money_value(raw_price)
    price_text = _clean_text(book.get("priceText") or raw_price)
    price_original = _clean_text(book.get("price_original") or book.get("precio_original"))
    return {
        "id": __import__('hashlib').sha256(_clean_text(book.get("url") or book.get("url_libro")).encode("utf-8")).hexdigest()[:24],
        "title": title,
        "author": _clean_text(book.get("author") or book.get("autor"), "No disponible"),
        # Firestore preserves Python numeric values as number fields.  The
        # storefront can therefore read them directly, instead of receiving
        # stringValue wrappers for values such as "$ 1,299".
        "price": price_value,
        "priceText": price_text if price_value > 0 else "No disponible",
        "priceOriginal": price_original or "No disponible",
        "priceOriginalValue": _money_value(price_original),
        "currency": _clean_text(book.get("currency"), "MXN"),
        "availability": bool(book.get("availability", True)),
        "url": _clean_text(book.get("url") or book.get("url_libro")),
        "imageUrl": _clean_text(book.get("image_url") or book.get("url_imagen") or book.get("url_imagen_hq")),
        "editorial": _clean_text(book.get("editorial"), "No disponible"),
        "pages": _pages_value(book.get("pages") or book.get("num_paginas")),
        "description": _clean_text(book.get("description") or book.get("descripcion"), "Descripción no disponible."),
        "category": _clean_text(book.get("category"), "Catálogo"),
        "format": _clean_text(book.get("format") or book.get("formato"), "No disponible"),
        "isbn": _clean_text(book.get("isbn")),
        "stock": _positive_int(book.get("stock"), 1),
        "badge": _clean_text(book.get("badge")),
        "pricingStrategy": _clean_text(book.get("pricing_strategy")),
        "isPsychologicalPrice": bool(book.get("is_psychological_price", False)),
        "smartPriceMargin": _money_value(book.get("smart_price_margin")),
        "delivery": _transformar_llegada(_clean_text(book.get("delivery_estimate") or book.get("tiempo_entrega"))),
        "deliveryDates": list(book.get("delivery_dates") or []),
        "condition": _clean_text(book.get("condition"), "No disponible"),
        "source": _clean_text(book.get("source"), "buscalibre"),
        "searchTerms": [_clean_text(search_query)],
        "qualityScore": _positive_int(book.get("qualityScore")),
        "coverTone": _cover_tone(title),
        "updatedAt": datetime.now(timezone.utc),
    }


catalog_writer = None


# Inicializar FirebaseUploader al importar el módulo
try:
    from firebase_uploader import FirebaseUploader
    catalog_writer = FirebaseUploader()
    # Verificar si la conexión fue exitosa probando un get simple
    try:
        # Intentar acceder a la colección para verificar que Firebase funciona
        test_ref = catalog_writer.db.collection('books').limit(1)
        test_ref.get()
        catalog_writer.enabled = True
    except Exception:
        # Firebase inicializado pero sin conexión real - deshabilitado
        catalog_writer.enabled = False
except ImportError:
    # FirebaseUploader no disponible - catalog_writer se mantendrá en None
    catalog_writer = type('MockCatalogWriter', (), {'enabled': False})()
except Exception:
    catalog_writer.enabled = False


def catalog_document_id(book: Dict[str, Any]) -> str:
    """Generate a book ID from title for price comparison support.
    
    Uses only the title as the ID so that:
    - Same book title (any source): creates/updates same record
    - Different prices from different sources: stored as separate price entries
    - Enables price comparison within the same catalog record
    - Compatible with poblar.py usage
    """
    title = _clean_text(book.get("title") or book.get("nombre"), "Libro sin título")
    # Create hash from title only (not source) for price comparison
    return hashlib.sha256(title.encode("utf-8")).hexdigest()[:24]


def _book_id_from_book(book: Dict[str, Any]) -> str:
    """Internal function for persist_catalog_books upsert logic."""
    title = _clean_text(book.get("title") or book.get("nombre"), "Libro sin título")
    # Create hash from title only (not source) for price comparison
    return hashlib.sha256(title.encode("utf-8")).hexdigest()[:24]


def persist_catalog_books(books: Iterable[Dict[str, Any]], search_query: str) -> int:
    """Save all found books supporting price comparison.
    
    Same title from different sources/prices will be stored in the same 
    document, with prices appended to a list. This enables:
    - Price comparison: same title shows multiple price options
    - Single source updates: price list grows with each scrape
    - Different books: separate records as before
    """
    from firebase_admin import firestore
    
    db = firestore.client()
    collection_name = 'books'
    saved_count = 0
    
    for book in books:
        # Normalize to our catalog schema
        catalog_book = prepare_catalog_book_document(book, search_query)
        book_id = _book_id_from_book(catalog_book)
        
        # Check if document already exists
        doc_ref = db.collection(collection_name).document(book_id)
        doc_snapshot = doc_ref.get()
        
        if doc_snapshot.exists:
            # Document exists - merge new price into existing price list
            existing = doc_snapshot.to_dict()
            current_prices = existing.get('priceHistory', [])
            new_price_entry = {
                'price': catalog_book.get('price', 0),
                'priceText': catalog_book.get('priceText', 'No disponible'),
                'source': catalog_book.get('source', 'buscalibre'),
                'url': catalog_book.get('url', ''),
                'date': datetime.now(timezone.utc).isoformat(),
            }
            # Replace a record from the same source URL so a new scrape
            # refreshes its price instead of leaving a stale top-level price.
            matching_index = next(
                (index for index, item in enumerate(current_prices)
                 if item.get('url') == new_price_entry.get('url')),
                None,
            )
            if matching_index is None:
                current_prices.append(new_price_entry)
            else:
                current_prices[matching_index] = new_price_entry
            # Update the document with the (possibly updated) price history
            doc_ref.set({
                **catalog_book,
                'priceHistory': current_prices,
                'updatedAt': datetime.now(timezone.utc),
            }, merge=True)
            # Always set top-level price fields from the latest price entry
            if current_prices:
                latest_price = current_prices[-1]
                doc_ref.update({
                    'price': latest_price.get('price'),
                    'priceText': latest_price.get('priceText'),
                })
            saved_count += 1
        else:
            # New document - initialize with price history
            catalog_book['priceHistory'] = [{
                'price': catalog_book.get('price', 0),
                'priceText': catalog_book.get('priceText', 'No disponible'),
                'source': catalog_book.get('source', 'buscalibre'),
                'url': catalog_book.get('url', ''),
                'date': datetime.now(timezone.utc).isoformat(),
            }]
            # Set top-level price fields for immediate access
            doc_ref.set({
                **catalog_book,
                'priceHistory': catalog_book['priceHistory'],
            }, merge=False)
            saved_count += 1
    
    logger.info("Saved %d catalog books to Firestore (search: '%s').", saved_count, search_query)
    return saved_count
