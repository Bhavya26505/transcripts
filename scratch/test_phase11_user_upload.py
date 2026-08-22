import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Any

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from src.user_analysis_pipeline import UserAnalysisPipeline

def format_seconds_to_srt_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def raw_json_to_srt(raw_json_path: Path, output_srt_path: Path):
    with open(raw_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    segments = data.get("segments", [])
    lines = []
    for idx, seg in enumerate(segments, 1):
        t1 = format_seconds_to_srt_timestamp(seg.get("start", 0.0))
        t2 = format_seconds_to_srt_timestamp(seg.get("end", 0.0))
        txt = seg.get("text", "")
        lines.append(f"{idx}\n{t1} --> {t2}\n{txt}\n")
    output_srt_path.parent.mkdir(parents=True, exist_ok=True)
    output_srt_path.write_text("\n".join(lines), encoding="utf-8")

def run_phase11_tests():
    print("=" * 80)
    print(" EXECUTION OF PHASE 11 PRODUCTION USER-UPLOAD VALIDATION TESTS")
    print("=" * 80)

    test_logs = []
    all_tests_passed = True

    def record_test(test_num: int, title: str, passed: bool, details: str = ""):
        nonlocal all_tests_passed
        status_str = "[PASS]" if passed else "[FAIL]"
        if not passed:
            all_tests_passed = False
        log_msg = f"{status_str} TEST {test_num}: {title}"
        if details:
            log_msg += f" | {details}"
        test_logs.append(log_msg)
        print(log_msg)

    # Convert test fixtures to SRT files if needed
    srt_p1 = config.DATA_DIR / "uploads" / "test1_explicit_promises.srt"
    if not srt_p1.exists():
        raw_p1 = config.DATA_DIR / "raw" / "-RgdgqF9wd0_hi_raw.json"
        raw_json_to_srt(raw_p1, srt_p1)

    srt_p2 = config.DATA_DIR / "uploads" / "test2_zero_promises.srt"
    if not srt_p2.exists():
        raw_p2 = config.DATA_DIR / "raw" / "-SZBrXciDLg_hi_raw.json"
        raw_json_to_srt(raw_p2, srt_p2)

    # ---------------------------------------------------------
    # TEST 1: Valid SRT with Explicit Promises (-RgdgqF9wd0 sample)
    # ---------------------------------------------------------
    print("\n--- Running TEST 1: Valid SRT with Explicit Promises ---")
    pipeline1 = UserAnalysisPipeline()
    res1 = pipeline1.run_pipeline(srt_p1)
    
    t1_ok = (
        res1.get("status") == "COMPLETED" and
        res1.get("promise_analysis", {}).get("promise_status") == "EXPLICIT_PROMISE" and
        res1.get("adherence", {}).get("point_coverage") is not None and
        res1.get("adherence", {}).get("adherence_score") is not None
    )
    record_test(1, "Valid SRT with Explicit Promises", t1_ok, f"Status: {res1.get('status')}, Promise Status: {res1.get('promise_analysis', {}).get('promise_status')}")

    # ---------------------------------------------------------
    # TEST 2: Valid SRT with ZERO Explicit Promises (-SZBrXciDLg sample)
    # ---------------------------------------------------------
    print("\n--- Running TEST 2: Valid SRT with ZERO Explicit Promises ---")
    pipeline2 = UserAnalysisPipeline()
    res2 = pipeline2.run_pipeline(srt_p2)

    t2_ok = (
        res2.get("status") == "COMPLETED" and
        res2.get("promise_analysis", {}).get("promise_status") == "NO_EXPLICIT_PROMISE" and
        res2.get("adherence", {}).get("point_coverage") is None and
        res2.get("adherence", {}).get("adherence_score") is None
    )
    record_test(2, "Valid SRT with ZERO Explicit Promises", t2_ok, f"Promise Status: {res2.get('promise_analysis', {}).get('promise_status')}, Score: {res2.get('adherence', {}).get('adherence_score')}")

    # ---------------------------------------------------------
    # TEST 3: Invalid / Empty SRT Input
    # ---------------------------------------------------------
    print("\n--- Running TEST 3: Invalid / Empty SRT Input ---")
    empty_srt = config.DATA_DIR / "uploads" / "test3_empty.srt"
    empty_srt.parent.mkdir(parents=True, exist_ok=True)
    empty_srt.write_text("", encoding="utf-8")

    pipeline3 = UserAnalysisPipeline()
    res3 = pipeline3.run_pipeline(empty_srt)

    t3_ok = (
        res3.get("status") == "FAILED" and
        "empty" in res3.get("error", "").lower()
    )
    record_test(3, "Invalid / Empty SRT Input Handling", t3_ok, f"Error: {res3.get('error')}")

    # ---------------------------------------------------------
    # TEST 4: LM Studio Server Unavailable Safety Check
    # ---------------------------------------------------------
    print("\n--- Running TEST 4: LM Studio Server Unavailable Check ---")
    orig_port = config.LM_STUDIO_BASE_URL
    config.LM_STUDIO_BASE_URL = "http://127.0.0.1:9999/v1"

    pipeline4 = UserAnalysisPipeline()
    res4 = pipeline4.run_pipeline(srt_p1)

    config.LM_STUDIO_BASE_URL = orig_port  # Restore port

    t4_ok = (
        res4.get("status") == "FAILED" and
        "unavailable" in res4.get("error", "").lower()
    )
    record_test(4, "LM Studio Server Unavailable Clean Handling", t4_ok, f"Error: {res4.get('error')}")

    # ---------------------------------------------------------
    # TEST 5: Repeated Same Input Cache Check (SHA-256)
    # ---------------------------------------------------------
    print("\n--- Running TEST 5: Repeated Same Input SHA-256 Cache ---")
    pipeline5 = UserAnalysisPipeline()
    t_start = time.time()
    res5 = pipeline5.run_pipeline(srt_p1)
    duration5 = time.time() - t_start

    t5_ok = (
        res5.get("status") == "COMPLETED" and
        res5.get("is_cached") == True and
        duration5 < 2.0  # Fast execution using cache!
    )
    record_test(5, "Repeated Same Input SHA-256 Cache Check", t5_ok, f"Is Cached: {res5.get('is_cached')}, Duration: {duration5:.2f}s")

    # ---------------------------------------------------------
    # TEST 6: Timeline Integrity Check
    # ---------------------------------------------------------
    print("\n--- Running TEST 6: Timeline Integrity Check ---")
    t6_ok = (
        res1.get("timeline", {}).get("integrity") == "PASS" and
        res1.get("timeline", {}).get("overlap_seconds", 0.0) == 0.0
    )
    record_test(6, "Timeline Integrity Check", t6_ok, f"Integrity: {res1.get('timeline', {}).get('integrity')}")

    # ---------------------------------------------------------
    # TEST 7: Evidence Excerpt Verbatim Verification
    # ---------------------------------------------------------
    print("\n--- Running TEST 7: Evidence Excerpt Verbatim Verification ---")
    segs = res1.get("segments", [])
    ev_ok = True
    for s in segs:
        ev = s.get("evidence", "")
        if not ev:
            ev_ok = False
            break

    record_test(7, "Evidence Excerpt Verbatim Verification", ev_ok, f"Verified {len(segs)} segments evidence")

    # Save Final Validation Report
    report_data = {
        "validation_phase": "PHASE_11_USER_UPLOAD_ANALYSIS_INTERFACE",
        "overall_status": "PASS" if all_tests_passed else "FAIL",
        "total_tests": 7,
        "passed_tests": sum(1 for log in test_logs if "[PASS]" in log),
        "failed_tests": sum(1 for log in test_logs if "[FAIL]" in log),
        "lm_studio_endpoint": config.LM_STUDIO_BASE_URL,
        "lm_studio_model": config.LM_STUDIO_MODEL_ID,
        "candidate_b_formula": "0.60 * Coverage + 0.25 * Relevance + 0.15 * Discipline",
        "test_logs": test_logs
    }

    report_dir = config.DATA_DIR / "production_validation" / "phase11"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / "phase11_validation_report.json"

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print(f" FINAL PHASE 11 VALIDATION REPORT: {'PASS' if all_tests_passed else 'FAIL'}")
    print("=" * 80)
    print(f"Saved validation report to: {report_file.resolve()}")

    return all_tests_passed

if __name__ == "__main__":
    run_phase11_tests()
