import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Any

# Force UTF-8 stdout for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import config
from src.llm_client import LMStudioClient
from src.phase10_pipeline import run_production_pipeline_for_video
from scratch.validate_phase11 import validate_phase11_results

def main():
    print("=" * 80)
    print(" PHASE 11: SMALL-BATCH PRODUCTION VALIDATION (10 NEW VIDEOS)")
    print("=" * 80)

    # 1. Verify LM Studio Connectivity
    client = LMStudioClient()
    print(f"Connecting to local LM Studio endpoint: {client.base_url}")
    try:
        models = client.check_connection_and_get_models(timeout=10)
        model_id = client.resolve_model_id(models)
        print(f"LM Studio Local Endpoint OK | Active Model: {model_id}\n")
    except Exception as e:
        print(f"\n[FATAL ERROR] LM Studio server is unavailable: {e}")
        print("Stopping Phase 11 safely. Please ensure LM Studio is running on port 1234.")
        sys.exit(1)

    # 2. Load Selected Videos Manifest
    manifest_path = Path("data/production_validation/phase11/selected_videos.json")
    if not manifest_path.exists():
        print("Manifest not found. Running video selection script...")
        from scratch.select_phase11_videos import select_videos
        select_videos()

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    selected_vids = [item["video_id"] for item in manifest.get("selected_videos", [])]
    if len(selected_vids) != 10:
        raise ValueError(f"Phase 11 strictly requires 10 selected videos. Found: {len(selected_vids)}")

    # 3. Load or Initialize Resumable State
    state_file = Path("data/production_validation/phase11/phase11_state.json")
    if state_file.exists():
        with open(state_file, "r", encoding="utf-8") as f:
            state_data = json.load(f)
    else:
        state_data = {
            "batch_status": "RUNNING",
            "video_states": {vid: "PENDING" for vid in selected_vids},
            "errors": {}
        }

    processed_results = {}
    completed_count = 0
    failed_count = 0
    total_qwen_calls = 0
    total_batch_time_start = time.time()

    print("-" * 80)
    print(f"STARTING PROCESSING FOR {len(selected_vids)} SELECTED NEW VIDEOS")
    print("-" * 80)

    for idx, vid in enumerate(selected_vids, 1):
        print(f"\n[{idx}/10] PROCESSING VIDEO: {vid}")
        current_state = state_data["video_states"].get(vid, "PENDING")

        # Check if production output already exists
        prod_json_path = Path("data/production_validation/phase10") / f"{vid}_production.json"
        if current_state == "COMPLETE" and prod_json_path.exists():
            print(f" ► Existing completed output found for {vid}. Re-using cached result.")
            with open(prod_json_path, "r", encoding="utf-8") as f:
                res = json.load(f)
            processed_results[vid] = res
            completed_count += 1
            total_qwen_calls += res.get("performance", {}).get("llm_calls_count", 0)
            continue

        state_data["video_states"][vid] = "RUNNING"
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2)

        try:
            res = run_production_pipeline_for_video(video_id=vid)
            processed_results[vid] = res
            state_data["video_states"][vid] = "COMPLETE"
            completed_count += 1
            llm_calls = res.get("performance", {}).get("llm_calls_count", 0)
            total_qwen_calls += llm_calls

            p_cnt = res.get("promised_points_count", 0)
            p_status = res.get("promise_status", "NO_EXPLICIT_PROMISE")
            score = res.get("adherence_score", {})
            score_val = score.get("final_score") if isinstance(score, dict) else score
            score_str = f"{score_val:.2f}" if score_val is not None else "N/A"
            proc_time = res.get("performance", {}).get("total_processing_time", 0.0)

            print(f" ► Promise Status   : {p_status} ({p_cnt} points)")
            print(f" ► Adherence Score  : {score_str}")
            print(f" ► Processing Time  : {proc_time:.2f}s (LLM calls: {llm_calls})")
            print(f" ► Video Status     : COMPLETE")

        except Exception as e:
            failed_count += 1
            state_data["video_states"][vid] = "FAILED"
            state_data["errors"][vid] = str(e)
            print(f" ► Video Status     : FAILED ({e})")
            processed_results[vid] = {
                "video_id": vid,
                "status": "FAILED",
                "error": str(e)
            }

        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2)

    total_batch_duration = round(time.time() - total_batch_time_start, 2)
    avg_proc_time = round(total_batch_duration / len(selected_vids), 2)

    # 4. Perform 22 Deterministic Assertion Checks
    all_assertions_pass, assertion_logs = validate_phase11_results(
        selected_video_ids=selected_vids,
        processed_results=processed_results
    )

    # 5. Format Per-Video Compact Validation Table
    table_rows = []
    explicit_promise_scores = []
    relevance_scores = []
    discipline_scores = []
    off_topic_pcts = []
    off_topic_ep_counts = []
    lang_dist = {}
    promise_dist = {"EXPLICIT_PROMISE": 0, "NO_EXPLICIT_PROMISE": 0}

    for vid in selected_vids:
        r = processed_results.get(vid, {})
        if r.get("status") == "FAILED":
            table_rows.append({
                "video_id": vid, "language": "N/A", "duration": 0.0, "promised_points": 0,
                "promise_status": "FAILED", "point_coverage": "N/A", "clear_relevance": 0.0,
                "topic_discipline": 0.0, "off_topic_pct": 0.0, "adherence_score": "N/A",
                "qwen_calls": 0, "processing_time": 0.0, "final_status": "FAILED"
            })
            continue

        p_cnt = r.get("promised_points_count", 0)
        p_status = r.get("promise_status", "NO_EXPLICIT_PROMISE")
        promise_dist[p_status] = promise_dist.get(p_status, 0) + 1

        lang = r.get("source_language", "hi").upper()
        lang_dist[lang] = lang_dist.get(lang, 0) + 1

        metrics = r.get("metrics", {})
        rel_m = metrics.get("clear_relevance", {})

        rel_val = rel_m.get("clearly_relevant_percentage", 0.0)
        off_val = metrics.get("off_topic_percentage", 0.0)
        disc_val = round(100.0 - off_val, 2)
        ep_cnt = metrics.get("off_topic_episode_count", 0)

        relevance_scores.append(rel_val)
        discipline_scores.append(disc_val)
        off_topic_pcts.append(off_val)
        off_topic_ep_counts.append(ep_cnt)

        cov_val = r.get("point_coverage")
        cov_str = f"{cov_val:.2f}%" if cov_val is not None else "N/A"

        adherence = r.get("adherence_score", {})
        score_val = adherence.get("final_score") if isinstance(adherence, dict) else adherence
        score_str = f"{score_val:.2f}" if score_val is not None else "N/A"

        if score_val is not None:
            explicit_promise_scores.append(score_val)

        perf = r.get("performance", {})
        llm_c = perf.get("llm_calls_count", 0)
        p_time = perf.get("total_processing_time", 0.0)

        table_rows.append({
            "video_id": vid,
            "language": lang,
            "duration": r.get("analysis_window", {}).get("duration", 0.0),
            "promised_points": p_cnt,
            "promise_status": p_status,
            "point_coverage": cov_str,
            "clear_relevance": rel_val,
            "topic_discipline": disc_val,
            "off_topic_pct": off_val,
            "adherence_score": score_str,
            "qwen_calls": llm_c,
            "processing_time": p_time,
            "final_status": "PASS" if r.get("validation", {}).get("all_validations_pass") else "FAIL"
        })

    avg_rel = round(sum(relevance_scores) / len(relevance_scores), 2) if relevance_scores else 0.0
    avg_disc = round(sum(discipline_scores) / len(discipline_scores), 2) if discipline_scores else 0.0
    avg_off = round(sum(off_topic_pcts) / len(off_topic_pcts), 2) if off_topic_pcts else 0.0
    avg_exp_score = round(sum(explicit_promise_scores) / len(explicit_promise_scores), 2) if explicit_promise_scores else None

    # 6. Save Report JSON & TXT
    report_json_data = {
        "phase": "PHASE_11_SMALL_BATCH_VALIDATION",
        "validation_status": "PASS" if (completed_count == 10 and all_assertions_pass) else "FAIL",
        "total_selected": 10,
        "total_completed": completed_count,
        "total_failed": failed_count,
        "explicit_promise_count": promise_dist.get("EXPLICIT_PROMISE", 0),
        "no_explicit_promise_count": promise_dist.get("NO_EXPLICIT_PROMISE", 0),
        "language_distribution": lang_dist,
        "performance_summary": {
            "total_qwen_calls": total_qwen_calls,
            "total_processing_time": total_batch_duration,
            "average_processing_time_per_video": avg_proc_time
        },
        "aggregate_metrics": {
            "average_relevance_percentage": avg_rel,
            "average_topic_discipline_percentage": avg_disc,
            "average_off_topic_percentage": avg_off,
            "average_explicit_promise_adherence_score": avg_exp_score,
            "videos_with_off_topic_episodes": sum(1 for c in off_topic_ep_counts if c > 0)
        },
        "table_rows": table_rows,
        "assertion_logs": assertion_logs
    }

    report_dir = Path("data/production_validation/phase11")
    report_dir.mkdir(parents=True, exist_ok=True)
    report_json_path = report_dir / "phase11_report.json"
    report_txt_path = report_dir / "phase11_report.txt"

    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(report_json_data, f, indent=2, ensure_ascii=False)

    txt_lines = [
        "=" * 90,
        " PHASE 11 BATCH PRODUCTION VALIDATION REPORT (10 NEW VIDEOS)",
        "=" * 90,
        f"{'Video ID':<15} | {'Lang':<5} | {'Pts':<3} | {'Cov %':<8} | {'Rel %':<7} | {'Disc %':<7} | {'Off-Top %':<9} | {'Score':<7} | {'Calls':<5} | {'Time':<7} | {'Status'}",
        "-" * 120
    ]

    for row in table_rows:
        line = (
            f"{row['video_id']:<15} | {row['language']:<5} | {row['promised_points']:<3} | "
            f"{row['point_coverage']:<8} | {row['clear_relevance']:>6.2f}% | {row['topic_discipline']:>6.2f}% | "
            f"{row['off_topic_pct']:>8.2f}% | {row['adherence_score']:<7} | {row['qwen_calls']:<5} | "
            f"{row['processing_time']:>6.1f}s | [{row['final_status']}]"
        )
        txt_lines.append(line)

    txt_lines.extend([
        "-" * 120,
        f"OVERALL PHASE 11 BATCH VALIDATION STATUS : {'PASS' if (completed_count == 10 and all_assertions_pass) else 'FAIL'}",
        f"Total Selected Videos                    : 10",
        f"Successfully Completed Videos           : {completed_count}",
        f"Failed Videos                            : {failed_count}",
        f"Explicit Promise Videos Count            : {promise_dist.get('EXPLICIT_PROMISE', 0)}",
        f"No Explicit Promise Videos Count         : {promise_dist.get('NO_EXPLICIT_PROMISE', 0)}",
        f"Total Qwen Calls Executed                : {total_qwen_calls}",
        f"Total Batch Processing Time              : {total_batch_duration:.2f}s ({(total_batch_duration/60.0):.2f} minutes)",
        f"Average Processing Time per Video        : {avg_proc_time:.2f}s",
        f"Average Explicit-Promise Adherence Score : {avg_exp_score if avg_exp_score is not None else 'N/A'}",
        "=" * 90
    ])

    report_txt_content = "\n".join(txt_lines)
    with open(report_txt_path, "w", encoding="utf-8") as f:
        f.write(report_txt_content)

    print("\n" + report_txt_content)
    print(f"\nSaved Phase 11 JSON report to: {report_json_path.resolve()}")
    print(f"Saved Phase 11 TXT report to : {report_txt_path.resolve()}")

    print("\n" + "=" * 80)
    print(" HARD ASSERTIONS SUMMARY (22 ASSERTIONS)")
    print("=" * 80)
    for log in assertion_logs:
        print(log)
    print("=" * 80)

    print("\nPhase 11 small-batch validation is complete. Do you approve proceeding to the user-upload production interface?")

if __name__ == "__main__":
    main()
