import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

base_url = "http://localhost:1234/v1"
print(f"Querying: GET {base_url}/models ...\n")

try:
    req = urllib.request.Request(f"{base_url}/models", headers={"Authorization": "Bearer lm-studio"})
    with urllib.request.urlopen(req, timeout=5) as response:
        status_code = response.status
        body = response.read().decode('utf-8')
        data = json.loads(body)
        print(f"HTTP Status: {status_code}")
        print("Raw Response Data:")
        print(json.dumps(data, indent=2))
except Exception as e:
    print(f"Error connecting to {base_url}/models:")
    print(f"  {e}")
