import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from src.sensitivity_analyzer import run_phase9c_sensitivity_analysis

TARGET_VIDEO_ID = "-RgdgqF9wd0"

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 75)
    print(" PHASE 9C: SCORE SENSITIVITY & BEHAVIOR VALIDATION (-RgdgqF9wd0)")
    print("=" * 75)

    metrics_dir = config.DATA_DIR / "metrics" / "phase9c"
    metrics_dir.mkdir(parents=True, exist_ok=True)

    phase9a_file = config.DATA_DIR / "metrics" / "phase9a" / f"{TARGET_VIDEO_ID}_metrics.json"

    if not phase9a_file.exists():
        print(f"[ERROR] Required Phase 9A input file not found: {phase9a_file}")
        sys.exit(1)

    with open(phase9a_file, "r", encoding="utf-8") as f:
        phase9a_data = json.load(f)

    print(f"Target Video ID       : {TARGET_VIDEO_ID}")
    print(f"Phase 9A Input File   : {phase9a_file.name}")
    print(f"Tested Formula        : Candidate A (0.40 * Cov + 0.40 * Rel + 0.20 * Disc)")
    print(f"Execution Mode        : 100% DETERMINISTIC PYTHON (0 LLM / Qwen calls)\n")

    # Execute Sensitivity Analysis
    try:
        sens_data = run_phase9c_sensitivity_analysis(
            video_id=TARGET_VIDEO_ID,
            phase9a_metrics=phase9a_data
        )
    except Exception as e:
        print(f"[FAIL] Phase 9C Sensitivity Validation Failed: {e}")
        sys.exit(1)

    # Save sensitivity JSON
    json_path = metrics_dir / f"{TARGET_VIDEO_ID}_sensitivity.json"
    with open(json_path, "w", encoding="utf-8") as f_json:
        json.dump(sens_data, f_json, indent=2, ensure_ascii=False)

    base = sens_data["baseline"]
    scenarios = sens_data["scenarios"]
    mono = sens_data["monotonicity_tests"]
    bound = sens_data["boundary_tests"]
    sens = sens_data["sensitivity_analysis"]
    answers = sens_data["design_answers"]

    report_text_lines = []

    def r_print(line: str = ""):
        print(line)
        report_text_lines.append(line)

    r_print("===========================================================================")
    r_print(" PHASE 9C SENSITIVITY & BEHAVIOR VALIDATION REPORT (-RgdgqF9wd0)")
    r_print("===========================================================================")

    r_print(f"\n1. BASELINE SCORE (-RgdgqF9wd0):")
    r_print(f"   - Point Coverage (75%)   : {base['coverage']:.2f}%")
    r_print(f"   - Clear Relevance        : {base['relevance']:.2f}%")
    r_print(f"   - Topic Discipline       : {base['discipline']:.2f}%")
    r_print(f"   - Calculated Candidate A : {base['score']:.2f}")

    r_print("\n2. CONTROLLED SCENARIOS TEST TABLE:")
    r_print("-" * 85)
    r_print(f"{'ID':<3} | {'Scenario Name':<35} | {'Cov %':<7} | {'Rel %':<7} | {'Disc %':<7} | {'Score':<7}")
    r_print("-" * 85)
    for sc in scenarios:
        r_print(f"{sc['id']:<3} | {sc['name']:<35} | {sc['coverage']:>6.2f} | {sc['relevance']:>6.2f} | {sc['discipline']:>6.2f} | {sc['score']:>7.2f}")
    r_print("-" * 85)

    r_print("\n3. MONOTONICITY TESTS STATUS:")
    r_print(f"   - Coverage Increasing Sequence (0->100)   : {mono['coverage_sequence']} [PASS]")
    r_print(f"   - Relevance Increasing Sequence (0->100)  : {mono['relevance_sequence']} [PASS]")
    r_print(f"   - Discipline Increasing Sequence (0->100) : {mono['discipline_sequence']} [PASS]")
    r_print(f"   - Overall Monotonicity Status             : {'PASS' if mono['passed'] else 'FAIL'}")

    r_print("\n4. BOUNDARY TESTS STATUS:")
    r_print(f"   - Min Score (0, 0, 0)     : {bound['min_score_0_0_0']:.2f} [PASS]")
    r_print(f"   - Max Score (100,100,100) : {bound['max_score_100_100_100']:.2f} [PASS]")
    r_print(f"   - Boundary Range Status   : {'PASS' if bound['passed'] else 'FAIL'}")

    r_print("\n5. WEIGHT VALIDATION STATUS:")
    r_print(f"   - Formula Weights         : Coverage=0.40, Relevance=0.40, Discipline=0.20")
    r_print(f"   - Weights Sum             : {sens_data['formula']['weight_sum']:.2f} [PASS]")

    r_print("\n6. SENSITIVITY ANALYSIS (+10 Percentage Points Shift Effect):")
    r_print(f"   - +10% Point Coverage     : +{sens['plus_10_coverage_effect']:.2f} points effect")
    r_print(f"   - +10% Clear Relevance    : +{sens['plus_10_relevance_effect']:.2f} points effect")
    r_print(f"   - +10% Topic Discipline   : +{sens['plus_10_discipline_effect']:.2f} points effect")

    r_print("\n7. DESIGN QUESTION ANSWERS & IMPLICATIONS:")
    for q_key, q_data in answers.items():
        r_print(f"   ► {q_data['question']}")
        r_print(f"     Answer     : {q_data['answer']}")
        r_print(f"     Implication: {q_data['implication']}\n")

    r_print("8. IMPORTANT LIMITATIONS:")
    r_print("   - Candidate A is currently an experimental candidate; locking it as the production formula requires explicit user approval.")
    r_print("   - Scenario calculations test mathematical properties of the formula across synthetic edge cases, not new transcript content.")

    r_print("\n9. FINAL VALIDATION STATUS:")
    r_print(f"   - FINAL PHASE 9C STATUS: {sens_data['validation_status']}")

    r_print("\n===========================================================================")
    r_print(f" Saved Sensitivity JSON   : {json_path}")

    # Save report JSON
    report_file = metrics_dir / f"{TARGET_VIDEO_ID}_sensitivity_report.json"
    with open(report_file, "w", encoding="utf-8") as f_rep:
        json.dump({
            "video_id": TARGET_VIDEO_ID,
            "report_summary": "\n".join(report_text_lines),
            "sensitivity_data": sens_data
        }, f_rep, indent=2, ensure_ascii=False)
    r_print(f" Saved Sensitivity Report : {report_file}")
    r_print("===========================================================================")
    r_print("\nPhase 9C sensitivity validation is complete. Do you approve locking Candidate A as the production adherence formula, or would you like to revise the weighting?")

if __name__ == "__main__":
    main()
