import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Use a more flexible pattern - just replace the specific method body
# We'll match from "async def extract_book_query" up to the next method
pattern = r'(async def extract_book_query\(self, message: str\) -> Optional\[str\]:.*?)(?=\n    async def enrich_book_query)'

def replacement(match):
    return '''async def extract_book_query(self, message: str) -> Optional[str]:
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
        return fallback_query'''

new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

if new_content != content:
    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('Replacement successful!')
else:
    print('Pattern did not match')