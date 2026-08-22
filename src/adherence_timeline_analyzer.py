import json
import re
import time
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional

import config
from src.llm_client import LMStudioClient

SYSTEM_PROMPT = """You analyze YouTube transcript segments against a creator's previously established content promise.

Classify each supplied segment independently while considering the overall promised direction.

Supporting explanations, examples, evidence, comparisons, context, and transitions can be relevant even when they do not directly state one of the promised points.

Only classify OFF_TOPIC when the segment is clearly unrelated to the promised direction.

Do not invent information.

Return ONLY a valid compact JSON object with NO markdown wrappers or reasoning.
Do not provide chain-of-thought, internal reasoning, video summaries, recommendations, or repeated transcripts."""

VALID_FUNCTIONS = {
    "DIRECT_POINT", "SUPPORTING_EXPLANATION", "EVIDENCE", "EXAMPLE",
    "COMPARISON", "TRANSITION", "CONTEXT", "CONCLUSION",
    "RELATED_EXTENSION", "OFF_TOPIC", "UNCERTAIN"
}

VALID_RELEVANCE = {
    "DIRECT", "SUPPORTING", "RELATED", "TRANSITION", "UNCERTAIN", "OFF_TOPIC"
}

VALID_POINTS = {
    "P1", "P2", "P3", "P4", "NONE", "MULTIPLE", "UNCERTAIN"
}

def normalize_text_for_matching(t: str) -> str:
    """Normalizes text for deterministic substring search (Hindi Devanagari & English)."""
    return re.sub(r'[^\w\u0900-\u097F]', '', t.lower())

def build_batch_adherence_prompt(
    video_id: str,
    batch_id: str,
    reference_hook: Dict[str, Any],
    segments_to_analyze: List[Dict[str, Any]],
    previous_segment_context: Optional[Dict[str, Any]] = None
) -> List[Dict[str, str]]:
    """
    Constructs compact prompt messages for analyzing a batch of semantic segments.
    """
    oa = reference_hook.get("opening_analysis", {})
    promise_desc = oa.get("promise", {}).get("description", "")
    expected_dir = oa.get("expected_direction", "")
    expected_pts = oa.get("expected_points", [])

    pts_text_lines = []
    for pt in expected_pts:
        pts_text_lines.append(f"{pt.get('point_id')}: {pt.get('description')}")
    pts_block = "\n".join(pts_text_lines)

    prev_context_block = ""
    if previous_segment_context:
        prev_context_block = (
            f"PREVIOUS SEGMENT CONTEXT (For transition reference only - DO NOT classify this segment):\n"
            f"[SEGMENT {previous_segment_context['segment_id']}]\n"
            f"TEXT: {previous_segment_context['text']}\n\n"
        )

    seg_blocks = []
    for seg in segments_to_analyze:
        seg_str = (
            f"[SEGMENT {seg['segment_id']}]\n"
            f"LANGUAGE: {seg.get('language', 'UNKNOWN')}\n"
            f"TIME: {seg['start_time']:.2f} - {seg['end_time']:.2f}\n"
            f"TEXT:\n{seg['text']}"
        )
        seg_blocks.append(seg_str)
    formatted_segs = "\n\n".join(seg_blocks)

    user_content = f"""CREATOR PROMISE:
{promise_desc}

EXPECTED DIRECTION:
{expected_dir}

EXPECTED POINTS:
{pts_block}

{prev_context_block}CURRENT TRANSCRIPT SEGMENTS TO CLASSIFY:

{formatted_segs}

Return ONLY a single valid JSON object with NO markdown wrapper and NO extra text:
{{
    "video_id": "{video_id}",
    "batch_id": "{batch_id}",
    "segments": [
        {{
            "segment_id": 3,
            "primary_point": "P1 | P2 | P3 | P4 | NONE | MULTIPLE | UNCERTAIN",
            "function": "DIRECT_POINT | SUPPORTING_EXPLANATION | EVIDENCE | EXAMPLE | COMPARISON | TRANSITION | CONTEXT | CONCLUSION | RELATED_EXTENSION | OFF_TOPIC",
            "relevance": "DIRECT | RELATED | OFF_TOPIC | UNCERTAIN",
            "confidence": 0.95,
            "evidence": "Short exact verbatim excerpt from this segment"
        }}
    ]
}}

CLASSIFICATION TAXONOMIES:
- primary_point: P1, P2, P3, P4, NONE, MULTIPLE, UNCERTAIN
- function: DIRECT_POINT, SUPPORTING_EXPLANATION, EVIDENCE, EXAMPLE, COMPARISON, TRANSITION, CONTEXT, CONCLUSION, RELATED_EXTENSION, OFF_TOPIC
- relevance: DIRECT, RELATED, OFF_TOPIC, UNCERTAIN (or SUPPORTING, TRANSITION)

RULES:
1. Classify EVERY supplied segment in the list independently. Output exactly one JSON object per input segment.
2. Segment IDs MUST match the input segment IDs exactly in order without omitting or inventing IDs.
3. Evidence text MUST be a short verbatim excerpt from that specific segment.
4. Return valid JSON only with NO markdown wrappers and NO reasoning text."""

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content}
    ]

# Keep alias for backward compatibility
build_phase8b_prompt = build_batch_adherence_prompt

def validate_batch_response(
    raw_response_text: str,
    segments_to_analyze: List[Dict[str, Any]]
) -> Tuple[bool, str, List[Dict[str, Any]], Dict[str, Any]]:
    """
    Strictly validates batch response from Qwen.
    Ensures input_segment_ids == output_segment_ids,
    verifies deterministic evidence substring presence,
    and enforces taxonomies.
    Returns (is_valid, error_msg, validated_segments, parsed_json).
    """
    cleaned_json_str = re.sub(r'^```(?:json)?\s*', '', raw_response_text, flags=re.IGNORECASE)
    cleaned_json_str = re.sub(r'\s*```$', '', cleaned_json_str).strip()

    parsed_json = {}
    try:
        parsed_json = json.loads(cleaned_json_str)
    except json.JSONDecodeError as e:
        match = re.search(r'(\{[\s\S]*\})', raw_response_text)
        if match:
            try:
                parsed_json = json.loads(match.group(1))
            except Exception as e2:
                return False, f"JSON parse error: {e2}", [], {}
        else:
            return False, f"JSON parse error: {e}", [], {}

    raw_analyses = []
    if isinstance(parsed_json, dict):
        raw_analyses = parsed_json.get("segments", parsed_json.get("segment_analyses", []))
    elif isinstance(parsed_json, list):
        raw_analyses = parsed_json

    if not isinstance(raw_analyses, list) or len(raw_analyses) == 0:
        return False, "Response contains no segment classification list.", [], parsed_json

    input_seg_ids = [s["segment_id"] for s in segments_to_analyze]
    output_seg_ids = [item.get("segment_id") for item in raw_analyses if isinstance(item, dict)]

    # Strict check: input_segment_ids == output_segment_ids
    if input_seg_ids != output_seg_ids:
        if set(input_seg_ids) != set(output_seg_ids) or len(input_seg_ids) != len(output_seg_ids):
            missing = set(input_seg_ids) - set(output_seg_ids)
            invented = set(output_seg_ids) - set(input_seg_ids)
            return False, f"Segment ID mismatch. Expected: {input_seg_ids}, Got: {output_seg_ids}. Missing: {list(missing)}, Invented: {list(invented)}", [], parsed_json

    # Build validated output for each input segment
    validated_segments = []
    raw_map = {item.get("segment_id"): item for item in raw_analyses if isinstance(item, dict)}

    for idx, source_seg in enumerate(segments_to_analyze):
        sid = source_seg["segment_id"]
        sa = raw_map.get(sid)
        if not sa and idx < len(raw_analyses):
            sa = raw_analyses[idx]

        if not sa:
            return False, f"Missing classification for segment {sid}", [], parsed_json

        primary_pt = sa.get("primary_point", "UNCERTAIN")
        fn = sa.get("function", "UNCERTAIN")
        rel = sa.get("relevance", "UNCERTAIN")
        conf = float(sa.get("confidence", 0.9)) if sa.get("confidence") is not None else 0.9
        ev_text = str(sa.get("evidence", "")).strip()

        # Taxonomy validations
        if fn not in VALID_FUNCTIONS:
            fn = "UNCERTAIN"
        if rel not in VALID_RELEVANCE:
            rel = "UNCERTAIN"
        if primary_pt not in VALID_POINTS and not any(p in primary_pt for p in ["P1", "P2", "P3", "P4"]):
            primary_pt = "NONE"

        # Deterministic evidence validation against source text
        norm_ev = normalize_text_for_matching(ev_text)
        norm_source = normalize_text_for_matching(source_seg["text"])

        ev_valid = True
        if not ev_text:
            ev_valid = False
        elif norm_ev not in norm_source and norm_source not in norm_ev:
            words = ev_text.split()
            if len(words) >= 4:
                sub_p = normalize_text_for_matching(" ".join(words[:4]))
                if sub_p not in norm_source:
                    ev_valid = False
            else:
                ev_valid = False

        validated_segments.append({
            "segment_id": sid,
            "start_time": source_seg["start_time"],
            "end_time": source_seg["end_time"],
            "primary_point": primary_pt,
            "function": fn,
            "relevance": rel,
            "confidence": conf,
            "evidence": ev_text,
            "evidence_validation": "PASSED" if ev_valid else "FAILED"
        })

    return True, "", validated_segments, parsed_json

def analyze_batch_with_cache(
    video_id: str,
    batch_index: int,
    segments_to_analyze: List[Dict[str, Any]],
    reference_hook: Dict[str, Any],
    client: LMStudioClient,
    chunks_dir: Optional[Path] = None,
    previous_segment_context: Optional[Dict[str, Any]] = None,
    max_retries: int = 2,
    temperature: float = 0.1,
    max_tokens: int = 3500,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Analyzes a single batch of segments with local disk caching and resumability.
    Saves to: chunks_dir / video_id / batch_001.json
    """
    chunks_dir = chunks_dir or config.ANALYSIS_CHUNKS_DIR
    video_chunk_dir = chunks_dir / video_id
    video_chunk_dir.mkdir(parents=True, exist_ok=True)

    batch_file = video_chunk_dir / f"batch_{batch_index:03d}.json"
    input_seg_ids = [s["segment_id"] for s in segments_to_analyze]
    batch_id = f"batch_{batch_index:03d}"

    # 1. Check disk cache
    if not force_refresh and batch_file.exists():
        try:
            with open(batch_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
            cached_sids = cached.get("segment_ids", [s.get("segment_id") for s in cached.get("segments", [])])
            if cached.get("status") == "COMPLETE" and cached_sids == input_seg_ids and cached.get("segments"):
                return {
                    "video_id": video_id,
                    "batch_id": batch_id,
                    "batch_index": batch_index,
                    "segment_ids": input_seg_ids,
                    "segment_count": len(segments_to_analyze),
                    "input_characters": cached.get("input_characters", 0),
                    "output_characters": cached.get("output_characters", 0),
                    "latency_seconds": 0.0,
                    "cache_hit": True,
                    "retry_count": 0,
                    "status": "COMPLETE",
                    "segments": cached.get("segments", []),
                    "raw_response": cached.get("raw_response", "")
                }
        except Exception:
            pass  # Fall through to re-compute on corrupt cache

    # 2. Cache miss or invalid -> Call Qwen
    messages = build_batch_adherence_prompt(
        video_id=video_id,
        batch_id=batch_id,
        reference_hook=reference_hook,
        segments_to_analyze=segments_to_analyze,
        previous_segment_context=previous_segment_context
    )
    input_char_count = sum(len(m["content"]) for m in messages)

    last_err = ""
    for attempt in range(max_retries + 1):
        raw_response, latency = client.send_completion(
            messages=messages,
            model_id=client.model_id,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=600
        )
        is_valid, err_msg, validated_segs, parsed_json = validate_batch_response(raw_response, segments_to_analyze)
        if is_valid:
            batch_record = {
                "video_id": video_id,
                "batch_id": batch_id,
                "batch_index": batch_index,
                "segment_ids": input_seg_ids,
                "segment_count": len(segments_to_analyze),
                "input_characters": input_char_count,
                "output_characters": len(raw_response),
                "latency_seconds": latency,
                "cache_hit": False,
                "retry_count": attempt,
                "status": "COMPLETE",
                "segments": validated_segs,
                "raw_response": raw_response
            }
            with open(batch_file, "w", encoding="utf-8") as f:
                json.dump(batch_record, f, indent=2, ensure_ascii=False)

            return batch_record
        else:
            last_err = err_msg
            if attempt < max_retries:
                time.sleep(1.0)

    fail_record = {
        "video_id": video_id,
        "batch_id": batch_id,
        "batch_index": batch_index,
        "segment_ids": input_seg_ids,
        "segment_count": len(segments_to_analyze),
        "input_characters": input_char_count,
        "output_characters": 0,
        "latency_seconds": 0.0,
        "cache_hit": False,
        "retry_count": max_retries,
        "status": "FAILED",
        "error": last_err,
        "segments": []
    }
    return fail_record

def analyze_adherence_in_batches(
    video_id: str,
    reference_hook: Dict[str, Any],
    segments_to_analyze: List[Dict[str, Any]],
    client: LMStudioClient,
    batch_size: Optional[int] = None,
    chunks_dir: Optional[Path] = None,
    previous_segment_context: Optional[Dict[str, Any]] = None,
    force_refresh: bool = False,
    progress_callback: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Orchestrates batch adherence analysis across all remaining segments.
    Divides segments dynamically into batches of batch_size (default ADHERENCE_BATCH_SIZE),
    executes sequentially with caching and resumability, and aggregates the results.
    """
    batch_size = batch_size or config.ADHERENCE_BATCH_SIZE
    chunks_dir = chunks_dir or config.ANALYSIS_CHUNKS_DIR

    chunks = [segments_to_analyze[i:i + batch_size] for i in range(0, len(segments_to_analyze), batch_size)]
    batch_metrics = []
    all_analyzed_segments = []

    total_qwen_calls = 0
    total_latency = 0.0
    total_input_chars = 0
    total_output_chars = 0

    prev_context = previous_segment_context

    for batch_idx, chunk_segs in enumerate(chunks, start=1):
        res = analyze_batch_with_cache(
            video_id=video_id,
            batch_index=batch_idx,
            segments_to_analyze=chunk_segs,
            reference_hook=reference_hook,
            client=client,
            chunks_dir=chunks_dir,
            previous_segment_context=prev_context,
            force_refresh=force_refresh
        )

        batch_metrics.append(res)
        all_analyzed_segments.extend(res.get("segments", []))

        if not res.get("cache_hit", False):
            total_qwen_calls += 1
            total_latency += res.get("latency_seconds", 0.0)

        total_input_chars += res.get("input_characters", 0)
        total_output_chars += res.get("output_characters", 0)

        prev_context = chunk_segs[-1]

        if progress_callback:
            progress_callback(batch_idx, len(chunks), res)

    ev_failed_count = sum(1 for s in all_analyzed_segments if s.get("evidence_validation") != "PASSED")

    return {
        "video_id": video_id,
        "batch_size": batch_size,
        "total_batches": len(chunks),
        "total_segments": len(segments_to_analyze),
        "batch_metrics": batch_metrics,
        "segments": all_analyzed_segments,
        "total_qwen_calls": total_qwen_calls,
        "total_latency_seconds": round(total_latency, 2),
        "total_input_characters": total_input_chars,
        "total_output_characters": total_output_chars,
        "evidence_validation_failures": ev_failed_count
    }

def analyze_and_validate_chunk(
    video_id: str,
    chunk_id: str,
    reference_hook: Dict[str, Any],
    segments_to_analyze: List[Dict[str, Any]],
    client: LMStudioClient,
    previous_segment_context: Optional[Dict[str, Any]] = None,
    temperature: float = 0.1,
    max_tokens: int = 3500
) -> Dict[str, Any]:
    """Backward compatibility wrapper for single chunk execution."""
    messages = build_batch_adherence_prompt(
        video_id, chunk_id, reference_hook, segments_to_analyze, previous_segment_context
    )
    input_char_count = sum(len(m["content"]) for m in messages)

    raw_response_text, latency = client.send_completion(
        messages=messages,
        model_id=client.model_id,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=600
    )

    is_valid, err_msg, validated_segs, parsed_json = validate_batch_response(raw_response_text, segments_to_analyze)

    return {
        "chunk_id": chunk_id,
        "raw_response": raw_response_text,
        "parsed_json": parsed_json,
        "segment_analyses": validated_segs,
        "input_char_count": input_char_count,
        "output_char_count": len(raw_response_text),
        "latency_seconds": latency,
        "json_valid": is_valid,
        "parse_error": err_msg
    }
