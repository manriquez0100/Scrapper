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
from pricing_strategy import calculate_smart_price


# Lista por defecto de 20 temas populares si no se proporcionan argumentos
DEFAULT_QUERIES = [

    # # =============================
    # # Literatura japonesa
    # # =============================
    # "Haruki Murakami libros",
    # "Tokio Blues",
    # "Kafka en la orilla",
    # "1Q84",
    # "La muerte del comendador",
    # "Ryu Murakami libros",
    # "Yasunari Kawabata libros",
    # "País de nieve",
    # "Osamu Dazai libros",
    # "Indigno de ser humano",
    # "El cielo es azul la tierra blanca",
    # "Banana Yoshimoto libros",
    # "Kitchen Banana Yoshimoto",
    # "Kenzaburo Oe libros",
    # "Shusaku Endo libros",
    # "El mar y el veneno",
    # "Sayaka Murata libros",
    # "Convenience Store Woman",
    # "Mieko Kawakami libros",
    # "Earthlings Sayaka Murata",

    # # =============================
    # # Literatura coreana y asiática
    # # =============================
    # "Han Kang libros",
    # "La vegetariana",
    # "Actos humanos",
    # "Kim Ji Young nacida en 1982",
    # "Cho Nam Joo libros",
    # "Almendra Sohn Won Pyung",
    # "Pachinko Min Jin Lee",
    # "Kim Young Ha libros",
    # " literatura china contemporánea",
    # "Mo Yan libros",
    # "El problema de los tres cuerpos Cixin Liu",
    # "Ken Liu libros",
    # "La gracia de los reyes",
    # "Jung Chang libros",

    # # =============================
    # # Literatura africana y del Medio Oriente
    # # =============================
    # "Chinua Achebe libros",
    # "Todo se desmorona",
    # "Chimamanda Ngozi Adichie libros",
    # "Americanah",
    # "Medio sol amarillo",
    # "El peligro de una historia única",
    # "Naguib Mahfouz libros",
    # "El callejón de los milagros",
    # "Tahar Ben Jelloun libros",
    # "Orhan Pamuk libros",
    # "El museo de la inocencia",
    # "Mi nombre es rojo",
    # "Khaled Hosseini libros",
    # "Cometas en el cielo",
    # "Mil soles espléndidos",
    # "Marjane Satrapi Persépolis",

    # # =============================
    # # Novela negra y thriller
    # # =============================
    # "Jo Nesbo libros",
    # "Stieg Larsson libros",
    # "Camilla Läckberg libros",
    # "Patricia Highsmith libros",
    # "El talento de Mr Ripley",
    # "Gillian Flynn libros",
    # "Sharp Objects",
    # "Tana French libros",
    # "Dennis Lehane libros",
    # "Mystic River",
    # "Michael Connelly libros",
    # "John Grisham libros",
    # "Harlan Coben libros",
    # "Thomas Harris libros",
    # "James Ellroy libros",
    # "Agatha Christie colección",
    # "Arthur Conan Doyle colección",
    # "Novela negra española",
    # "Novela policiaca nórdica",
    # "Thriller psicológico libros",

    # # =============================
    # # Autores contemporáneos
    # # =============================
    # "Sally Rooney libros",
    # "Ottessa Moshfegh libros",
    # "Elena Ferrante libros",
    # "Donna Tartt libros",
    # "La historia secreta Donna Tartt",
    # "Zadie Smith libros",
    # "Kazuo Ishiguro libros",
    # "Nunca me abandones",
    # "David Foster Wallace libros",
    # "Infinite Jest",
    # "Cormac McCarthy libros",
    # "La carretera",
    # "Philip Roth libros",
    # "Paul Auster libros",
    # "Ian McEwan libros",
    # "Jonathan Franzen libros",
    # "Chuck Palahniuk libros",
    # "Fight Club libro",
    # "Bret Easton Ellis libros",
    # "American Psycho",
    # "Neil Gaiman libros",
    # "Terry Pratchett libros",
    # "Douglas Adams libros",
    # "Margaret Atwood libros",
    # "El cuento de la criada",
    # "Kazuo Ishiguro novelas",

    # # =============================
    # # Literatura mexicana adicional
    # # =============================
    # "Fernando del Paso libros",
    # "José Agustín libros",
    # "Pasta de Conchos libros",
    # "Jorge Ibargüengoitia libros",
    # "Las muertas Jorge Ibargüengoitia",
    # "Elena Poniatowska libros",
    # "Hasta no verte Jesús mío",
    # "Guillermo Arriaga libros",
    # "Valeria Luiselli libros",
    # "Los ingrávidos",
    # "Cristina Rivera Garza libros",
    # "Nadie me verá llorar",
    # "Brenda Navarro libros",
    # "Temporada de huracanes Fernanda Melchor",
    # "Ángeles Mastretta libros",
    # "Arráncame la vida",
    # "Eduardo Antonio Parra libros",
    # "David Toscana libros",
    # "Emiliano Monge libros",
    # "Literatura de Guanajuato",
    # "Historia de León Guanajuato libros",
    # "Historia de Guanajuato libros",
    # "Crónicas de México libros",
    # "Literatura mexicana contemporánea",

    # # =============================
    # # Feminismo y estudios sociales
    # # =============================
    # "El segundo sexo Simone de Beauvoir",
    # "Calibán y la bruja",
    # "Silvia Federici libros",
    # "Mujeres hombres y poder Mary Beard",
    # "We Should All Be Feminists",
    # "Todos deberíamos ser feministas",
    # "Feminismo para principiantes",
    # "El género en disputa Judith Butler",
    # "Los hombres me explican cosas",
    # "Rebecca Solnit libros",
    # "Feminismo libros historia",
    # "Sociología libros",
    # "Antropología cultural libros",
    # "Michel de Certeau libros",
    # "Zygmunt Bauman libros",
    # "Modernidad líquida",
    # "La sociedad del espectáculo",
    # "Guy Debord libros",
    # "Vigilar y castigar",
    # "La distinción Pierre Bourdieu",
    # "Capital cultural Bourdieu",

    # # =============================
    # # Arquitectura, diseño y urbanismo
    # # =============================
    # "Le Corbusier libros",
    # "Frank Lloyd Wright libros",
    # "Arquitectura moderna libros",
    # "Arquitectura mexicana libros",
    # "Luis Barragán libros",
    # "Tatiana Bilbao libros",
    # "Arquitectura brutalista libros",
    # "Historia de la arquitectura",
    # "Urbanismo libros",
    # "La imagen de la ciudad Kevin Lynch",
    # "Jane Jacobs Muerte y vida de las grandes ciudades",
    # "Diseño industrial libros",
    # "Interiorismo libros",
    # "Bauhaus libros",
    # "Art Deco libros",
    # "Historia del diseño gráfico",
    # "Tipografía libros",
    # "Atlas de arquitectura",

    # # =============================
    # # Medicina y ciencias biológicas
    # # =============================
    # "Oliver Sacks libros",
    # "El hombre que confundió a su mujer con un sombrero",
    # "Despertares Oliver Sacks",
    # "Robert Sapolsky libros",
    # "Por qué las cebras no tienen úlceras",
    # "Neurociencia libros divulgación",
    # "Biología molecular libros",
    # "Genética libros divulgación",
    # "Richard Dawkins libros",
    # "El relojero ciego",
    # "El gen egoísta Richard Dawkins",
    # "David Attenborough libros",
    # "Microbiología libros",
    # "La vida secreta de los árboles",
    # "Entangled Life Merlin Sheldrake",
    # "Medicina narrativa libros",
    # "Historia de la medicina libros",

    # # =============================
    # # Matemáticas y pensamiento científico
    # # =============================
    # "Gödel Escher Bach Douglas Hofstadter",
    # "El hombre que calculaba",
    # "Matemáticas recreativas libros",
    # "La música de los números primos",
    # "Fermat el último teorema",
    # "Simon Singh libros",
    # "El universo matemático",
    # "Historia de las matemáticas",
    # "Lógica matemática libros",
    # "Probabilidad libros",
    # "Teoría de juegos libros",
    # "El arte de la estadística David Spiegelhalter",
    # "Mathematics for Machine Learning",

    # # =============================
    # # Política, poder y geopolítica
    # # =============================
    # "Geopolítica libros",
    # "Prisioneros de la geografía",
    # "Tim Marshall libros",
    # "El choque de civilizaciones",
    # "Samuel Huntington libros",
    # "La doctrina del shock Naomi Klein",
    # "No Logo Naomi Klein",
    # "Manufacturing Consent",
    # "Edward Said Orientalismo",
    # "El fin de la historia Francis Fukuyama",
    # "Robert D Kaplan libros",
    # "Historia del espionaje libros",
    # "CIA libros historia",
    # "KGB libros historia",
    # "Historia de la diplomacia",
    # "Historia de las revoluciones",

    # # =============================
    # # Premios literarios
    # # =============================
    # "Premio Nobel de literatura libros",
    # "Premio Booker novelas",
    # "Premio Pulitzer ficción",
    # "Premio Cervantes libros",
    # "Premio Alfaguara novela",
    # "Premio Herralde novela",
    # "Premio Planeta libros",
    # "Premio FIL literatura",
    # "Premio Goncourt novelas",
    # "Premio Hugo ciencia ficción",
    # "Premio Nebula ciencia ficción",
    # "Premio Locus fantasía",
    # "Premios literarios novelas contemporáneas",

    # # =============================
    # # Editoriales y catálogo
    # # =============================
    # "Editorial Acantilado catálogo",
    # "Editorial Anagrama catálogo",
    # "Editorial Siruela catálogo",
    # "Editorial Sexto Piso catálogo",
    # "Editorial Impedimenta catálogo",
    # "Editorial Alianza libros",
    # "Editorial Austral clásicos",
    # "Editorial Minotauro catálogo",
    # "Editorial Valdemar terror",
    # "Editorial Porrúa libros",
    # "Fondo de Cultura Económica catálogo",
    # "Editorial Era libros",
    # "Editorial Periférica catálogo",
    # "Editorial Libros del Asteroide",
    # "Editorial Nórdica libros",
    # "Editorial Atalanta libros",
    # "Editorial Capitán Swing catálogo",
    # "Editorial Taschen libros",
    # "Editorial O'Reilly libros",
    # "Editorial Norma libros",

    # # =============================
    # # Coleccionismo y libros difíciles
    # # =============================
    # "Primera edición libros literatura",
    # "Libros firmados por autores",
    # "Libros autografiados colección",
    # "Libros antiguos mexicanos",
    # "Libros raros colección",
    # "Libros descatalogados literatura",
    # "Ediciones limitadas libros",
    # "Libros ilustrados ediciones especiales",
    # "Colecciones completas libros",
    # "Libros vintage",
    # "Libros de colección años 80",
    # "Libros de colección años 90",
    # "Enciclopedias antiguas",
    # "Diccionarios antiguos",
    # "Libros de arte descatalogados",
    # "Novelas gráficas ediciones especiales",
    # "Libros primeras ediciones México",

    # # =============================
    # # Idioma original / mercado internacional
    # # =============================
    # "Best selling fiction books in English",
    # "Classic literature books in English",
    # "Vintage science fiction books",
    # "Rare fantasy books",
    # "Contemporary literary fiction",
    # "Award winning novels",
    # "International bestselling books",
    # "Used books collectible editions",
    # "Vintage Penguin Classics",
    # "Oxford World's Classics books",
    # "Everyman's Library collection",
    # "Folio Society books",
    # "Vintage paperback books",
    # "First edition hardcover books",
    # "Signed books collectible",

    # # =============================
    # # Temas adicionales
    # # =============================
    # "Libros de criminología",
    # "True crime libros",
    # "Libros de ocultismo",
    # "Historia de la alquimia",
    # "Simbolismo y esoterismo libros",
    # "Historia de la masonería libros",
    # "Mitología comparada",
    # "Arqueología libros",
    # "Civilizaciones antiguas",
    # "Egiptología libros",
    # "Historia medieval libros",
    # "Historia del arte contemporáneo",
    # "Historia del cine libros",
    # "Guiones de cine publicados",
    # "Libros sobre fotografía analógica",
    # "Libros de ajedrez",
    # "Libros de cocina internacional",
    # "Libros de gastronomía mexicana",
    # "Libros de vinos",
    # "Libros de viajes y exploración",
    # "Expediciones libros",
    # "Naturaleza y vida silvestre libros",
    # "Filosofía de la tecnología",
    # "Inteligencia artificial libros",
    # "Historia de internet",
    # "Ciberseguridad libros",
    #"Robótica libros",
    #"Blockchain libros",
    #"Historia de los videojuegos",
    "Game design libros",
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

    print("[*] Iniciando poblar automático de BuscaLibre con pricing inteligente")
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
            doc = prepare_catalog_book_document(book, query)

            # Reemplazar el precio con el precio inteligente calculado
            # Firestore catalog usa "priceText" y "price" fields
            doc["price"] = f"${precio_venta:,.2f}"
            doc["priceText"] = f"${precio_venta:,.2f}"
            
            # Guardar información del pricing en metadatos
            doc["pricing_strategy"] = estrategia
            doc["is_psycological_price"] = es_psicologico
            doc["smart_price_original"] = precio_original
            doc["smart_price_margin"] = margen_bruto
            doc["smart_price_percent"] = pricing_result.get("margen_porcentaje", 0)

            print(f"[*] Guardando libro: '{doc.get('title', 'Desconocido')}'")
            print(f"   Precio inteligente: ${precio_venta:,.2f} (estrat: {estrategia})")
            print(f"   Margen: ${margen_bruto:,.2f} ({pricing_result.get('margen_porcentaje', 0)}%)")

            # Persistir en Firestore usando la misma funcion que el backend
            # Solo si Firestore está disponible
            if firestore_available:
                saved = persist_catalog_books([book], query)
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