"""Script para poblar automáticamente la base de datos de BuscaLibre con múltiples temas.

Este script utiliza el mismo método de simulación de interacción humana:
- Abre buscalibre.com
- Escribe la consulta carácter a carácter (como un humano)
- Presiona enter para buscar
- Extrae el título y otra información de los libros encontrados
- Solo guarda en la base de datos si hay resultados Y no son duplicados

Uso:
    python poblar.py "Tema 1" "Tema 2" "Tema 3" ...

Omitiendo los argumentos, usará una lista por defecto de 20 temas populares.
"""

import asyncio
import sys
import os

# Asegurar que el path incluye la carpeta Scrapper
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from buscalibre_tool import search_buscalibre
from firestore_catalog import (
    persist_catalog_books,
    catalog_document_id,
    prepare_catalog_book_document,
)


# Lista por defecto de 20 temas populares si no se proporcionan argumentos
DEFAULT_QUERIES = [
    "El Principito",
    "Harry Potter",
    "Cien años de soledad",
    "Don Quijote de la Mancha",
    "El Código Da Vinci",
    "Harry Potter y la cámara secreta",
    "El Señor de los Anillos",
    "Orgullo y prejuicio",
    "El pequeño príncipe",
    "Crónica de una muerte anunciada",
    "Yo, Robot",
    "Fundación",
    "Dune",
    "1984",
    "Matar a un ruiseñor",
]


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
    # Obtener las consultas de los argumentos o usar la lista por defecto
    if len(sys.argv) > 1:
        # Los argumentos son las consultas de búsqueda
        queries = sys.argv[1:]
    else:
        # Usar la lista por defecto
        queries = DEFAULT_QUERIES
        print(f"[*] Sin argumentos proporcionados. Usando {len(queries)} temas por defecto.")

    # Limitar a 20 temas como máximo
    queries = queries[:20]

    # Inicializar Firestore
    from firestore_catalog import catalog_writer

    if not catalog_writer.enabled:
        print("[!] Firestore deshabilitado. Ejecutando búsqueda pero sin guardar en BD.")
        print("[*] Los resultados se mostrarán pero no se insertarán en la base.")
        firestore_available = False
    else:
        catalog_writer._initialize()
        db = catalog_writer.db
        firestore_available = True

    print("[*] Iniciando poblar automático de BuscaLibre")
    print(f"[+] Total de temas a procesar: {len(queries)}")
    print("-" * 60)

    total_saved = 0
    total_skipped = 0  # Contador de libros duplicados
    total_searched = 0

    for i, query in enumerate(queries, 1):
        total_searched += 1
        print(f"\n[{i}/{len(queries)}] Buscando: '{query}'")

        # Ejecutar la búsqueda en BuscaLibre (mismo metodo que el backend)
        result = asyncio.run(search_buscalibre(query, max_results=10, ganancia_envio=200.0))

        # Verificar si hay errores o no hay resultados
        if result.get("error"):
            print(f"[!] Error en la busqueda: {result['error']}")
            continue

        books = result.get("results", [])
        print(f"[+] Encontrados {len(books)} libros")

        if not books:
            print(f"[!] No se encontraron resultados para '{query}'. Sin guardar en BD.")
            continue

        # Procesar cada libro encontrado
        for book in books:
            # Generar el ID documental usando la misma función que el backend
            book_id = catalog_document_id(book)

            # Verificar si ya existe en la base de datos
            if firestore_available:
                if check_book_exists(db, book_id):
                    total_skipped += 1
                    # No imprimir todo para no saturar la salida, solo al final
                    continue

            # Preparar el documento para persistir
            doc = prepare_catalog_book_document(book, query)

            # Persistir en Firestore usando la misma funcion que el backend
            print(f"[*] Guardando libro: '{doc['title']}'...")
            saved = persist_catalog_books([book], query)

            total_saved += saved
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