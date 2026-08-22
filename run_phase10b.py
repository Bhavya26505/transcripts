import sys
import json
from pathlib import Path

# Force UTF-8 stdout encoding for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from src.phase10_pipeline import run_production_pipeline_for_video
from scratch.validate_phase10b import main as run_validation

def main():
    print("=" * 80)
    print(" PHASE 10B — NO-PROMISE HANDLING CORRECTION RUNNER")
    print("=" * 80)

    success = run_validation()

    # Create Phase 10B Batch Report JSON
    test_videos = ["-ckuMh4Px9M", "0xNCJH5161s", "1jnEhDmvQbk", "1l37N5wcDgs", "1sVOwYhItqk", "-RgdgqF9wd0"]
    batch_records = []

    for vid in test_videos:
        prod_path = Path("data/production_validation/phase10") / f"{vid}_production.json"
        with open(prod_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        adherence = data.get("adherence_score", {})
        score_val = adherence.get("final_score") if isinstance(adherence, dict) else adherence
        cov_val = data.get("point_coverage")

        batch_records.append({
            "video_id": vid,
            "promise_status": data.get("promise_status"),
            "promised_points_count": data.get("promised_points_count"),
            "point_coverage_status": data.get("point_coverage_status"),
            "point_coverage_percentage": cov_val,
            "clear_relevance_percentage": data.get("metrics", {}).get("clear_relevance", {}).get("clearly_relevant_percentage"),
            "topic_discipline_percentage": round(100.0 - data.get("metrics", {}).get("off_topic_percentage", 0.0), 2),
            "off_topic_percentage": data.get("metrics", {}).get("off_topic_percentage"),
            "off_topic_episodes_count": data.get("metrics", {}).get("off_topic_episode_count"),
            "final_adherence_score": score_val,
            "validation_status": "PASS" if data.get("validation", {}).get("all_validations_pass") else "FAIL"
        })

    report_data = {
        "phase": "PHASE_10B_NO_PROMISE_CORRECTION",
        "validation_status": "PASS" if success else "FAIL",
        "total_test_videos": len(batch_records),
        "llm_calls_made": 0,
        "videos_reprocessed": 0,
        "videos_report": batch_records
    }

    report_path = Path("data/production_validation/phase10/phase10b_batch_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    print(f"\nSaved Phase 10B Report JSON: {report_path.resolve()}")

if __name__ == "__main__":
    main()
