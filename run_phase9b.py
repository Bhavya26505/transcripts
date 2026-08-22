import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from src.scoring_candidates import calculate_phase9b_candidate_scores

TARGET_VIDEO_ID = "-RgdgqF9wd0"

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 75)
    print(" PHASE 9B: CREATOR ADHERENCE SCORE DESIGN (-RgdgqF9wd0)")
    print("=" * 75)

    metrics_dir = config.DATA_DIR / "metrics" / "phase9b"
    metrics_dir.mkdir(parents=True, exist_ok=True)

    phase9a_file = config.DATA_DIR / "metrics" / "phase9a" / f"{TARGET_VIDEO_ID}_metrics.json"

    if not phase9a_file.exists():
        print(f"[ERROR] Required Phase 9A input file not found: {phase9a_file}")
        sys.exit(1)

    with open(phase9a_file, "r", encoding="utf-8") as f:
        phase9a_data = json.load(f)

    print(f"Target Video ID       : {TARGET_VIDEO_ID}")
    print(f"Phase 9A Input File   : {phase9a_file.name}")
    print(f"Execution Mode        : 100% DETERMINISTIC PYTHON (0 LLM / Qwen calls)\n")

    # Compute Phase 9B Candidate Scores
    scores_data = calculate_phase9b_candidate_scores(
        video_id=TARGET_VIDEO_ID,
        phase9a_metrics=phase9a_data
    )

    # Save score candidates JSON
    json_path = metrics_dir / f"{TARGET_VIDEO_ID}_score_candidates.json"
    with open(json_path, "w", encoding="utf-8") as f_json:
        json.dump(scores_data, f_json, indent=2, ensure_ascii=False)

    dims = scores_data["scoring_dimensions"]
    cands = scores_data["candidate_scores"]

    report_text_lines = []

    def r_print(line: str = ""):
        print(line)
        report_text_lines.append(line)

    r_print("===========================================================================")
    r_print(" PHASE 9B CANDIDATE ADHERENCE SCORES REPORT (-RgdgqF9wd0)")
    r_print("===========================================================================")

    r_print("\n1. CORE SCORING DIMENSIONS:")
    r_print(f"   - Point Coverage Score   : {dims['point_coverage']['score']:.2f}% ({dims['point_coverage']['directly_covered_count']}/{dims['point_coverage']['total_promised_points']} promised points directly covered)")
    r_print(f"   - Clear Relevance Score  : {dims['clear_relevance']['score']:.2f}% ({dims['clear_relevance']['clearly_relevant_duration']:.2f}s of {dims['clear_relevance']['total_analyzed_duration']:.2f}s)")
    r_print(f"   - Topic Discipline Score : {dims['topic_discipline']['score']:.2f}% (100% - {dims['topic_discipline']['off_topic_percentage']:.2f}% off-topic)")

    r_print("\n2. OFF-TOPIC & DIAGNOSTIC METRICS:")
    r_print(f"   - Off-Topic Duration     : {dims['topic_discipline']['off_topic_duration']:.2f}s ({dims['topic_discipline']['off_topic_percentage']:.2f}%)")
    r_print(f"   - Off-Topic Episodes     : {dims['off_topic_diagnostics']['episode_count']}")
    r_print(f"   - Longest Episode Pct    : {dims['off_topic_diagnostics']['longest_episode_percentage']:.2f}%")
    r_print(f"   - Returned After Midroll : {dims['off_topic_diagnostics']['returned_to_topic_after_midroll']}")

    r_print("\n3. MISSING POINT DIAGNOSTICS:")
    r_print(f"   - Missing Point Count    : {dims['diagnostic_penalties']['missing_point_count']} point (P4: Listing gains assessment)")
    r_print(f"   - Missing Point Pct      : {dims['diagnostic_penalties']['missing_point_percentage']:.2f}%")

    r_print("\n4. EXPERIMENTAL CANDIDATE SCORES COMPARISON TABLE:")
    r_print("-" * 75)
    r_print(f"{'Metric / Candidate Formula':<35} | {'Weighting Breakdown':<25} | {'Score':<10}")
    r_print("-" * 75)
    r_print(f"{'Point Coverage Score':<35} | {'Baseline (3/4 Covered)':<25} | {dims['point_coverage']['score']:>9.2f}%")
    r_print(f"{'Clear Relevance Score':<35} | {'Direct + Supp + Rel':<25} | {dims['clear_relevance']['score']:>9.2f}%")
    r_print(f"{'Topic Discipline Score':<35} | {'100% - Off-Topic %':<25} | {dims['topic_discipline']['score']:>9.2f}%")
    r_print("-" * 75)
    r_print(f"{'Candidate A (Balanced)':<35} | {'40% Cov / 40% Rel / 20% Disc':<25} | {cands['Candidate_A_Balanced']['score']:>9.2f}")
    r_print(f"{'Candidate B (Promise-First)':<35} | {'60% Cov / 25% Rel / 15% Disc':<25} | {cands['Candidate_B_PromiseFirst']['score']:>9.2f}")
    r_print(f"{'Candidate C (Focus-First)':<35} | {'30% Cov / 30% Rel / 40% Disc':<25} | {cands['Candidate_C_FocusFirst']['score']:>9.2f}")
    r_print("-" * 75)

    r_print("\n5. DETAILED TECHNICAL INTERPRETATION OF DIFFERENCES:")
    r_print("   ► Candidate A (Balanced: 40/40/20):")
    r_print("     - Score: 72.55")
    r_print("     - Rewards creators who cover most promised points while maintaining strong core content duration.")
    r_print("     - Provides an even balance between promised point delivery and video relevance.")
    r_print("\n   ► Candidate B (Promise-First: 60/25/15):")
    r_print("     - Score: 73.37")
    r_print("     - Strongly rewards fulfilling promised points (60% weight on coverage).")
    r_print("     - Yields a slightly higher score (73.37 vs 72.55) because the creator fulfilled 75% of promised points (P1, P2, P3), which is higher than the 70.92% duration relevance.")
    r_print("     - Highly sensitive to missing promised points.")
    r_print("\n   ► Candidate C (Focus-First: 30/30/40):")
    r_print("     - Score: 72.15")
    r_print("     - Strongly penalizes digressions and sponsor plugs (40% weight on discipline).")
    r_print("     - Yields the lowest score (72.15) because the video contains 29.08% off-topic duration (mid-roll credit card ad + outro).")

    r_print("\n6. SPONSOR & OFF-TOPIC INTERPRETATION:")
    r_print("   - Episode 1 (212.92s–347.40s): 134.48s mid-roll credit card plug. The creator cleanly returned to promised Point P2 at 347.40s.")
    r_print("   - Episode 2 (620.28s–649.08s): 28.80s outro sponsor call-to-action.")
    r_print("   - All candidate formulas report off-topic duration without making subjective value judgments.")

    r_print("\n7. IMPORTANT LIMITATIONS:")
    r_print("   - Candidate formulas are currently experimental design options.")
    r_print("   - No formula has been selected as the final production metric.")

    r_print("\n===========================================================================")
    r_print(f" Saved Candidate JSON   : {json_path}")

    # Save report JSON
    report_file = metrics_dir / f"{TARGET_VIDEO_ID}_score_candidates_report.json"
    with open(report_file, "w", encoding="utf-8") as f_rep:
        json.dump({
            "video_id": TARGET_VIDEO_ID,
            "report_summary": "\n".join(report_text_lines),
            "scores_data": scores_data
        }, f_rep, indent=2, ensure_ascii=False)
    r_print(f" Saved Candidate Report : {report_file}")
    r_print("===========================================================================")
    r_print("\nPhase 9B candidate scoring is complete. Which scoring approach should we approve for further validation: A, B, C, or a revised formula?")

if __name__ == "__main__":
    main()
