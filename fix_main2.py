import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''async def extract_book_query(self, message: str) -> Optional[str]:
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
            response = await self.llm.generate('''

new = '''async def extract_book_query(self, message: str) -> Optional[str]:
        try:
            system_prompt = self.behavior["query_extraction_instructions"]
            response = await asyncio.wait_for(
                self.llm.generate(
                    [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": message},
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

        query = " ".join(response.strip().strip('"\'').split())
        if query and query.upper() != "NO_BOOK_QUERY":
            return query

        fallback_query = extract_query_fallback(message)
        if fallback_query:
            logger.info("Usando consulta de respaldo: %s", fallback_query)
        return fallback_query

    async def enrich_book_query(self, query: str) -> str:
        """Add the author only when LM Studio identifies a specific book title."""
        try:
            response = await asyncio.wait_for('''

if old in content:
    content = content.replace(old, new)
    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Replacement successful!')
else:
    print('Old string not found!')