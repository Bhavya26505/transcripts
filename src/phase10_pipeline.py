import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

import config
from src.llm_client import LMStudioClient
from src.parser import parse_srt_file
from src.preprocessor import preprocess_transcript
from src.segmenter import segment_transcript
from src.language_detector import enrich_segmented_transcript_with_language
from src.hook_analyzer import prepare_opening_segments, analyze_video_hook
from src.adherence_timeline_analyzer import analyze_adherence_in_batches
from src.adherence_metrics import calculate_phase9a_metrics

def run_production_pipeline_for_video(
    video_id: str,
    raw_dir: Optional[Path] = None,
    preprocessed_dir: Optional[Path] = None,
    segmented_dir: Optional[Path] = None,
    language_dir: Optional[Path] = None,
    analysis_dir: Optional[Path] = None,
    analysis_segments_dir: Optional[Path] = None,
    metrics_dir: Optional[Path] = None,
    production_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Executes Phases 2 through 9D end-to-end production analysis pipeline for a given video ID.
    Reuses existing cached phase files if present.
    """
    start_total_time = time.time()

    raw_dir = raw_dir or config.RAW_DIR
    preprocessed_dir = preprocessed_dir or config.PREPROCESSED_DIR
    segmented_dir = segmented_dir or config.SEGMENTED_DIR
    language_dir = language_dir or config.LANGUAGE_DIR
    analysis_dir = analysis_dir or config.ANALYSIS_DIR
    analysis_segments_dir = analysis_segments_dir or (config.DATA_DIR / "analysis_segments")

    metrics_dir = metrics_dir or (config.DATA_DIR / "metrics" / "phase9a")
    production_dir = production_dir or (config.DATA_DIR / "production_validation" / "phase10")

    metrics_dir.mkdir(parents=True, exist_ok=True)
    production_dir.mkdir(parents=True, exist_ok=True)

    llm_client = LMStudioClient()
    llm_calls_count = 0
    retries_count = 0

    # ---------------------------------------------------------
    # STEPS 1-4: LANGUAGE METADATA ENRICHMENT (PHASE 2-5)
    # ---------------------------------------------------------
    lang_file_path = None
    for candidate_lang in [f"{video_id}_hi_lang.json", f"{video_id}_en_lang.json", f"{video_id}_lang.json"]:
        cp = language_dir / candidate_lang
        if cp.exists():
            lang_file_path = cp
            break

    if lang_file_path and lang_file_path.exists():
        with open(lang_file_path, "r", encoding="utf-8") as f:
            lang_res = json.load(f)
    else:
        # Find raw file
        raw_json_path = None
        for candidate_name in [f"{video_id}_hi_raw.json", f"{video_id}_en_raw.json", f"{video_id}_raw.json"]:
            cp = raw_dir / candidate_name
            if cp.exists():
                raw_json_path = cp
                break

        srt_file_path = None
        for candidate_srt in [f"{video_id}_hi.srt", f"{video_id}_en.srt", f"{video_id}.srt"]:
            cp = raw_dir / candidate_srt
            if cp.exists():
                srt_file_path = cp
                break

        if raw_json_path:
            with open(raw_json_path, "r", encoding="utf-8") as f:
                raw_transcript = json.load(f)
            preprocessed_res = preprocess_transcript(raw_transcript)
            sub_count = len(raw_transcript.get("segments", []))
        elif srt_file_path:
            parsed_subtitles = parse_srt_file(str(srt_file_path))
            raw_transcript = {
                "video_id": video_id,
                "language": "hi",
                "segments": [
                    {
                        "subtitle_id": s["id"],
                        "start": s["start_time"],
                        "end": s["end_time"],
                        "text": s["text"]
                    }
                    for s in parsed_subtitles
                ]
            }
            preprocessed_res = preprocess_transcript(raw_transcript)
            sub_count = len(parsed_subtitles)
        else:
            raise FileNotFoundError(f"No raw data found for video {video_id} in {raw_dir}")

        segmented_path = segmented_dir / f"{video_id}_hi_segmented.json"
        if not segmented_path.exists():
            segmented_path = segmented_dir / f"{video_id}_segmented.json"

        if not segmented_path.exists():
            segmentation_res = segment_transcript(preprocessed_res)
            semantic_segments = segmentation_res["segments"]
        else:
            with open(segmented_path, "r", encoding="utf-8") as f:
                segmentation_res = json.load(f)
                semantic_segments = segmentation_res["segments"]

        out_lang_path = language_dir / f"{video_id}_hi_lang.json"
        lang_res = enrich_segmented_transcript_with_language(segmentation_res)
        with open(out_lang_path, "w", encoding="utf-8") as f:
            json.dump(lang_res, f, indent=2, ensure_ascii=False)
        lang_file_path = out_lang_path

    # ---------------------------------------------------------
    # STEP 5: PREPARE PHASE 7 OPENING WINDOW
    # ---------------------------------------------------------
    formatted_text, opening_segs, actual_duration, end_ts = prepare_opening_segments(
        lang_file_path=str(lang_file_path),
        target_window=90.0,
        max_window=120.0
    )

    # ---------------------------------------------------------
    # STEP 6: PHASE 7 QWEN HOOK ANALYSIS
    # ---------------------------------------------------------
    hook_analysis_path = analysis_dir / f"{video_id}_hook.json"
    phase7_latency = 0.0

    if not hook_analysis_path.exists():
        t0_p7 = time.time()
        hook_analysis_data = analyze_video_hook(
            video_id=video_id,
            lang_file_path=str(lang_file_path),
            client=llm_client
        )
        phase7_latency = time.time() - t0_p7
        llm_calls_count += 1
        with open(hook_analysis_path, "w", encoding="utf-8") as f:
            json.dump(hook_analysis_data, f, indent=2, ensure_ascii=False)
    else:
        with open(hook_analysis_path, "r", encoding="utf-8") as f:
            hook_analysis_data = json.load(f)

    # ---------------------------------------------------------
    # STEP 7: PHASE 8 QWEN ADHERENCE TIMELINE ANALYSIS (5-SEGMENT CHUNKS)
    # ---------------------------------------------------------
    all_segs = lang_res.get("segments", [])
    later_segments = [s for s in all_segs if s["start_time"] >= end_ts]
    if not later_segments:
        later_segments = all_segs[len(opening_segs):]

    segment_analysis_path = analysis_segments_dir / f"{video_id}_segment_analysis.json"
    phase8_latency = 0.0

    if not segment_analysis_path.exists():
        t0_p8 = time.time()
        prev_seg_context = opening_segs[-1] if opening_segs else None

        batch_res = analyze_adherence_in_batches(
            video_id=video_id,
            reference_hook=hook_analysis_data,
            segments_to_analyze=later_segments,
            client=llm_client,
            batch_size=config.ADHERENCE_BATCH_SIZE,
            chunks_dir=config.ANALYSIS_CHUNKS_DIR,
            previous_segment_context=prev_seg_context
        )
        llm_calls_count += batch_res["total_qwen_calls"]
        phase8_latency = time.time() - t0_p8

        chunk_analyses = batch_res["segments"]

        segment_analysis_data = {
            "video_id": video_id,
            "opening_segments_count": len(opening_segs),
            "analyzed_segments_count": len(chunk_analyses),
            "segments": chunk_analyses
        }
        with open(segment_analysis_path, "w", encoding="utf-8") as f:
            json.dump(segment_analysis_data, f, indent=2, ensure_ascii=False)
    else:
        with open(segment_analysis_path, "r", encoding="utf-8") as f:
            segment_analysis_data = json.load(f)

    # ---------------------------------------------------------
    # STEP 8: PHASE 9A DETERMINISTIC ADHERENCE METRICS & PHASE 10B NO-PROMISE LOGIC
    # ---------------------------------------------------------
    metrics_path = metrics_dir / f"{video_id}_metrics.json"
    metrics_data = calculate_phase9a_metrics(
        video_id=video_id,
        reference_hook=hook_analysis_data,
        segment_timeline=segment_analysis_data
    )
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics_data, f, indent=2, ensure_ascii=False)

    # ---------------------------------------------------------
    # STEP 9: SCORE ASSIGNMENT & NO-PROMISE HANDLING
    # ---------------------------------------------------------
    pmeta = metrics_data.get("promise_meta", {})
    cov_m = metrics_data.get("point_coverage")
    rel_m = metrics_data.get("relevance_metrics", {})

    promise_status = pmeta.get("promise_status", "NO_EXPLICIT_PROMISE")
    promised_points_count = pmeta.get("promised_points_count", 0)
    point_coverage_status = pmeta.get("point_coverage_status", "NOT_APPLICABLE")

    clear_relevance_score = rel_m.get("clearly_relevant_percentage", 0.0)
    topic_discipline_score = round(100.0 - rel_m.get("off_topic_percentage", 0.0), 2)

    if promised_points_count > 0:
        point_coverage_score = pmeta.get("point_coverage_score")
        final_score = pmeta.get("adherence_score")
    else:
        point_coverage_score = None
        final_score = None

    # ---------------------------------------------------------
    # STEP 10: DETERMINISTIC VALIDATIONS (12 CHECKS)
    # ---------------------------------------------------------
    integ = metrics_data.get("timeline_integrity", {})
    timeline_ok = (integ.get("status") == "PASS")

    ev_segs = segment_analysis_data.get("segments", [])
    evidence_ok = all(s.get("evidence_validation") == "PASSED" for s in ev_segs)

    math_val = metrics_data.get("mathematical_validation", {})
    metric_ok = (math_val.get("status") == "PASS")

    if final_score is not None:
        score_ok = (0.0 <= final_score <= 100.0)
    else:
        score_ok = True

    all_validations_pass = (timeline_ok and evidence_ok and metric_ok and score_ok)

    total_proc_time = round(time.time() - start_total_time, 2)

    # Construct final production analysis JSON
    oa = hook_analysis_data.get("opening_analysis", {})
    missing_pts = [pt for pt, info in (cov_m or {}).items() if info.get("coverage_type") == "NOT_COVERED"] if cov_m else []

    production_result = {
        "video_id": video_id,
        "source_language": "hi",
        "promise_status": promise_status,
        "promised_points_count": promised_points_count,
        "point_coverage": point_coverage_score,
        "point_coverage_status": point_coverage_status,
        "hook": oa.get("hook", {}),
        "creator_promise": oa.get("promise", {}),
        "expected_points": oa.get("expected_points", []),
        "segment_analysis": ev_segs,
        "metrics": {
            "point_coverage": cov_m,
            "clear_relevance": rel_m,
            "off_topic_percentage": rel_m.get("off_topic_percentage", 0.0),
            "off_topic_episode_count": metrics_data.get("off_topic", {}).get("episode_count", 0),
            "missing_points": missing_pts
        },
        "adherence_score": {
            "point_coverage_weight": 0.60,
            "clear_relevance_weight": 0.25,
            "topic_discipline_weight": 0.15,
            "point_coverage_score": point_coverage_score,
            "clear_relevance_score": clear_relevance_score,
            "topic_discipline_score": topic_discipline_score,
            "final_score": final_score
        },
        "validation": {
            "timeline_integrity": timeline_ok,
            "evidence_integrity": evidence_ok,
            "metric_integrity": metric_ok,
            "score_integrity": score_ok,
            "all_validations_pass": all_validations_pass
        },
        "performance": {
            "phase7_latency": round(phase7_latency, 2),
            "phase8_latency": round(phase8_latency, 2),
            "llm_calls_count": llm_calls_count,
            "retries_count": retries_count,
            "total_processing_time": total_proc_time
        }
    }

    prod_json_path = production_dir / f"{video_id}_production.json"
    with open(prod_json_path, "w", encoding="utf-8") as f:
        json.dump(production_result, f, indent=2, ensure_ascii=False)

    return production_result
