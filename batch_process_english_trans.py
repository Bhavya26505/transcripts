#!/usr/bin/env python3
"""
Batch Transcript Processing Pipeline for English Trans Folders

Workflow:
Start script
    ↓
Find all video folders in English Trans (sorted naturally: Video 1, Video 2 ... Video 204)
    ↓
Video 1 → Analyze → Save Video 1/result.json
    ↓
Video 2 → Analyze → ERROR? ── YES ──> Save Video 2/result.error.json → NEXT
    │                           │
    └─────────── NO ────────────┘
    ↓
Save Video 2/result.json
    ↓
Video 3 ... Finish
"""

import os
import sys
import re
import json
import time
import argparse
import traceback
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Reconfigure Windows console to UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from src.llm_client import LMStudioClient
from src.user_analysis_pipeline import UserAnalysisPipeline, validate_upload_file

DEFAULT_ENGLISH_TRANS_DIR = Path(r"C:\Users\ADMIN\OneDrive\Desktop\english trans")
SUPPORTED_EXTENSIONS = [".srt", ".vtt", ".txt"]


def natural_sort_key(path: Path) -> List[Any]:
    """
    Splits string into numeric and non-numeric chunks for natural sorting.
    E.g. 'Video 1', 'Video 2', ..., 'Video 10', 'Video 204'
    """
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', path.name)]


def find_video_folders(root_dir: Path) -> List[Path]:
    """
    Discovers all subdirectories in the given root folder and sorts them naturally.
    """
    if not root_dir.exists() or not root_dir.is_dir():
        raise FileNotFoundError(f"Root directory does not exist or is not a directory: {root_dir}")

    folders = [d for d in root_dir.iterdir() if d.is_dir()]
    folders.sort(key=natural_sort_key)
    return folders


def find_transcript_file(folder: Path) -> Optional[Path]:
    """
    Finds the transcript file in a video folder.
    Prioritizes 'en.srt', then any '*.srt', '*.vtt', '*.txt'.
    """
    # Priority 1: en.srt
    primary = folder / "en.srt"
    if primary.exists() and primary.is_file():
        return primary

    # Priority 2: any supported subtitle file
    for ext in SUPPORTED_EXTENSIONS:
        files = list(folder.glob(f"*{ext}"))
        if files:
            # Exclude any previous result/error json files
            valid_files = [f for f in files if not f.name.endswith(".json")]
            if valid_files:
                return sorted(valid_files, key=lambda f: f.stat().st_size, reverse=True)[0]

    return None


def format_duration(seconds: float) -> str:
    """Formats seconds into human readable MM:SS or HH:MM:SS string."""
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def process_single_video_folder(
    folder: Path,
    index: int,
    total: int,
    force: bool = False,
    retry_errors_only: bool = False
) -> Dict[str, Any]:
    """
    Executes analysis for a single video folder.
    Branches based on success/error:
    - Success -> writes folder/result.json, removes folder/result.error.json
    - Error   -> writes folder/result.error.json
    """
    folder_name = folder.name
    result_json_path = folder / "result.json"
    error_json_path = folder / "result.error.json"

    print("\n" + "=" * 80)
    print(f" [{index}/{total}] ({index/total*100:5.1f}%) PROCESSING FOLDER: {folder_name}")
    print("=" * 80)

    # 1. Check if already completed
    if result_json_path.exists() and not force and not retry_errors_only:
        print(f" ► Existing 'result.json' found. Skipping (use --force to reprocess).")
        try:
            with open(result_json_path, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
            score_val = cached_data.get("adherence", {}).get("adherence_score")
            score_str = f"{score_val:.2f}" if score_val is not None else "N/A"
            return {
                "folder": folder_name,
                "status": "SKIPPED",
                "score": score_str,
                "result_file": str(result_json_path),
                "duration_seconds": 0.0
            }
        except Exception:
            pass

    # If retry_errors_only is requested and no error file exists and result exists, skip
    if retry_errors_only and not error_json_path.exists() and result_json_path.exists():
        print(f" ► No error detected previously and 'result.json' is present. Skipping.")
        return {
            "folder": folder_name,
            "status": "SKIPPED",
            "score": "N/A",
            "result_file": str(result_json_path),
            "duration_seconds": 0.0
        }

    # 2. Locate transcript file
    transcript_file = find_transcript_file(folder)
    if not transcript_file:
        err_msg = f"No transcript file (.srt, .vtt, .txt) found in folder '{folder_name}'."
        print(f" ❌ ERROR: {err_msg}")
        error_payload = {
            "video_folder": folder_name,
            "status": "ERROR",
            "error": err_msg,
            "failed_stage": "DISCOVERY",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        }
        with open(error_json_path, "w", encoding="utf-8") as f:
            json.dump(error_payload, f, indent=2, ensure_ascii=False)
        print(f" 💾 Saved error details to: {error_json_path}")
        return {
            "folder": folder_name,
            "status": "ERROR",
            "error": err_msg,
            "error_file": str(error_json_path),
            "duration_seconds": 0.0
        }

    file_size_kb = transcript_file.stat().st_size / 1024
    print(f" ► Transcript File : {transcript_file.name} ({file_size_kb:.1f} KB)")

    # 3. Validate transcript file
    is_valid, validation_err = validate_upload_file(transcript_file)
    if not is_valid:
        print(f" ❌ VALIDATION FAILED: {validation_err}")
        error_payload = {
            "video_folder": folder_name,
            "status": "ERROR",
            "error": validation_err,
            "failed_stage": "INPUT_VALIDATION",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "file": transcript_file.name,
            "file_size_bytes": transcript_file.stat().st_size
        }
        with open(error_json_path, "w", encoding="utf-8") as f:
            json.dump(error_payload, f, indent=2, ensure_ascii=False)
        print(f" 💾 Saved error details to: {error_json_path}")
        print(f" ⏩ Advancing to NEXT video...")
        return {
            "folder": folder_name,
            "status": "ERROR",
            "error": validation_err,
            "error_file": str(error_json_path),
            "duration_seconds": 0.0
        }

    # 4. Execute Analysis Pipeline
    start_proc_time = time.time()
    sanitized_id = re.sub(r'[^a-zA-Z0-9_-]', '_', folder_name)
    pipeline = UserAnalysisPipeline(analysis_id=f"batch_{sanitized_id}")

    try:
        pipeline_res = pipeline.run_pipeline(
            file_path=transcript_file,
            filename=transcript_file.name
        )

        proc_duration = round(time.time() - start_proc_time, 2)

        # Check for pipeline failure
        if pipeline_res.get("status") == "FAILED":
            err_msg = pipeline_res.get("error", "Unknown pipeline analysis error")
            print(f" ❌ PIPELINE FAILED: {err_msg}")
            error_payload = {
                "video_folder": folder_name,
                "status": "ERROR",
                "error": err_msg,
                "failed_stage": pipeline_res.get("failed_stage", "UNKNOWN"),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                "processing_time_seconds": proc_duration,
                "stages": pipeline_res.get("stages", [])
            }
            with open(error_json_path, "w", encoding="utf-8") as f:
                json.dump(error_payload, f, indent=2, ensure_ascii=False)
            print(f" 💾 Saved error details to: {error_json_path}")
            print(f" ⏩ Advancing to NEXT video...")
            return {
                "folder": folder_name,
                "status": "ERROR",
                "error": err_msg,
                "error_file": str(error_json_path),
                "duration_seconds": proc_duration
            }

        # 5. Success Branch: Save result.json
        with open(result_json_path, "w", encoding="utf-8") as f:
            json.dump(pipeline_res, f, indent=2, ensure_ascii=False)

        # Clean up any previous error file
        if error_json_path.exists():
            try:
                error_json_path.unlink()
            except Exception:
                pass

        # Extract summary metrics for display
        adh = pipeline_res.get("adherence", {})
        score_val = adh.get("adherence_score")
        cov_val = adh.get("point_coverage")
        rel_val = adh.get("clear_relevance_score")
        disc_val = adh.get("topic_discipline_score")
        hook_info = pipeline_res.get("hook", {})
        p_info = pipeline_res.get("promise_analysis", {})
        points_cnt = p_info.get("promised_points_count", 0)

        score_str = f"{score_val:.2f}" if score_val is not None else "N/A"
        cov_str = f"{cov_val:.2f}%" if cov_val is not None else "N/A"
        rel_str = f"{rel_val:.2f}%" if rel_val is not None else "N/A"
        disc_str = f"{disc_val:.2f}%" if disc_val is not None else "N/A"

        print("-" * 80)
        print(f" ✅ ANALYSIS COMPLETE for {folder_name} ({proc_duration}s)")
        print(f" ► Hook Identified       : {hook_info.get('type', 'UNKNOWN')} ({hook_info.get('confidence', 0.0)*100:.0f}% conf)")
        print(f" ► Creator Promises      : {p_info.get('promise_status')} ({points_cnt} promised points)")
        print(f" ► Point Coverage        : {cov_str}")
        print(f" ► Clear Relevance       : {rel_str}")
        print(f" ► Topic Discipline      : {disc_str}")
        print(f" ► FINAL ADHERENCE SCORE : {score_str}")
        print(f" 💾 Saved Result to      : {result_json_path}")
        print("-" * 80)

        return {
            "folder": folder_name,
            "status": "SUCCESS",
            "score": score_str,
            "promised_points": points_cnt,
            "point_coverage": cov_str,
            "clear_relevance": rel_str,
            "topic_discipline": disc_str,
            "duration_seconds": proc_duration,
            "result_file": str(result_json_path)
        }

    except Exception as ex:
        proc_duration = round(time.time() - start_proc_time, 2)
        err_msg = str(ex)
        tb_str = traceback.format_exc()
        print(f" ❌ UNHANDLED EXCEPTION in {folder_name}: {err_msg}")
        traceback.print_exc()

        error_payload = {
            "video_folder": folder_name,
            "status": "ERROR",
            "error": err_msg,
            "error_type": type(ex).__name__,
            "traceback": tb_str,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "processing_time_seconds": proc_duration
        }
        with open(error_json_path, "w", encoding="utf-8") as f:
            json.dump(error_payload, f, indent=2, ensure_ascii=False)
        print(f" 💾 Saved error details to: {error_json_path}")
        print(f" ⏩ Advancing to NEXT video...")

        return {
            "folder": folder_name,
            "status": "ERROR",
            "error": err_msg,
            "error_file": str(error_json_path),
            "duration_seconds": proc_duration
        }


def run_batch_pipeline(
    target_dir: Path = DEFAULT_ENGLISH_TRANS_DIR,
    start_folder: Optional[str] = None,
    limit: Optional[int] = None,
    specific_video: Optional[str] = None,
    force: bool = False,
    retry_errors_only: bool = False,
    delay_between_videos: float = 0.0
):
    """
    Main batch runner orchestrating the discovery, sequential execution, and summary reporting.
    """
    print("=" * 80)
    print(" BATCH TRANSCRIPT PROCESSING PIPELINE — ENGLISH TRANS")
    print("=" * 80)
    print(f" Target Directory   : {target_dir}")
    print(f" LM Studio Base URL : {config.LM_STUDIO_BASE_URL}")
    print(f" LM Studio Model    : {config.LM_STUDIO_MODEL_ID}")
    print(f" Force Reprocess    : {force}")
    print(f" Retry Errors Only  : {retry_errors_only}\n")

    # 1. Verify LM Studio Server
    client = LMStudioClient()
    try:
        print(f"🔌 Checking connection to LM Studio ({client.base_url})...")
        models = client.check_connection_and_get_models(timeout=10)
        model_id = client.resolve_model_id(models)
        print(f"✅ LM Studio Endpoint Online! Model: {model_id}\n")
    except Exception as e:
        print(f"\n❌ [FATAL ERROR] LM Studio server is unreachable at {client.base_url}: {e}")
        print("Please ensure LM Studio is running on port 1234 before starting.")
        sys.exit(1)

    # 2. Discover video folders
    all_folders = find_video_folders(target_dir)
    total_found = len(all_folders)
    print(f"🔍 Discovered {total_found} video folders in '{target_dir}'.")

    # Filter folders according to arguments
    if specific_video:
        matching = [d for d in all_folders if d.name.lower() == specific_video.lower()]
        if not matching:
            print(f"❌ Error: Specific video folder '{specific_video}' not found in '{target_dir}'.")
            sys.exit(1)
        folders_to_process = matching
    else:
        folders_to_process = all_folders

        # Handle start offset
        if start_folder:
            start_idx = None
            for idx, d in enumerate(folders_to_process):
                if d.name.lower() == start_folder.lower() or (start_folder.isdigit() and str(idx + 1) == start_folder):
                    start_idx = idx
                    break
            if start_idx is not None:
                print(f"⏩ Starting from '{folders_to_process[start_idx].name}' (index {start_idx + 1}/{total_found}).")
                folders_to_process = folders_to_process[start_idx:]
            else:
                print(f"⚠️ Warning: Start folder '{start_folder}' not found. Starting from beginning.")

        # Handle limit
        if limit and limit > 0:
            print(f"🔢 Limiting run to {limit} video(s).")
            folders_to_process = folders_to_process[:limit]

    total_to_process = len(folders_to_process)
    print(f"📋 Total folders to process in this session: {total_to_process}\n")

    summary_records = []
    success_count = 0
    error_count = 0
    skipped_count = 0
    total_time_start = time.time()

    try:
        for idx, folder in enumerate(folders_to_process, 1):
            res = process_single_video_folder(
                folder=folder,
                index=idx,
                total=total_to_process,
                force=force,
                retry_errors_only=retry_errors_only
            )
            summary_records.append(res)

            st = res.get("status")
            if st == "SUCCESS":
                success_count += 1
            elif st == "ERROR":
                error_count += 1
            elif st == "SKIPPED":
                skipped_count += 1

            if delay_between_videos > 0 and idx < total_to_process:
                time.sleep(delay_between_videos)

    except KeyboardInterrupt:
        print("\n\n⚠️ Execution interrupted by user (Ctrl+C). Saving current batch progress...")

    total_batch_duration = round(time.time() - total_time_start, 2)
    processed_count = success_count + error_count
    avg_duration = round(total_batch_duration / processed_count, 2) if processed_count > 0 else 0.0

    # 3. Final Summary Display
    print("\n" + "=" * 85)
    print(" BATCH EXECUTION SUMMARY REPORT — ENGLISH TRANS")
    print("=" * 85)
    print(f" Total Folders Scanned       : {total_to_process}")
    print(f" ✅ Successfully Analyzed    : {success_count} (saved as 'result.json')")
    print(f" ❌ Errors Encountered       : {error_count} (saved as 'result.error.json')")
    print(f" ⏭️ Skipped (Already Done)   : {skipped_count}")
    print(f" ⏱️ Total Session Time       : {total_batch_duration}s ({total_batch_duration/60:.2f} mins)")
    print(f" ⚡ Average Time per Video   : {avg_duration}s")
    print("=" * 85)

    # Print Table of Results
    print(f"\n{'#':<4} | {'Folder':<12} | {'Status':<8} | {'Score':<7} | {'Cov %':<7} | {'Rel %':<7} | {'Disc %':<7} | {'Time (s)'}")
    print("-" * 85)
    for i, r in enumerate(summary_records, 1):
        f_name = r.get("folder", "")
        status = r.get("status", "")
        score = r.get("score", "N/A")
        cov = r.get("point_coverage", "N/A")
        rel = r.get("clear_relevance", "N/A")
        disc = r.get("topic_discipline", "N/A")
        dur = r.get("duration_seconds", 0.0)
        print(f"{i:<4} | {f_name:<12} | {status:<8} | {score:>7} | {cov:>7} | {rel:>7} | {disc:>7} | {dur:>7.1f}")
    print("-" * 85)

    # Save summary JSON
    summary_file = target_dir / "batch_summary.json"
    try:
        summary_payload = {
            "target_directory": str(target_dir),
            "executed_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "total_scanned": total_to_process,
            "successful_count": success_count,
            "error_count": error_count,
            "skipped_count": skipped_count,
            "total_processing_time_seconds": total_batch_duration,
            "average_time_per_video_seconds": avg_duration,
            "records": summary_records
        }
        with open(summary_file, "w", encoding="utf-8") as f_sum:
            json.dump(summary_payload, f_sum, indent=2, ensure_ascii=False)
        print(f"\n💾 Saved overall Batch Summary JSON to: {summary_file}")
    except Exception as ex:
        print(f"Could not save batch_summary.json: {ex}")

    print("\n🎉 Batch processing finished successfully!\n")


def parse_cli_args():
    parser = argparse.ArgumentParser(
        description="Batch process all video folders in English Trans directory."
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=str(DEFAULT_ENGLISH_TRANS_DIR),
        help=f"Root directory containing video folders (default: {DEFAULT_ENGLISH_TRANS_DIR})"
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="Video folder name or index to start from (e.g. 'Video 5' or 5)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of video folders to process in this run"
    )
    parser.add_argument(
        "--video",
        type=str,
        default=None,
        help="Process a single specific video folder (e.g. 'Video 1')"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reprocessing even if 'result.json' already exists"
    )
    parser.add_argument(
        "--retry-errors",
        action="store_true",
        help="Only process folders that currently have 'result.error.json' or no result"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Delay in seconds between processing each video (default: 0.0)"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_cli_args()
    run_batch_pipeline(
        target_dir=Path(args.dir),
        start_folder=args.start,
        limit=args.limit,
        specific_video=args.video,
        force=args.force,
        retry_errors_only=args.retry_errors,
        delay_between_videos=args.delay
    )
