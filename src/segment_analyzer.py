import json
import re
import time
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional

import config
from src.llm_client import LMStudioClient

SYSTEM_PROMPT = """You are analyzing segments of a YouTube video transcript against the creator's previously established opening promise.

Your task is to classify each supplied segment.

Use only the supplied transcript segments and opening reference context.

Do not invent information.

A segment may be relevant even if it does not directly mention a promised point. Supporting explanations, evidence, examples, context, comparisons, and transitions can be relevant.

Only classify OFF_TOPIC when the segment is clearly unrelated to the established direction.

Return valid JSON matching the requested schema ONLY."""

def build_chunk_analysis_messages(
    video_id: str,
    chunk_id: str,
    reference_hook: Dict[str, Any],
    segments_to_analyze: List[Dict[str, Any]]
) -> List[Dict[str, str]]:
    """Constructs prompt messages for analyzing a chunk of semantic segments."""
    oa = reference_hook.get("opening_analysis", {})
    promise_desc = oa.get("promise", {}).get("description", "")
    expected_dir = oa.get("expected_direction", "")
    expected_pts = oa.get("expected_points", [])

    pts_text_lines = []
    for pt in expected_pts:
        pts_text_lines.append(f"{pt.get('point_id')}: {pt.get('description')}")
    pts_block = "\n".join(pts_text_lines)

    seg_blocks = []
    for seg in segments_to_analyze:
        seg_str = (
            f"[SEGMENT {seg['segment_id']}]\n"
            f"TIME: {seg['start_time']:.2f} - {seg['end_time']:.2f}\n"
            f"LANGUAGE: {seg.get('language', 'UNKNOWN')}\n"
            f"TEXT:\n{seg['text']}"
        )
        seg_blocks.append(seg_str)
    formatted_segs = "\n\n".join(seg_blocks)

    user_content = f"""CREATOR PROMISE:
{promise_desc}

EXPECTED POINTS:
{pts_block}

EXPECTED DIRECTION:
{expected_dir}

CURRENT TRANSCRIPT SEGMENTS TO ANALYZE:

{formatted_segs}

Return ONLY a single valid JSON object with NO markdown wrapper:
{{
    "video_id": "{video_id}",
    "chunk_id": "{chunk_id}",
    "segment_analyses": [
        {{
            "segment_id": 3,
            "start_time": 0.0,
            "end_time": 0.0,
            "primary_point": "P1 | P2 | P3 | P4 | NONE | MULTIPLE | UNCERTAIN",
            "function": "DIRECT_POINT | SUPPORTING_EXPLANATION | EVIDENCE | EXAMPLE | COMPARISON | TRANSITION | CONTEXT | CONCLUSION | RELATED_EXTENSION | OFF_TOPIC | UNCERTAIN",
            "relevance": "DIRECT | SUPPORTING | RELATED | TRANSITION | UNCERTAIN | OFF_TOPIC",
            "confidence": 0.95,
            "evidence": "Short exact text excerpt from segment"
        }}
    ]
}}

CLASSIFICATION TAXONOMIES:
- function: DIRECT_POINT, SUPPORTING_EXPLANATION, EVIDENCE, EXAMPLE, COMPARISON, TRANSITION, CONTEXT, CONCLUSION, RELATED_EXTENSION, OFF_TOPIC, UNCERTAIN
- relevance: DIRECT (directly covers P1-P4), SUPPORTING (gives background/evidence/numbers/examples for a point), RELATED (relevant to direction but not specific P1-P4), TRANSITION (moves between topics), UNCERTAIN, OFF_TOPIC (clearly unrelated)
- primary_point: P1, P2, P3, P4, NONE, MULTIPLE, UNCERTAIN

RULES:
1. Timestamps MUST match the supplied segment timestamps exactly.
2. Evidence text MUST be a short verbatim excerpt from that specific segment.
3. Return valid JSON only with NO markdown wrappers."""

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content}
    ]

def analyze_segment_chunk(
    video_id: str,
    chunk_id: str,
    reference_hook: Dict[str, Any],
    segments_to_analyze: List[Dict[str, Any]],
    client: LMStudioClient,
    temperature: float = 0.1,
    max_tokens: int = 3500
) -> Dict[str, Any]:
    """Sends a single batch of semantic segments to Qwen and parses the JSON analysis."""
    messages = build_chunk_analysis_messages(video_id, chunk_id, reference_hook, segments_to_analyze)
    input_char_count = sum(len(m["content"]) for m in messages)

    raw_response_text, latency = client.send_completion(
        messages=messages,
        model_id=client.model_id,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=600
    )

    cleaned_json_str = re.sub(r'^```(?:json)?\s*', '', raw_response_text, flags=re.IGNORECASE)
    cleaned_json_str = re.sub(r'\s*```$', '', cleaned_json_str).strip()

    parsed_json = {}
    json_valid = True
    parse_error = ""

    try:
        parsed_json = json.loads(cleaned_json_str)
    except json.JSONDecodeError as e:
        match = re.search(r'(\{[\s\S]*\})', raw_response_text)
        if match:
            try:
                parsed_json = json.loads(match.group(1))
            except Exception as e2:
                json_valid = False
                parse_error = str(e2)
        else:
            json_valid = False
            parse_error = str(e)

    seg_analyses = parsed_json.get("segment_analyses", []) if isinstance(parsed_json, dict) else []

    # Map timestamps & segment_id if missing or mismatch
    for idx, seg in enumerate(segments_to_analyze):
        if idx < len(seg_analyses):
            sa = seg_analyses[idx]
            sa["segment_id"] = seg["segment_id"]
            sa["start_time"] = seg["start_time"]
            sa["end_time"] = seg["end_time"]

    return {
        "chunk_id": chunk_id,
        "raw_response": raw_response_text,
        "parsed_json": parsed_json,
        "segment_analyses": seg_analyses,
        "input_char_count": input_char_count,
        "output_char_count": len(raw_response_text),
        "latency_seconds": latency,
        "json_valid": json_valid,
        "parse_error": parse_error
    }
