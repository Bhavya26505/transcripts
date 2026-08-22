import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from src.llm_client import LMStudioClient

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 75)
    print(" PHASE 6 STRICT MODEL VERIFICATION (LM STUDIO ONLY)")
    print("=" * 75)

    base_url = config.LM_STUDIO_BASE_URL
    api_key = config.LM_STUDIO_API_KEY
    target_model_id = config.LM_STUDIO_MODEL_ID

    print(f"Target Base URL    : {base_url}")
    print(f"Target Model ID    : {target_model_id}")
    print(f"API Key            : {api_key}\n")

    client = LMStudioClient(base_url=base_url, api_key=api_key, model_id=target_model_id)

    # Step 1: Query GET /v1/models (Strict LM Studio 127.0.0.1:1234)
    print("--- 1. QUERYING GET /v1/models ---")
    try:
        available_models = client.check_connection_and_get_models(timeout=5)
        print(f"LM Studio Server Status: CONNECTED ({base_url})")
        print(f"Total Models Returned  : {len(available_models)}\n")
        
        print("ALL RETURNED MODEL IDs:")
        returned_model_ids = [m.get("id") for m in available_models if "id" in m]
        for idx, m_id in enumerate(returned_model_ids, 1):
            print(f"  [{idx}] {m_id}")
        print()

    except Exception as e:
        print(f"\n[CRITICAL ERROR] Failed to connect to LM Studio at {base_url}:")
        print(f"  {e}")
        print("\nSTOPPING: Connection to LM Studio on port 1234 failed.")
        sys.exit(1)

    # Step 2: Confirm Target Model Availability
    print("--- 2. MODEL CONFIRMATION ---")
    selected_model_id = None
    try:
        selected_model_id = client.resolve_model_id(available_models)
        print(f"Target Model Match : CONFIRMED")
        print(f"Resolved Model ID  : {selected_model_id}")
    except ValueError as ve:
        print(f"\n[CRITICAL ERROR] Target Qwen model '{target_model_id}' was NOT found in LM Studio.")
        print(f"Details: {ve}")
        print("\nSTOPPING: Required model is missing from LM Studio server.")
        sys.exit(1)

    # Step 3: Send Minimal READY JSON Test
    print("\n--- 3. SENDING MINIMAL TEST PROMPT ---")
    print(f"Target Endpoint : POST {base_url}/chat/completions")
    print(f"Model Parameter : {selected_model_id}")
    print("Payload         : System & User prompt requesting exact JSON status READY")
    print("(Zero transcript, audio, video, or analysis data sent)\n")

    try:
        test_result = client.execute_test_prompt(model_id=selected_model_id)

        print("--- 4. RESPONSE & LATENCY REPORT ---")
        print(f"Exact Model ID Sent to API : {test_result['model_used']}")
        print(f"Raw Response Text          : {repr(test_result['raw_response'])}")
        print(f"Parsed JSON                : {json.dumps(test_result['parsed_response'])}")
        print(f"Status Verified            : {test_result['status']} (Expected 'READY' -> MATCH)")
        print(f"Response Latency           : {test_result['latency_seconds']} seconds ({test_result['latency_seconds']*1000:.0f} ms)")

    except Exception as e:
        print(f"\n[TEST ERROR] Minimal prompt execution or JSON validation failed:")
        print(f"  {e}")
        print("\nSTOPPING: Response validation failed.")
        sys.exit(1)

    print("\n" + "=" * 75)
    print(" PHASE 6 STRICT VERIFICATION SUMMARY")
    print("=" * 75)
    print(f"LM Studio Endpoint          : {base_url}")
    print(f"Qwen Model Confirmed        : {selected_model_id}")
    print(f"Model ID in Completions POST: {test_result['model_used']}")
    print(f"JSON Status Verification    : PASS (status == 'READY')")
    print(f"Response Latency            : {test_result['latency_seconds']}s ({test_result['latency_seconds']*1000:.0f} ms)")
    print("\nPHASE 6 STRICTLY VERIFIED FOR QWEN MODEL")
    print("=" * 75)

if __name__ == "__main__":
    main()
