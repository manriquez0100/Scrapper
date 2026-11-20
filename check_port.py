import requests
try:
    resp = requests.get('http://127.0.0.1:9222/json/version', timeout=2)
    print(f'Status: {resp.status_code}')
    print(f'Browser: {resp.json().get("Browser", "Unknown")}')
except Exception as e:
    print(f'Error: {e}')