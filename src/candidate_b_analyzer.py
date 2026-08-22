import json
from pathlib import Path
from typing import Dict, List, Any

def candidate_B_formula(coverage: float, relevance: float, discipline: float) -> float:
    return round((0.60 * coverage) + (0.25 * relevance) + (0.15 * discipline), 2)

def candidate_A_formula(coverage: float, relevance: float, discipline: float) -> float:
    return round((0.40 * coverage) + (0.40 * relevance) + (0.20 * discipline), 2)

def run_phase9d_candidate_b_analysis(
    video_id: str,
    phase9a_metrics: Dict[str, Any]
) -> Dict[str, Any]:
    # 1. Baseline Inputs from Phase 9A
    rel_m = phase9a_metrics.get("relevance_metrics", {})
    cov_m = phase9a_metrics.get("point_coverage", {})

    total_pts = len(cov_m)
    dir_covered = sum(1 for p in cov_m.values() if p.get("coverage_type") == "DIRECTLY_COVERED")

    base_cov = round((dir_covered / total_pts) * 100, 2) if total_pts > 0 else 0.0
    base_rel = rel_m.get("clearly_relevant_percentage", 70.92)
    base_disc = round(100.0 - rel_m.get("off_topic_percentage", 29.08), 2)

    base_score_B = candidate_B_formula(base_cov, base_rel, base_disc)
    base_score_A = candidate_A_formula(base_cov, base_rel, base_disc)

    # 2. Controlled Scenarios Definition
    scenarios_def = [
        {"id": 1, "name": "Ideal Video", "coverage": 100.0, "relevance": 100.0, "discipline": 100.0},
        {"id": 2, "name": "Current Baseline (-RgdgqF9wd0)", "coverage": base_cov, "relevance": base_rel, "discipline": base_disc},
        {"id": 3, "name": "All Points Covered, Low Digression", "coverage": 100.0, "relevance": 90.0, "discipline": 90.0},
        {"id": 4, "name": "Few Points Covered, Very Focused", "coverage": 25.0, "relevance": 95.0, "discipline": 95.0},
        {"id": 5, "name": "All Points Covered, High Digression", "coverage": 100.0, "relevance": 60.0, "discipline": 60.0},
        {"id": 6, "name": "No Points Covered, Perfect Focus", "coverage": 0.0, "relevance": 100.0, "discipline": 100.0},
        {"id": 7, "name": "Perfect Point Coverage, Poor Focus", "coverage": 100.0, "relevance": 30.0, "discipline": 30.0},
        {"id": 8, "name": "One Missing Point (75% Coverage)", "coverage": 75.0, "relevance": 90.0, "discipline": 90.0},
        {"id": 9, "name": "Sponsor Interruption (Minor Off-Topic)", "coverage": 100.0, "relevance": 85.0, "discipline": 85.0}
    ]

    scenarios_results = []
    for sc in scenarios_def:
        sc_score_B = candidate_B_formula(sc["coverage"], sc["relevance"], sc["discipline"])
        sc_score_A = candidate_A_formula(sc["coverage"], sc["relevance"], sc["discipline"])
        sc_res = dict(sc)
        sc_res["score_B"] = sc_score_B
        sc_res["score_A"] = sc_score_A
        sc_res["diff_B_minus_A"] = round(sc_score_B - sc_score_A, 2)
        scenarios_results.append(sc_res)

        if not (0.0 <= sc_score_B <= 100.0):
            raise ValueError(f"ASSERTION FAILED: Scenario {sc['id']} Candidate B score {sc_score_B} outside [0, 100].")

    # 3. Critical Promise-Coverage Maximum-Score Test (Relevance=100, Discipline=100)
    promise_coverage_table = []
    for cov_val in [0.0, 25.0, 50.0, 75.0, 100.0]:
        max_s = candidate_B_formula(cov_val, 100.0, 100.0)
        promise_coverage_table.append({
            "coverage": cov_val,
            "relevance": 100.0,
            "discipline": 100.0,
            "max_possible_score": max_s
        })

    # Verify 0% coverage max score == 40.00
    zero_cov_max = promise_coverage_table[0]["max_possible_score"]
    if zero_cov_max != 40.00:
        raise ValueError(f"CRITICAL PROMISE-COVERAGE TEST FAILED: 0% coverage max score is {zero_cov_max}, expected 40.00.")

    # 4. Critical Focus Penalty Test (Coverage=100)
    focus_penalty_table = []
    for f_val in [100.0, 80.0, 60.0, 40.0, 20.0, 0.0]:
        f_score = candidate_B_formula(100.0, f_val, f_val)
        focus_penalty_table.append({
            "coverage": 100.0,
            "relevance": f_val,
            "discipline": f_val,
            "score": f_score
        })

    # 5. Monotonicity Tests
    mono_test_A = [candidate_B_formula(c, 50.0, 50.0) for c in [0.0, 25.0, 50.0, 75.0, 100.0]]
    mono_test_B = [candidate_B_formula(50.0, r, 50.0) for r in [0.0, 25.0, 50.0, 75.0, 100.0]]
    mono_test_C = [candidate_B_formula(50.0, 50.0, d) for d in [0.0, 25.0, 50.0, 75.0, 100.0]]

    is_mono_A = all(mono_test_A[i] <= mono_test_A[i+1] for i in range(len(mono_test_A)-1))
    is_mono_B = all(mono_test_B[i] <= mono_test_B[i+1] for i in range(len(mono_test_B)-1))
    is_mono_C = all(mono_test_C[i] <= mono_test_C[i+1] for i in range(len(mono_test_C)-1))

    if not (is_mono_A and is_mono_B and is_mono_C):
        raise ValueError("MONOTONICITY TEST FAILED: Score sequence is non-monotonic.")

    # 6. Boundary Tests
    bound_min = candidate_B_formula(0.0, 0.0, 0.0)
    bound_max = candidate_B_formula(100.0, 100.0, 100.0)
    bound_ok = (bound_min == 0.0 and bound_max == 100.0)

    if not bound_ok:
        raise ValueError(f"BOUNDARY TEST FAILED: min={bound_min}, max={bound_max}")

    # 7. Weight Validation
    w_cov, w_rel, w_disc = 0.60, 0.25, 0.15
    w_sum = round(w_cov + w_rel + w_disc, 2)
    weight_ok = (w_sum == 1.00)

    if not weight_ok:
        raise ValueError(f"WEIGHT VALIDATION FAILED: Sum = {w_sum}")

    # 8. Programmatic Sensitivity Analysis (+10 percentage points shift)
    base_calc = candidate_B_formula(50.0, 50.0, 50.0)
    shift_cov = round(candidate_B_formula(60.0, 50.0, 50.0) - base_calc, 2)
    shift_rel = round(candidate_B_formula(50.0, 60.0, 50.0) - base_calc, 2)
    shift_disc = round(candidate_B_formula(50.0, 50.0, 60.0) - base_calc, 2)

    sens_ok = (shift_cov == 6.00 and shift_rel == 2.50 and shift_disc == 1.50)

    if not sens_ok:
        raise ValueError(f"SENSITIVITY ANALYSIS FAILED: cov={shift_cov}, rel={shift_rel}, disc={shift_disc}")

    # 9. Comparison Table Candidate A vs Candidate B
    comparison_table = [
        {"metric": "Baseline Score (-RgdgqF9wd0)", "candidate_A": base_score_A, "candidate_B": base_score_B, "diff": round(base_score_B - base_score_A, 2)},
        {"metric": "Zero-Point Maximum (Cov=0, Rel=100, Disc=100)", "candidate_A": 60.00, "candidate_B": 40.00, "diff": -20.00},
        {"metric": "Full-Coverage / Poor-Focus (Cov=100, Rel=30, Disc=30)", "candidate_A": 58.00, "candidate_B": 72.00, "diff": +14.00},
        {"metric": "One-Missing-Point (Cov=75, Rel=90, Disc=90)", "candidate_A": 84.00, "candidate_B": 81.00, "diff": -3.00},
        {"metric": "Few Points Covered, Very Focused (Cov=25, Rel=95, Disc=95)", "candidate_A": 67.00, "candidate_B": 53.00, "diff": -14.00}
    ]

    # 10. Design Question Answers
    design_answers = {
        "Q1_zero_coverage_max_score": {
            "question": "What is the maximum score when ZERO promised points are covered?",
            "answer": "EXACTLY 40.00. Under Candidate B, if Coverage=0%, maximum possible score even with 100% relevance and 100% discipline is 40.00 (0.60*0 + 0.25*100 + 0.15*100 = 40.00).",
            "implication": "Enforces a strict cap of 40 points when the creator fails to cover any promised points."
        },
        "Q2_few_points_covered_focused": {
            "question": "What happens when only 1/4 promised points are covered but the video is otherwise highly focused?",
            "answer": "Yields 53.00 (Scenario 4: Cov=25%, Rel=95%, Disc=95%).",
            "implication": "Candidate B prevents highly focused digression videos from receiving a passing adherence score when 75% of promised points are missed."
        },
        "Q3_response_to_missing_points": {
            "question": "How strongly does Candidate B respond to missing promised points?",
            "answer": "VERY STRONGLY. For a 4-point promise, missing 1 point reduces Point Coverage by 25%, causing a 15.00 point drop in final score (25% * 0.60 = 15.00).",
            "implication": "Each omitted opening promise applies a strict 15-point penalty."
        },
        "Q4_response_to_off_topic_content": {
            "question": "How strongly does Candidate B respond to off-topic content?",
            "answer": "MODERATE TO STRONG. Combined weight for Relevance (25%) and Discipline (15%) is 40%. A 50% off-topic digression reduces score by 20.00 points (50% * 0.40 = 20.00).",
            "implication": "Sponsor plugs and off-topic digressions are penalized fairly while prioritizing promise delivery."
        },
        "Q5_digression_penalty_under_full_coverage": {
            "question": "Does Candidate B preserve a meaningful penalty for severe digression even when all promised points are covered?",
            "answer": "YES. Even with 100% Point Coverage, if relevance and discipline drop to 0%, the score drops to 60.00 (Focus Penalty Test).",
            "implication": "Full promise coverage cannot completely eliminate severe off-topic penalties."
        },
        "Q6_missing_point_penalty_under_focused_content": {
            "question": "Does Candidate B preserve a meaningful penalty when promised points are missing even if the video is focused?",
            "answer": "YES. Missing 3/4 promised points (Cov=25%) caps the maximum achievable score at 55.00 regardless of perfect 100% focus.",
            "implication": "Focus alone cannot compensate for unfulfilled creator promises."
        },
        "Q7_monotonicity_verification": {
            "question": "Is the score monotonic for every dimension?",
            "answer": "YES. Verified programmatically across Coverage, Relevance, and Discipline sequences.",
            "implication": "Increasing any metric dimension strictly increases or maintains the final score."
        },
        "Q8_boundary_range_verification": {
            "question": "Does the formula remain bounded between 0 and 100?",
            "answer": "YES. Verified programmatically (Min=0.00 at (0,0,0) and Max=100.00 at (100,100,100)).",
            "implication": "100% mathematically valid bounds."
        }
    }

    integ_ok = (phase9a_metrics.get("timeline_integrity", {}).get("status") == "PASS")
    final_pass = (integ_ok and bound_ok and weight_ok and sens_ok and is_mono_A and is_mono_B and is_mono_C and zero_cov_max == 40.00)

    return {
        "video_id": video_id,
        "validation_status": "PASS" if final_pass else "FAIL",
        "formula": {
            "name": "Candidate B (Promise-First)",
            "expression": "0.60 * Point_Coverage + 0.25 * Clear_Relevance + 0.15 * Topic_Discipline",
            "weight_coverage": w_cov,
            "weight_relevance": w_rel,
            "weight_discipline": w_disc,
            "weight_sum": w_sum,
            "weight_sum_passed": weight_ok
        },
        "baseline": {
            "coverage": base_cov,
            "relevance": base_rel,
            "discipline": base_disc,
            "score_B": base_score_B,
            "score_A": base_score_A
        },
        "scenarios": scenarios_results,
        "promise_coverage_table": promise_coverage_table,
        "focus_penalty_table": focus_penalty_table,
        "monotonicity_tests": {
            "coverage_sequence": mono_test_A,
            "relevance_sequence": mono_test_B,
            "discipline_sequence": mono_test_C,
            "passed": is_mono_A and is_mono_B and is_mono_C
        },
        "boundary_tests": {
            "min_score_0_0_0": bound_min,
            "max_score_100_100_100": bound_max,
            "passed": bound_ok
        },
        "sensitivity_analysis": {
            "plus_10_coverage_effect": shift_cov,
            "plus_10_relevance_effect": shift_rel,
            "plus_10_discipline_effect": shift_disc,
            "passed": sens_ok
        },
        "comparison_candidate_A_vs_B": comparison_table,
        "design_answers": design_answers
    }
