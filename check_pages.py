import requests
import json

try:
    resp = requests.get('http://127.0.0.1:9222/json/list', timeout=2)
    pages = resp.json()
    print(f'Total pages: {len(pages)}')
    for p in pages:
        print(f'  Type: {p.get("type", "?")}  URL: {p.get("url", "?")[:80]}')
except Exception as e:
    print(f'Error: {e}')