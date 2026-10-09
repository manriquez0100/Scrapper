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
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

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

# Lock for thread-safe file operations
_conversations_lock = asyncio.Lock()


async def load_conversations() -> Dict:
    """Load conversations from JSON file."""
    async with _conversations_lock:
        try:
            with CONVERSATIONS_FILE.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {"conversations": []}


async def save_conversations(data: Dict) -> None:
    """Save conversations to JSON file."""
    async with _conversations_lock:
        try:
            with CONVERSATIONS_FILE.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            logger.error("Failed to save conversations: %s", exc)


async def add_message_to_conversation(session_id: str, role: str, content: str, catalog_images: Optional[List[str]] = None) -> None:
    """Add a message to a conversation, creating it if needed."""
    data = await load_conversations()
    conversations = data.get("conversations", [])
    
    conv = next((c for c in conversations if c["id"] == session_id), None)
    if not conv:
        conv = {
            "id": session_id,
            "created_at": datetime.now(ZoneInfo(ASSISTANT_TIMEZONE)).isoformat(),
            "messages": []
        }
        conversations.append(conv)
    
    conv["messages"].append({
        "role": role,
        "content": content,
        "catalog_images": catalog_images or [],
        "timestamp": datetime.now(ZoneInfo(ASSISTANT_TIMEZONE)).isoformat()
    })
    
    await save_conversations({"conversations": conversations})


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
    }
    missing_keys = required_keys.difference(config)
    if missing_keys:
        raise RuntimeError(
            "Faltan claves en la configuración de comportamiento: "
            + ", ".join(sorted(missing_keys))
        )
    return config


def get_greeting(behavior: Dict[str, str]) -> str:
    """Return the configured greeting for the assistant's local time."""
    hour = datetime.now(ZoneInfo(ASSISTANT_TIMEZONE)).hour
    if 5 <= hour < 12:
        return behavior["greeting_morning"]
    if 12 <= hour < 19:
        return behavior["greeting_afternoon"]
    return behavior["greeting_evening"]


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


class Agent:
    def __init__(self, llm: LLMProvider, behavior: Optional[Dict[str, str]] = None):
        self.llm = llm
        self.behavior = behavior or load_behavior_config()

    async def extract_book_query(self, message: str) -> Optional[str]:
        system_prompt = self.behavior["query_extraction_instructions"]
        response = await self.llm.generate(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
            temperature=0.1,
            max_tokens=80,
        )

        query = " ".join(response.strip().strip('"\\\'').split())
        if query and query.upper() != "NO_BOOK_QUERY":
            return query

        fallback_query = extract_query_fallback(message)
        if fallback_query:
            logger.info("Usando consulta de respaldo: %s", fallback_query)
        return fallback_query

    async def enrich_book_query(self, query: str) -> str:
        """Add the author only when LM Studio identifies a specific book title."""
        try:
            response = await self.llm.generate(
                [
                    {
                        "role": "system",
                        "content": self.behavior["query_enrichment_instructions"],
                    },
                    {"role": "user", "content": query},
                ],
                temperature=0.0,
                max_tokens=80,
            )
        except Exception:
            logger.exception("No se pudo enriquecer la consulta; se usará la original")
            return query
        enriched_query = " ".join(response.strip().strip('"\\\'').split())
        if not enriched_query or enriched_query.upper() == "NO_ENRICHMENT":
            return query
        return enriched_query

    async def generate_response(self, query: str, results: List[Dict]) -> str:
        if not results:
            return self.behavior["no_results_response_template"].format(query=query)

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
        response = await self.llm.generate(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Cliente busca: {query}"},
            ],
            temperature=0.3,
            max_tokens=700,
        )
        if response.strip():
            return response.strip()

        first_result = response_results[0]
        title = first_result["title"]
        price = first_result["price"]
        if first_result["availability"] and price != "No disponible":
            return self.behavior["available_with_price_template"].format(
                title=title, price=price
            )
        if first_result["availability"]:
            return self.behavior["available_without_price_template"].format(title=title)
        return self.behavior["availability_unknown_template"].format(title=title)

    async def handle_message(self, message: str) -> Tuple[str, List[str]]:
        query = await self.extract_book_query(message)
        if not query:
            return self.behavior["no_book_query_response"], []

        search_query = await self.enrich_book_query(query)
        if search_query != query:
            logger.info("Consulta enriquecida para Buscalibre: %s", search_query)

        search_results = await search_buscalibre(search_query, max_results=5)
        if search_results.get("error"):
            logger.warning("Buscalibre search failed: %s", search_results["error"])
            return self.behavior["search_error_response"], []

        results = search_results.get("results", [])
        response = await self.generate_response(query, results)
        catalog_images = await asyncio.to_thread(generate_catalog_images, results)
        if catalog_images:
            response = (
                f"{response} "
                f"{self.behavior['catalog_notice_template'].format(count=len(catalog_images))}"
            )
            response = {response}
        return response, catalog_images


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


class ConversationSummary(BaseModel):
    id: str
    created_at: str
    preview: str


class Conversation(BaseModel):
    id: str
    created_at: str
    messages: List[Dict]


@app.post("/message", response_model=MessageResponse)
async def receive_message(request: MessageRequest) -> MessageResponse:
    try:
        session_id = request.session_id or str(uuid4())
        response, catalog_images = await agent.handle_message(request.message)
        response_with_greeting = f"{get_greeting(agent.behavior)} {response}"
        
        await add_message_to_conversation(session_id, "user", request.message)
        await add_message_to_conversation(session_id, "assistant", response_with_greeting, catalog_images)
        
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
    for conv in sorted(conversations, key=lambda x: x["created_at"], reverse=True):
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
            preview=preview
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
    await save_conversations({"conversations": conversations})
    return {"status": "deleted"}


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


app.mount("/catalogos", StaticFiles(directory=CATALOG_DIR), name="catalogos")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)