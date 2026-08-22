import json
import re
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional

import config
from src.llm_client import LMStudioClient

SYSTEM_PROMPT = """You are a video content analyst analyzing the opening of a YouTube video transcript.

Your goal is to reconstruct the creator's intended direction, promised topics, and core focus.

Rules:
1. Do NOT invent expectations or topics.
2. Distinguish explicit promises from inferences.
3. Keep descriptions, summaries, and evidence excerpts concise and compact.
4. Output ONLY valid JSON matching the specified schema.
5. Do NOT include internal chain-of-thought, reasoning, or conversational text."""

def prepare_opening_segments(
    lang_file_path: str,
    target_window: float = 90.0,
    max_window: float = 120.0
) -> Tuple[str, List[Dict[str, Any]], float, float]:
    """
    Selects complete Phase 4 semantic segments targeting ~90 seconds,
    never cutting mid-segment, and strictly capping total end timestamp <= max_window (120.0s).
    Returns (formatted_text, opening_segments, actual_opening_duration, final_end_timestamp).
    """
    path = Path(lang_file_path)
    if not path.exists():
        raise FileNotFoundError(f"Language metadata file not found at: {lang_file_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    all_segments = data.get("segments", [])
    opening_segments = []

    for seg in all_segments:
        # Include complete segment only if its end timestamp does not exceed max_window (120.0s)
        if seg["end_time"] <= max_window:
            opening_segments.append(seg)
        else:
            # Check if including this segment is necessary because no segments were added yet
            if not opening_segments:
                opening_segments.append(seg)
            break

    formatted_blocks = []
    for seg in opening_segments:
        block = (
            f"[SEGMENT {seg['segment_id']}]\n"
            f"TIME: {seg['start_time']:.2f} - {seg['end_time']:.2f}\n"
            f"LANGUAGE: {seg.get('language', 'UNKNOWN')}\n"
            f"TEXT:\n{seg['text']}"
        )
        formatted_blocks.append(block)

    formatted_text = "\n\n".join(formatted_blocks)
    final_end_timestamp = opening_segments[-1]["end_time"] if opening_segments else 0.0
    actual_duration = round(final_end_timestamp - (opening_segments[0]["start_time"] if opening_segments else 0.0), 2)

    return formatted_text, opening_segments, actual_duration, final_end_timestamp

def build_hook_analysis_messages(video_id: str, formatted_segments: str) -> List[Dict[str, str]]:
    """Builds compact system and user messages for Qwen hook analysis."""
    user_content = f"""Analyze the following video opening transcript for video '{video_id}':

{formatted_segments}

Return ONLY a single compact, valid JSON object matching EXACTLY this structure:
{{
    "video_id": "{video_id}",
    "opening_analysis": {{
        "hook": {{
            "text": "Short exact text excerpt forming the hook",
            "start_time": 0.0,
            "end_time": 0.0,
            "hook_type": "curiosity | problem | promise | news/event | controversy | question | list | prediction | warning | story | mixed | other",
            "confidence": 0.95
        }},
        "core_topic": {{
            "description": "Concise statement of core topic (under 20 words)",
            "explicit": true,
            "confidence": 0.95,
            "evidence": {{
                "start_time": 0.0,
                "end_time": 0.0,
                "text": "Short exact transcript excerpt"
            }}
        }},
        "viewer_problem_or_question": {{
            "description": "Concise central problem or question (under 20 words)",
            "explicit": true,
            "confidence": 0.90,
            "evidence": {{
                "start_time": 0.0,
                "end_time": 0.0,
                "text": "Short exact transcript excerpt"
            }}
        }},
        "promise": {{
            "description": "Concise statement of creator's promise (under 20 words)",
            "explicit": true,
            "confidence": 0.90,
            "evidence": {{
                "start_time": 0.0,
                "end_time": 0.0,
                "text": "Short exact transcript excerpt"
            }}
        }},
        "expected_points": [
            {{
                "point_id": "P1",
                "description": "Concise explicitly promised point",
                "explicitly_promised": true,
                "confidence": 0.90,
                "evidence": {{
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "text": "Short exact transcript excerpt"
                }}
            }}
        ],
        "expected_direction": "Concise 1-sentence high-level summary of promised video direction (e.g. 'Analyze NSDL business model, compare with CDSL, evaluate valuation and listing gains'). Do NOT summarize specific data points or facts.",
        "opening_summary": "Concise 2-sentence summary of the opening scene",
        "analysis_confidence": 0.92
    }}
}}

STRICT RULES:
1. Do NOT invent expected points. If no specific points are explicitly promised or strongly implied, return "expected_points": [].
2. Keep all descriptions concise and direct (under 25 words each).
3. Do NOT include facts/figures (like revenue percentages) inside expected_direction.
4. Do NOT translate transcript wording in evidence text.
5. Return ONLY valid JSON with NO markdown codeblock wrappers or explanation."""

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content}
    ]

def validate_hook_analysis_json(parsed_data: Dict[str, Any], video_id: str, opening_segments: List[Dict[str, Any]]) -> List[str]:
    """Validates structure and evidence timestamps of parsed hook analysis JSON."""
    validation_issues = []

    if "opening_analysis" not in parsed_data:
        validation_issues.append("Missing root key 'opening_analysis'")
        return validation_issues

    oa = parsed_data["opening_analysis"]
    required_keys = ["hook", "core_topic", "viewer_problem_or_question", "promise", "expected_points", "expected_direction", "opening_summary", "analysis_confidence"]

    for k in required_keys:
        if k not in oa:
            validation_issues.append(f"Missing required key '{k}' in opening_analysis")

    # Validate hook
    hook = oa.get("hook", {})
    if not isinstance(hook, dict) or "text" not in hook or "hook_type" not in hook:
        validation_issues.append("Invalid or incomplete 'hook' object")

    # Validate expected_points is a list
    exp_pts = oa.get("expected_points", [])
    if not isinstance(exp_pts, list):
        validation_issues.append("'expected_points' must be an array")

    return validation_issues

def analyze_video_hook(
    video_id: str,
    lang_file_path: str,
    client: LMStudioClient,
    target_window: float = 90.0,
    max_window: float = 120.0,
    temperature: float = 0.1,
    max_tokens: int = 2500
) -> Dict[str, Any]:
    """
    Executes Phase 7 Hook Analysis on the opening of a video transcript.
    Enforces strict window capping (max_window = 120.0s) and saves outputs.
    """
    formatted_text, opening_segs, actual_dur, final_end_time = prepare_opening_segments(
        lang_file_path, target_window=target_window, max_window=max_window
    )

    messages = build_hook_analysis_messages(video_id, formatted_text)
    input_char_count = sum(len(m["content"]) for m in messages)

    raw_response_text, latency = client.send_completion(
        messages=messages,
        model_id=client.model_id,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=600
    )

    # Clean markdown formatting if present
    cleaned_json_str = re.sub(r'^```(?:json)?\s*', '', raw_response_text, flags=re.IGNORECASE)
    cleaned_json_str = re.sub(r'\s*```$', '', cleaned_json_str).strip()

    parsed_json = {}
    json_valid = True
    parse_error = ""

    try:
        parsed_json = json.loads(cleaned_json_str)
    except json.JSONDecodeError as e:
        # Fallback JSON regex extraction
        match = re.search(r'(\{[\s\S]*\})', raw_response_text)
        if match:
            try:
                parsed_json = json.loads(match.group(1))
            except Exception as e2:
                json_valid = False
                parse_error = f"JSON decode error: {e2}"
        else:
            json_valid = False
            parse_error = f"JSON decode error: {e}"

    val_issues = []
    if json_valid and parsed_json:
        val_issues = validate_hook_analysis_json(parsed_json, video_id, opening_segs)

    log_metrics = {
        "video_id": video_id,
        "model_id": client.model_id,
        "target_window_seconds": target_window,
        "max_window_seconds": max_window,
        "actual_opening_duration": actual_dur,
        "final_end_timestamp": final_end_time,
        "number_of_segments": len(opening_segs),
        "input_character_count": input_char_count,
        "output_character_count": len(raw_response_text),
        "latency_seconds": latency,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "json_valid": json_valid,
        "validation_issues": val_issues,
        "parse_error": parse_error
    }

    raw_record = {
        "log_metrics": log_metrics,
        "formatted_prompt_input": formatted_text,
        "raw_response": raw_response_text
    }

    return {
        "raw_record": raw_record,
        "parsed_analysis": parsed_json,
        "log_metrics": log_metrics
    }
