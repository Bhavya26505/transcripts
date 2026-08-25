import json
import re
import os
import sys
import time
import uuid
import hashlib
import csv
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

import config
from src.parser import parse_srt_string, parse_timestamp_to_seconds, clean_text
from src.preprocessor import preprocess_transcript
from src.segmenter import segment_transcript
from src.language_detector import enrich_segmented_transcript_with_language, classify_text_language
from src.llm_client import LMStudioClient
from src.hook_analyzer import prepare_opening_segments, analyze_video_hook
from src.adherence_timeline_analyzer import analyze_adherence_in_batches
from src.adherence_metrics import calculate_phase9a_metrics

ALLOWED_EXTENSIONS = {".srt", ".vtt", ".txt"}

def compute_file_sha256(file_path: Path) -> str:
    """Computes SHA-256 hex digest of file contents."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def validate_upload_file(file_path: Path) -> Tuple[bool, str]:
    """
    Validates uploaded transcript file.
    Returns (is_valid, error_message).
    """
    if not file_path.exists():
        return False, "Uploaded file does not exist."

    ext = file_path.suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Unsupported file type '{ext}'. Supported types: .srt, .vtt, .txt"

    file_size = file_path.stat().st_size
    if file_size == 0:
        return False, "Uploaded transcript is empty."
    if file_size > 50 * 1024 * 1024:
        return False, "Uploaded file exceeds maximum size limit of 50MB."

    # Try reading file with encodings
    content = None
    for enc in ['utf-8-sig', 'utf-8', 'latin-1']:
        try:
            content = file_path.read_text(encoding=enc)
            break
        except UnicodeDecodeError:
            continue

    if content is None or not content.strip():
        return False, "Transcript could not be decoded or contains no readable text."

    # Reject HTML error / rate limit response
    lower_content = content.lower().strip()
    if lower_content.startswith(("<!doctype html", "<html", "<?xml")) or "<html" in lower_content[:300] or "<title>sorry" in lower_content or "automated queries" in lower_content:
        return False, "File contains an HTML error or rate-limit response, not a valid transcript."

    # Check for subtitle structure
    entries, issues = parse_srt_string(content)
    if not entries:
        if ext in {".srt", ".vtt"}:
            return False, f"File format '{ext}' contains no valid subtitle timestamp entries (e.g. '00:00:00,000 --> 00:00:05,000')."
        # Fallback line parser for raw .txt
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if not lines:
            return False, "No valid text lines found in uploaded file."

    return True, ""

class UserAnalysisPipeline:
    """
    Orchestrates the Phase 11 user-upload analysis pipeline for a single transcript item.
    """
    def __init__(self, analysis_id: Optional[str] = None):
        self.analysis_id = analysis_id or uuid.uuid4().hex[:12]
        self.base_dir = config.DATA_DIR / "user_analysis" / self.analysis_id
        
        self.input_dir = self.base_dir / "input"
        self.raw_dir = self.base_dir / "raw"
        self.prep_dir = self.base_dir / "preprocessed"
        self.seg_dir = self.base_dir / "segmented"
        self.lang_dir = self.base_dir / "language"
        self.analysis_dir = self.base_dir / "analysis"
        self.analysis_seg_dir = self.base_dir / "analysis_segments"
        self.analysis_chunks_dir = self.base_dir / "analysis_chunks"
        self.metrics_dir = self.base_dir / "metrics"

        for d in [self.input_dir, self.raw_dir, self.prep_dir, self.seg_dir,
                  self.lang_dir, self.analysis_dir, self.analysis_seg_dir, self.analysis_chunks_dir, self.metrics_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self.stages_status = [
            {"stage": "INPUT_VALIDATION", "status": "PENDING", "error": None},
            {"stage": "SRT_PARSING", "status": "PENDING", "error": None},
            {"stage": "PREPROCESSING", "status": "PENDING", "error": None},
            {"stage": "SEMANTIC_SEGMENTATION", "status": "PENDING", "error": None},
            {"stage": "LANGUAGE_DETECTION", "status": "PENDING", "error": None},
            {"stage": "LM_STUDIO_CHECK", "status": "PENDING", "error": None},
            {"stage": "HOOK_ANALYSIS", "status": "PENDING", "error": None},
            {"stage": "ADHERENCE_ANALYSIS", "status": "PENDING", "error": None},
            {"stage": "ADHERENCE_METRICS", "status": "PENDING", "error": None},
            {"stage": "SCORING_FINALIZATION", "status": "PENDING", "error": None}
        ]
        self.status = "QUEUED"
        self.current_stage = "INPUT_VALIDATION"
        self.error_message = ""
        self.result_data = None

    def _save_status(self):
        try:
            status_file = self.base_dir / "status.json"
            status_payload = {
                "analysis_id": self.analysis_id,
                "status": self.status,
                "current_stage": self.current_stage,
                "error": self.error_message,
                "stages": self.stages_status,
                "result": self.result_data if self.status == "COMPLETED" else None
            }
            with open(status_file, "w", encoding="utf-8") as f:
                json.dump(status_payload, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def update_stage(self, stage_name: str, status: str, error: Optional[str] = None):
        self.current_stage = stage_name
        if status == "FAILED":
            self.status = "FAILED"
            self.error_message = error or ""
        timestamp = time.strftime("%H:%M:%S")
        for s in self.stages_status:
            if s["stage"] == stage_name:
                s["status"] = status
                s["error"] = error
                break

        status_symbols = {
            "RUNNING": "⏳ RUNNING",
            "COMPLETED": "✅ COMPLETED",
            "FAILED": "❌ FAILED"
        }
        sym = status_symbols.get(status, status)
        if error:
            print(f"[{timestamp}] [PIPELINE] [{self.analysis_id}] {sym} -> {stage_name} | ERROR: {error}", flush=True)
        else:
            print(f"[{timestamp}] [PIPELINE] [{self.analysis_id}] {sym} -> {stage_name}", flush=True)

        self._save_status()

    def run_pipeline(self, file_path: Path, filename: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes single-item analysis pipeline end-to-end.
        """
        start_time = time.time()
        filename = filename or file_path.name
        self.status = "PROCESSING"
        timestamp = time.strftime("%H:%M:%S")
        file_size_kb = file_path.stat().st_size / 1024 if file_path.exists() else 0
        print(f"\n[{timestamp}] [PIPELINE] [{self.analysis_id}] 🚀 Starting Analysis Pipeline for '{filename}' ({file_size_kb:.1f} KB)", flush=True)

        # ---------------------------------------------------------
        # STAGE 1: INPUT VALIDATION
        # ---------------------------------------------------------
        self.update_stage("INPUT_VALIDATION", "RUNNING")
        is_valid, err = validate_upload_file(file_path)
        if not is_valid:
            self.update_stage("INPUT_VALIDATION", "FAILED", err)
            self.status = "FAILED"
            self.error_message = err
            return self._build_failure_result(err)

        # Check Cache index
        content_hash = compute_file_sha256(file_path)
        cache_index_path = config.DATA_DIR / "uploads" / "hash_index.json"
        cache_index_path.parent.mkdir(parents=True, exist_ok=True)
        
        cached_result = self._check_cache(cache_index_path, content_hash)
        if cached_result:
            print(f"[{timestamp}] [PIPELINE] [{self.analysis_id}] ⚡ Cache Hit! Reusing existing result for SHA-256: {content_hash[:12]}...", flush=True)
            self.status = "COMPLETED"
            self.result_data = cached_result
            for s in self.stages_status:
                s["status"] = "COMPLETED"
            return cached_result

        self.update_stage("INPUT_VALIDATION", "COMPLETED")

        # Copy input file to isolated input directory
        dest_input = self.input_dir / filename
        with open(file_path, "rb") as sf, open(dest_input, "wb") as df:
            df.write(sf.read())

        # Read content
        content = dest_input.read_text(encoding='utf-8-sig', errors='replace')

        try:
            # ---------------------------------------------------------
            # STAGE 2: SRT PARSING
            # ---------------------------------------------------------
            self.update_stage("SRT_PARSING", "RUNNING")
            entries, issues = parse_srt_string(content)
            
            if not entries:
                # Basic line-by-line fallback for txt
                lines = [line.strip() for line in content.splitlines() if line.strip()]
                entries = []
                cur_t = 0.0
                for idx, line in enumerate(lines, 1):
                    dur = min(max(len(line) * 0.1, 2.0), 10.0)
                    entries.append({
                        "subtitle_id": idx,
                        "start": round(cur_t, 3),
                        "end": round(cur_t + dur, 3),
                        "text": clean_text(line)
                    })
                    cur_t += dur

            if not entries:
                err = "No valid subtitle entries were detected."
                self.update_stage("SRT_PARSING", "FAILED", err)
                self.status = "FAILED"
                self.error_message = err
                return self._build_failure_result(err)

            raw_transcript = {
                "video_id": self.analysis_id,
                "source_type": dest_input.suffix.lstrip("."),
                "language": "HI",
                "segments": entries
            }
            raw_path = self.raw_dir / f"{self.analysis_id}_raw.json"
            with open(raw_path, "w", encoding="utf-8") as f:
                json.dump(raw_transcript, f, indent=2, ensure_ascii=False)

            print(f"[{time.strftime('%H:%M:%S')}] [PIPELINE] [{self.analysis_id}] 📄 Parsed {len(entries)} subtitle lines.", flush=True)
            self.update_stage("SRT_PARSING", "COMPLETED")

            # ---------------------------------------------------------
            # STAGE 3: DETERMINISTIC PREPROCESSING
            # ---------------------------------------------------------
            self.update_stage("PREPROCESSING", "RUNNING")
            preprocessed_res = preprocess_transcript(raw_transcript)
            prep_path = self.prep_dir / f"{self.analysis_id}_preprocessed.json"
            with open(prep_path, "w", encoding="utf-8") as f:
                json.dump(preprocessed_res, f, indent=2, ensure_ascii=False)
            self.update_stage("PREPROCESSING", "COMPLETED")

            # ---------------------------------------------------------
            # STAGE 4: SEMANTIC SEGMENTATION
            # ---------------------------------------------------------
            self.update_stage("SEMANTIC_SEGMENTATION", "RUNNING")
            segmentation_res = segment_transcript(preprocessed_res)
            seg_path = self.seg_dir / f"{self.analysis_id}_segmented.json"
            with open(seg_path, "w", encoding="utf-8") as f:
                json.dump(segmentation_res, f, indent=2, ensure_ascii=False)
            print(f"[{time.strftime('%H:%M:%S')}] [PIPELINE] [{self.analysis_id}] 🧩 Created {len(segmentation_res.get('segments', []))} semantic segments.", flush=True)
            self.update_stage("SEMANTIC_SEGMENTATION", "COMPLETED")

            # ---------------------------------------------------------
            # STAGE 5: LANGUAGE DETECTION
            # ---------------------------------------------------------
            self.update_stage("LANGUAGE_DETECTION", "RUNNING")
            lang_res = enrich_segmented_transcript_with_language(segmentation_res)
            lang_path = self.lang_dir / f"{self.analysis_id}_lang.json"
            with open(lang_path, "w", encoding="utf-8") as f:
                json.dump(lang_res, f, indent=2, ensure_ascii=False)
            print(f"[{time.strftime('%H:%M:%S')}] [PIPELINE] [{self.analysis_id}] 🌐 Language detection: {lang_res.get('dominant_language', 'HI')}", flush=True)
            self.update_stage("LANGUAGE_DETECTION", "COMPLETED")

            # ---------------------------------------------------------
            # STAGE 6: LM STUDIO CONNECTION & MODEL VERIFICATION
            # ---------------------------------------------------------
            self.update_stage("LM_STUDIO_CHECK", "RUNNING")
            client = LMStudioClient()
            try:
                print(f"[{time.strftime('%H:%M:%S')}] [PIPELINE] [{self.analysis_id}] 🔌 Connecting to LM Studio at {client.base_url}...", flush=True)
                models = client.check_connection_and_get_models(timeout=10)
                model_id = client.resolve_model_id(models)
                print(f"[{time.strftime('%H:%M:%S')}] [PIPELINE] [{self.analysis_id}] 🤖 LM Studio model verified: {model_id}", flush=True)
            except Exception as ex:
                err = f"LM Studio server is unavailable at {client.base_url} ({ex})"
                print(f"[{time.strftime('%H:%M:%S')}] [PIPELINE ERROR] [{self.analysis_id}] {err}", flush=True)
                self.update_stage("LM_STUDIO_CHECK", "FAILED", err)
                self.status = "FAILED"
                self.error_message = err
                return self._build_failure_result(err)

            self.update_stage("LM_STUDIO_CHECK", "COMPLETED")

            # ---------------------------------------------------------
            # STAGE 7: HOOK & CREATOR PROMISE ANALYSIS
            # ---------------------------------------------------------
            self.update_stage("HOOK_ANALYSIS", "RUNNING")
            print(f"[{time.strftime('%H:%M:%S')}] [PIPELINE] [{self.analysis_id}] 🎯 Running opening hook analysis (target window: 90s)...", flush=True)
            formatted_text, opening_segs, actual_duration, end_ts = prepare_opening_segments(
                lang_file_path=str(lang_path),
                target_window=90.0,
                max_window=120.0
            )

            hook_analysis_data = analyze_video_hook(
                video_id=self.analysis_id,
                lang_file_path=str(lang_path),
                client=client
            )
            parsed_hook = hook_analysis_data.get("parsed_analysis", hook_analysis_data)
            oa = parsed_hook.get("opening_analysis", {})
            h_info = oa.get("hook", {})
            print(f"[{time.strftime('%H:%M:%S')}] [PIPELINE] [{self.analysis_id}] 🎯 Hook identified: Type='{h_info.get('hook_type', 'UNKNOWN')}' | Confidence={h_info.get('confidence', 0.0)*100:.0f}%", flush=True)

            hook_path = self.analysis_dir / f"{self.analysis_id}_hook.json"
            with open(hook_path, "w", encoding="utf-8") as f:
                json.dump(hook_analysis_data, f, indent=2, ensure_ascii=False)

            self.update_stage("HOOK_ANALYSIS", "COMPLETED")

            # ---------------------------------------------------------
            # STAGE 8: SEGMENT ADHERENCE TIMELINE ANALYSIS (BATCHED CHUNKS)
            # ---------------------------------------------------------
            self.update_stage("ADHERENCE_ANALYSIS", "RUNNING")
            all_segs = lang_res.get("segments", [])
            later_segments = [s for s in all_segs if s["start_time"] >= end_ts]
            if not later_segments:
                later_segments = all_segs[len(opening_segs):]

            prev_seg_context = opening_segs[-1] if opening_segs else None
            print(f"[{time.strftime('%H:%M:%S')}] [PIPELINE] [{self.analysis_id}] 🔍 Analyzing {len(later_segments)} segments in batches...", flush=True)

            def on_batch_progress(idx, total, res):
                cache_str = "⚡ CACHE HIT" if res.get("cache_hit") else f"⏱️ QWEN ({res.get('latency_seconds', 0.0):.2f}s)"
                print(f"[{time.strftime('%H:%M:%S')}] [PIPELINE] [{self.analysis_id}] 🔍 Batch [{idx}/{total}] -> Segments {res.get('segment_ids')} | Status: {res.get('status')} | {cache_str}", flush=True)

            batch_res = analyze_adherence_in_batches(
                video_id=self.analysis_id,
                reference_hook=parsed_hook,
                segments_to_analyze=later_segments,
                client=client,
                batch_size=config.ADHERENCE_BATCH_SIZE,
                chunks_dir=self.analysis_chunks_dir,
                previous_segment_context=prev_seg_context,
                progress_callback=on_batch_progress
            )

            chunk_analyses = batch_res["segments"]

            segment_analysis_data = {
                "video_id": self.analysis_id,
                "opening_segments_count": len(opening_segs),
                "analyzed_segments_count": len(chunk_analyses),
                "segments": chunk_analyses
            }
            seg_analysis_path = self.analysis_seg_dir / f"{self.analysis_id}_segment_analysis.json"
            with open(seg_analysis_path, "w", encoding="utf-8") as f:
                json.dump(segment_analysis_data, f, indent=2, ensure_ascii=False)

            self.update_stage("ADHERENCE_ANALYSIS", "COMPLETED")

            # ---------------------------------------------------------
            # STAGE 9: DETERMINISTIC ADHERENCE METRICS & PHASE 10B NO-PROMISE LOGIC
            # ---------------------------------------------------------
            self.update_stage("ADHERENCE_METRICS", "RUNNING")
            metrics_data = calculate_phase9a_metrics(
                video_id=self.analysis_id,
                reference_hook=parsed_hook,
                segment_timeline=segment_analysis_data
            )
            metrics_path = self.metrics_dir / f"{self.analysis_id}_metrics.json"
            with open(metrics_path, "w", encoding="utf-8") as f:
                json.dump(metrics_data, f, indent=2, ensure_ascii=False)

            self.update_stage("ADHERENCE_METRICS", "COMPLETED")

            # ---------------------------------------------------------
            # STAGE 10: CANDIDATE B SCORING & FINALIZATION
            # ---------------------------------------------------------
            self.update_stage("SCORING_FINALIZATION", "RUNNING")

            pmeta = metrics_data.get("promise_meta", {})
            cov_m = metrics_data.get("point_coverage")
            rel_m = metrics_data.get("relevance_metrics", {})
            off_m = metrics_data.get("off_topic", {})

            promise_status = pmeta.get("promise_status", "NO_EXPLICIT_PROMISE")
            promised_points_count = pmeta.get("promised_points_count", 0)
            point_coverage_status = pmeta.get("point_coverage_status", "NOT_APPLICABLE")

            clear_relevance_score = rel_m.get("clearly_relevant_percentage", 0.0)
            off_topic_pct = rel_m.get("off_topic_percentage", 0.0)
            topic_discipline_score = round(100.0 - off_topic_pct, 2)

            if promised_points_count > 0:
                point_coverage_score = pmeta.get("point_coverage_score")
                final_adherence_score = pmeta.get("adherence_score")
            else:
                point_coverage_score = None
                final_adherence_score = None

            oa = parsed_hook.get("opening_analysis", {})
            hook_info = oa.get("hook", {})
            promise_info = oa.get("promise", {})
            exp_pts = oa.get("expected_points", [])

            ev_segs = segment_analysis_data.get("segments", [])
            total_duration = metrics_data.get("analysis_window", {}).get("duration", 0.0)
            source_lang = lang_res.get("dominant_language", "HI")

            # Build structured final result object
            final_result = {
                "analysis_id": self.analysis_id,
                "status": "COMPLETED",
                "input": {
                    "filename": filename,
                    "duration_seconds": total_duration,
                    "language": source_lang,
                    "processed_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                    "total_subtitles": len(entries),
                    "total_semantic_segments": len(lang_res.get("segments", []))
                },
                "hook": {
                    "type": hook_info.get("hook_type", hook_info.get("type", "UNKNOWN")),
                    "confidence": hook_info.get("confidence", 0.0),
                    "start_time": hook_info.get("start_time", 0.0),
                    "end_time": hook_info.get("end_time", 0.0),
                    "text": hook_info.get("text", "")
                },
                "promise_analysis": {
                    "promise_status": promise_status,
                    "promised_points_count": promised_points_count,
                    "creator_promise": promise_info.get("description", promise_info.get("promise_text", "")),
                    "expected_direction": oa.get("expected_direction", promise_info.get("expected_direction", "")),
                    "expected_points": exp_pts
                },
                "adherence": {
                    "point_coverage": point_coverage_score,
                    "point_coverage_status": point_coverage_status,
                    "clear_relevance_score": clear_relevance_score,
                    "topic_discipline_score": topic_discipline_score,
                    "adherence_score": final_adherence_score
                },
                "off_topic": {
                    "percentage": off_topic_pct,
                    "episode_count": off_m.get("episode_count", 0),
                    "longest_episode_seconds": off_m.get("longest_episode_duration", 0.0),
                    "returned_to_topic": off_m.get("returned_to_topic", True)
                },
                "timeline": {
                    "integrity": metrics_data.get("timeline_integrity", {}).get("status", "PASS"),
                    "overlap_seconds": metrics_data.get("timeline_integrity", {}).get("overlap_duration", 0.0),
                    "uncovered_seconds": 0.0
                },
                "segments": ev_segs,
                "stages": self.stages_status,
                "total_processing_time": round(time.time() - start_time, 2)
            }

            self.update_stage("SCORING_FINALIZATION", "COMPLETED")
            self.status = "COMPLETED"
            self.result_data = final_result

            # Save final_result.json
            res_json_path = self.base_dir / "final_result.json"
            with open(res_json_path, "w", encoding="utf-8") as f:
                json.dump(final_result, f, indent=2, ensure_ascii=False)

            # Generate segment_timeline.csv
            self._write_csv_timeline(ev_segs, self.base_dir / "segment_timeline.csv")

            # Update SHA-256 cache index
            self._save_to_cache(cache_index_path, content_hash, final_result)

            elapsed = round(time.time() - start_time, 2)
            score_str = f"{final_adherence_score:.2f}" if final_adherence_score is not None else "N/A"
            print(f"[{time.strftime('%H:%M:%S')}] [PIPELINE] [{self.analysis_id}] 🏆 Pipeline SUCCESS in {elapsed}s | Score: {score_str} | Relevance: {clear_relevance_score}% | Discipline: {topic_discipline_score}%\n", flush=True)

            return final_result

        except Exception as ex:
            err = str(ex)
            print(f"[{time.strftime('%H:%M:%S')}] [PIPELINE ERROR] [{self.analysis_id}] Pipeline exception at {self.current_stage}: {err}", flush=True)
            import traceback
            traceback.print_exc()
            self.update_stage(self.current_stage, "FAILED", err)
            self.status = "FAILED"
            self.error_message = err
            return self._build_failure_result(err)

    def _write_csv_timeline(self, segments: List[Dict[str, Any]], csv_path: Path):
        """Generates CSV segment timeline export file."""
        fieldnames = ["segment_id", "start_time", "end_time", "primary_point", "function", "relevance", "confidence", "evidence"]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for seg in segments:
                writer.writerow({
                    "segment_id": seg.get("segment_id", ""),
                    "start_time": seg.get("start_time", 0.0),
                    "end_time": seg.get("end_time", 0.0),
                    "primary_point": seg.get("primary_point", ""),
                    "function": seg.get("function", ""),
                    "relevance": seg.get("relevance", ""),
                    "confidence": seg.get("confidence", 0.0),
                    "evidence": seg.get("evidence", "")
                })

    def _build_failure_result(self, error_msg: str) -> Dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "status": "FAILED",
            "error": error_msg,
            "failed_stage": self.current_stage,
            "stages": self.stages_status
        }

    def _check_cache(self, index_path: Path, content_hash: str) -> Optional[Dict[str, Any]]:
        if not index_path.exists():
            return None
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                idx = json.load(f)
            cached_id = idx.get(content_hash)
            if cached_id:
                cached_file = config.DATA_DIR / "user_analysis" / cached_id / "final_result.json"
                if cached_file.exists():
                    with open(cached_file, "r", encoding="utf-8") as f:
                        res = json.load(f)
                    res["analysis_id"] = self.analysis_id
                    res["is_cached"] = True
                    return res
        except Exception:
            pass
        return None

    def _save_to_cache(self, index_path: Path, content_hash: str, result_data: Dict[str, Any]):
        try:
            idx = {}
            if index_path.exists():
                with open(index_path, "r", encoding="utf-8") as f:
                    idx = json.load(f)
            idx[content_hash] = self.analysis_id
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(idx, f, indent=2)
        except Exception:
            pass
