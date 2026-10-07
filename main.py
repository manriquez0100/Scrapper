"""FastAPI app that orchestrates LM Studio and Buscalibre book searches."""

import json
import logging
import os
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.staticfiles import StaticFiles

from buscalibre_tool import search_buscalibre
from buscalibreUpdating_11 import FacebookAdGenerator
from llm_provider import LLMProvider, get_llm_provider

load_dotenv()
logger = logging.getLogger(__name__)
BEHAVIOR_CONFIG_PATH = Path(
    os.getenv("ASSISTANT_BEHAVIOR_CONFIG", Path(__file__).with_name("behavior.json"))
)


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
        "customer_care_instructions",
        "no_book_query_response",
        "no_results_response_template",
        "search_error_response",
        "available_with_price_template",
        "available_without_price_template",
        "availability_unknown_template",
        "catalog_notice_template",
    }
    missing_keys = required_keys.difference(config)
    if missing_keys:
        raise RuntimeError(
            "Faltan claves en la configuración de comportamiento: "
            + ", ".join(sorted(missing_keys))
        )
    return config


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
        return None if query.upper() == "NO_BOOK_QUERY" else query or None

    async def generate_response(self, query: str, results: List[Dict]) -> str:
        if not results:
            return self.behavior["no_results_response_template"].format(query=query)

        # Evita enviar descripciones y URLs largas que retrasan innecesariamente a Gemma.
        response_results = [
            {
                "title": result.get("title", "No disponible"),
                "author": result.get("author", "No disponible"),
                "price": result.get("price", "No disponible"),
                "currency": result.get("currency", "MXN"),
                "availability": result.get("availability", False),
                "editorial": result.get("editorial", "No disponible"),
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

        # Algunos modelos generan solo reasoning_content. La consulta no debe fallar
        # cuando ocurre: los datos ya fueron obtenidos de Buscalibre.
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

        # search_buscalibre mueve Selenium a un hilo, para no bloquear FastAPI.
        search_results = await search_buscalibre(query, max_results=5)
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
            response = f"{response}\n\nCatálogo: " + " ".join(catalog_images)
        return response, catalog_images


llm_provider = get_llm_provider()
agent = Agent(llm_provider)

app = FastAPI(
    title="Book Search Agent",
    description="Procesa preguntas en español, busca libros en Buscalibre y responde naturalmente con LM Studio.",
    version="1.0.0",
)


class MessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2_000, description="Pregunta del cliente en lenguaje natural")


class MessageResponse(BaseModel):
    response: str
    catalog_images: List[str] = Field(default_factory=list)


@app.post("/message", response_model=MessageResponse)
async def receive_message(request: MessageRequest) -> MessageResponse:
    try:
        response, catalog_images = await agent.handle_message(request.message)
        return MessageResponse(response=response, catalog_images=catalog_images)
    except Exception:
        logger.exception("Error processing message")
        raise HTTPException(500, "Error interno del servidor")


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


app.mount("/catalogos", StaticFiles(directory=CATALOG_DIR), name="catalogos")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
