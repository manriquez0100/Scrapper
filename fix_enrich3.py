import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the enrich_book_query method
old_enrich = '''async def enrich_book_query(self, query: str) -> str:
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
        enriched_query = " ".join(response.strip().strip('"\'').split())
        if not enriched_query or enriched_query.upper() == "NO_ENRICHMENT":
            return query
        return enriched_query'''

new_enrich = '''async def enrich_book_query(self, query: str) -> str:
        """Add the author only when LM Studio identifies a specific book title."""
        try:
            response = await asyncio.wait_for(
                self.llm.generate(
                    [
                        {
                            "role": "system",
                            "content": self.behavior["query_enrichment_instructions"],
                        },
                        {"role": "user", "content": query},
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
        enriched_query = " ".join(response.strip().strip('"\'').split())
        if not enriched_query or enriched_query.upper() == "NO_ENRICHMENT":
            return query
        return enriched_query'''

if old_enrich in content:
    content = content.replace(old_enrich, new_enrich)
    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Enrich replacement successful!')
else:
    print('Old enrich not found, trying regex...')
    # Try regex with raw pattern (not compiled)
    pattern = r'async def enrich_book_query\(self, query: str\) -> str:.*?(?=\n    async def|\nclass |\Z)'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        print('Found with regex')
        content = re.sub(pattern, new_enrich, content, count=1, flags=re.DOTALL)
        with open('main.py', 'w', encoding='utf-8') as f:
            f.write(content)
        print('Regex replacement successful!')
    else:
        print('Not found with regex either')

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done')