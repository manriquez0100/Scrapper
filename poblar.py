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
import os
import unicodedata
from typing import Any, Dict, Optional

# Asegurar que el path incluye la carpeta Scrapper
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from buscalibre_tool import search_buscalibre
from firestore_catalog import (
    persist_catalog_books,
    catalog_document_id,
    prepare_catalog_book_document,
)
from pricing_strategy import calculate_smart_price


DEFAULT_QUERIES = [
    # Game design y videojuegos
    "Game design libros",
    "The Art of Game Design Jesse Schell",
    "Game programming patterns",
    "Level design libros",
    "Video game storytelling libros",
    "Historia de los videojuegos libros",
    "Nintendo art books",
    "Dark Souls design works",
    "Bloodborne artbook",
    "Final Fantasy art books",
    "Concept art videojuegos",
    "Indie game development libros",
    "RPG design libros",
    "Narrative design videojuegos",
    "Pixel art libros",

    # Literatura japonesa
    "Haruki Murakami libros",
    "Tokio Blues",
    "Kafka en la orilla",
    "1Q84",
    "La muerte del comendador",
    "Ryu Murakami libros",
    "Yasunari Kawabata libros",
    "País de nieve",
    "Osamu Dazai libros",
    "Indigno de ser humano",
    "Banana Yoshimoto libros",
    "Kitchen Banana Yoshimoto",
    "Kenzaburo Oe libros",
    "Shusaku Endo libros",
    "El mar y el veneno",
    "Sayaka Murata libros",
    "Convenience Store Woman",
    "Mieko Kawakami libros",
    "Earthlings Sayaka Murata",
    "Yoko Ogawa libros",
    "El embarazo de mi hermana",
    "Junichiro Tanizaki libros",
    "El elogio de la sombra",
    "Ryunosuke Akutagawa libros",
    "Rashomon",
    "Mishima Yukio libros",
    "Confesiones de una máscara",
    "El pabellón de oro",

    # Literatura coreana y asiática
    "Han Kang libros",
    "La vegetariana",
    "Actos humanos",
    "Kim Ji Young nacida en 1982",
    "Cho Nam Joo libros",
    "Almendra Sohn Won Pyung",
    "Pachinko Min Jin Lee",
    "Kim Young Ha libros",
    "Literatura china contemporánea",
    "Mo Yan libros",
    "El problema de los tres cuerpos Cixin Liu",
    "Ken Liu libros",
    "La gracia de los reyes",
    "Jung Chang libros",
    "Yu Hua libros",
    "Vivir Yu Hua",
    "Xiaolu Guo libros",
    " literatura vietnamita contemporánea",
    "Literatura taiwanesa",
    " literatura india contemporánea",
    "Rabindranath Tagore libros",
    "Arundhati Roy libros",
    "El dios de las pequeñas cosas",

    # Literatura africana y del Medio Oriente
    "Chinua Achebe libros",
    "Todo se desmorona",
    "Chimamanda Ngozi Adichie libros",
    "Americanah",
    "Medio sol amarillo",
    "El peligro de una historia única",
    "Naguib Mahfouz libros",
    "El callejón de los milagros",
    "Tahar Ben Jelloun libros",
    "Orhan Pamuk libros",
    "El museo de la inocencia",
    "Mi nombre es rojo",
    "Khaled Hosseini libros",
    "Cometas en el cielo",
    "Mil soles espléndidos",
    "Marjane Satrapi Persépolis",
    "Ngugi wa Thiong'o libros",
    "Ben Okri libros",
    "Amin Maalouf libros",
    "Leila Slimani libros",
    " literatura árabe contemporánea",
    "Literatura persa libros",
    "Literatura nigeriana contemporánea",

    # Novela negra, crimen y thriller
    "Jo Nesbo libros",
    "Stieg Larsson libros",
    "Camilla Läckberg libros",
    "Patricia Highsmith libros",
    "El talento de Mr Ripley",
    "Gillian Flynn libros",
    "Sharp Objects",
    "Tana French libros",
    "Dennis Lehane libros",
    "Mystic River",
    "Michael Connelly libros",
    "John Grisham libros",
    "Harlan Coben libros",
    "Thomas Harris libros",
    "James Ellroy libros",
    "Agatha Christie colección",
    "Arthur Conan Doyle colección",
    "Novela negra española",
    "Novela policiaca nórdica",
    "Thriller psicológico libros",
    "True crime libros",
    "Criminología libros",
    "Novela de detectives clásica",
    "Raymond Chandler libros",
    "El sueño eterno",
    "Dashiell Hammett libros",
    "El halcón maltés",
    "Edgar Allan Poe cuentos completos",
    "Patricia Cornwell libros",
    "Robert Galbraith libros",
    "Sicarios y narcotráfico literatura",
    "Novela negra latinoamericana",
    "Crimen organizado libros",

    # Autores contemporáneos
    "Sally Rooney libros",
    "Ottessa Moshfegh libros",
    "Elena Ferrante libros",
    "Donna Tartt libros",
    "La historia secreta Donna Tartt",
    "Zadie Smith libros",
    "Kazuo Ishiguro libros",
    "Nunca me abandones",
    "David Foster Wallace libros",
    "Infinite Jest",
    "Cormac McCarthy libros",
    "La carretera",
    "Philip Roth libros",
    "Paul Auster libros",
    "Ian McEwan libros",
    "Jonathan Franzen libros",
    "Chuck Palahniuk libros",
    "Fight Club libro",
    "Bret Easton Ellis libros",
    "American Psycho",
    "Neil Gaiman libros",
    "Terry Pratchett libros",
    "Douglas Adams libros",
    "Margaret Atwood libros",
    "El cuento de la criada",
    "George Saunders libros",
    "Ben Lerner libros",
    "Hanif Kureishi libros",
    "Nick Cave libros",
    "R. F. Kuang libros",
    "Mona Awad libros",
    "Mariana Enriquez libros",
    "Samanta Schweblin libros",
    "Pedro Mairal libros",
    "Andrés Neuman libros",
    "Juan Gabriel Vásquez libros",
    "Sergio Pitol libros",
    "Roberto Bolaño libros",
    "2666 Roberto Bolaño",
    "Los detectives salvajes",

    # Literatura mexicana
    "Fernando del Paso libros",
    "José Agustín libros",
    "Pasta de Conchos libros",
    "Jorge Ibargüengoitia libros",
    "Las muertas Jorge Ibargüengoitia",
    "Elena Poniatowska libros",
    "Hasta no verte Jesús mío",
    "Guillermo Arriaga libros",
    "Valeria Luiselli libros",
    "Los ingrávidos",
    "Cristina Rivera Garza libros",
    "Nadie me verá llorar",
    "Brenda Navarro libros",
    "Temporada de huracanes Fernanda Melchor",
    "Ángeles Mastretta libros",
    "Arráncame la vida",
    "Eduardo Antonio Parra libros",
    "David Toscana libros",
    "Emiliano Monge libros",
    "Literatura de Guanajuato",
    "Historia de León Guanajuato libros",
    "Historia de Guanajuato libros",
    "Crónicas de México libros",
    "Literatura mexicana contemporánea",
    "Juan Rulfo libros",
    "Pedro Páramo ediciones",
    "El llano en llamas",
    "Carlos Fuentes libros",
    "La muerte de Artemio Cruz",
    "José Emilio Pacheco libros",
    "Las batallas en el desierto",
    "Elena Garro libros",
    "Los recuerdos del porvenir",
    "Octavio Paz libros",
    "Rosario Castellanos libros",
    "Balún Canán",
    "Amparo Dávila libros",
    "Cuentos de terror mexicanos",
    "Francisco Tario libros",
    "Jorge Volpi libros",
    "Aura Carlos Fuentes",
    "Literatura del norte de México",
    "Literatura indígena mexicana",
    "Literatura chicana libros",
    "Poesía mexicana contemporánea",

    # Feminismo y estudios sociales
    "El segundo sexo Simone de Beauvoir",
    "Calibán y la bruja",
    "Silvia Federici libros",
    "Mujeres hombres y poder Mary Beard",
    "We Should All Be Feminists",
    "Todos deberíamos ser feministas",
    "Feminismo para principiantes",
    "El género en disputa Judith Butler",
    "Los hombres me explican cosas",
    "Rebecca Solnit libros",
    "Feminismo libros historia",
    "Sociología libros",
    "Antropología cultural libros",
    "Michel de Certeau libros",
    "Zygmunt Bauman libros",
    "Modernidad líquida",
    "La sociedad del espectáculo",
    "Guy Debord libros",
    "Vigilar y castigar",
    "La distinción Pierre Bourdieu",
    "Capital cultural Bourdieu",
    "Angela Davis libros",
    " bell hooks libros",
    "Audre Lorde libros",
    "Judith Butler ensayos",
    "Donna Haraway libros",
    "Estudios de género libros",
    "Teoría queer libros",
    "Historia del movimiento feminista",
    "Sociología urbana",
    "Estudios culturales libros",
    "Ensayos sobre capitalismo",
    "Crítica social contemporánea",

    # Arquitectura, diseño y urbanismo
    "Le Corbusier libros",
    "Frank Lloyd Wright libros",
    "Arquitectura moderna libros",
    "Arquitectura mexicana libros",
    "Luis Barragán libros",
    "Tatiana Bilbao libros",
    "Arquitectura brutalista libros",
    "Historia de la arquitectura",
    "Urbanismo libros",
    "La imagen de la ciudad Kevin Lynch",
    "Jane Jacobs Muerte y vida de las grandes ciudades",
    "Diseño industrial libros",
    "Interiorismo libros",
    "Bauhaus libros",
    "Art Deco libros",
    "Historia del diseño gráfico",
    "Tipografía libros",
    "Atlas de arquitectura",
    "Arquitectura japonesa libros",
    "Minimalismo arquitectura",
    "Arquitectura soviética libros",
    "Arquitectura latinoamericana",
    "Fotografía arquitectónica libros",
    "Diseño editorial libros",
    "Historia del mobiliario",
    "Brutalismo arquitectura fotografía",

    # Medicina y ciencias biológicas
    "Oliver Sacks libros",
    "El hombre que confundió a su mujer con un sombrero",
    "Despertares Oliver Sacks",
    "Robert Sapolsky libros",
    "Por qué las cebras no tienen úlceras",
    "Neurociencia libros divulgación",
    "Biología molecular libros",
    "Genética libros divulgación",
    "Richard Dawkins libros",
    "El relojero ciego",
    "El gen egoísta Richard Dawkins",
    "David Attenborough libros",
    "Microbiología libros",
    "La vida secreta de los árboles",
    "Entangled Life Merlin Sheldrake",
    "Medicina narrativa libros",
    "Historia de la medicina libros",
    "Carl Sagan libros",
    "Cosmos Carl Sagan",
    "Stephen Jay Gould libros",
    "Evolución biológica libros",
    "Neuropsicología libros",
    "Psicología cognitiva libros",
    "Cerebro humano libros",
    "Anatomía humana ilustrada",
    "Botánica libros",
    "Micología libros",
    "Ecología libros",
    "Biodiversidad libros",
    "Zoología libros",
    "Biología marina libros",

    # Matemáticas y pensamiento científico
    "Gödel Escher Bach Douglas Hofstadter",
    "El hombre que calculaba",
    "Matemáticas recreativas libros",
    "La música de los números primos",
    "Fermat el último teorema",
    "Simon Singh libros",
    "El universo matemático",
    "Historia de las matemáticas",
    "Lógica matemática libros",
    "Probabilidad libros",
    "Teoría de juegos libros",
    "El arte de la estadística David Spiegelhalter",
    "Mathematics for Machine Learning",
    "Matemáticas avanzadas libros",
    "Topología libros",
    "Geometría libros",
    "Álgebra abstracta libros",
    "Física cuántica divulgación",
    "Relatividad libros",
    "Astrofísica libros",
    "Cosmología libros",
    "Richard Feynman libros",
    "El carácter de la ley física",
    "Stephen Hawking libros",
    "Historia de la ciencia libros",
    "Filosofía de la ciencia",
    "Método científico libros",
    "Ciencia ficción científica libros",

    # Política, poder y geopolítica
    "Geopolítica libros",
    "Prisioneros de la geografía",
    "Tim Marshall libros",
    "El choque de civilizaciones",
    "Samuel Huntington libros",
    "La doctrina del shock Naomi Klein",
    "No Logo Naomi Klein",
    "Manufacturing Consent",
    "Edward Said Orientalismo",
    "El fin de la historia Francis Fukuyama",
    "Robert D Kaplan libros",
    "Historia del espionaje libros",
    "CIA libros historia",
    "KGB libros historia",
    "Historia de la diplomacia",
    "Historia de las revoluciones",
    "Historia de la Guerra Fría",
    "Imperios historia libros",
    "Colonialismo libros",
    "Historia del fascismo",
    "Historia del comunismo",
    "Propaganda política libros",
    "Teoría política contemporánea",
    "Democracia libros",
    "Poder y vigilancia libros",
    "Historia de los servicios secretos",
    "Conflictos internacionales libros",
    "Guerra moderna libros",
    "Historia militar libros",
    "Inteligencia militar libros",

    # Premios literarios
    "Premio Nobel de literatura libros",
    "Premio Booker novelas",
    "Premio Pulitzer ficción",
    "Premio Cervantes libros",
    "Premio Alfaguara novela",
    "Premio Herralde novela",
    "Premio Planeta libros",
    "Premio FIL literatura",
    "Premio Goncourt novelas",
    "Premio Hugo ciencia ficción",
    "Premio Nebula ciencia ficción",
    "Premio Locus fantasía",
    "Premios literarios novelas contemporáneas",
    "International Booker Prize libros",
    "National Book Award novelas",
    "Premios literatura independiente",
    "Premios de novela gráfica",
    "Premios de ensayo",

    # Editoriales y catálogo
    "Editorial Acantilado catálogo",
    "Editorial Anagrama catálogo",
    "Editorial Siruela catálogo",
    "Editorial Sexto Piso catálogo",
    "Editorial Impedimenta catálogo",
    "Editorial Alianza libros",
    "Editorial Austral clásicos",
    "Editorial Minotauro catálogo",
    "Editorial Valdemar terror",
    "Editorial Porrúa libros",
    "Fondo de Cultura Económica catálogo",
    "Editorial Era libros",
    "Editorial Periférica catálogo",
    "Editorial Libros del Asteroide",
    "Editorial Nórdica libros",
    "Editorial Atalanta libros",
    "Editorial Capitán Swing catálogo",
    "Editorial Taschen libros",
    "Editorial O'Reilly libros",
    "Editorial Norma libros",
    "Editorial Libros del Zorro Rojo",
    "Editorial Akal catálogo",
    "Editorial Almadía catálogo",
    "Editorial Sexto Piso novedades",
    "Editorial Candaya libros",
    "Editorial La Caja de Cerillos",
    "Editorial Lumen catálogo",
    "Editorial Blackie Books catálogo",
    "Editorial Alpha Decay catálogo",
    "Editorial Galaxia Gutenberg libros",
    "Editorial Hueders libros",

    # Coleccionismo y libros difíciles
    "Primera edición libros literatura",
    "Libros firmados por autores",
    "Libros autografiados colección",
    "Libros antiguos mexicanos",
    "Libros raros colección",
    "Libros descatalogados literatura",
    "Ediciones limitadas libros",
    "Libros ilustrados ediciones especiales",
    "Colecciones completas libros",
    "Libros vintage",
    "Libros de colección años 80",
    "Libros de colección años 90",
    "Enciclopedias antiguas",
    "Diccionarios antiguos",
    "Libros de arte descatalogados",
    "Novelas gráficas ediciones especiales",
    "Libros primeras ediciones México",
    "Libros de culto ediciones antiguas",
    "Ediciones de bolsillo vintage",
    "Libros agotados editoriales",
    "Libros raros de ciencia ficción",
    "Libros antiguos de filosofía",
    "Revistas literarias antiguas",
    "Coleccionismo de manga",
    "Libros ilustrados de colección",

    # Idioma original y mercado internacional
    "Best selling fiction books in English",
    "Classic literature books in English",
    "Vintage science fiction books",
    "Rare fantasy books",
    "Contemporary literary fiction",
    "Award winning novels",
    "International bestselling books",
    "Used books collectible editions",
    "Vintage Penguin Classics",
    "Oxford World's Classics books",
    "Everyman's Library collection",
    "Folio Society books",
    "Vintage paperback books",
    "First edition hardcover books",
    "Signed books collectible",
    "French literature rare books",
    "German literature classic books",
    "Italian literature contemporary books",
    "Russian literature rare editions",
    "Spanish rare books",
    "Latin American literature first editions",
    "English academic books",
    "Japanese books translated English",
    "Foreign language vintage books",

    # Terror, horror y ocultismo
    "Stephen King libros primeras ediciones",
    "Clive Barker libros",
    "Thomas Ligotti libros",
    "Shirley Jackson libros",
    "La maldición de Hill House",
    "H.P. Lovecraft libros",
    "Cthulhu libros ediciones",
    "Bram Stoker Drácula ediciones",
    "Mary Shelley Frankenstein ediciones",
    "Robert W Chambers El rey de amarillo",
    "Terror gótico libros",
    "Horror cósmico libros",
    "Folk horror libros",
    "Terror psicológico novelas",
    "Historia del ocultismo libros",
    "Simbolismo y esoterismo libros",
    "Historia de la alquimia",
    "Historia de la masonería libros",
    "Mitología comparada",
    "Demonología libros históricos",
    "Brujería historia libros",
    "Folclore oscuro libros",
    "Cuentos de fantasmas clásicos",

    # Fantasía y ciencia ficción
    "Ursula K Le Guin libros",
    "El nombre del mundo es bosque",
    "Octavia Butler libros",
    "Parentesco Octavia Butler",
    "Philip K Dick libros",
    "Ubik Philip K Dick",
    "Neuromante William Gibson",
    "William Gibson libros",
    "Isaac Asimov libros",
    "Fundación Asimov",
    "Frank Herbert Dune",
    "Dune ediciones de colección",
    "Ray Bradbury libros",
    "Fahrenheit 451 ediciones",
    "Gene Wolfe libros",
    "China Miéville libros",
    "Jeff VanderMeer libros",
    "Aniquilación Jeff VanderMeer",
    "Ted Chiang cuentos",
    "Exhalación Ted Chiang",
    "Adrian Tchaikovsky libros",
    "N.K. Jemisin libros",
    "Elric Michael Moorcock",
    "Conan Robert E Howard",
    "Dragonlance libros",
    "Malaz libros",
    "The Witcher libros colección",
    "Tolkien ediciones ilustradas",
    "Fantasía oscura libros",
    "Space opera libros",
    "Cyberpunk novelas",
    "Distopías literarias",

    # Filosofía
    "Friedrich Nietzsche libros",
    "Así habló Zaratustra",
    "Arthur Schopenhauer libros",
    "El mundo como voluntad y representación",
    "Albert Camus libros",
    "El mito de Sísifo",
    "Jean Paul Sartre libros",
    "Simone de Beauvoir filosofía",
    "Hannah Arendt libros",
    "La condición humana",
    "Michel Foucault libros",
    "Gilles Deleuze libros",
    "Slavoj Žižek libros",
    "Byung Chul Han libros",
    "La sociedad del cansancio",
    "Mark Fisher Realismo capitalista",
    "Walter Benjamin libros",
    "Theodor Adorno libros",
    "Ludwig Wittgenstein libros",
    "Bertrand Russell libros",
    "Emil Cioran libros",
    "Filosofía existencialista libros",
    "Estoicismo libros clásicos",
    "Filosofía oriental libros",
    "Filosofía budista libros",
    "Filosofía de la mente",
    "Ética libros",
    "Metafísica libros",
    "Estética filosofía",

    # Historia y civilizaciones
    "Historia universal libros",
    "Historia de Roma libros",
    "Imperio romano libros",
    "Historia de Grecia antigua",
    "Civilización maya libros",
    "Civilización azteca libros",
    "Historia del antiguo Egipto",
    "Mesopotamia libros historia",
    "Vikingos historia libros",
    "Edad Media libros",
    "Renacimiento historia libros",
    "Revolución francesa libros",
    "Revolución mexicana libros",
    "Historia de la independencia de México",
    "Historia de América Latina",
    "Historia de China libros",
    "Historia de Japón libros",
    "Historia de la India libros",
    "Historia del Imperio otomano",
    "Historia de África libros",
    "Historia de las religiones",
    "Arqueología libros",
    "Civilizaciones antiguas",
    "Egiptología libros",
    "Historia medieval libros",
    "Historia del arte contemporáneo",
    "Historia del cine libros",
    "Guiones de cine publicados",
    "Libros sobre fotografía analógica",
    "Libros de ajedrez",
    "Libros de cocina internacional",
    "Libros de gastronomía mexicana",
    "Libros de vinos",
    "Libros de viajes y exploración",
    "Expediciones libros",
    "Naturaleza y vida silvestre libros",
    "Filosofía de la tecnología",
    "Inteligencia artificial libros",
    "Historia de internet",
    "Ciberseguridad libros",
    "Robótica libros",
    "Blockchain libros",
    "Historia de los videojuegos",
]

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
    parser.add_argument("--max-results", type=int, default=10, help="Resultados por consulta (predeterminado: 10).")
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
