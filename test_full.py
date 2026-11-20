import requests
import json

response = requests.post(
    'http://localhost:8000/message',
    json={'message': 'busco harry potter 1'},
    timeout=60
)
print(f'Status: {response.status_code}')
data = response.json()
print(f'Response: {data["response"][:300]}')
print(f'Images: {len(data["catalog_images"])}')