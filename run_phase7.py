import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from src.llm_client import LMStudioClient
from src.hook_analyzer import analyze_video_hook

TARGET_VIDEO_ID = "-RgdgqF9wd0"

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 75)
    print(" PHASE 7 CORRECTION PASS: HOOK ANALYSIS (-RgdgqF9wd0)")
    print("=" * 75)

    config.ANALYSIS_RAW_DIR.mkdir(parents=True, exist_ok=True)
    config.ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    hi_lang_file = config.LANGUAGE_DIR / f"{TARGET_VIDEO_ID}_hi_lang.json"
    if not hi_lang_file.exists():
        print(f"[ERROR] Language metadata file not found at {hi_lang_file}. Run Phase 5 first.")
        sys.exit(1)

    print(f"Target Video ID       : {TARGET_VIDEO_ID}")
    print(f"Transcript Selected   : HINDI / Original ({hi_lang_file.name})")
    print(f"LM Studio Endpoint    : {config.LM_STUDIO_BASE_URL}")
    print(f"Model ID              : {config.LM_STUDIO_MODEL_ID}")
    print(f"Target Opening Window : {config.HOOK_TARGET_WINDOW_SECONDS}s (Max Cap: {config.HOOK_MAX_WINDOW_SECONDS}s)\n")

    client = LMStudioClient(
        base_url=config.LM_STUDIO_BASE_URL,
        api_key=config.LM_STUDIO_API_KEY,
        model_id=config.LM_STUDIO_MODEL_ID
    )

    print("Executing Qwen hook analysis with strict window capping...\n")
    analysis_result = analyze_video_hook(
        video_id=TARGET_VIDEO_ID,
        lang_file_path=str(hi_lang_file),
        client=client,
        target_window=config.HOOK_TARGET_WINDOW_SECONDS,
        max_window=config.HOOK_MAX_WINDOW_SECONDS,
        temperature=0.1,
        max_tokens=2500
    )

    raw_record = analysis_result["raw_record"]
    parsed_analysis = analysis_result["parsed_analysis"]
    log_metrics = analysis_result["log_metrics"]

    # Save outputs
    raw_out_file = config.ANALYSIS_RAW_DIR / f"{TARGET_VIDEO_ID}_hook_raw.json"
    with open(raw_out_file, "w", encoding="utf-8") as f_raw:
        json.dump(raw_record, f_raw, indent=2, ensure_ascii=False)

    parsed_out_file = config.ANALYSIS_DIR / f"{TARGET_VIDEO_ID}_hook.json"
    with open(parsed_out_file, "w", encoding="utf-8") as f_parsed:
        json.dump(parsed_analysis, f_parsed, indent=2, ensure_ascii=False)

    oa = parsed_analysis.get("opening_analysis", {})
    hook = oa.get("hook", {})
    topic = oa.get("core_topic", {})
    problem = oa.get("viewer_problem_or_question", {})
    promise = oa.get("promise", {})
    points = oa.get("expected_points", [])

    print("=" * 75)
    print(" PHASE 7 CORRECTION PASS — FINAL REPORT")
    print("=" * 75)
    print(f"1.  Actual Opening Duration : {log_metrics['actual_opening_duration']} seconds (End Timestamp: {log_metrics['final_end_timestamp']}s)")
    print(f"2.  Number of Segments     : {log_metrics['number_of_segments']} segments")
    print(f"3.  Input Size             : {log_metrics['input_character_count']} characters")
    print(f"4.  Output Size            : {log_metrics['output_character_count']} characters")
    print(f"5.  Latency                : {log_metrics['latency_seconds']} seconds ({log_metrics['latency_seconds']*1000:.0f} ms)")
    
    print("\n6.  HOOK:")
    print(f"    - Type       : {hook.get('hook_type')}")
    print(f"    - Confidence : {hook.get('confidence')}")
    print(f"    - Timestamp  : [{hook.get('start_time')}s - {hook.get('end_time')}s]")
    print(f"    - Text       : {repr(hook.get('text'))}")

    print("\n7.  CORE TOPIC:")
    print(f"    - Description : {topic.get('description')}")
    print(f"    - Explicit    : {topic.get('explicit')}")
    print(f"    - Confidence  : {topic.get('confidence')}")

    print("\n8.  VIEWER PROBLEM / QUESTION:")
    print(f"    - Description : {problem.get('description')}")
    print(f"    - Explicit    : {problem.get('explicit')}")
    print(f"    - Confidence  : {problem.get('confidence')}")

    print("\n9.  PROMISE:")
    print(f"    - Description : {promise.get('description')}")
    print(f"    - Explicit    : {promise.get('explicit')}")
    print(f"    - Confidence  : {promise.get('confidence')}")

    print("\n10. EXPECTED POINTS PROMISED:")
    print(f"    - Total Points : {len(points)}")
    for pt in points:
        ev = pt.get("evidence", {})
        print(f"    ► [{pt.get('point_id')}]: {pt.get('description')}")
        print(f"      Explicitly Promised: {pt.get('explicitly_promised')} | Confidence: {pt.get('confidence')}")
        print(f"      Evidence           : [{ev.get('start_time')}s - {ev.get('end_time')}s] {repr(ev.get('text'))}")

    print("\n11. EXPECTED DIRECTION:")
    print(f"    - Direction : {oa.get('expected_direction')}")

    print("\n12. EVIDENCE SUMMARY (ALL SECTION EVIDENCE EXCERPTS):")
    for sec_name, sec_obj in [("Core Topic", topic), ("Viewer Problem", problem), ("Promise", promise)]:
        ev = sec_obj.get("evidence", {}) if isinstance(sec_obj, dict) else {}
        print(f"    - [{sec_name}] [{ev.get('start_time')}s - {ev.get('end_time')}s]: {repr(ev.get('text'))}")

    print("\n13. JSON VALIDATION STATUS:")
    print(f"    - Status          : {'PASS' if log_metrics['json_valid'] and not log_metrics['validation_issues'] else 'FAIL'}")
    if log_metrics['validation_issues']:
        print(f"    - Validation Issues: {log_metrics['validation_issues']}")

    print("\n" + "=" * 75)
    print(" PHASE 7 RE-RUN COMPLETE")
    print("=" * 75)

if __name__ == "__main__":
    main()
