"""FastAPI app that orchestrates LM Studio and Buscalibre book searches."""

import json
import logging
from typing import Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from buscalibre_tool import search_buscalibre
from llm_provider import LLMProvider, get_llm_provider

load_dotenv()
logger = logging.getLogger(__name__)


class Agent:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    async def extract_book_query(self, message: str) -> Optional[str]:
        system_prompt = """Extrae una consulta para buscar libros a partir del mensaje del cliente.
Devuelve ÚNICAMENTE el título, autor y/o número de tomo que sirvan para buscar.
Elimina saludos, preguntas y texto conversacional. Conserva los números de saga o
volumen: por ejemplo, "busco el segundo de Harry Potter" devuelve "Harry Potter 2".
Si no hay una solicitud clara de libro, devuelve exactamente: NO_BOOK_QUERY.
No uses comillas, listas, etiquetas ni explicaciones."""
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
            return f"No encontré resultados para '{query}'. ¿Podrías darme más detalles como autor, ISBN o editorial?"

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
        system_prompt = f"""Eres un asistente de atención al cliente de una librería.
Genera una respuesta natural, breve y amable en español basada SOLO en los resultados reales.
No inventes precios, autores, disponibilidad, URLs ni ningún dato que no aparezca en el JSON.
Menciona como máximo las tres primeras opciones y da prioridad a la que coincide mejor.

Resultados de Buscalibre:
{results_text}"""
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
            return f"Sí, encontramos {title} por {price}."
        if first_result["availability"]:
            return f"Sí, encontramos {title}. El precio no está disponible en este momento."
        return f"Encontramos {title}, pero su disponibilidad no está confirmada en este momento."

    async def handle_message(self, message: str) -> str:
        query = await self.extract_book_query(message)
        if not query:
            return "¡Hola! ¿En qué libro te puedo ayudar hoy?"

        # search_buscalibre mueve Selenium a un hilo, para no bloquear FastAPI.
        search_results = await search_buscalibre(query, max_results=5)
        if search_results.get("error"):
            logger.warning("Buscalibre search failed: %s", search_results["error"])
            return "Tuve un problema al buscar el libro. Intenta nuevamente en unos momentos."

        return await self.generate_response(query, search_results.get("results", []))


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


@app.post("/message", response_model=MessageResponse)
async def receive_message(request: MessageRequest) -> MessageResponse:
    try:
        return MessageResponse(response=await agent.handle_message(request.message))
    except Exception:
        logger.exception("Error processing message")
        raise HTTPException(500, "Error interno del servidor")


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
