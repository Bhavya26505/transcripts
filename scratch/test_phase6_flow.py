import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.llm_client import LMStudioClient

def test_ollama_openai_endpoint():
    sys.stdout.reconfigure(encoding='utf-8')
    print("Testing OpenAI-compatible Endpoint (Ollama on port 11434):")
    client = LMStudioClient(base_url="http://localhost:11434/v1", api_key="ollama")
    models = client.check_connection_and_get_models()
    print("Models:", [m["id"] for m in models])
    model_id = client.resolve_model_id(models)
    print("Resolved model:", model_id)
    res = client.execute_test_prompt(model_id=model_id)
    print("Test Result:")
    print(res)

if __name__ == "__main__":
    test_ollama_openai_endpoint()
