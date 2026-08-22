import json
import sys
from pathlib import Path

from src.phase10_pipeline import run_production_pipeline_for_video

def main():
    print("=" * 80)
    print(" PHASE 10B — NO-PROMISE HANDLING DETERMINISTIC VALIDATION")
    print("=" * 80)

    # Test set: 5 Phase 10 validation videos + baseline video -RgdgqF9wd0
    test_videos = ["-ckuMh4Px9M", "0xNCJH5161s", "1jnEhDmvQbk", "1l37N5wcDgs", "1sVOwYhItqk", "-RgdgqF9wd0"]

    results = {}
    assertions_passed = True
    assertion_logs = []

    for vid in test_videos:
        res = run_production_pipeline_for_video(video_id=vid)
        results[vid] = res

    print("\nPROCESSED VIDEO RESULTS:")
    print("-" * 80)
    print(f"{'Video ID':<15} | {'Promise Status':<20} | {'Pts':<4} | {'Cov Status':<15} | {'Cov %':<8} | {'Score':<8}")
    print("-" * 80)

    for vid, r in results.items():
        p_status = r["promise_meta"]["promise_status"] if "promise_meta" in r else r["promise_status"]
        p_cnt = r["promised_points_count"]
        c_status = r["point_coverage_status"]
        cov = r["point_coverage"]
        score = r["adherence_score"]["final_score"] if isinstance(r["adherence_score"], dict) else r["adherence_score"]

        cov_str = f"{cov:.2f}%" if cov is not None else "N/A"
        score_str = f"{score:.2f}" if score is not None else "N/A"

        print(f"{vid:<15} | {p_status:<20} | {p_cnt:<4} | {c_status:<15} | {cov_str:<8} | {score_str:<8}")

    print("-" * 80)

    # ---------------------------------------------------------
    # PROGRAMMATIC HARD ASSERTIONS
    # ---------------------------------------------------------
    def check_assertion(name: str, condition: bool, detail: str = ""):
        nonlocal assertions_passed
        if condition:
            assertion_logs.append(f" [PASS] {name}")
        else:
            assertions_passed = False
            assertion_logs.append(f" [FAIL] {name} - {detail}")

    # Assertion 1: Zero promised points NEVER produce point_coverage == 0
    zero_promise_vids = [v for v, r in results.items() if r["promised_points_count"] == 0]
    check_assertion(
        "Assertion 1: Zero promised points NEVER produce point_coverage == 0",
        all(results[v]["point_coverage"] != 0 for v in zero_promise_vids),
        f"Found 0 coverage in zero-promise vids: {[v for v in zero_promise_vids if results[v]['point_coverage'] == 0]}"
    )

    # Assertion 2: Zero promised points NEVER produce point_coverage == 100
    check_assertion(
        "Assertion 2: Zero promised points NEVER produce point_coverage == 100",
        all(results[v]["point_coverage"] != 100 for v in zero_promise_vids),
        f"Found 100 coverage in zero-promise vids: {[v for v in zero_promise_vids if results[v]['point_coverage'] == 100]}"
    )

    # Assertion 3: Zero promised points produce point_coverage is None
    check_assertion(
        "Assertion 3: Zero promised points produce point_coverage is None",
        all(results[v]["point_coverage"] is None for v in zero_promise_vids),
        f"Non-None point_coverage found in zero-promise vids"
    )

    # Assertion 4: Zero promised points produce point_coverage_status == 'NOT_APPLICABLE'
    check_assertion(
        "Assertion 4: Zero promised points produce point_coverage_status == 'NOT_APPLICABLE'",
        all(results[v]["point_coverage_status"] == "NOT_APPLICABLE" for v in zero_promise_vids),
        f"Incorrect point_coverage_status found"
    )

    # Assertion 5: Zero promised points produce adherence_score is None
    check_assertion(
        "Assertion 5: Zero promised points produce adherence_score is None",
        all(results[v]["adherence_score"]["final_score"] is None for v in zero_promise_vids),
        f"Non-None adherence_score found in zero-promise vids"
    )

    # Assertion 6: Videos with promised points > 0 still calculate Candidate B normally
    promised_vids = [v for v, r in results.items() if r["promised_points_count"] > 0]
    check_assertion(
        "Assertion 6: Videos with promised points > 0 still calculate Candidate B normally",
        all(results[v]["adherence_score"]["final_score"] is not None and results[v]["point_coverage"] is not None for v in promised_vids),
        f"Promised videos missing scores"
    )

    # Assertion 7: Baseline video -RgdgqF9wd0 regression test (Coverage = 75.00%, Score = 73.37)
    rgd = results["-RgdgqF9wd0"]
    rgd_cov_ok = (rgd["point_coverage"] == 75.0)
    rgd_score_ok = (rgd["adherence_score"]["final_score"] == 73.37)
    check_assertion(
        "Assertion 7: -RgdgqF9wd0 baseline regression (Coverage = 75.00%, Score = 73.37)",
        rgd_cov_ok and rgd_score_ok,
        f"Actual coverage: {rgd['point_coverage']}, actual score: {rgd['adherence_score']['final_score']}"
    )

    # Assertion 8: Candidate B weights remain 0.60 / 0.25 / 0.15
    check_assertion(
        "Assertion 8: Candidate B weights remain 0.60 / 0.25 / 0.15",
        all(r["adherence_score"]["point_coverage_weight"] == 0.60 and
            r["adherence_score"]["clear_relevance_weight"] == 0.25 and
            r["adherence_score"]["topic_discipline_weight"] == 0.15 for v, r in results.items()),
        "Candidate B weights altered"
    )

    # Assertion 9: Number of new Qwen / LLM calls == 0
    total_llm_calls = sum(r["performance"]["llm_calls_count"] for v, r in results.items())
    check_assertion(
        "Assertion 9: Number of new Qwen / LLM calls == 0",
        total_llm_calls == 0,
        f"Total LLM calls made: {total_llm_calls}"
    )

    # Assertion 10: Existing timeline/relevance/discipline metrics remain unchanged
    check_assertion(
        "Assertion 10: Existing timeline/relevance/discipline metrics remain unchanged",
        all(r["validation"]["timeline_integrity"] and r["validation"]["metric_integrity"] for v, r in results.items()),
        "Validation status failed for metrics/timeline integrity"
    )

    print("\nHARD ASSERTIONS RESULTS:")
    print("-" * 80)
    for log in assertion_logs:
        print(log)
    print("-" * 80)

    if assertions_passed:
        print("\nOVERALL PHASE 10B VALIDATION STATUS: PASS")
    else:
        print("\nOVERALL PHASE 10B VALIDATION STATUS: FAIL")

    return assertions_passed

if __name__ == "__main__":
    main()
