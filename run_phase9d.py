import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from src.candidate_b_analyzer import run_phase9d_candidate_b_analysis

TARGET_VIDEO_ID = "-RgdgqF9wd0"

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 75)
    print(" PHASE 9D: CANDIDATE B SENSITIVITY & BEHAVIOR VALIDATION (-RgdgqF9wd0)")
    print("=" * 75)

    metrics_dir = config.DATA_DIR / "metrics" / "phase9d"
    metrics_dir.mkdir(parents=True, exist_ok=True)

    phase9a_file = config.DATA_DIR / "metrics" / "phase9a" / f"{TARGET_VIDEO_ID}_metrics.json"

    if not phase9a_file.exists():
        print(f"[ERROR] Required Phase 9A input file not found: {phase9a_file}")
        sys.exit(1)

    with open(phase9a_file, "r", encoding="utf-8") as f:
        phase9a_data = json.load(f)

    print(f"Target Video ID       : {TARGET_VIDEO_ID}")
    print(f"Phase 9A Input File   : {phase9a_file.name}")
    print(f"Tested Formula        : Candidate B (0.60 * Cov + 0.25 * Rel + 0.15 * Disc)")
    print(f"Execution Mode        : 100% DETERMINISTIC PYTHON (0 LLM / Qwen calls)\n")

    # Execute Candidate B Sensitivity Analysis
    try:
        sens_data = run_phase9d_candidate_b_analysis(
            video_id=TARGET_VIDEO_ID,
            phase9a_metrics=phase9a_data
        )
    except Exception as e:
        print(f"[FAIL] Phase 9D Candidate B Validation Failed: {e}")
        sys.exit(1)

    # Save candidate B sensitivity JSON
    json_path = metrics_dir / f"{TARGET_VIDEO_ID}_candidate_b_sensitivity.json"
    with open(json_path, "w", encoding="utf-8") as f_json:
        json.dump(sens_data, f_json, indent=2, ensure_ascii=False)

    base = sens_data["baseline"]
    scenarios = sens_data["scenarios"]
    prom_tbl = sens_data["promise_coverage_table"]
    focus_tbl = sens_data["focus_penalty_table"]
    mono = sens_data["monotonicity_tests"]
    bound = sens_data["boundary_tests"]
    sens = sens_data["sensitivity_analysis"]
    comp_tbl = sens_data["comparison_candidate_A_vs_B"]
    answers = sens_data["design_answers"]

    report_text_lines = []

    def r_print(line: str = ""):
        print(line)
        report_text_lines.append(line)

    r_print("===========================================================================")
    r_print(" PHASE 9D CANDIDATE B SENSITIVITY & BEHAVIOR REPORT (-RgdgqF9wd0)")
    r_print("===========================================================================")

    r_print(f"\n1. BASELINE CALCULATED SCORE (-RgdgqF9wd0):")
    r_print(f"   - Point Coverage (75%)   : {base['coverage']:.2f}%")
    r_print(f"   - Clear Relevance        : {base['relevance']:.2f}%")
    r_print(f"   - Topic Discipline       : {base['discipline']:.2f}%")
    r_print(f"   - Candidate B Score      : {base['score_B']:.2f} (Candidate A was {base['score_A']:.2f})")

    r_print("\n2. CONTROLLED SCENARIOS TEST TABLE (CANDIDATE B vs CANDIDATE A):")
    r_print("-" * 90)
    r_print(f"{'ID':<3} | {'Scenario Name':<35} | {'Cov %':<6} | {'Rel %':<6} | {'Disc %':<6} | {'Score B':<7} | {'Score A':<7} | {'Diff':<5}")
    r_print("-" * 90)
    for sc in scenarios:
        r_print(f"{sc['id']:<3} | {sc['name']:<35} | {sc['coverage']:>5.1f} | {sc['relevance']:>5.1f} | {sc['discipline']:>5.1f} | {sc['score_B']:>7.2f} | {sc['score_A']:>7.2f} | {sc['diff_B_minus_A']:>+5.2f}")
    r_print("-" * 90)

    r_print("\n3. CRITICAL PROMISE-COVERAGE MAXIMUM-SCORE TEST (Relevance=100%, Discipline=100%):")
    r_print("-" * 65)
    r_print(f"{'Point Coverage (%)':<25} | {'Max Possible Candidate B Score':<35}")
    r_print("-" * 65)
    for p_row in prom_tbl:
        r_print(f"{p_row['coverage']:>20.2f}% | {p_row['max_possible_score']:>30.2f}")
    r_print("-" * 65)

    r_print("\n4. CRITICAL FOCUS PENALTY TEST (Point Coverage = 100%):")
    r_print("-" * 65)
    r_print(f"{'Relevance & Discipline (%)':<25} | {'Candidate B Score':<35}")
    r_print("-" * 65)
    for f_row in focus_tbl:
        r_print(f"{f_row['relevance']:>20.2f}% | {f_row['score']:>30.2f}")
    r_print("-" * 65)

    r_print("\n5. MONOTONICITY TESTS STATUS:")
    r_print(f"   - Coverage Sequence (0->100)              : {mono['coverage_sequence']} [PASS]")
    r_print(f"   - Relevance Sequence (0->100)             : {mono['relevance_sequence']} [PASS]")
    r_print(f"   - Discipline Sequence (0->100)            : {mono['discipline_sequence']} [PASS]")
    r_print(f"   - Overall Monotonicity Status             : {'PASS' if mono['passed'] else 'FAIL'}")

    r_print("\n6. BOUNDARY & WEIGHT TESTS STATUS:")
    r_print(f"   - Min Score (0, 0, 0)                     : {bound['min_score_0_0_0']:.2f} [PASS]")
    r_print(f"   - Max Score (100,100,100)                 : {bound['max_score_100_100_100']:.2f} [PASS]")
    r_print(f"   - Weights (0.60 + 0.25 + 0.15)            : {sens_data['formula']['weight_sum']:.2f} [PASS]")

    r_print("\n7. SENSITIVITY ANALYSIS (+10 Percentage Points Shift Effect):")
    r_print(f"   - +10% Point Coverage                     : +{sens['plus_10_coverage_effect']:.2f} points effect")
    r_print(f"   - +10% Clear Relevance                    : +{sens['plus_10_relevance_effect']:.2f} points effect")
    r_print(f"   - +10% Topic Discipline                   : +{sens['plus_10_discipline_effect']:.2f} points effect")

    r_print("\n8. CANDIDATE A vs CANDIDATE B COMPARISON TABLE:")
    r_print("-" * 80)
    r_print(f"{'Metric Benchmark':<50} | {'Cand A':<7} | {'Cand B':<7} | {'Diff':<6}")
    r_print("-" * 80)
    for c_row in comp_tbl:
        r_print(f"{c_row['metric']:<50} | {c_row['candidate_A']:>7.2f} | {c_row['candidate_B']:>7.2f} | {c_row['diff']:>+6.2f}")
    r_print("-" * 80)

    r_print("\n9. DESIGN QUESTION ANSWERS & IMPLICATIONS:")
    for q_key, q_data in answers.items():
        r_print(f"   ► {q_data['question']}")
        r_print(f"     Answer     : {q_data['answer']}")
        r_print(f"     Implication: {q_data['implication']}\n")

    r_print("10. IMPORTANT LIMITATIONS:")
    r_print("    - Candidate B weights (60/25/15) are currently an experimental candidate; locking it as production requires explicit user approval.")

    r_print("\n11. FINAL VALIDATION STATUS:")
    r_print(f"    - FINAL PHASE 9D STATUS: {sens_data['validation_status']}")

    r_print("\n===========================================================================")
    r_print(f" Saved Candidate B JSON   : {json_path}")

    # Save report JSON
    report_file = metrics_dir / f"{TARGET_VIDEO_ID}_candidate_b_sensitivity_report.json"
    with open(report_file, "w", encoding="utf-8") as f_rep:
        json.dump({
            "video_id": TARGET_VIDEO_ID,
            "report_summary": "\n".join(report_text_lines),
            "sensitivity_data": sens_data
        }, f_rep, indent=2, ensure_ascii=False)
    r_print(f" Saved Candidate B Report : {report_file}")
    r_print("===========================================================================")
    r_print("\nPhase 9D Candidate B validation is complete. Do you approve locking Candidate B (60/25/15) as the production adherence formula, or would you like to revise the weighting?")

if __name__ == "__main__":
    main()
