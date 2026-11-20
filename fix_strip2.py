with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# The issue is: strip('"\'\'') should be strip('"\'')
# Current: strip('"\'\'') - this is 5 chars in source: " \ ' ' '
# Should be: strip('"\'') - 3 chars: " \ '

# Fix both occurrences
content = content.replace(
    "strip('\"\\'')",
    "strip('\"\\\\')"
)

# Also check enrich_book_query area
content = content.replace(
    "strip('\"\\'')",
    "strip('\"\\\\')"
)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed!')