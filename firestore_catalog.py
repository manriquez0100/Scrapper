"""Persist scraper results in the Firestore catalog without blocking customer replies."""

from __future__ import annotations

import hashlib
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

logger = logging.getLogger(__name__)
LOG_FILE = Path(__file__).with_name("logs") / "firebase_catalog.log"


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


def _cover_tone(title: str) -> str:
    tones = ("midnight", "terracotta", "ochre", "jungle", "clay", "ocean")
    return tones[int(hashlib.sha256(title.encode("utf-8")).hexdigest(), 16) % len(tones)]


def catalog_document_id(book: Dict[str, Any]) -> str:
    """Create a stable ID, preferring the source product URL to prevent duplicates."""
    identity = _clean_text(book.get("url") or book.get("url_libro"))
    if not identity:
        identity = "|".join((
            _clean_text(book.get("title") or book.get("nombre")).lower(),
            _clean_text(book.get("author") or book.get("autor")).lower(),
            _clean_text(book.get("isbn")).lower(),
        ))
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return f"book_{digest}"


def prepare_catalog_book_document(book: Dict[str, Any], search_query: str) -> Dict[str, Any]:
    """Normalize a BuscaLibre/MercadoLibre result into the shared catalog schema."""
    title = _clean_text(book.get("title") or book.get("nombre"), "Libro sin título")
    price_text = _clean_text(book.get("price") or book.get("precio_con_envio"))
    price_original = _clean_text(book.get("price_original") or book.get("precio_original"))
    return {
        "id": catalog_document_id(book),
        "title": title,
        "author": _clean_text(book.get("author") or book.get("autor"), "No disponible"),
        "price": _money_value(price_text),
        "priceText": price_text or "No disponible",
        "priceOriginal": price_original or "No disponible",
        "currency": _clean_text(book.get("currency"), "MXN"),
        "availability": bool(book.get("availability", True)),
        "url": _clean_text(book.get("url") or book.get("url_libro")),
        "imageUrl": _clean_text(book.get("image_url") or book.get("url_imagen") or book.get("url_imagen_hq")),
        "editorial": _clean_text(book.get("editorial"), "No disponible"),
        "pages": _pages_value(book.get("pages") or book.get("num_paginas")),
        "description": _clean_text(book.get("description") or book.get("descripcion"), "Descripción no disponible."),
        "delivery": _clean_text(book.get("delivery_estimate") or book.get("tiempo_entrega"), "No disponible"),
        "deliveryDates": list(book.get("delivery_dates") or []),
        "condition": _clean_text(book.get("condition"), "No disponible"),
        "source": _clean_text(book.get("source"), "buscalibre"),
        "searchTerms": [_clean_text(search_query)],
        "coverTone": _cover_tone(title),
        "updatedAt": datetime.now(timezone.utc),
    }


class FirestoreCatalogWriter:
    """Lazy Firestore client. Missing credentials never interrupt a search."""

    def __init__(self, db: Any = None, enabled: Optional[bool] = None) -> None:
        self.db = db
        configured_enabled = os.getenv("FIREBASE_CATALOG_ENABLED")
        default_key = Path(__file__).with_name("firebase-credentials.json")
        self.enabled = enabled if enabled is not None else (
            configured_enabled.lower() in {"1", "true", "yes"}
            if configured_enabled is not None
            else bool(os.getenv("FIREBASE_PROJECT_ID") or default_key.is_file())
        )
        self.collection = os.getenv("FIREBASE_CATALOG_COLLECTION", "books")
        self._initialization_attempted = db is not None
        self._array_union: Any = None

    def _initialize(self) -> bool:
        if self.db is not None:
            return True
        if self._initialization_attempted or not self.enabled:
            logger.warning(
                "FIRESTORE_SYNC_SKIPPED | reason=%s | collection=%s",
                "disabled" if not self.enabled else "previous_initialization_failed",
                self.collection,
            )
            return False
        self._initialization_attempted = True
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore

            project_id = os.getenv("FIREBASE_PROJECT_ID")
            key_path = Path(os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY_PATH", "firebase-credentials.json"))
            if not key_path.is_absolute():
                key_path = Path(__file__).parent / key_path

            if not firebase_admin._apps:
                if key_path.is_file():
                    credential = credentials.Certificate(str(key_path))
                    firebase_admin.initialize_app(credential, {"projectId": project_id} if project_id else None)
                else:
                    credential = credentials.ApplicationDefault()
                    firebase_admin.initialize_app(credential, {"projectId": project_id} if project_id else None)
            self.db = firestore.client()
            self._array_union = firestore.ArrayUnion
            logger.info("FIRESTORE_CONNECTED | collection=%s | project=%s", self.collection, project_id or "default")
            return True
        except Exception as exc:
            logger.exception(
                "FIRESTORE_CONNECTION_FAILED | collection=%s | error=%s", self.collection, exc
            )
            return False

    def persist(self, books: Iterable[Dict[str, Any]], search_query: str) -> int:
        items = list(books)
        logger.info(
            "FIRESTORE_SYNC_STARTED | query=%r | found_results=%d | collection=%s",
            search_query,
            len(items),
            self.collection,
        )
        if not self._initialize():
            logger.warning(
                "FIRESTORE_SYNC_FINISHED | query=%r | attempted=%d | saved=0 | status=skipped",
                search_query,
                len(items),
            )
            return 0
        saved = 0
        failures = 0
        for book in items:
            try:
                document = prepare_catalog_book_document(book, search_query)
                if self._array_union:
                    document["searchTerms"] = self._array_union(document["searchTerms"])
                write_result = self.db.collection(self.collection).document(document["id"]).set(document, merge=True)
                saved += 1
                logger.info(
                    "FIRESTORE_UPSERT_CONFIRMED | id=%s | title=%r | source=%s | update_time=%s",
                    document["id"],
                    document["title"],
                    document["source"],
                    getattr(write_result, "update_time", "unknown"),
                )
            except Exception as exc:
                failures += 1
                logger.exception(
                    "FIRESTORE_UPSERT_FAILED | title=%r | error=%s",
                    book.get("title") or book.get("nombre"),
                    exc,
                )
        logger.info(
            "FIRESTORE_SYNC_FINISHED | query=%r | attempted=%d | saved=%d | failed=%d | status=%s",
            search_query,
            len(items),
            saved,
            failures,
            "success" if failures == 0 else "partial_failure",
        )
        return saved


catalog_writer = FirestoreCatalogWriter()


def persist_catalog_books(books: Iterable[Dict[str, Any]], search_query: str) -> int:
    """Save all found books with an upsert; safe to run from an async worker."""
    return catalog_writer.persist(books, search_query)
