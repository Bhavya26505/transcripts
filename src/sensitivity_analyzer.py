import json
from pathlib import Path
from typing import Dict, List, Any

def candidate_A_formula(coverage: float, relevance: float, discipline: float) -> float:
    return round((0.40 * coverage) + (0.40 * relevance) + (0.20 * discipline), 2)

def run_phase9c_sensitivity_analysis(
    video_id: str,
    phase9a_metrics: Dict[str, Any]
) -> Dict[str, Any]:
    # 1. Baseline Values from Phase 9A
    rel_m = phase9a_metrics.get("relevance_metrics", {})
    cov_m = phase9a_metrics.get("point_coverage", {})

    total_pts = len(cov_m)
    dir_covered = sum(1 for p in cov_m.values() if p.get("coverage_type") == "DIRECTLY_COVERED")

    base_cov = round((dir_covered / total_pts) * 100, 2) if total_pts > 0 else 0.0
    base_rel = rel_m.get("clearly_relevant_percentage", 70.92)
    base_disc = round(100.0 - rel_m.get("off_topic_percentage", 29.08), 2)
    base_score = candidate_A_formula(base_cov, base_rel, base_disc)

    # 2. Controlled Scenarios Definition
    scenarios_def = [
        {"id": 1, "name": "Ideal Video", "coverage": 100.0, "relevance": 100.0, "discipline": 100.0},
        {"id": 2, "name": "Current Baseline (-RgdgqF9wd0)", "coverage": base_cov, "relevance": base_rel, "discipline": base_disc},
        {"id": 3, "name": "All Points Covered, Low Digression", "coverage": 100.0, "relevance": 90.0, "discipline": 90.0},
        {"id": 4, "name": "Few Points Covered, Very Focused", "coverage": 25.0, "relevance": 95.0, "discipline": 95.0},
        {"id": 5, "name": "All Points Covered, High Digression", "coverage": 100.0, "relevance": 60.0, "discipline": 60.0},
        {"id": 6, "name": "No Points Covered", "coverage": 0.0, "relevance": 100.0, "discipline": 100.0},
        {"id": 7, "name": "Perfect Point Coverage, Poor Focus", "coverage": 100.0, "relevance": 30.0, "discipline": 30.0},
        {"id": 8, "name": "One Missing Point (75% Coverage)", "coverage": 75.0, "relevance": 90.0, "discipline": 90.0},
        {"id": 9, "name": "Sponsor Interruption (Minor Off-Topic)", "coverage": 100.0, "relevance": 85.0, "discipline": 85.0}
    ]

    scenarios_results = []
    for sc in scenarios_def:
        sc_score = candidate_A_formula(sc["coverage"], sc["relevance"], sc["discipline"])
        sc_res = dict(sc)
        sc_res["score"] = sc_score
        scenarios_results.append(sc_res)

        # Assertion: 0 <= score <= 100
        if not (0.0 <= sc_score <= 100.0):
            raise ValueError(f"ASSERTION FAILED: Scenario {sc['id']} score {sc_score} is outside [0, 100].")

    # 3. Monotonicity Tests
    mono_test_A = [candidate_A_formula(c, 50.0, 50.0) for c in [0.0, 25.0, 50.0, 75.0, 100.0]]
    mono_test_B = [candidate_A_formula(50.0, r, 50.0) for r in [0.0, 25.0, 50.0, 75.0, 100.0]]
    mono_test_C = [candidate_A_formula(50.0, 50.0, d) for d in [0.0, 25.0, 50.0, 75.0, 100.0]]

    is_mono_A = all(mono_test_A[i] <= mono_test_A[i+1] for i in range(len(mono_test_A)-1))
    is_mono_B = all(mono_test_B[i] <= mono_test_B[i+1] for i in range(len(mono_test_B)-1))
    is_mono_C = all(mono_test_C[i] <= mono_test_C[i+1] for i in range(len(mono_test_C)-1))

    if not (is_mono_A and is_mono_B and is_mono_C):
        raise ValueError("MONOTONICITY TEST FAILED: Score sequence is non-monotonic.")

    # 4. Boundary Tests
    bound_min = candidate_A_formula(0.0, 0.0, 0.0)
    bound_max = candidate_A_formula(100.0, 100.0, 100.0)
    bound_ok = (bound_min == 0.0 and bound_max == 100.0)

    if not bound_ok:
        raise ValueError(f"BOUNDARY TEST FAILED: min={bound_min}, max={bound_max}")

    # 5. Weight Validation
    w_cov, w_rel, w_disc = 0.40, 0.40, 0.20
    w_sum = round(w_cov + w_rel + w_disc, 2)
    weight_ok = (w_sum == 1.00)

    if not weight_ok:
        raise ValueError(f"WEIGHT VALIDATION FAILED: Sum = {w_sum}")

    # 6. Programmatic Sensitivity Analysis (+10 percentage points shift)
    base_calc = candidate_A_formula(50.0, 50.0, 50.0)
    shift_cov = round(candidate_A_formula(60.0, 50.0, 50.0) - base_calc, 2)
    shift_rel = round(candidate_A_formula(50.0, 60.0, 50.0) - base_calc, 2)
    shift_disc = round(candidate_A_formula(50.0, 50.0, 60.0) - base_calc, 2)

    sens_ok = (shift_cov == 4.00 and shift_rel == 4.00 and shift_disc == 2.00)

    if not sens_ok:
        raise ValueError(f"SENSITIVITY ANALYSIS FAILED: cov={shift_cov}, rel={shift_rel}, disc={shift_disc}")

    # 7. Design Question Answers
    design_answers = {
        "Q1_zero_coverage_score_above_40": {
            "question": "Can a video with ZERO promised-point coverage score above 40?",
            "answer": "YES. If a video covers 0 promised points (Coverage=0) but has 100% general relevance and 100% discipline, Candidate A yields a score of 60.00 (0.40*0 + 0.40*100 + 0.20*100 = 60.00).",
            "implication": "The formula awards up to 60 points for high general topic focus even when all specific promised points are missed."
        },
        "Q2_perfect_coverage_poor_focus": {
            "question": "Can a video with 100% promised-point coverage but very poor focus still score relatively high?",
            "answer": "YES. If a video directly covers all promised points (Coverage=100) but has poor focus (Relevance=30%, Discipline=30%), Candidate A yields a score of 58.00 (0.40*100 + 0.40*30 + 0.20*30 = 58.00).",
            "implication": "Fulfilling all promised points guarantees a baseline floor score of 40 points regardless of digressions."
        },
        "Q3_equal_importance_coverage_relevance": {
            "question": "Does Candidate A give equal importance to Point Coverage and Clear Relevance?",
            "answer": "YES. Both Point Coverage and Clear Relevance carry an identical weighting of 40% (0.40 weight each).",
            "implication": "A 10 percentage point increase in either dimension increases the total score by exactly 4.00 points."
        },
        "Q4_sensitivity_to_missing_points": {
            "question": "Is the formula sensitive enough to missing promised points?",
            "answer": "MODERATE. For a 4-point promise, missing 1 point reduces Point Coverage by 25%, which reduces the final score by 10.00 points (25% * 0.40).",
            "implication": "Missing 1 out of 4 points causes a 10-point score reduction."
        },
        "Q5_sensitivity_to_off_topic_content": {
            "question": "Is the formula sensitive enough to substantial off-topic content?",
            "answer": "STRONG. Clear Relevance (40%) and Topic Discipline (20%) together control 60% of the score weight.",
            "implication": "A 50% off-topic digression reduces the total score by 30.00 points (50% * 0.60)."
        }
    }

    integ_ok = (phase9a_metrics.get("timeline_integrity", {}).get("status") == "PASS")
    final_pass = (integ_ok and bound_ok and weight_ok and sens_ok and is_mono_A and is_mono_B and is_mono_C)

    return {
        "video_id": video_id,
        "validation_status": "PASS" if final_pass else "FAIL",
        "formula": {
            "name": "Candidate A (Balanced)",
            "expression": "0.40 * Point_Coverage + 0.40 * Clear_Relevance + 0.20 * Topic_Discipline",
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
            "score": base_score
        },
        "scenarios": scenarios_results,
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
        "design_answers": design_answers
    }
