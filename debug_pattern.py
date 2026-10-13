import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Use regex to find and replace
pattern = re.compile(
    r'async def extract_book_query\(self, message: str\) -> Optional\[str\]:.*?async def enrich_book_query',
    re.DOTALL
)

match = pattern.search(content)
if match:
    print("Found match!")
    print(match.group()[:500])
else:
    print("No match found")
    # Try simpler pattern
    idx = content.find('async def extract_book_query')
    if idx >= 0:
        # Find the next async def enrich_book_query
        idx2 = content.find('async def enrich_book_query', idx)
        if idx2 >= 0:
            print(content[idx:idx2+50])
        else:
            print("enrich_book_query not found after extract_book_query")