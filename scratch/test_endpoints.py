import urllib.request
import json

def test_url(url):
    print(f"Testing URL: {url}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Python"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            print(f"  Status: {resp.status}")
            print(f"  Body: {resp.read().decode('utf-8')[:300]}")
    except Exception as e:
        print(f"  Error: {e}")

test_url("http://localhost:11434/v1/models")
test_url("http://localhost:11434/api/tags")
test_url("http://localhost:8000/v1/models")
test_url("http://localhost:8000/docs")
test_url("http://localhost:1234/v1/models")
