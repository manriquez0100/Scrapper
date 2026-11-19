import requests
import json

# Test LM Studio directly
response = requests.post(
    "http://172.19.32.1:1234/v1/chat/completions",
    headers={"Content-Type": "application/json"},
    json={
        "model": "google/gemma-4-e4b",
        "messages": [{"role": "user", "content": "hola"}],
        "max_tokens": 10
    },
    timeout=30
)
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")