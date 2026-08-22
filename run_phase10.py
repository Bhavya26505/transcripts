import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from src.llm_client import LMStudioClient
from src.phase10_pipeline import run_production_pipeline_for_video

SELECTED_5_VIDEOS = [
    "-ckuMh4Px9M",
    "0xNCJH5161s",
    "1jnEhDmvQbk",
    "1l37N5wcDgs",
    "1sVOwYhItqk"
]

EXCLUDED_VIDEOS = {
    "-RgdgqF9wd0",
    "-SZBrXciDLg",
    "-XwsCHg9fEA",
    "-_E7at6WAlQ",
    "0LXDjMNLiWY"
}

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 80)
    print(" PHASE 10: PRODUCTION SCORING & SMALL-BATCH END-TO-END VALIDATION (5 NEW VIDEOS)")
    print("=" * 80)

    # Output directory
    output_dir = config.DATA_DIR / "production_validation" / "phase10"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load dataset index
    index_file = config.DATA_DIR / "dataset_index.json"
    with open(index_file, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    video_map = {v["video_id"]: v for v in dataset}

    # Verify selected videos
    for vid in SELECTED_5_VIDEOS:
        if vid in EXCLUDED_VIDEOS:
            print(f"[FATAL ERROR] Selected video {vid} is in the excluded list!")
            sys.exit(1)
        if vid not in video_map:
            print(f"[FATAL ERROR] Selected video {vid} not found in dataset_index.json!")
            sys.exit(1)

    print(f"Selected 5 NEW Videos  : {SELECTED_5_VIDEOS}")
    print(f"Excluded Video Count   : {len(EXCLUDED_VIDEOS)}")
    print(f"Locked Production Score: 0.60 * Coverage + 0.25 * Relevance + 0.15 * Discipline")
    print(f"LM Studio Model        : {config.LM_STUDIO_MODEL_ID}")
    print(f"LM Studio Base URL     : {config.LM_STUDIO_BASE_URL}\n")

    client = LMStudioClient()

    results = []
    total_batch_start = time.time()

    for idx, vid in enumerate(SELECTED_5_VIDEOS, 1):
        v_entry = video_map[vid]
        print("-" * 80)
        print(f" PROCESSING VIDEO {idx}/5: {vid}")
        print("-" * 80)

        try:
            prod_res = run_production_pipeline_for_video(v_entry, client)
        except Exception as e:
            print(f"[FAIL] Error processing video {vid}: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

        prod_file = output_dir / f"{vid}_production.json"
        with open(prod_file, "w", encoding="utf-8") as f_out:
            json.dump(prod_res, f_out, indent=2, ensure_ascii=False)

        results.append(prod_res)

        sc = prod_res["adherence_score"]
        val = prod_res["validation"]
        perf = prod_res["performance"]

        print(f" ► Phase 7 Hook & Promises Extracted : {len(prod_res['expected_points'])} promised point(s)")
        print(f" ► Segment Timeline Analyzed        : {len(prod_res['segment_analysis'])} segment(s)")
        print(f" ► Point Coverage Score (60%)       : {sc['point_coverage_score']:.2f}%")
        print(f" ► Clear Relevance Score (25%)      : {sc['clear_relevance_score']:.2f}%")
        print(f" ► Topic Discipline Score (15%)     : {sc['topic_discipline_score']:.2f}%")
        print(f" ► FINAL PRODUCTION ADHERENCE SCORE : {sc['final_score']:.2f}")
        print(f" ► Validation Status                : {'PASS' if val['all_validations_pass'] else 'FAIL'}")
        print(f" ► Processing Time                  : {perf['total_processing_time']}s (LLM calls: {perf['llm_calls_count']})\n")

    total_batch_time = round(time.time() - total_batch_start, 2)

    # ---------------------------------------------------------
    # BATCH REPORT CREATION & DISPLAY
    # ---------------------------------------------------------
    batch_report_data = {
        "batch_size": len(results),
        "total_processing_time_seconds": total_batch_time,
        "average_processing_time_per_video": round(total_batch_time / len(results), 2),
        "locked_production_formula": "0.60 * Coverage + 0.25 * Relevance + 0.15 * Discipline",
        "videos_summary": []
    }

    report_lines = []
    def r_print(line: str = ""):
        print(line)
        report_lines.append(line)

    r_print("=========================================================================================")
    r_print(" PHASE 10 BATCH PRODUCTION VALIDATION REPORT (5 NEW VIDEOS)")
    r_print("=========================================================================================")
    r_print(f"{'Video ID':<13} | {'Promised':<8} | {'Cov %':<7} | {'Rel %':<7} | {'Disc %':<7} | {'Off-Top %':<8} | {'Episodes':<8} | {'Score':<7} | {'Status'}")
    r_print("-" * 95)

    all_passed = True
    for r in results:
        vid = r["video_id"]
        exp_cnt = len(r["expected_points"])
        sc = r["adherence_score"]
        met = r["metrics"]
        val_pass = r["validation"]["all_validations_pass"]

        if not val_pass:
            all_passed = False

        status_str = "PASS" if val_pass else "FAIL"

        r_print(f"{vid:<13} | {exp_cnt:<8} | {sc['point_coverage_score']:>6.2f} | {sc['clear_relevance_score']:>6.2f} | {sc['topic_discipline_score']:>6.2f} | {met['off_topic_percentage']:>7.2f}% | {met['off_topic_episode_count']:<8} | {sc['final_score']:>7.2f} | [{status_str}]")

        batch_report_data["videos_summary"].append({
            "video_id": vid,
            "expected_points_count": exp_cnt,
            "covered_points_count": sum(1 for p in met["point_coverage"].values() if p.get("coverage_type") == "DIRECTLY_COVERED"),
            "missing_points_count": len(met["missing_points"]),
            "point_coverage_score": sc["point_coverage_score"],
            "clear_relevance_score": sc["clear_relevance_score"],
            "topic_discipline_score": sc["topic_discipline_score"],
            "off_topic_percentage": met["off_topic_percentage"],
            "off_topic_episodes_count": met["off_topic_episode_count"],
            "final_adherence_score": sc["final_score"],
            "validation_status": status_str,
            "total_processing_time": r["performance"]["total_processing_time"]
        })

    r_print("-" * 95)
    r_print(f"\nOVERALL PHASE 10 BATCH VALIDATION STATUS : {'PASS' if all_passed else 'FAIL'}")
    r_print(f"Total Batch Execution Time              : {total_batch_time} seconds ({total_batch_time/60:.2f} minutes)")
    r_print(f"Average Execution Time per Video        : {total_batch_time/len(results):.2f} seconds\n")

    # Save batch report JSON
    batch_report_path = output_dir / "phase10_batch_report.json"
    with open(batch_report_path, "w", encoding="utf-8") as f_rep:
        json.dump(batch_report_data, f_rep, indent=2, ensure_ascii=False)

    r_print(f"Saved Batch Report JSON: {batch_report_path}")
    r_print("=========================================================================================")
    r_print("\nPhase 10 five-video production validation is complete. Do you approve scaling the validated pipeline to the remaining dataset?")

if __name__ == "__main__":
    main()
