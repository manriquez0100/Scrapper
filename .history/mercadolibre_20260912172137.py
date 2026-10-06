"""
Cliente básico para buscar libros en Mercado Libre México (MLM).

IMPORTANTE:
- No pongas tus credenciales directamente en este archivo.
- Usa un archivo .env en la misma carpeta.
- Este módulo SOLO realiza búsquedas y consultas de productos.
"""

import os
import re
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv


# Cargar variables del archivo .env
load_dotenv()

SITE_ID = os.getenv("MELI_SITE_ID", "MLM")
ACCESS_TOKEN = os.getenv("MELI_ACCESS_TOKEN", "")

BASE_URL = "https://api.mercadolibre.com"
REQUEST_TIMEOUT = 20


class MercadoLibreError(Exception):
    """Error controlado de la API de Mercado Libre."""


class MercadoLibreClient:
    def __init__(
        self,
        access_token: Optional[str] = None,
        site_id: Optional[str] = None,
    ):
        self.access_token = access_token or ACCESS_TOKEN
        self.site_id = site_id or SITE_ID

        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
        })

        if self.access_token:
            self.session.headers.update({
                "Authorization": f"Bearer {self.access_token}"
            })

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.access_token:
            raise MercadoLibreError(
                "No se encontró MELI_ACCESS_TOKEN en el archivo .env."
            )

        url = f"{BASE_URL}{endpoint}"

        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise MercadoLibreError(
                f"No fue posible conectarse con Mercado Libre: {exc}"
            ) from exc

        if not response.ok:
            try:
                detalle = response.json()
            except ValueError:
                detalle = response.text

            raise MercadoLibreError(
                f"Mercado Libre respondió HTTP {response.status_code}: "
                f"{detalle}"
            )

        try:
            return response.json()
        except ValueError as exc:
            raise MercadoLibreError(
                "Mercado Libre devolvió una respuesta que no es JSON."
            ) from exc

    @staticmethod
    def normalizar_isbn(isbn: str) -> str:
        """Deja únicamente números y conserva X para ISBN-10."""
        if not isbn:
            return ""

        isbn = str(isbn).strip().upper()
        isbn = re.sub(r"[^0-9X]", "", isbn)

        return isbn

    def buscar_por_isbn(
        self,
        isbn: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Busca un libro usando ISBN.

        Mercado Libre permite utilizar ISBN como identificador universal.
        """
        isbn = self.normalizar_isbn(isbn)

        if not isbn:
            return []

        data = self._request(
            "GET",
            "/products/search",
            params={
                "site_id": self.site_id,
                "product_identifier": isbn,
                "status": "active",
                "limit": limit,
            },
        )

        return self._normalizar_resultados(data)

    def buscar_por_titulo_autor(
        self,
        titulo: str,
        autor: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Busca un libro por título y, opcionalmente, autor."""

        partes = []

        if titulo:
            partes.append(titulo.strip())

        if autor:
            partes.append(autor.strip())

        query = " ".join(partes).strip()

        if not query:
            return []

        data = self._request(
            "GET",
            "/products/search",
            params={
                "site_id": self.site_id,
                "q": query,
                "status": "active",
                "limit": limit,
            },
        )

        return self._normalizar_resultados(data)

    def buscar(
        self,
        titulo: Optional[str] = None,
        autor: Optional[str] = None,
        isbn: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Método general.

        Prioridad:
        1. ISBN
        2. Título + autor
        3. Título
        """
        if isbn:
            resultados = self.buscar_por_isbn(isbn, limit)
            if resultados:
                return resultados

        if titulo:
            return self.buscar_por_titulo_autor(titulo, autor, limit)

        return []

    def obtener_producto(self, product_id: str) -> Dict[str, Any]:
        """Obtiene información detallada de un producto de catálogo."""
        if not product_id:
            raise ValueError("product_id es obligatorio.")

        return self._request(
            "GET",
            f"/products/{product_id}",
        )

    def _normalizar_resultados(
        self,
        data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Convierte la respuesta de Mercado Libre a una estructura
        más sencilla para nuestro proyecto.
        """
        resultados = []

        productos = data.get("results", [])

        if isinstance(productos, dict):
            productos = [productos]

        for producto in productos:
            if not isinstance(producto, dict):
                continue

            resultados.append(self._normalizar_producto(producto))

        return resultados

    @staticmethod
    def _normalizar_producto(
        producto: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Normaliza un producto de catálogo.

        Nota:
        /products/search es principalmente una búsqueda de catálogo.
        El precio/publicación del vendedor puede requerir consultar
        información adicional de listings/items.
        """
        buy_box = producto.get("buy_box_winner") or {}

        return {
            "fuente": "mercadolibre",
            "id": producto.get("id"),
            "titulo": (
                producto.get("name")
                or producto.get("title")
                or ""
            ),
            "autor": producto.get("author"),
            "isbn13": None,
            "isbn10": None,
            "precio": buy_box.get("price"),
            "moneda": buy_box.get("currency_id", "MXN"),
            "imagen": (
                producto.get("thumbnail")
                or producto.get("pictures", [{}])[0].get("url")
                if producto.get("pictures")
                else producto.get("thumbnail")
            ),
            "url": producto.get("permalink"),
            "disponible": bool(buy_box),
            "raw": producto,
        }


def imprimir_resultados(resultados: List[Dict[str, Any]]) -> None:
    """Muestra resultados de forma legible en consola."""

    if not resultados:
        print("\nNo se encontraron resultados.")
        return

    print(f"\nSe encontraron {len(resultados)} resultado(s):\n")

    for indice, libro in enumerate(resultados, start=1):
        print("=" * 70)
        print(f"Resultado #{indice}")
        print(f"Título:     {libro.get('titulo')}")
        print(f"Autor:      {libro.get('autor') or 'No disponible'}")
        print(f"Precio:     {libro.get('precio') or 'No disponible'} "
              f"{libro.get('moneda', 'MXN')}")
        print(f"Disponible: {libro.get('disponible')}")
        print(f"ID:         {libro.get('id')}")
        print(f"URL:        {libro.get('url') or 'No disponible'}")


def main() -> None:
    print("=" * 70)
    print(" BUSCADOR DE LIBROS - MERCADO LIBRE MÉXICO")
    print("=" * 70)

    if not ACCESS_TOKEN:
        print("\nERROR:")
        print("No encontré MELI_ACCESS_TOKEN.")
        print("Crea un archivo .env junto a mercadolibre.py con:")
        print()
        print("MELI_CLIENT_ID=TU_CLIENT_ID")
        print("MELI_CLIENT_SECRET=TU_CLIENT_SECRET")
        print("MELI_ACCESS_TOKEN=TU_ACCESS_TOKEN")
        print("MELI_REFRESH_TOKEN=TU_REFRESH_TOKEN")
        print("MELI_SITE_ID=MLM")
        return

    cliente = MercadoLibreClient()

    print("\nPuedes buscar por ISBN o por título.")
    print("Ejemplo ISBN: 9789505158425")
    print("Escribe 'salir' para terminar.\n")

    while True:
        busqueda = input("ISBN o título: ").strip()

        if busqueda.lower() == "salir":
            break

        if not busqueda:
            continue

        try:
            if re.fullmatch(r"[0-9Xx -]{10,20}", busqueda):
                resultados = cliente.buscar_por_isbn(busqueda)
            else:
                resultados = cliente.buscar_por_titulo_autor(busqueda)

            imprimir_resultados(resultados)

        except MercadoLibreError as exc:
            print(f"\nERROR: {exc}\n")
        except KeyboardInterrupt:
            print("\n\nPrograma terminado.")
            break


if __name__ == "__main__":
    main()
