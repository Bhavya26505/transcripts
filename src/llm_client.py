import json
import re
import time
import urllib.request
import urllib.error
from typing import Dict, List, Any, Optional, Tuple

import config

class LMStudioClient:
    """
    Isolated LM Studio API Client (OpenAI-compatible local endpoint).
    Handles model discovery, request execution with automatic retry,
    latency measurement, JSON response extraction, and error handling.
    """

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None, model_id: Optional[str] = None):
        self.base_url = (base_url or config.LM_STUDIO_BASE_URL).rstrip('/')
        self.api_key = api_key or config.LM_STUDIO_API_KEY
        self.model_id = model_id or config.LM_STUDIO_MODEL_ID

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def check_connection_and_get_models(self, timeout: int = 10) -> List[Dict[str, Any]]:
        """
        Queries GET /v1/models endpoint to verify connectivity and discover loaded models.
        """
        models_url = f"{self.base_url}/models"
        req = urllib.request.Request(models_url, headers=self._get_headers(), method="GET")

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status != 200:
                    raise ConnectionError(f"HTTP Status {resp.status} received from {models_url}")
                body = resp.read().decode('utf-8')
                data = json.loads(body)
                return data.get("data", [])
        except urllib.error.URLError as e:
            raise ConnectionError(
                f"Failed to connect to LM Studio at {models_url}.\n"
                f"Error detail: {e.reason}\n"
                f"Please ensure LM Studio local server is running on port 1234."
            ) from e
        except Exception as e:
            raise ConnectionError(f"Unexpected error querying {models_url}: {e}") from e

    def resolve_model_id(self, available_models: List[Dict[str, Any]]) -> str:
        if not available_models:
            raise ValueError("No loaded models found in LM Studio server response.")

        available_ids = [m["id"] for m in available_models]

        if self.model_id:
            if self.model_id in available_ids:
                return self.model_id
            for m_id in available_ids:
                if self.model_id.lower() in m_id.lower() or m_id.lower() in self.model_id.lower():
                    return m_id
            raise ValueError(
                f"Configured model ID '{self.model_id}' is not loaded in LM Studio.\n"
                f"Currently available models: {available_ids}"
            )

        return available_ids[0]

    def send_completion(
        self,
        messages: List[Dict[str, str]],
        model_id: str,
        temperature: float = 0.0,
        max_tokens: int = 2500,
        timeout: int = 600,
        max_retries: int = 3
    ) -> Tuple[str, float]:
        """
        Sends a chat completion request to /v1/chat/completions with automatic retry logic.
        Returns (content_text, latency_seconds).
        """
        chat_url = f"{self.base_url}/chat/completions"
        payload = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        data_bytes = json.dumps(payload).encode('utf-8')
        last_exception = None

        for attempt in range(1, max_retries + 1):
            req = urllib.request.Request(chat_url, data=data_bytes, headers=self._get_headers(), method="POST")
            start_time = time.time()
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    elapsed_time = round(time.time() - start_time, 3)
                    if resp.status != 200:
                        raise RuntimeError(f"LM Studio API returned HTTP status {resp.status}")
                    body = resp.read().decode('utf-8')
                    res_json = json.loads(body)
                    choices = res_json.get("choices", [])
                    if not choices:
                        raise ValueError("LM Studio returned empty choices in completion response.")
                    content = choices[0].get("message", {}).get("content", "").strip()
                    return content, elapsed_time
            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    time.sleep(2.0)
                else:
                    raise ConnectionError(f"LM Studio completion failed after {max_retries} attempts: {e}") from e

        raise ConnectionError(f"LM Studio completion failed: {last_exception}")

    def execute_test_prompt(self, model_id: str) -> Dict[str, Any]:
        messages = [
            {
                "role": "system",
                "content": "You are a local language model being tested through LM Studio."
            },
            {
                "role": "user",
                "content": 'Return exactly this JSON and nothing else:\n{\n  "status": "READY"\n}'
            }
        ]

        raw_content, latency = self.send_completion(messages, model_id=model_id, temperature=0.0, max_tokens=100)

        cleaned_content = re.sub(r'^```(?:json)?\s*', '', raw_content, flags=re.IGNORECASE)
        cleaned_content = re.sub(r'\s*```$', '', cleaned_content).strip()

        parsed_json = {}
        try:
            parsed_json = json.loads(cleaned_content)
        except json.JSONDecodeError as e:
            match = re.search(r'\{\s*"status"\s*:\s*"([^"]+)"\s*\}', raw_content)
            if match:
                parsed_json = {"status": match.group(1)}
            else:
                raise ValueError(f"Failed to parse model response as JSON. Raw output: {repr(raw_content)}") from e

        status_val = parsed_json.get("status")
        if status_val != "READY":
            raise ValueError(f"Expected status 'READY' but model returned '{status_val}'. Full JSON: {parsed_json}")

        return {
            "status": status_val,
            "latency_seconds": latency,
            "model_used": model_id,
            "raw_response": raw_content,
            "parsed_response": parsed_json
        }
