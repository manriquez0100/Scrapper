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
from buscalibreUpdating_11 import FacebookAdGenerator
from llm_provider import LLMProvider, get_llm_provider

load_dotenv()
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


async def add_message_to_conversation(session_id: str, role: str, content: str, catalog_images: Optional[List[str]] = None, client_name: Optional[str] = None) -> None:
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
    
    conv["messages"].append({
        "role": role,
        "content": content,
        "catalog_images": catalog_images or [],
        "timestamp": datetime.now(ZoneInfo(ASSISTANT_TIMEZONE)).isoformat()
    })
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


def generate_catalog_images(results: List[Dict]) -> List[str]:
    """Reuse the existing Facebook promotional card generator for book covers."""
    catalog_id = uuid4().hex
    output_dir = CATALOG_DIR / catalog_id
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
            image_urls.append(f"/catalogos/{catalog_id}/{filename}")

    return image_urls


def extract_query_fallback(message: str) -> Optional[str]:
    """Recover a clear book request when the model returns NO_BOOK_QUERY."""
    clean_message = " ".join(message.strip().split())
    if not re.search(
        r"\b(busco|buscar|quiero|quisiera|necesito|tienen|tendrá|tendrán|tendrás|tendras)\b",
        clean_message,
        flags=re.IGNORECASE,
    ):
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
        r"\b(?:tendrás|tendras|tendrá|tendrán|tienen)\s+"
        r"(?:(?:algo|libros?)\s+)?de\s+(.+?)(?:[?.!]|$)",
        clean_message,
        flags=re.IGNORECASE,
    )
    if availability_match:
        query = availability_match.group(1).strip(" ,.-¿¡")
        return query if len(query) >= 3 else None

    query = re.sub(
        r"^\s*(?:hola[,! ]*)?"
        r"(?:busco|buscar|quiero|quisiera|necesito)\s+"
        r"(?:(?:algo|un libro|el libro|la novela)\s+)?(?:de\s+)?",
        "",
        clean_message,
        flags=re.IGNORECASE,
    )
    query = re.split(r"[?.!]", query, maxsplit=1)[0]
    query = re.sub(
        r"\b(?:lo|la)\s+(?:tienen|tendrá|tendrán)\b.*$|\b(?:por favor|gracias)\b.*$",
        "",
        query,
        flags=re.IGNORECASE,
    )
    query = query.strip(" ,.-¿¡")
    return query if len(query) >= 3 and any(char.isalpha() for char in query) else None


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
            return intent == "PAYMENT_INFO"
        except asyncio.TimeoutError:
            logger.warning("LM Studio timeout classifying payment intent; using fallback")
        except Exception as exc:
            logger.warning("Could not classify payment intent with LM Studio: %s", exc)

        # The fallback only keeps service available if LM Studio is unavailable.
        return bool(re.search(
            r"\b(pag[ao]|pago|pagar|pagos|comprar|compra|pedido|pedir|dep[oó]sito|"
            r"comprobante|transferencia|env[ií]o|enviar|datos de env[ií]o)\b",
            message,
            flags=re.IGNORECASE,
        ))

    def purchase_and_shipping_response(self) -> str:
        """Return the approved, gradual buying explanation without bank details."""
        return self.behavior["purchase_and_shipping_response"]

    async def extract_book_query(self, message: str, conversation_context: str = "") -> Optional[str]:
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
            return extract_query_fallback(message)
        except Exception as e:
            logger.exception("Error extracting book query: %s", e)
            return extract_query_fallback(message)

        query = " ".join(response.strip().strip("\"\\'").split())
        if query and query.upper() != "NO_BOOK_QUERY":
            return query

        fallback_query = extract_query_fallback(message)
        if fallback_query:
            logger.info("Usando consulta de respaldo: %s", fallback_query)
        return fallback_query
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
        if not enriched_query or enriched_query.upper() == "NO_ENRICHMENT":
            return query
        return enriched_query
    async def generate_response(self, query: str, results: List[Dict], name: str = "", conversation_context: str = "") -> str:
        if not results:
            return self.behavior["no_results_response_template"].format(query=query, name=name)

        response_results = [
            {
                "title": result.get("title", "No disponible"),
                "author": result.get("author", "No disponible"),
                "price": result.get("price", "No disponible"),
                "currency": result.get("currency", "MXN"),
                "availability": result.get("availability", False),
                "editorial": result.get("editorial", "No disponible"),
                "delivery_estimate": result.get("delivery_estimate", "No disponible"),
                "delivery_dates": result.get("delivery_dates", []),
            }
            for result in results[:3]
        ]
        results_text = json.dumps(response_results, ensure_ascii=False, indent=2)
        system_prompt = (
            f"{self.behavior['customer_care_instructions']}\n\n"
            f"Resultados de Buscalibre:\n{results_text}"
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
        if response.strip():
            # Ensure single paragraph, no newlines
            return " ".join(response.strip().split())

        first_result = response_results[0]
        title = first_result["title"]
        price = first_result["price"]
        editorial = first_result["editorial"]
        delivery_estimate = first_result["delivery_estimate"]
        delivery = f"Entrega en {delivery_estimate}." if delivery_estimate and delivery_estimate != "No disponible" else ""
        
        if first_result["availability"] and price != "No disponible":
            return self.behavior["available_with_price_template"].format(title=title, price=price, editorial=editorial, delivery=delivery)
        if first_result["availability"]:
            return self.behavior["available_without_price_template"].format(title=title, editorial=editorial, delivery=delivery)
        return self.behavior["availability_unknown_template"].format(title=title, editorial=editorial)

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

    async def handle_message(self, message: str, session_id: Optional[str] = None) -> Tuple[str, List[str], str]:
        # Extract sender name from message
        sender_name = await self.extract_sender_name(message)
        
        # If we have a session_id, check for persisted name
        persisted_name = ""
        conversation_context = ""
        previous_messages: List[Dict] = []
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
        
        # Use persisted name if available, otherwise use extracted name
        name = persisted_name or sender_name

        # This branch must precede book extraction: payment questions are not searches.
        if await self.is_payment_or_purchase_question(message):
            return self.purchase_and_shipping_response(), [], name

        if is_delivery_question(message):
            delivery_answer = latest_delivery_answer(previous_messages if session_id else [])
            if delivery_answer:
                return delivery_answer, [], name
            return (
                "No tengo un plazo de entrega registrado para esta conversación. "
                "Si gusta, puedo consultar de nuevo el libro.",
                [],
                name,
            )
        
        query = await self.extract_book_query(message, conversation_context)
        if not query:
            if conversation_context:
                return await self.generate_context_response(message, conversation_context), [], name
            return self.behavior["no_book_query_response"], [], name
        
        search_query = await self.enrich_book_query(query, conversation_context)
        if search_query != query:
            logger.info("Consulta enriquecida para Buscalibre: %s", search_query)
        
        pricing_config = await get_pricing_config()
        search_results = await search_buscalibre(
            search_query,
            max_results=5,
            ganancia_envio=pricing_config["ganancia_envio"],
        )
        if search_results.get("error"):
            logger.warning("Buscalibre search failed: %s", search_results["error"])
            return self.behavior["search_error_response"].format(name=name), [], name
        
        results = search_results.get("results", [])
        response = await self.generate_response(query, results, name, conversation_context)
        catalog_images = await asyncio.to_thread(generate_catalog_images, results)
        if catalog_images:
            response = (
                f"{response} "
                f"{self.behavior['catalog_notice_template'].format(count=len(catalog_images))}"
            )
        return response, catalog_images, name


llm_provider = get_llm_provider()
agent = Agent(llm_provider)

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Shutdown: close httpx client
    if hasattr(llm_provider, 'close'):
        await llm_provider.close()

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
        response, catalog_images, sender_name = await agent.handle_message(request.message, session_id)
        
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
        await add_message_to_conversation(session_id, "assistant", response_with_greeting, catalog_images, client_name=sender_name)
        
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
