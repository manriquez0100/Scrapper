from firestore_catalog import prepare_catalog_book_document

# Test with 'Envío rápido'
book_rapido = {
    'title': 'Test Book',
    'author': 'Test Author',
    'price': 100,
    'price_original': 200,
    'currency': 'MXN',
    'availability': True,
    'url': 'https://example.test/book',
    'image_url': 'https://example.test/cover.jpg',
    'delivery_estimate': 'Envío rápido',
}

doc = prepare_catalog_book_document(book_rapido, 'Test Query')
print('Delivery with Envío rápido:', doc.get('delivery'))

# Test with no delivery
book_no_del = {
    'title': 'Test Book',
    'author': 'Test Author',
    'price': 100,
    'price_original': 200,
    'currency': 'MXN',
    'availability': True,
    'url': 'https://example.test/book',
    'image_url': 'https://example.test/cover.jpg',
}

doc2 = prepare_catalog_book_document(book_no_del, 'Test Query')
print('Delivery without estimate:', doc2.get('delivery'))