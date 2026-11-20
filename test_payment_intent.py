import requests
import json

# Test payment intent classification
prompt = """Clasifica el mensaje del cliente. Responde ÚNICAMENTE PAYMENT_INFO si pregunta por cómo comprar, hacer un pedido, pagar, método o datos de pago, depósito, comprobante, envío o los datos que debe proporcionar para recibir el libro. Responde ÚNICAMENTE OTHER en cualquier otro caso. No añadas explicaciones."""

messages = [
    {"role": "system", "content": prompt},
    {"role": "user", "content": "harry potter"}
]

response = requests.post(
    "http://172.19.32.1:1234/v1/chat/completions",
    headers={"Content-Type": "application/json"},
    json={
        "model": "google/gemma-4-e4b",
        "messages": messages,
        "max_tokens": 12,
        "temperature": 0.0
    },
    timeout=30
)

print(f"Status: {response.status_code}")
data = response.json()
content = data['choices'][0]['message']['content']
print(f"Content: '{content}'")
print(f"Is PAYMENT_INFO: {content.strip().upper().split()[0] == 'PAYMENT_INFO'}")