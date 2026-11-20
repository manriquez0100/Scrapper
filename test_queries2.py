import requests
import json

# Test different queries
queries = [
    "harry potter",
    "libro harry potter",
    "novela harry potter",
]

for q in queries:
    print(f"\n--- Query: '{q}' ---")
    try:
        response = requests.post(
            'http://localhost:8000/message',
            json={'message': q},
            timeout=60
        )
        data = response.json()
        print(f'Status: {response.status_code}')
        print(f'Response: {data["response"][:200]}')
        print(f'Images: {len(data["catalog_images"])}')
    except Exception as e:
        print(f'Error: {e}')