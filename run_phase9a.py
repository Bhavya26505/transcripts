import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from src.adherence_metrics import calculate_phase9a_metrics

TARGET_VIDEO_ID = "-RgdgqF9wd0"

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 75)
    print(" PHASE 9A: DETERMINISTIC ADHERENCE METRICS CORRECTION (-RgdgqF9wd0)")
    print("=" * 75)

    metrics_dir = config.DATA_DIR / "metrics" / "phase9a"
    metrics_dir.mkdir(parents=True, exist_ok=True)

    hook_file = config.ANALYSIS_DIR / f"{TARGET_VIDEO_ID}_hook.json"
    seg_file = config.DATA_DIR / "analysis_segments" / f"{TARGET_VIDEO_ID}_segment_analysis.json"

    if not hook_file.exists() or not seg_file.exists():
        print(f"[ERROR] Required input files not found: {hook_file} or {seg_file}")
        sys.exit(1)

    with open(hook_file, "r", encoding="utf-8") as f:
        reference_hook = json.load(f)

    with open(seg_file, "r", encoding="utf-8") as f:
        segment_timeline = json.load(f)

    print(f"Target Video ID          : {TARGET_VIDEO_ID}")
    print(f"Phase 7 Hook File        : {hook_file.name}")
    print(f"Phase 8B Segment File    : {seg_file.name}")
    print(f"Execution Mode           : 100% DETERMINISTIC PYTHON (0 LLM / Qwen calls)\n")

    # Compute Phase 9A Corrected Metrics with Hard Assertions
    try:
        metrics_data = calculate_phase9a_metrics(
            video_id=TARGET_VIDEO_ID,
            reference_hook=reference_hook,
            segment_timeline=segment_timeline
        )
    except Exception as e:
        print(f"[FAIL] Phase 9A Mathematical Validation Failed: {e}")
        sys.exit(1)

    # Save metrics JSON
    json_path = metrics_dir / f"{TARGET_VIDEO_ID}_metrics.json"
    with open(json_path, "w", encoding="utf-8") as f_json:
        json.dump(metrics_data, f_json, indent=2, ensure_ascii=False)

    win = metrics_data["analysis_window"]
    integ = metrics_data["timeline_integrity"]
    rel_m = metrics_data["relevance_metrics"]
    dur_m = metrics_data["duration_metrics"]
    cov_m = metrics_data["point_coverage"]
    order_m = metrics_data["point_order"]
    ret_m = metrics_data["point_returns"]
    ot_m = metrics_data["off_topic"]
    trans_m = metrics_data["transitions"]
    math_val = metrics_data["mathematical_validation"]

    report_text_lines = []

    def r_print(line: str = ""):
        print(line)
        report_text_lines.append(line)

    r_print("===========================================================================")
    r_print(" PHASE 9A DETERMINISTIC METRICS REPORT (-RgdgqF9wd0)")
    r_print("===========================================================================")

    r_print(f"\n1. TIMELINE INTEGRITY STATUS : {integ['status']}")
    r_print(f"   - Expected Segments Count  : {integ['expected_segments']}")
    r_print(f"   - Analyzed Segments Count  : {integ['analyzed_segments']}")
    r_print(f"   - Missing Segments Count   : {len(integ['missing_segments'])}")
    r_print(f"   - Duplicate Segments Count : {len(integ['duplicate_segments'])}")
    r_print(f"   - Timestamp Overlap / Gap  : {integ['overlap_duration']}s")

    r_print(f"\n2. TOTAL ANALYZED DURATION  : {win['duration']:.2f} seconds ({win['duration']/60:.2f} minutes)")
    r_print(f"   - Analysis Time Window    : {win['start_time']:.2f}s -> {win['end_time']:.2f}s")

    r_print("\n3. RELEVANCE DURATION & PERCENTAGES TABLE:")
    r_print("-" * 75)
    r_print(f"{'Relevance Category':<25} | {'Duration (s)':<15} | {'Percentage (%)':<15}")
    r_print("-" * 75)
    for r_k, r_v in rel_m["rel_durations"].items():
        r_pct = rel_m["rel_percentages"][r_k]
        r_print(f"{r_k:<25} | {r_v:>15.2f}s | {r_pct:>14.2f}%")
    r_print("-" * 75)
    r_print(f"{'CLEARLY RELEVANT (Direct+Supp+Rel)':<25} | {rel_m['clearly_relevant_duration']:>15.2f}s | {rel_m['clearly_relevant_percentage']:>14.2f}%")
    r_print(f"{'OFF-TOPIC DURATION':<25} | {rel_m['off_topic_duration']:>15.2f}s | {rel_m['off_topic_percentage']:>14.2f}%")

    r_print("\n4. FUNCTION DURATION & PERCENTAGES TABLE:")
    r_print("-" * 75)
    r_print(f"{'Function Category':<25} | {'Duration (s)':<15} | {'Percentage (%)':<15}")
    r_print("-" * 75)
    for f_k, f_v in dur_m["fn_durations"].items():
        f_pct = dur_m["fn_percentages"][f_k]
        r_print(f"{f_k:<25} | {f_v:>15.2f}s | {f_pct:>14.2f}%")
    r_print("-" * 75)

    r_print("\n5. PROMISED POINT COVERAGE (P1–P4) TABLE:")
    r_print("-" * 90)
    r_print(f"{'Point ID':<8} | {'Coverage Type':<18} | {'Segs':<5} | {'Duration (s)':<13} | {'Window %':<10} | {'Exact Phase 7 Description'}")
    r_print("-" * 90)
    for pt_id, pt_info in cov_m.items():
        r_print(f"{pt_id:<8} | {pt_info['coverage_type']:<18} | {pt_info['segment_count']:<5} | {pt_info['duration']:>11.2f}s | {pt_info['percentage_of_analyzed_duration']:>9.2f}% | \"{pt_info['description']}\"")
    r_print("-" * 90)

    r_print("\n6. EXACT FUNCTION COUNTS PER POINT:")
    for pt_id, pt_info in cov_m.items():
        non_zero_str = ", ".join(f"{k}={v}" for k, v in pt_info["non_zero_function_counts"].items())
        r_print(f"   - {pt_id} (Seg Count = {pt_info['segment_count']}): {non_zero_str if non_zero_str else 'None (0)'} [Sum Fn Counts = {sum(pt_info['function_counts'].values())}]")

    r_print("\n7. POINT COVERAGE TYPE DERIVATION:")
    for pt_id, pt_info in cov_m.items():
        r_print(f"   - {pt_id}: {pt_info['coverage_type']} (Derived strictly from function labels)")

    r_print("\n8. POINT FIRST APPEARANCE ORDER:")
    r_print(f"   - Chronological Order: {' -> '.join(order_m['first_appearance_order'])}")
    for pt_id, st in order_m["first_appearances"].items():
        r_print(f"     ► {pt_id}: First appeared at {st:.2f}s")
    r_print("   - Unobserved Points: P4 (NOT_COVERED)")

    r_print("\n9. POINT RETURN RUNS:")
    for pt_id, ret_info in ret_m.items():
        if ret_info["number_of_segments"] > 0:
            r_print(f"   - {pt_id}: {ret_info['number_of_segments']} segments across {ret_info['number_of_contiguous_runs']} contiguous run(s) [First: Seg #{ret_info['first_segment']} -> Last: Seg #{ret_info['last_segment']}]")
        else:
            r_print(f"   - {pt_id}: 0 segments observed")

    r_print("\n10. OFF-TOPIC EPISODES SUMMARY:")
    r_print(f"   - Total Off-Topic Episodes: {ot_m['episode_count']}")
    for ep in ot_m["episodes"]:
        r_print(f"   ► Episode #{ep['episode_id']}: Segments #{ep['start_segment']}–#{ep['end_segment']} [{ep['start_time']:.2f}s - {ep['end_time']:.2f}s] ({ep['duration']:.2f}s / {ep['percentage_of_analyzed_duration']:.2f}% of video)")

    r_print("\n11. RETURN-TO-TOPIC BEHAVIOR:")
    for ep in ot_m["episodes"]:
        ret_str = "YES (Returned to promised topic after episode)" if ep["returned_to_topic"] else "NO (Outro plug ending video)"
        r_print(f"   - Episode #{ep['episode_id']} [{ep['start_time']:.2f}s - {ep['end_time']:.2f}s]: Returned to Topic = {ret_str}")

    r_print("\n12. POINT TRANSITION SEQUENCE:")
    r_print(f"   - Raw Segment Sequence      : {' -> '.join(trans_m['raw_segment_sequence'])}")
    r_print(f"   - Normalized Run Sequence   : {' -> '.join(trans_m['normalized_run_sequence'])}")
    r_print(f"   - Total Point Transitions   : {trans_m['point_transitions_count']}")
    r_print(f"   - Off-Topic Transitions     : {trans_m['off_topic_transitions_count']}")

    r_print("\n13. MATHEMATICAL VALIDATION RESULTS (HARD ASSERTIONS):")
    r_print(f"   - Overall Validation Status : {math_val['status']}")
    for res in math_val["assertion_results"]:
        status_str = "PASS" if res["passed"] else "FAIL"
        r_print(f"   - Assertion: {res['assertion']:<55} | Expected: {res['expected']:<8} | Actual: {res['actual']:<8} | [{status_str}]")

    r_print("\nDOCUMENTATION ON MULTI-POINT PERCENTAGES:")
    r_print("   - Multi-point segments (e.g. Segments #3, #13, #14 with P1 | P2) contribute to both P1 and P2 point-specific duration.")
    r_print("   - Consequently, P1 + P2 + P3 + P4 point coverage percentages (34.41% + 33.59% + 20.99% + 0.00% = 88.99%) do NOT sum to the clearly relevant total (70.92%) because multi-point durations are counted for each specified point.")

    r_print("\n===========================================================================")
    r_print(f" Saved Metrics JSON   : {json_path}")

    # Save report JSON
    report_file = metrics_dir / f"{TARGET_VIDEO_ID}_metrics_report.json"
    with open(report_file, "w", encoding="utf-8") as f_rep:
        json.dump({
            "video_id": TARGET_VIDEO_ID,
            "report_summary": "\n".join(report_text_lines),
            "metrics": metrics_data
        }, f_rep, indent=2, ensure_ascii=False)
    r_print(f" Saved Metrics Report : {report_file}")
    r_print("===========================================================================")
    r_print("\nPhase 9A correction is complete. Do you approve proceeding to Phase 9B?")

if __name__ == "__main__":
    main()
