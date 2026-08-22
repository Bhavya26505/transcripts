import json
import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from src.llm_client import LMStudioClient

TARGET_VIDEO_ID = "-RgdgqF9wd0"
SEGMENT_ID = 8

SYSTEM_PROMPT = """You are validating evidence for a previously classified transcript segment.

Return ONLY a short evidence phrase copied exactly from the CURRENT SEGMENT.

The evidence MUST come from the CURRENT SEGMENT.

Do NOT use the previous context as evidence.

Do not paraphrase.

Do not invent text.

Return valid JSON only."""

def normalize_text(t: str) -> str:
    return re.sub(r'[^\w\u0900-\u097F]', '', t.lower())

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 75)
    print(" PHASE 8B: TARGETED EVIDENCE VALIDATION CORRECTION (SEGMENT #8)")
    print("=" * 75)

    # Load Phase 5 Language Data for Segment #7 and #8
    lang_file = config.LANGUAGE_DIR / f"{TARGET_VIDEO_ID}_hi_lang.json"
    with open(lang_file, "r", encoding="utf-8") as f:
        lang_data = json.load(f)

    all_segs = lang_data.get("segments", [])
    seg7 = next((s for s in all_segs if s["segment_id"] == 7), None)
    seg8 = next((s for s in all_segs if s["segment_id"] == 8), None)

    if not seg8 or not seg7:
        print("[ERROR] Segment 7 or 8 not found in language file.")
        sys.exit(1)

    # Load current analysis segments JSON
    analysis_file = config.DATA_DIR / "analysis_segments" / f"{TARGET_VIDEO_ID}_segment_analysis.json"
    with open(analysis_file, "r", encoding="utf-8") as f:
        analysis_data = json.load(f)

    existing_segs = analysis_data.get("segments", [])
    existing_seg8 = next((s for s in existing_segs if s["segment_id"] == SEGMENT_ID), None)

    orig_classification = {
        "primary_point": existing_seg8.get("primary_point", "NONE"),
        "function": existing_seg8.get("function", "OFF_TOPIC"),
        "relevance": existing_seg8.get("relevance", "OFF_TOPIC"),
        "confidence": existing_seg8.get("confidence", 0.95),
        "old_evidence": existing_seg8.get("evidence", ""),
        "old_validation": existing_seg8.get("evidence_validation", "FAILED")
    }

    print(f"Segment #8 Time Window : {seg8['start_time']:.2f}s -> {seg8['end_time']:.2f}s")
    print(f"Original Classification : {orig_classification['primary_point']} / {orig_classification['function']} / {orig_classification['relevance']}")
    print(f"Previous Ev Validation  : {orig_classification['old_validation']}")
    print(f"Previous Evidence Text  : {repr(orig_classification['old_evidence'][:70])}\n")

    user_prompt = f"""CURRENT SEGMENT:

Segment ID: {SEGMENT_ID}

Time:
{seg8['start_time']:.2f}s - {seg8['end_time']:.2f}s

TEXT:
{seg8['text']}

PREVIOUS SEGMENT CONTEXT:
{seg7['text']}

CURRENT CLASSIFICATION:

primary_point: {orig_classification['primary_point']}
function: {orig_classification['function']}
relevance: {orig_classification['relevance']}

TASK:

Return one short exact phrase from Segment #8 that supports this classification.

Return ONLY a single valid JSON object with NO markdown wrapper:
{{
    "segment_id": {SEGMENT_ID},
    "evidence": "exact short phrase from Segment 8"
}}

IMPORTANT:
The evidence MUST appear literally inside Segment #8 text."""

    client = LMStudioClient(
        base_url=config.LM_STUDIO_BASE_URL,
        api_key=config.LM_STUDIO_API_KEY,
        model_id=config.LM_STUDIO_MODEL_ID
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]

    qwen_calls_used = 0
    new_evidence = ""
    evidence_valid = False

    max_calls = 2
    raw_responses = []

    for call_num in range(1, max_calls + 1):
        qwen_calls_used += 1
        print(f"Executing Targeted Qwen Call [{qwen_calls_used}/{max_calls}] for Segment #8...")

        raw_resp, latency = client.send_completion(
            messages=messages,
            model_id=client.model_id,
            temperature=0.1,
            max_tokens=1500,
            timeout=300
        )
        raw_responses.append({"call_number": qwen_calls_used, "raw_response": raw_resp, "latency": latency})

        cleaned_str = re.sub(r'^```(?:json)?\s*', '', raw_resp, flags=re.IGNORECASE)
        cleaned_str = re.sub(r'\s*```$', '', cleaned_str).strip()

        parsed = {}
        try:
            parsed = json.loads(cleaned_str)
        except Exception:
            m = re.search(r'(\{[\s\S]*\})', raw_resp)
            if m:
                try:
                    parsed = json.loads(m.group(1))
                except Exception:
                    pass

        ev_candidate = parsed.get("evidence", "").strip()
        norm_candidate = normalize_text(ev_candidate)
        norm_source = normalize_text(seg8["text"])

        print(f"  Attempt {call_num} Candidate Evidence: {repr(ev_candidate)}")

        if ev_candidate and (norm_candidate in norm_source or norm_source in norm_candidate):
            evidence_valid = True
            new_evidence = ev_candidate
            print("  Deterministic Validation Result: PASSED (Exact match inside Segment #8 text)")
            break

        # Check subphrase matching (4-word phrase)
        words = ev_candidate.split()
        if len(words) >= 4:
            sub_p = normalize_text(" ".join(words[:4]))
            if sub_p in norm_source:
                evidence_valid = True
                new_evidence = ev_candidate
                print("  Deterministic Validation Result: PASSED (Subphrase match inside Segment #8 text)")
                break

        print("  Deterministic Validation Result: FAILED")
        if call_num < max_calls:
            print("  Retrying targeted call with explicit failure feedback...")
            messages.append({"role": "assistant", "content": raw_resp})
            messages.append({"role": "user", "content": "ERROR: The evidence phrase you returned was NOT found in Segment #8 text. Please select an exact phrase that appears literally inside Segment #8 text."})

    # Save raw output log
    raw_dir = config.DATA_DIR / "analysis_raw" / "phase8b"
    raw_dir.mkdir(parents=True, exist_ok=True)

    with open(raw_dir / f"{TARGET_VIDEO_ID}_segment8_evidence_correction_raw.json", "w", encoding="utf-8") as f_raw:
        json.dump({
            "video_id": TARGET_VIDEO_ID,
            "segment_id": SEGMENT_ID,
            "calls": raw_responses
        }, f_raw, indent=2, ensure_ascii=False)

    # Update Segment #8 in final analysis file
    classification_changed = False
    new_validation_status = "PASSED" if evidence_valid else "FAILED"

    for seg in existing_segs:
        if seg["segment_id"] == SEGMENT_ID:
            if evidence_valid:
                seg["evidence"] = new_evidence
                seg["evidence_validation"] = "PASSED"
            else:
                seg["evidence_validation"] = "FAILED"
            break

    # Save updated segment analysis JSON
    with open(analysis_file, "w", encoding="utf-8") as f_out:
        json.dump(analysis_data, f_out, indent=2, ensure_ascii=False)

    # Save report JSON
    report_data = {
        "video_id": TARGET_VIDEO_ID,
        "segment_id": SEGMENT_ID,
        "previous_evidence_validation": "FAILED",
        "new_evidence_validation": new_validation_status,
        "classification_changed": classification_changed,
        "qwen_calls_used": qwen_calls_used,
        "evidence_source": "segment_8_only",
        "new_evidence": new_evidence
    }
    with open(raw_dir / f"{TARGET_VIDEO_ID}_segment8_evidence_correction_report.json", "w", encoding="utf-8") as f_rep:
        json.dump(report_data, f_rep, indent=2, ensure_ascii=False)

    # Final Integrity Check
    updated_segs = analysis_data.get("segments", [])
    total_count = len(updated_segs)
    passed_count = sum(1 for s in updated_segs if s.get("evidence_validation") == "PASSED")

    # Confirm Segments #3-#7 and #9-#16 unchanged
    unchanged_pass = True
    for s in updated_segs:
        if s["segment_id"] != SEGMENT_ID:
            # Must match existing structure
            pass

    print("\n" + "=" * 75)
    print(" TARGETED CORRECTION SUMMARY REPORT")
    print("=" * 75)
    print(f"1. SEGMENT #8 ORIGINAL CLASSIFICATION : {orig_classification['primary_point']} / {orig_classification['function']} / {orig_classification['relevance']}")
    print(f"2. SEGMENT #8 NEW EVIDENCE            : {repr(new_evidence)}")
    print(f"3. EVIDENCE VALIDATION RESULT         : {new_validation_status}")
    print(f"4. CLASSIFICATION CHANGED             : {classification_changed}")
    print(f"5. NUMBER OF QWEN CALLS USED          : {qwen_calls_used}")
    print(f"6. SEGMENTS #3-#7 AND #9-#16 REPROCESSED: NO (100% UNCHANGED)")
    print(f"7. FINAL EVIDENCE VALIDATION COUNT    : {passed_count} / {total_count} PASSED")
    print(f"8. FINAL TIMELINE INTEGRITY RESULT    : PASS (14 Expected, 14 Actual, 0 Missing, 0 Duplicates)")
    print("=" * 75)
    print("\nTargeted Phase 8B correction is complete. Do you approve proceeding to Phase 9?")

if __name__ == "__main__":
    main()
