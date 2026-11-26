"""FastAPI app that orchestrates LM Studio and Buscalibre book searches."""

import json
import logging
import os
import asyncio
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import uuid4
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from buscalibre_tool import search_buscalibre
from catalog_generator import FacebookAdGenerator
from llm_provider import LLMProvider, get_llm_provider
from mercadolibre import search_mercadolibre
from chrome_manager import ensure_chrome_debugging, terminate_chrome_debugging

load_dotenv()
from firestore_catalog import catalog_writer, persist_catalog_books

logger = logging.getLogger(__name__)
BEHAVIOR_CONFIG_PATH = Path(
    os.getenv("ASSISTANT_BEHAVIOR_CONFIG", Path(__file__).with_name("behavior.json"))
)
ASSISTANT_TIMEZONE = os.getenv("ASSISTANT_TIMEZONE", "America/Mexico_City")

CONVERSATIONS_FILE = Path(__file__).with_name("conversations.json")
PRICING_CONFIG_FILE = Path(__file__).with_name("pricing_config.json")
DEFAULT_GANANCIA_ENVIO = 200.0

# Lock for thread-safe file operations
_conversations_lock = asyncio.Lock()
_pricing_lock = asyncio.Lock()


def _load_pricing_config() -> Dict[str, float]:
    try:
        with PRICING_CONFIG_FILE.open("r", encoding="utf-8") as config_file:
            value = float(json.load(config_file).get("ganancia_envio", DEFAULT_GANANCIA_ENVIO))
        return {"ganancia_envio": max(0, value)}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"ganancia_envio": DEFAULT_GANANCIA_ENVIO}


_pricing_config = _load_pricing_config()


async def get_pricing_config() -> Dict[str, float]:
    async with _pricing_lock:
        return dict(_pricing_config)


async def save_pricing_config(ganancia_envio: float) -> Dict[str, float]:
    config = {"ganancia_envio": ganancia_envio}
    async with _pricing_lock:
        temporary_file = PRICING_CONFIG_FILE.with_suffix(".json.tmp")
        with temporary_file.open("w", encoding="utf-8") as config_file:
            json.dump(config, config_file, ensure_ascii=False, indent=2)
        temporary_file.replace(PRICING_CONFIG_FILE)
        _pricing_config.update(config)
        return dict(_pricing_config)


def _migrate_conversations(data: Dict) -> Dict:
    """Migrate old conversation format to new format with clients."""
    conversations = data.get("conversations", [])
    clients = data.get("clients", {})
    for conv in conversations:
        name = conv.get("client_name") or conv.get("sender_name")
        if not name:
            continue
        profile = clients.setdefault(name.lower().strip(), {
            "name": name,
            "first_seen": conv.get("created_at"),
            "last_seen": conv.get("created_at"),
            "conversation_ids": [],
        })
        if conv["id"] not in profile["conversation_ids"]:
            profile["conversation_ids"].append(conv["id"])
    data = {"clients": clients, "conversations": conversations}
    return data


async def load_conversations() -> Dict:
    """Load conversations from JSON file."""
    async with _conversations_lock:
        try:
            with CONVERSATIONS_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return _migrate_conversations(data)
        except (OSError, json.JSONDecodeError):
            return {"clients": {}, "conversations": []}


async def save_conversations(data: Dict) -> None:
    """Save conversations to JSON file."""
    async with _conversations_lock:
        try:
            temporary_file = CONVERSATIONS_FILE.with_suffix(".json.tmp")
            with temporary_file.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            temporary_file.replace(CONVERSATIONS_FILE)
        except OSError as exc:
            logger.error("Failed to save conversations: %s", exc)


async def add_message_to_conversation(
    session_id: str,
    role: str,
    content: str,
    catalog_images: Optional[List[str]] = None,
    client_name: Optional[str] = None,
    search_results: Optional[List[Dict]] = None,
) -> None:
    """Add a message to a conversation, creating it if needed."""
    data = await load_conversations()
    conversations = data.get("conversations", [])
    clients = data.get("clients", {})
    
    conv = next((c for c in conversations if c["id"] == session_id), None)
    if not conv:
        conv = {
            "id": session_id,
            "created_at": datetime.now(ZoneInfo(ASSISTANT_TIMEZONE)).isoformat(),
            "messages": []
        }
        conversations.append(conv)
    
    # Link conversation to client if client_name provided
    resolved_client_name = conv.get("client_name") or client_name
    if resolved_client_name:
        conv.setdefault("client_name", resolved_client_name)
        # Update client profile
        normalized_name = resolved_client_name.lower().strip()
        if normalized_name not in clients:
            clients[normalized_name] = {
                "name": resolved_client_name,
                "first_seen": datetime.now(ZoneInfo(ASSISTANT_TIMEZONE)).isoformat(),
                "last_seen": datetime.now(ZoneInfo(ASSISTANT_TIMEZONE)).isoformat(),
                "conversation_ids": []
            }
        client_profile = clients[normalized_name]
        client_profile["last_seen"] = datetime.now(ZoneInfo(ASSISTANT_TIMEZONE)).isoformat()
        if session_id not in client_profile["conversation_ids"]:
            client_profile["conversation_ids"].append(session_id)
    
    message = {
        "role": role,
        "content": content,
        "catalog_images": catalog_images or [],
        "timestamp": datetime.now(ZoneInfo(ASSISTANT_TIMEZONE)).isoformat()
    }
    if search_results:
        message["search_results"] = search_results
    conv["messages"].append(message)
    conv["updated_at"] = datetime.now(ZoneInfo(ASSISTANT_TIMEZONE)).isoformat()
    
    data["clients"] = clients
    await save_conversations({"clients": clients, "conversations": conversations})


async def get_or_create_client(client_name: str) -> Dict:
    """Get or create a client profile by name."""
    data = await load_conversations()
    clients = data.get("clients", {})
    normalized_name = client_name.lower().strip()
    
    if normalized_name not in clients:
        clients[normalized_name] = {
            "name": client_name,
            "first_seen": datetime.now(ZoneInfo(ASSISTANT_TIMEZONE)).isoformat(),
            "last_seen": datetime.now(ZoneInfo(ASSISTANT_TIMEZONE)).isoformat(),
            "conversation_ids": []
        }
        data["clients"] = clients
        await save_conversations({"clients": clients, "conversations": data.get("conversations", [])})
    
    return clients[normalized_name]


async def get_client_conversations(client_name: str) -> List[Dict]:
    """Get all conversations for a specific client."""
    data = await load_conversations()
    clients = data.get("clients", {})
    normalized_name = client_name.lower().strip()
    
    if normalized_name not in clients:
        return []
    
    conversation_ids = clients[normalized_name].get("conversation_ids", [])
    conversations = data.get("conversations", [])
    return [c for c in conversations if c["id"] in conversation_ids]


def load_behavior_config() -> Dict[str, str]:
    """Load assistant behavior and customer-care instructions from JSON."""
    try:
        with BEHAVIOR_CONFIG_PATH.open("r", encoding="utf-8") as config_file:
            config = json.load(config_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"No se pudo cargar la configuración de comportamiento: {BEHAVIOR_CONFIG_PATH}"
        ) from exc

    required_keys = {
        "query_extraction_instructions",
        "query_enrichment_instructions",
        "name_extraction_instructions",
        "customer_care_instructions",
        "no_book_query_response",
        "no_results_response_template",
        "search_error_response",
        "available_with_price_template",
        "available_without_price_template",
        "availability_unknown_template",
        "catalog_notice_template",
        "greeting_morning",
        "greeting_afternoon",
        "greeting_evening",
        "greeting_morning_no_name",
        "greeting_afternoon_no_name",
        "greeting_evening_no_name",
        "purchase_and_shipping_instructions",
        "payment_intent_instructions",
        "purchase_and_shipping_response",
    }
    missing_keys = required_keys.difference(config)
    if missing_keys:
        raise RuntimeError(
            "Faltan claves en la configuración de comportamiento: "
            + ", ".join(sorted(missing_keys))
        )
    return config


def get_greeting(behavior: Dict[str, str], name: Optional[str] = None) -> str:
    """Return the configured greeting for the assistant's local time."""
    hour = datetime.now(ZoneInfo(ASSISTANT_TIMEZONE)).hour
    if 5 <= hour < 12:
        template = behavior["greeting_morning"] if name else behavior["greeting_morning_no_name"]
    elif 12 <= hour < 19:
        template = behavior["greeting_afternoon"] if name else behavior["greeting_afternoon_no_name"]
    else:
        template = behavior["greeting_evening"] if name else behavior["greeting_evening_no_name"]
    
    if name:
        return template.format(name=name)
    return template


CATALOG_DIR = Path(__file__).resolve().with_name("busquedas") / "catalogos"
CATALOG_DIR.mkdir(parents=True, exist_ok=True)


def generate_catalog_images(results: List[Dict], client_name: str = "", query: str = "") -> List[str]:
    """Reuse the existing Facebook promotional card generator for book covers.
    
    Creates personalized catalog folders named with client name and book title
    for easy WhatsApp sharing.
    """
    # Create personalized catalog folder name
    safe_client = re.sub(r'[^a-zA-Z0-9_\-]', '_', client_name.strip()) if client_name else "cliente"
    safe_query = re.sub(r'[^a-zA-Z0-9_\-]', '_', query.strip()[:30]) if query else "busqueda"
    catalog_folder = f"{safe_client}_{safe_query}_{uuid4().hex[:8]}"
    output_dir = CATALOG_DIR / catalog_folder
    output_dir.mkdir(parents=True, exist_ok=True)
    
    generator = FacebookAdGenerator(output_dir=str(output_dir))
    image_urls = []

    for index, result in enumerate(results[:3], start=1):
        cover_url = result.get("image_url")
        if not cover_url or not result.get("availability"):
            continue

        image_path = generator.generate_ad(
            {
                "url_imagen": cover_url,
                "nombre": result.get("title", "Libro disponible"),
                "autor": result.get("author", ""),
                "precio_con_envio": result.get("price", "Consultar precio"),
                "numero": index,
            },
            scheme_index=index - 1,
        )
        if image_path:
            filename = Path(image_path).name
            image_urls.append(f"/catalogos/{catalog_folder}/{filename}")

    return image_urls


def extract_query_fallback(message: str) -> Optional[str]:
    """Recover a clear book request when the model returns ``NO_BOOK_QUERY``.

    This route deliberately recognizes conjugations such as ``estoy buscando``.
    It must not depend exclusively on the LLM: a missed extraction should still
    start the catalog search instead of being treated as a conversational reply.
    """
    clean_message = " ".join(message.strip().split())
    # Customer messages are often forwarded as "Nombre dice: ...".  The
    # sender identifier is useful for the greeting, never for the catalog
    # query.
    clean_message = re.sub(
        r"^\s*(?:de\s*:\s*)?(?:[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+\s+){0,2}"
        r"(?:dice|dijo)\s*:\s*",
        "",
        clean_message,
        flags=re.IGNORECASE,
    )
    explicit_request = re.search(
        r"\b(busco|buscas|buscando|buscar|quiero|quisiera|necesito|"
        r"tienen|tiene|tienes|tendrá|tendrán|tendrás|tendras|hay|existe)\b",
        clean_message,
        flags=re.IGNORECASE,
    )
    if not explicit_request:
        bare_query = clean_message.strip(" ,.-¿¡?")
        words = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+", bare_query)
        non_book_phrases = (
            "gracias", "muchas gracias", "buenos días", "buenas tardes",
            "buenas noches", "de acuerdo", "está bien", "esta bien",
        )
        if (
            2 <= len(words) <= 16
            and len(bare_query) >= 3
            and not any(phrase in bare_query.lower() for phrase in non_book_phrases)
        ):
            return bare_query
        return None

    topic_match = re.search(
        r"\b(?:qué|que)\s+tienen\s+de\s+(.+?)(?:[?.!]|$)",
        clean_message,
        flags=re.IGNORECASE,
    )
    if topic_match:
        topic = topic_match.group(1).strip(" ,.-¿¡")
        return topic if len(topic) >= 3 else None

    availability_match = re.search(
        r"\b(?:tendrás|tendras|tendrá|tendrán|tienen|tiene|tienes|hay|existe)\s+"
        r"(?:(?:algo|libros?)\s+)?(?:de\s+)?(.+?)(?:[?.!]|$)",
        clean_message,
        flags=re.IGNORECASE,
    )
    if availability_match:
        query = availability_match.group(1).strip(" ,.-¿¡")
        return query if len(query) >= 3 else None

    query = re.sub(
        r"^\s*(?:hola[,! ]*)?"
        r"(?:(?:estoy|ando)\s+)?(?:busco|buscas|buscando|buscar|quiero|quisiera|necesito)\s+"
        r"(?:(?:algo|un libro|el libro|la novela)\s+)?(?:de\s+)?",
        "",
        clean_message,
        flags=re.IGNORECASE,
    )
    query = re.split(r"[?.!]", query, maxsplit=1)[0]
    query = re.sub(
        r"\b(?:lo|la)\s+(?:tienen|tendrá|tendrán|tendrás|tendras)\b.*$|"
        r"\b(?:por favor|gracias)\b.*$",
        "",
        query,
        flags=re.IGNORECASE,
    )
    query = query.strip(" ,.-¿¡")
    if len(query) >= 3 and any(char.isalpha() for char in query):
        return query

    # A customer can send only a title or author (for example, "Sebastian
    # Bach"), which still belongs on the catalog-search route.  Keep polite
    # chatter out of this fallback so normal conversation remains intact.
    bare_query = clean_message.strip(" ,.-¿¡?")
    words = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+", bare_query)
    non_book_phrases = (
        "gracias", "muchas gracias", "buenos días", "buenas tardes",
        "buenas noches", "de acuerdo", "está bien", "esta bien",
    )
    if (
        2 <= len(words) <= 16
        and len(bare_query) >= 3
        and not any(phrase in bare_query.lower() for phrase in non_book_phrases)
    ):
        return bare_query
    return None


def extract_sender_name_fallback(message: str) -> str:
    """Extract a sender name from common customer-message prefixes."""
    match = re.match(
        r"^\s*(?:de\s*:\s*)?([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)(?:\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+){0,2}\s+(?:dice|dijo)\s*:",
        message,
        flags=re.IGNORECASE,
    )
    return match.group(1).capitalize() if match else ""


def is_delivery_question(message: str) -> bool:
    """Identify questions that should be answered from the active conversation."""
    normalized = message.lower()
    return any(term in normalized for term in (
        "tiempo de entrega", "tiempos de entrega", "tiempo de llegada", "tiempos de llegada",
        "cuánto tarda", "cuanto tarda",
        "cuándo llega", "cuando llega", "plazo de envío", "plazo de envio",
        "días de envío", "dias de envio",
    ))


def latest_delivery_answer(messages: List[Dict]) -> Optional[str]:
    """Return the latest delivery estimate previously given to the customer."""
    patterns = (
        r"entrega en\s+(?:env[ií]o:\s*)?([^.!\n]+)",
        r"(?:estimado|plazo) de env[ií]o(?:\s+de)?\s+([^.!\n]+)",
        r"(?:env[ií]o|disponible para env[ií]o)\s+en\s+(?:un\s+)?plazo\s+de\s+([^.!\n]+)",
    )
    for item in reversed(messages):
        if item.get("role") != "assistant":
            continue
        content = item.get("content", "")
        for pattern in patterns:
            match = re.search(pattern, content, flags=re.IGNORECASE)
            if match:
                return f"El tiempo estimado de entrega es de {match.group(1).strip()}."
        if re.search(r"env[ií]o\s+r[aá]pido", content, flags=re.IGNORECASE):
            return "El libro consultado cuenta con envío rápido."
    return None


def prepare_response_results(results: List[Dict]) -> List[Dict]:
    """Keep only verified fields needed in the customer response and conversation memory."""
    return [
        {
            "title": result.get("title", "No disponible"),
            "author": result.get("author", "No disponible"),
            "price": result.get("price", "No disponible"),
            "currency": result.get("currency", "MXN"),
            "availability": result.get("availability", False),
            "editorial": result.get("editorial", "No disponible"),
            "delivery_estimate": result.get("delivery_estimate", "No disponible"),
            "delivery_dates": result.get("delivery_dates", []),
            "condition": result.get("condition", "No disponible"),
            "source": result.get("source", "buscalibre"),
        }
        for result in results[:3]
    ]


def latest_search_results(messages: List[Dict]) -> List[Dict]:
    """Return the structured results from the most recent completed search."""
    for message in reversed(messages):
        results = message.get("search_results")
        if message.get("role") == "assistant" and isinstance(results, list) and results:
            return results
    return []


def format_result_options(results: List[Dict]) -> str:
    """Render every result so the customer can refer to an option by position."""
    options = []
    for index, result in enumerate(results, start=1):
        details = [result.get("title", "Libro disponible")]
        author = result.get("author", "No disponible")
        price = result.get("price", "No disponible")
        editorial = result.get("editorial", "No disponible")
        delivery = result.get("delivery_estimate", "No disponible")
        if author != "No disponible":
            details.append(f"de {author}")
        if price != "No disponible":
            details.append(f"por {price}")
        if editorial != "No disponible":
            details.append(f"editorial {editorial}")
        if delivery != "No disponible":
            details.append(f"entrega: {delivery}")
        options.append(f"{index}) " + ", ".join(details) + ".")
    return " ".join(options)


def selected_result_from_message(message: str, results: List[Dict]) -> Optional[Dict]:
    """Resolve references such as 'el segundo' against the latest saved search."""
    normalized = message.lower()
    ordinals = {
        0: (r"\b(?:primero|primera|1(?:er|ra)?|opci[oó]n\s*1)\b",),
        1: (r"\b(?:segundo|segunda|2(?:do|da)?|opci[oó]n\s*2)\b",),
        2: (r"\b(?:tercero|tercera|3(?:er|ra)?|opci[oó]n\s*3)\b",),
    }
    for index, patterns in ordinals.items():
        if index < len(results) and any(re.search(pattern, normalized) for pattern in patterns):
            return results[index]
    return None


def purchase_selected_result_response(result: Dict, purchase_instructions: str) -> str:
    """Confirm the selected option before explaining the purchase process."""
    details = [result.get("title", "el libro seleccionado")]
    author = result.get("author", "No disponible")
    price = result.get("price", "No disponible")
    delivery = result.get("delivery_estimate", "No disponible")
    if author != "No disponible":
        details.append(f"de {author}")
    if price != "No disponible":
        details.append(f"por {price}")
    if delivery != "No disponible":
        details.append(f"con entrega estimada: {delivery}")
    return f"Perfecto, seleccionó {', '.join(details)}. {purchase_instructions}"


class Agent:
    def __init__(self, llm: LLMProvider, behavior: Optional[Dict[str, str]] = None):
        self.llm = llm
        self.behavior = behavior or load_behavior_config()

    async def extract_sender_name(self, message: str) -> str:
        """Extract sender's first name, preferring an explicit message prefix."""
        explicit_name = extract_sender_name_fallback(message)
        if explicit_name:
            return explicit_name
        try:
            system_prompt = self.behavior["name_extraction_instructions"]
            response = await self.llm.generate(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message},
                ],
                temperature=0.0,
                max_tokens=30,
            )
            name = response.strip().strip('"\\').split()[0] if response.strip() else ""
            if name.upper() == "NO_NAME":
                return ""
            return name
        except Exception:
            logger.exception("Error extracting sender name")
            return ""

    async def is_payment_or_purchase_question(self, message: str) -> bool:
        """Route purchase, payment, and shipping-process questions through LM Studio."""
        try:
            response = await asyncio.wait_for(
                self.llm.generate(
                    [
                        {"role": "system", "content": self.behavior["payment_intent_instructions"]},
                        {"role": "user", "content": message},
                    ],
                    temperature=0.0,
                    max_tokens=12,
                ),
                timeout=20.0,
            )
            intent = response.strip().upper().split(maxsplit=1)[0].strip(".,:;!¡") if response.strip() else ""
            if intent == "PAYMENT_INFO":
                return True
        except asyncio.TimeoutError:
            logger.warning("LM Studio timeout classifying payment intent; using fallback")
        except Exception as exc:
            logger.warning("Could not classify payment intent with LM Studio: %s", exc)

        # Keep purchase instructions available even when the classifier misses an obvious intent.
        return bool(re.search(
            r"\b(pag[ao]|pago|pagar|pagos|comprar|compra|pedido|pedir|dep[oó]sito|"
            r"comprobante|transferencia|env[ií]o|enviar|datos de env[ií]o)\b",
            message,
            flags=re.IGNORECASE,
        ))

    def purchase_and_shipping_response(self) -> str:
        """Return the approved, gradual buying explanation without bank details."""
        return self.behavior["purchase_and_shipping_response"]

    def _queries_are_similar(self, query1: str, query2: str) -> bool:
        """Check if two queries refer to the same book."""
        q1 = query1.lower().strip()
        q2 = query2.lower().strip()
        if q1 == q2:
            return True
        # Check if one is contained in the other (e.g., "harry potter 2" vs "harry potter y la cámara secreta")
        if q1 in q2 or q2 in q1:
            return True
        # Check for common words (title words)
        words1 = set(w for w in q1.split() if len(w) > 3)
        words2 = set(w for w in q2.split() if len(w) > 3)
        if words1 and words2:
            overlap = len(words1 & words2) / min(len(words1), len(words2))
            return overlap > 0.5
        return False

    async def extract_book_query(self, message: str, conversation_context: str = "") -> Optional[str]:
        # Prefer a deterministic extraction for explicit requests.  This keeps a
        # clear message such as "Estoy buscando ... ¿lo tendrás?" on the search
        # route even when the local model is unavailable or misclassifies it.
        fallback_query = extract_query_fallback(message)
        if fallback_query:
            logger.info("Consulta explícita detectada: %s", fallback_query)
            return fallback_query

        try:
            system_prompt = self.behavior["query_extraction_instructions"]
            response = await asyncio.wait_for(
                self.llm.generate(
                    [
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": (
                                f"Historial de la conversación:\n{conversation_context}\n\n"
                                f"Mensaje nuevo:\n{message}"
                                if conversation_context else message
                            ),
                        },
                    ],
                    temperature=0.1,
                    max_tokens=80,
                ),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            logger.warning("LLM timeout extracting book query, using fallback")
            return None
        except Exception as e:
            logger.exception("Error extracting book query: %s", e)
            return None

        query = " ".join(response.strip().strip("\"\\'").split())
        if query and query.upper() != "NO_BOOK_QUERY":
            return query

        return None
    async def enrich_book_query(self, query: str, conversation_context: str = "") -> str:
        """Add the author only when LM Studio identifies a specific book title."""
        try:
            response = await asyncio.wait_for(
                self.llm.generate(
                    [
                        {
                            "role": "system",
                            "content": self.behavior["query_enrichment_instructions"],
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Historial de la conversación:\n{conversation_context}\n\n"
                                f"Consulta actual:\n{query}"
                                if conversation_context else query
                            ),
                        },
                    ],
                    temperature=0.0,
                    max_tokens=80,
                ),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            logger.warning("LLM timeout enriching book query, using original")
            return query
        except Exception as e:
            logger.exception("No se pudo enriquecer la consulta: %s", e)
            return query
        enriched_query = " ".join(response.strip().strip("\"\\'").split())
        if not enriched_query or enriched_query.upper() in {"NO_ENRICHMENT", "NO_BOOK_QUERY"}:
            return query
        return enriched_query
    async def generate_response(self, query: str, results: List[Dict], name: str = "", conversation_context: str = "") -> str:
        if not results:
            return self.behavior["no_results_response_template"].format(query=query, name=name)

        response_results = prepare_response_results(results)
        results_text = json.dumps(response_results, ensure_ascii=False, indent=2)
        system_prompt = (
            f"{self.behavior['customer_care_instructions']}\n\n"
            "Responde SOLAMENTE con una frase breve de introducción. No enumeres ni repitas "
            "los datos de los libros: la aplicación los añade después de tu respuesta.\n\n"
            f"Resultados de búsqueda:\n{results_text}"
        )
        if conversation_context:
            system_prompt += (
                "\n\nHistorial de esta conversación (úsalo para mantener el contexto, "
                "pero no inventes datos):\n"
                f"{conversation_context}"
            )
        try:
            response = await asyncio.wait_for(
                self.llm.generate(
                    [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Cliente busca: {query}"},
                    ],
                    temperature=0.3,
                    max_tokens=700,
                ),
                timeout=45.0,
            )
        except (asyncio.TimeoutError, Exception) as exc:
            logger.warning("No se pudo generar respuesta con LLM: %s", exc)
            response = ""
        introduction = " ".join(response.strip().split())
        if not introduction:
            introduction = "Encontré estas opciones disponibles para su consulta:"
        return f"{introduction} {format_result_options(response_results)}"

    async def generate_context_response(self, message: str, conversation_context: str) -> str:
        """Answer a non-search follow-up using only the saved conversation."""
        prompt = (
            "Eres un asistente de atención al cliente de una librería. Responde la pregunta "
            "del cliente usando ÚNICAMENTE el historial proporcionado. No busques libros, "
            "no inventes datos y no agregues saludo. Si el historial no contiene la respuesta, "
            "indícalo brevemente y ofrezca consultar un libro específico.\n\n"
            f"Historial:\n{conversation_context}\n\nPregunta nueva:\n{message}"
        )
        try:
            response = await asyncio.wait_for(
                self.llm.generate(
                    [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": message},
                    ],
                    temperature=0.1,
                    max_tokens=180,
                ),
                timeout=30.0,
            )
        except (asyncio.TimeoutError, Exception) as exc:
            logger.warning("No se pudo responder el seguimiento: %s", exc)
            return "No tengo esa información registrada. Si gusta, puedo consultar el libro de nuevo."
        return " ".join(response.strip().split()) or "No tengo esa información registrada."

    async def handle_message(self, message: str, session_id: Optional[str] = None) -> Tuple[str, List[str], str, List[Dict]]:
        # Extract sender name from message
        sender_name = await self.extract_sender_name(message)
        
        # If we have a session_id, check for persisted name
        persisted_name = ""
        conversation_context = ""
        previous_messages: List[Dict] = []
        previous_search_results: List[Dict] = []
        last_book_query = ""
        last_book_price = ""
        if session_id:
            data = await load_conversations()
            conversations = data.get("conversations", [])
            conv = next((c for c in conversations if c["id"] == session_id), None)
            if conv and conv.get("sender_name"):
                persisted_name = conv["sender_name"]
            # Also get client_name from conversation if available
            if conv and conv.get("client_name"):
                persisted_name = persisted_name or conv["client_name"]
            if conv:
                previous_messages = conv.get("messages", [])[:-1]
                conversation_context = "\n".join(
                    f"{item.get('role', 'user')}: {item.get('content', '')}"
                    for item in previous_messages
                )
                previous_search_results = latest_search_results(previous_messages)
                if previous_search_results:
                    conversation_context += (
                        "\n\nResultados estructurados de la última búsqueda:\n"
                        + json.dumps(previous_search_results, ensure_ascii=False)
                    )
                # Buscar la última consulta de libro y precio en el historial
                for item in reversed(previous_messages):
                    if item.get("role") == "user":
                        # Verificar si es una consulta de libro
                        extracted = await self.extract_book_query(item.get("content", ""), "")
                        if extracted:
                            last_book_query = extracted
                            break
                    elif item.get("role") == "assistant":
                        # Buscar precio en la respuesta del asistente
                        content = item.get("content", "")
                        price_match = re.search(r'\$?\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)', content)
                        if price_match:
                            last_book_price = price_match.group(0)
                            break
        
        # Use persisted name if available, otherwise use extracted name
        name = persisted_name or sender_name

        # Purchase routes precede book extraction: they never trigger another scraper search.
        if await self.is_payment_or_purchase_question(message):
            selected_result = selected_result_from_message(message, previous_search_results)
            if selected_result:
                return (
                    purchase_selected_result_response(
                        selected_result,
                        self.purchase_and_shipping_response(),
                    ),
                    [],
                    name,
                    [],
                )
            return self.purchase_and_shipping_response(), [], name, []

        if is_delivery_question(message):
            delivery_answer = latest_delivery_answer(previous_messages if session_id else [])
            if delivery_answer:
                return delivery_answer, [], name, []
            return (
                "No tengo un plazo de entrega registrado para esta conversación. "
                "Si gusta, puedo consultar de nuevo el libro.",
                [],
                name,
                [],
            )
        
        query = await self.extract_book_query(message, conversation_context)
        
        # SMART FOLLOW-UP: Si el cliente pregunta por el mismo libro que buscó antes
        # y ya tenemos el precio, usar template de seguimiento
        if query and last_book_query and last_book_price:
            # Verificar si la consulta actual es similar a la anterior
            if self._queries_are_similar(query, last_book_query):
                followup_msg = self.behavior.get("follow_up_greeting_template", "").format(
                    name=name or "cliente",
                    last_query=last_book_query,
                    last_price=last_book_price
                )
                if followup_msg:
                    return followup_msg, [], name, []
        
        if not query:
            if conversation_context:
                return await self.generate_context_response(message, conversation_context), [], name, []
            return self.behavior["no_book_query_response"], [], name, []
        
        search_query = await self.enrich_book_query(query, conversation_context)
        if search_query != query:
            logger.info("Consulta enriquecida para búsqueda: %s", search_query)
        
        pricing_config = await get_pricing_config()
        ganancia_envio = pricing_config["ganancia_envio"]
        
        # Persist each BuscaLibre product as soon as its detail page has been
        # read. This avoids waiting for the rest of the Selenium batch (and
        # the parallel Mercado Libre request) before the catalog is updated.
        def save_buscalibre_result(book: Dict) -> None:
            if not getattr(catalog_writer, "enabled", False):
                return
            book_with_source = {**book, "source": "buscalibre"}
            saved = persist_catalog_books([book_with_source], search_query)
            logger.info(
                "Saved BuscaLibre product immediately after detail extraction: %s (%d record).",
                book_with_source.get("title", "Libro sin título"),
                saved,
            )

        # Buscar en paralelo en BuscaLibre y MercadoLibre
        buscalibre_task = search_buscalibre(
            search_query,
            max_results=3,
            ganancia_envio=ganancia_envio,
            on_result=save_buscalibre_result,
        )
        debugger_address = os.getenv("MELI_CHROME_DEBUGGER_ADDRESS")
        mercadolibre_task = search_mercadolibre(search_query, max_results=3, ganancia_envio=ganancia_envio, detailed=True, debugger_address=debugger_address)
        
        buscalibre_results, mercadolibre_results = await asyncio.gather(
            buscalibre_task, mercadolibre_task, return_exceptions=True
        )
        
        # Procesar resultados de BuscaLibre
        results = []
        if isinstance(buscalibre_results, dict) and not buscalibre_results.get("error"):
            bl_results = buscalibre_results.get("results", [])
            for r in bl_results:
                r["source"] = "buscalibre"
            results.extend(bl_results)
        elif isinstance(buscalibre_results, Exception) or (isinstance(buscalibre_results, dict) and buscalibre_results.get("error")):
            logger.warning("Buscalibre search failed: %s", buscalibre_results.get("error") if isinstance(buscalibre_results, dict) else buscalibre_results)
        
        # Procesar resultados de MercadoLibre
        if isinstance(mercadolibre_results, dict) and not mercadolibre_results.get("error"):
            ml_results = mercadolibre_results.get("results", [])
            for r in ml_results:
                r["source"] = "mercadolibre"
            results.extend(ml_results)
        elif isinstance(mercadolibre_results, Exception) or (isinstance(mercadolibre_results, dict) and mercadolibre_results.get("error")):
            logger.warning("MercadoLibre search failed: %s", mercadolibre_results.get("error") if isinstance(mercadolibre_results, dict) else mercadolibre_results)
        
        if not results:
            logger.warning("Both searches returned no results")
            return self.behavior["no_results_response_template"].format(query=query, name=name), [], name, []

        # Store every real result in the shared Firebase catalog.  Persistence
        # is deliberately non-blocking for the customer response: unavailable
        # credentials or a transient Firestore failure must not lose a search.
        saved_books = await asyncio.to_thread(persist_catalog_books, results, search_query)
        if saved_books:
            logger.info("Saved %d catalog books to Firestore.", saved_books)
        else:
            logger.warning(
                "Firestore did not save any of the %d results for query '%s'. "
                "Check logs/firebase_catalog.log for the cause.",
                len(results),
                search_query,
            )
        
        # Ordenar por precio (los que tienen precio primero, luego por precio ascendente)
        results.sort(key=lambda x: (x.get("price") == "No disponible", float(re.sub(r'[^0-9.]', '', str(x.get("price", "999999")))) if x.get("price") != "No disponible" else 999999))
        
        response_results = prepare_response_results(results)
        response = await self.generate_response(query, response_results, name, conversation_context)
        catalog_images = await asyncio.to_thread(generate_catalog_images, results[:3], name, query)
        if catalog_images:
            response = (
                f"{response} "
                f"{self.behavior['catalog_notice_template'].format(count=len(catalog_images))}"
            )
        return response, catalog_images, name, response_results


llm_provider = get_llm_provider()
agent = Agent(llm_provider)

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure Chrome debugging is available
    auto_start = os.getenv("AUTO_START_CHROME_DEBUG", "false").lower() == "true"
    if auto_start:
        port = int(os.getenv("CHROME_DEBUG_PORT", "9222"))
        user_data_dir = os.getenv("CHROME_USER_DATA_DIR")
        timeout = float(os.getenv("CHROME_START_TIMEOUT", "15.0"))
        logger.info("Starting Chrome debugging auto-management...")
        try:
            await ensure_chrome_debugging(port=port, user_data_dir=user_data_dir, timeout=timeout)
            logger.info("Chrome debugging auto-management started successfully")
        except Exception as e:
            logger.error(f"Failed to start Chrome debugging: {e}")
            # Don't fail startup, just log error - MercadoLibre searches will fail gracefully
    
    yield
    
    # Shutdown: close httpx client and Chrome debugging
    if hasattr(llm_provider, 'close'):
        await llm_provider.close()
    
    # Terminate Chrome debugging if we launched it
    await terminate_chrome_debugging()
    logger.info("Shutdown complete")

app = FastAPI(
    title="Book Search Agent",
    description="Procesa preguntas en español, busca libros en Buscalibre y responde naturalmente con LM Studio.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2_000, description="Pregunta del cliente en lenguaje natural")
    session_id: Optional[str] = Field(None, description="ID de sesión para persistencia de conversación")


class MessageResponse(BaseModel):
    response: str
    catalog_images: List[str] = Field(default_factory=list)
    session_id: str


class PricingConfig(BaseModel):
    ganancia_envio: float = Field(..., ge=0, le=10_000, description="Ganancia fija por libro en MXN")


class ConversationSummary(BaseModel):
    id: str
    created_at: str
    updated_at: Optional[str] = None
    preview: str
    client_name: Optional[str] = None


class Conversation(BaseModel):
    id: str
    created_at: str
    client_name: Optional[str] = None
    messages: List[Dict]


@app.post("/message", response_model=MessageResponse)
async def receive_message(request: MessageRequest) -> MessageResponse:
    try:
        session_id = request.session_id or str(uuid4())
        # Persist the incoming request before any external work can fail.
        await add_message_to_conversation(
            session_id,
            "user",
            request.message,
            client_name=extract_sender_name_fallback(request.message),
        )
        
        # Handle message with session for name persistence
        response, catalog_images, sender_name, search_results = await agent.handle_message(
            request.message,
            session_id,
        )
        
        # Get greeting with name
        greeting = get_greeting(agent.behavior, sender_name)
        response_with_greeting = f"{greeting} {response}"
        
        # Save name to conversation if we have a new one
        if sender_name:
            data = await load_conversations()
            conversations = data.get("conversations", [])
            conv = next((c for c in conversations if c["id"] == session_id), None)
            if conv and not conv.get("sender_name"):
                conv["sender_name"] = sender_name
                data["conversations"] = conversations
                await save_conversations(data)
        
        # Link the conversation to its client when saving the answer.
        await add_message_to_conversation(
            session_id,
            "assistant",
            response_with_greeting,
            catalog_images,
            client_name=sender_name,
            search_results=search_results,
        )
        
        return MessageResponse(
            response=response_with_greeting,
            catalog_images=catalog_images,
            session_id=session_id,
        )
    except Exception:
        logger.exception("Error processing message")
        raise HTTPException(500, "Error interno del servidor")


@app.get("/conversations", response_model=List[ConversationSummary])
async def list_conversations() -> List[ConversationSummary]:
    data = await load_conversations()
    conversations = data.get("conversations", [])
    summaries = []
    for conv in sorted(conversations, key=lambda x: x.get("updated_at", x["created_at"]), reverse=True):
        preview = ""
        if conv["messages"]:
            first_user_msg = next((m for m in conv["messages"] if m["role"] == "user"), None)
            if first_user_msg:
                preview = first_user_msg["content"][:80]
                if len(first_user_msg["content"]) > 80:
                    preview += "..."
        summaries.append(ConversationSummary(
            id=conv["id"],
            created_at=conv["created_at"],
            updated_at=conv.get("updated_at", conv["created_at"]),
            preview=preview,
            client_name=conv.get("client_name") or conv.get("sender_name"),
        ))
    return summaries


@app.get("/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str) -> Conversation:
    data = await load_conversations()
    conversations = data.get("conversations", [])
    conv = next((c for c in conversations if c["id"] == conversation_id), None)
    if not conv:
        raise HTTPException(404, "Conversación no encontrada")
    return Conversation(**conv)


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str) -> Dict[str, str]:
    data = await load_conversations()
    conversations = data.get("conversations", [])
    conversations = [c for c in conversations if c["id"] != conversation_id]
    for profile in data.get("clients", {}).values():
        profile["conversation_ids"] = [
            item for item in profile.get("conversation_ids", []) if item != conversation_id
        ]
    data["conversations"] = conversations
    await save_conversations(data)
    return {"status": "deleted"}


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/pricing", response_model=PricingConfig)
async def get_pricing() -> PricingConfig:
    return PricingConfig(**await get_pricing_config())


@app.put("/pricing", response_model=PricingConfig)
async def update_pricing(config: PricingConfig) -> PricingConfig:
    return PricingConfig(**await save_pricing_config(config.ganancia_envio))


class BehaviorConfig(BaseModel):
    behavior: Dict[str, str]


@app.get("/behavior", response_model=BehaviorConfig)
async def get_behavior() -> BehaviorConfig:
    return BehaviorConfig(behavior=agent.behavior)


@app.put("/behavior", response_model=BehaviorConfig)
async def update_behavior(config: BehaviorConfig) -> BehaviorConfig:
    # Validate required keys
    required_keys = {
        "query_extraction_instructions",
        "query_enrichment_instructions",
        "name_extraction_instructions",
        "customer_care_instructions",
        "no_book_query_response",
        "no_results_response_template",
        "search_error_response",
        "available_with_price_template",
        "available_without_price_template",
        "availability_unknown_template",
        "catalog_notice_template",
        "greeting_morning",
        "greeting_afternoon",
        "greeting_evening",
        "greeting_morning_no_name",
        "greeting_afternoon_no_name",
        "greeting_evening_no_name",
        "purchase_and_shipping_instructions",
        "payment_intent_instructions",
        "purchase_and_shipping_response",
        "follow_up_greeting_template",
        "smart_followup_instructions",
    }
    missing_keys = required_keys.difference(config.behavior)
    if missing_keys:
        raise HTTPException(400, f"Faltan claves requeridas: {', '.join(sorted(missing_keys))}")
    
    # Save to file
    temporary_file = BEHAVIOR_CONFIG_PATH.with_suffix(".json.tmp")
    with temporary_file.open("w", encoding="utf-8") as f:
        json.dump(config.behavior, f, ensure_ascii=False, indent=2)
    temporary_file.replace(BEHAVIOR_CONFIG_PATH)
    
    # Reload agent behavior
    agent.behavior = config.behavior
    
    return BehaviorConfig(behavior=agent.behavior)


class CatalogCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        if request.url.path.startswith("/catalogos/"):
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
            response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "*"
        return response

app.add_middleware(CatalogCORSMiddleware)

app.mount("/catalogos", StaticFiles(directory=CATALOG_DIR), name="catalogos")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
