with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the strip string literal issue
# The problem is: strip('"\'\'') - should be strip('"\'')
# Let's fix both occurrences

# Fix in extract_book_query
content = content.replace(
    "strip('\"\\'')",
    "strip('\"\\\'')"
)

# Also check enrich_book_query
content = content.replace(
    "strip('\"\\'')",
    "strip('\"\\\'')"
)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed!')