import requests
import json

# Test with queries that should NOT trigger payment intent
test_cases = [
    "harry potter",
    "libro harry potter 1",
    "quiero comprar harry potter",
    "busco harry potter",
]

for q in test_cases:
    print(f"\n=== Query: '{q}' ===")
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