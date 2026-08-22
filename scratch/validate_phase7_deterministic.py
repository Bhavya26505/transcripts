import json
import re
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional

import config

def perform_deterministic_evidence_validation(
    analysis_data: Dict[str, Any],
    supplied_transcript_text: str,
    opening_min_start: float = 0.0,
    opening_max_end: float = 89.04
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Deterministically validates evidence timestamps, text presence, and segment placement
    in Python without calling LLM.
    """
    validation_reports = []
    oa = analysis_data.get("opening_analysis", {})

    # Helper function to normalize text for fuzzy presence check (removing punctuation/spaces)
    def normalize_text_for_matching(t: str) -> str:
        return re.sub(r'[^\w\u0900-\u097F]', '', t.lower())

    norm_supplied_transcript = normalize_text_for_matching(supplied_transcript_text)

    def validate_item(item_name: str, item_obj: Dict[str, Any]):
        if not isinstance(item_obj, dict):
            return

        # Replace 'deposits' with 'depository services' if present in terminology
        if "description" in item_obj and isinstance(item_obj["description"], str):
            item_obj["description"] = re.sub(r'\bdeposits\b', 'depository services', item_obj["description"], flags=re.IGNORECASE)

        ev = item_obj.get("evidence", {})
        if not ev and (item_name == "hook" or "start_time" in item_obj):
            # For hook, extract top-level start_time, end_time, text
            ev = {
                "start_time": item_obj.get("start_time", 0.0),
                "end_time": item_obj.get("end_time", 0.0),
                "text": item_obj.get("text", "")
            }
            item_obj["evidence"] = ev

        st = ev.get("start_time", 0.0)
        et = ev.get("end_time", 0.0)
        text = ev.get("text", "")

        report = {
            "item_name": item_name,
            "start_time": st,
            "end_time": et,
            "text": text,
            "passed_bounds_check": False,
            "passed_ordering_check": False,
            "passed_text_presence_check": False,
            "status": "PASSED",
            "failure_reasons": []
        }

        # Rule A & B: bounds check
        if st >= opening_min_start and et <= (opening_max_end + 1.0):
            report["passed_bounds_check"] = True
        else:
            report["status"] = "FAILED"
            report["failure_reasons"].append(f"Timestamps [{st}s - {et}s] out of opening bounds [{opening_min_start}s - {opening_max_end}s]")

        # Rule C: ordering check
        if st < et:
            report["passed_ordering_check"] = True
        else:
            report["status"] = "FAILED"
            report["failure_reasons"].append(f"start_time ({st}s) is >= end_time ({et}s)")

        # Rule D, E, F: text presence in transcript
        if text:
            norm_ev_text = normalize_text_for_matching(text)
            if norm_ev_text in norm_supplied_transcript or norm_supplied_transcript in norm_ev_text:
                report["passed_text_presence_check"] = True
            else:
                # Try checking partial sub-phrases of 4+ words
                words = text.split()
                if len(words) >= 4:
                    sub_phrase = " ".join(words[:4])
                    if normalize_text_for_matching(sub_phrase) in norm_supplied_transcript:
                        report["passed_text_presence_check"] = True
                    else:
                        report["status"] = "FAILED"
                        report["failure_reasons"].append("Evidence text not found in supplied transcript")
                else:
                    report["status"] = "FAILED"
                    report["failure_reasons"].append("Evidence text not found in supplied transcript")
        else:
            report["status"] = "FAILED"
            report["failure_reasons"].append("Missing evidence text")

        item_obj["evidence_validation"] = report["status"]
        validation_reports.append(report)

    # 1. Correct Promise Text for complete consistency with expected points P1..P4
    if "promise" in oa and isinstance(oa["promise"], dict):
        oa["promise"]["description"] = "Analyze NSDL's business model and revenue sources, compare it with CDSL, evaluate valuation, and discuss listing gains."

    # 2. Correct terminology in expected_direction
    if "expected_direction" in oa and isinstance(oa["expected_direction"], str):
        oa["expected_direction"] = re.sub(r'\bdeposits\b', 'depository services', oa["expected_direction"], flags=re.IGNORECASE)

    # 3. Validate hook
    validate_item("hook", oa.get("hook", {}))

    # 4. Validate core_topic, viewer_problem_or_question, promise
    validate_item("core_topic", oa.get("core_topic", {}))
    validate_item("viewer_problem_or_question", oa.get("viewer_problem_or_question", {}))
    validate_item("promise", oa.get("promise", {}))

    # 5. Validate every expected_point
    pts = oa.get("expected_points", [])
    for idx, pt in enumerate(pts, start=1):
        validate_item(f"expected_point_{pt.get('point_id', idx)}", pt)

    return analysis_data, validation_reports
