import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from mercadolibre import search_mercadolibre

async def test():
    print("Testing MercadoLibre search...")
    result = await search_mercadolibre(
        query='harry potter',
        max_results=3,
        ganancia_envio=200,
        detailed=False,
        debugger_address='127.0.0.1:9222',
    )
    print(f'Results: {len(result.get("results", []))}')
    print(f'Error: {result.get("error", "Ninguno")}')
    for i, r in enumerate(result.get('results', []), 1):
        print(f'  {i}. {r.get("title", "Sin titulo")} | {r.get("price", "N/A")} | {r.get("source", "?")}')

asyncio.run(test())