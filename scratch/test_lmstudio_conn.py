import urllib.request
import json

base_url = "http://localhost:1234/v1"

print(f"Connecting to LM Studio endpoint: {base_url}/models ...")

try:
    req = urllib.request.Request(f"{base_url}/models", headers={"Authorization": "Bearer lm-studio"})
    with urllib.request.urlopen(req, timeout=5) as response:
        status_code = response.status
        body = response.read().decode('utf-8')
        data = json.loads(body)
        print(f"HTTP Status Code: {status_code}")
        print("Available Models from LM Studio:")
        print(json.dumps(data, indent=2))
except Exception as e:
    print(f"Connection Error: {e}")
