"""Unit tests for the Firestore catalog normalization and upsert behavior."""

import unittest
import logging

from firestore_catalog import FirestoreCatalogWriter, catalog_document_id, prepare_catalog_book_document


class FakeDocument:
    def __init__(self):
        self.calls = []

    def set(self, document, merge=False):
        self.calls.append((document, merge))


class FakeCollection:
    def __init__(self):
        self.documents = {}

    def document(self, identifier):
        return self.documents.setdefault(identifier, FakeDocument())


class FakeDatabase:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, FakeCollection())


class FirestoreCatalogTests(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.book = {
            "title": "Segunda Fundación", "author": "Isaac Asimov", "price": "$ 289",
            "price_original": "$ 89", "url": "https://example.test/segunda-fundacion",
            "image_url": "https://example.test/cover.jpg", "pages": "304 páginas",
            "availability": True, "delivery_estimate": "Envío rápido", "source": "buscalibre",
        }

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_normalizes_scraper_data_for_the_web_catalog(self):
        document = prepare_catalog_book_document(self.book, "Segunda Fundación Asimov")
        self.assertEqual(document["title"], "Segunda Fundación")
        self.assertEqual(document["price"], 289.0)
        self.assertEqual(document["pages"], 304)
        self.assertEqual(document["searchTerms"], ["Segunda Fundación Asimov"])
        self.assertTrue(document["imageUrl"].startswith("https://"))

    def test_has_a_stable_id_for_upserts(self):
        self.assertEqual(catalog_document_id(self.book), catalog_document_id(dict(self.book)))

    def test_saves_each_result_with_merge(self):
        database = FakeDatabase()
        writer = FirestoreCatalogWriter(db=database, enabled=True)
        self.assertEqual(writer.persist([self.book], "fundación"), 1)
        document = database.collection("books").documents[catalog_document_id(self.book)]
        self.assertEqual(len(document.calls), 1)
        self.assertTrue(document.calls[0][1])

    def test_returns_zero_when_firestore_is_disabled(self):
        writer = FirestoreCatalogWriter(enabled=False)
        self.assertEqual(writer.persist([self.book], "fundación"), 0)


if __name__ == "__main__":
    unittest.main()
