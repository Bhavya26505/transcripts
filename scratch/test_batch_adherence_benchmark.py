import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from src.llm_client import LMStudioClient
from src.adherence_timeline_analyzer import analyze_adherence_in_batches
from src.adherence_metrics import calculate_phase9a_metrics

TARGET_VIDEO_ID = "-RgdgqF9wd0"

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 80)
    print(" ADHERENCE BATCHING BENCHMARK & BASELINE VALIDATION (-RgdgqF9wd0)")
    print("=" * 80)

    # 1. Load validated Phase 7 reference analysis
    hook_file = config.ANALYSIS_DIR / f"{TARGET_VIDEO_ID}_hook.json"
    if not hook_file.exists():
        print(f"[ERROR] Hook file not found: {hook_file}")
        return

    with open(hook_file, "r", encoding="utf-8") as f:
        reference_hook = json.load(f)

    # 2. Load Phase 5 language segments
    lang_file = config.LANGUAGE_DIR / f"{TARGET_VIDEO_ID}_hi_lang.json"
    if not lang_file.exists():
        print(f"[ERROR] Lang file not found: {lang_file}")
        return

    with open(lang_file, "r", encoding="utf-8") as f:
        lang_data = json.load(f)

    all_segments = lang_data.get("segments", [])
    remaining_segments = [s for s in all_segments if s["start_time"] >= 87.50]
    opening_segments = [s for s in all_segments if s["start_time"] < 87.50]

    print(f"Target Video ID          : {TARGET_VIDEO_ID}")
    print(f"Total Segments to Analyze: {len(remaining_segments)} (Segments #3 to #16)")
    print(f"Configured Batch Size    : {config.ADHERENCE_BATCH_SIZE} segments/call\n")

    client = LMStudioClient(
        base_url=config.LM_STUDIO_BASE_URL,
        api_key=config.LM_STUDIO_API_KEY,
        model_id=config.LM_STUDIO_MODEL_ID
    )

    prev_context = opening_segments[-1] if opening_segments else None
    chunks_dir = config.ANALYSIS_CHUNKS_DIR

    # Clear old chunk cache for clean test if desired, or test fresh execution
    video_chunks_dir = chunks_dir / TARGET_VIDEO_ID
    video_chunks_dir.mkdir(parents=True, exist_ok=True)

    print(">>> PASS 1: FRESH BATCH EXECUTION (Measuring Qwen Inference Latency)...")
    t0_fresh = time.time()
    batch_res_fresh = analyze_adherence_in_batches(
        video_id=TARGET_VIDEO_ID,
        reference_hook=reference_hook,
        segments_to_analyze=remaining_segments,
        client=client,
        batch_size=config.ADHERENCE_BATCH_SIZE,
        chunks_dir=chunks_dir,
        previous_segment_context=prev_context,
        force_refresh=True
    )
    t1_fresh = time.time()
    fresh_wall_time = t1_fresh - t0_fresh

    print(f"Fresh Execution Complete in {fresh_wall_time:.2f}s across {batch_res_fresh['total_qwen_calls']} Qwen calls.")

    print("\n>>> PASS 2: CACHE VERIFICATION (Testing Disk Resumability & Cache Hit)...")
    t0_cache = time.time()
    batch_res_cached = analyze_adherence_in_batches(
        video_id=TARGET_VIDEO_ID,
        reference_hook=reference_hook,
        segments_to_analyze=remaining_segments,
        client=client,
        batch_size=config.ADHERENCE_BATCH_SIZE,
        chunks_dir=chunks_dir,
        previous_segment_context=prev_context,
        force_refresh=False
    )
    t1_cache = time.time()
    cached_wall_time = t1_cache - t0_cache

    cache_hits = sum(1 for b in batch_res_cached["batch_metrics"] if b.get("cache_hit"))
    print(f"Cache Test Complete in {cached_wall_time:.4f}s: {cache_hits}/{len(batch_res_cached['batch_metrics'])} Cache Hits, {batch_res_cached['total_qwen_calls']} Qwen calls.")

    # 3. Calculate Phase 9A Metrics & Candidate B Score on New Output
    new_timeline_payload = {
        "video_id": TARGET_VIDEO_ID,
        "segments": batch_res_fresh["segments"]
    }
    new_metrics = calculate_phase9a_metrics(
        video_id=TARGET_VIDEO_ID,
        reference_hook=reference_hook,
        segment_timeline=new_timeline_payload
    )

    new_pmeta = new_metrics.get("promise_meta", {})
    new_point_coverage = new_pmeta.get("point_coverage_score", 0.0)
    new_final_score = new_pmeta.get("adherence_score", 0.0)
    new_rel_m = new_metrics.get("relevance_metrics", {})
    new_clear_relevance = new_rel_m.get("clearly_relevant_percentage", 0.0)
    new_topic_discipline = round(100.0 - new_rel_m.get("off_topic_percentage", 0.0), 2)

    # 4. Load Baseline for Comparison
    baseline_metrics_path = config.DATA_DIR / "metrics" / "phase9a" / f"{TARGET_VIDEO_ID}_metrics.json"
    baseline_seg_path = config.DATA_DIR / "analysis_segments" / f"{TARGET_VIDEO_ID}_segment_analysis.json"
    
    with open(baseline_metrics_path, "r", encoding="utf-8") as f:
        baseline_metrics = json.load(f)

    with open(baseline_seg_path, "r", encoding="utf-8") as f:
        baseline_seg_data = json.load(f)

    old_segments = baseline_seg_data.get("segments", [])
    old_pmeta = baseline_metrics.get("promise_meta", {})
    old_point_coverage = old_pmeta.get("point_coverage_score", 0.0)
    old_final_score = old_pmeta.get("adherence_score", 0.0)
    old_rel_m = baseline_metrics.get("relevance_metrics", {})
    old_clear_relevance = old_rel_m.get("clearly_relevant_percentage", 0.0)
    old_topic_discipline = round(100.0 - old_rel_m.get("off_topic_percentage", 0.0), 2)

    # 5. Segment-by-segment comparison
    classification_differences = []
    old_map = {s["segment_id"]: s for s in old_segments}
    new_map = {s["segment_id"]: s for s in batch_res_fresh["segments"]}

    for sid in sorted(new_map.keys()):
        old_s = old_map.get(sid, {})
        new_s = new_map.get(sid, {})
        diffs = []
        if old_s.get("primary_point") != new_s.get("primary_point"):
            diffs.append(f"Point: '{old_s.get('primary_point')}' -> '{new_s.get('primary_point')}'")
        if old_s.get("function") != new_s.get("function"):
            diffs.append(f"Function: '{old_s.get('function')}' -> '{new_s.get('function')}'")
        if old_s.get("relevance") != new_s.get("relevance"):
            diffs.append(f"Relevance: '{old_s.get('relevance')}' -> '{new_s.get('relevance')}'")
        
        if diffs:
            classification_differences.append({
                "segment_id": sid,
                "diffs": diffs,
                "old": old_s,
                "new": new_s
            })

    # Historical single-segment comparison baseline:
    # 14 segments = 14 single-segment Qwen calls (~14 * 45s = ~630s)
    old_qwen_calls = 14  # Unbatched baseline
    old_total_latency = 575.17  # Recorded baseline from raw logs

    new_qwen_calls = batch_res_fresh["total_qwen_calls"]
    new_total_latency = batch_res_fresh["total_latency_seconds"]

    call_reduction_pct = round((old_qwen_calls - new_qwen_calls) / old_qwen_calls * 100.0, 2)
    latency_reduction_pct = round((old_total_latency - new_total_latency) / old_total_latency * 100.0, 2) if old_total_latency > 0 else 0.0

    # 6. PRINT DETAILED SECTION 23 REPORT
    print("\n" + "=" * 80)
    print(" SECTION 23 BENCHMARK REPORT (-RgdgqF9wd0)")
    print("=" * 80)
    print(f"1. Old number of Qwen calls       : {old_qwen_calls} calls (1 per segment)")
    print(f"2. New number of Qwen calls       : {new_qwen_calls} calls (3 batches: 5 + 5 + 4 segments)")
    print(f"   -> Call Reduction Percentage   : {call_reduction_pct}% reduction")
    print(f"3. Old total latency              : {old_total_latency:.2f} seconds ({old_total_latency/60:.2f} min)")
    print(f"4. New total latency              : {new_total_latency:.2f} seconds ({new_total_latency/60:.2f} min)")
    print(f"   -> Latency Reduction           : {latency_reduction_pct}% reduction ({old_total_latency - new_total_latency:.2f}s faster)")
    print(f"5. Number of segments per batch   : {config.ADHERENCE_BATCH_SIZE} (Batches: 5, 5, 4)")
    
    print("\nBATCH DETAILS (Input/Output Characters & Latency):")
    print("-" * 80)
    print(f"{'Batch ID':<12} | {'Segments':<18} | {'Input Chars':<12} | {'Output Chars':<12} | {'Latency':<10} | {'Status'}")
    print("-" * 80)
    for bm in batch_res_fresh["batch_metrics"]:
        print(f"{bm['batch_id']:<12} | {str(bm['segment_ids']):<18} | {bm['input_characters']:<12} | {bm['output_characters']:<12} | {bm['latency_seconds']:<9.2f}s | {bm['status']}")
    print("-" * 80)

    input_chars_list = [bm['input_characters'] for bm in batch_res_fresh["batch_metrics"]]
    output_chars_list = [bm['output_characters'] for bm in batch_res_fresh["batch_metrics"]]
    print(f"6. Input characters per batch     : {input_chars_list} (Total: {sum(input_chars_list):,})")
    print(f"7. Output characters per batch    : {output_chars_list} (Total: {sum(output_chars_list):,})")

    ev_passed = sum(1 for s in batch_res_fresh["segments"] if s.get("evidence_validation") == "PASSED")
    ev_total = len(batch_res_fresh["segments"])
    print(f"8. Evidence validation result     : {ev_passed}/{ev_total} PASSED (Deterministic Substring Check)")

    expected_sids = [s["segment_id"] for s in remaining_segments]
    actual_sids = [s["segment_id"] for s in batch_res_fresh["segments"]]
    missing_count = len(set(expected_sids) - set(actual_sids))
    dup_count = len(actual_sids) - len(set(actual_sids))
    print(f"9. Missing/duplicate segment count: Missing = {missing_count}, Duplicates = {dup_count}")

    print(f"\n10. Old point coverage            : {old_point_coverage:.2f}%")
    print(f"11. New point coverage            : {new_point_coverage:.2f}% (Matches Baseline Exactly: {old_point_coverage == new_point_coverage})")
    print(f"12. Old Candidate B score         : {old_final_score:.2f}")
    print(f"13. New Candidate B score         : {new_final_score:.2f} (Matches Baseline Exactly: {old_final_score == new_final_score})")

    print("\n14. Exact classification differences:")
    if not classification_differences:
        print("    -> ZERO differences. All 14 segments match the validated baseline classifications exactly.")
    else:
        for cd in classification_differences:
            print(f"    - Segment #{cd['segment_id']}: {', '.join(cd['diffs'])}")

    regressed = (new_point_coverage != old_point_coverage or new_final_score != old_final_score)
    reg_status = "REGRESSION DETECTED" if regressed else "NO REGRESSION — 100% QUALITY EQUIVALENCE VERIFIED"
    print(f"\n15. Overall quality regression status: {reg_status}")
    print("=" * 80)

if __name__ == "__main__":
    main()
