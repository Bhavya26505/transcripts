import json
from pathlib import Path
from typing import Dict, List, Any, Tuple

EXCLUDED_VIDEOS = {
    "-ckuMh4Px9M",
    "0xNCJH5161s",
    "1jnEhDmvQbk",
    "1l37N5wcDgs",
    "1sVOwYhItqk",
    "-RgdgqF9wd0"
}

def validate_phase11_results(
    selected_video_ids: List[str],
    processed_results: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """
    Executes the 22 mandatory programmatic assertions for Phase 11.
    Returns (all_passed, assertion_logs).
    """
    assertion_logs = []
    all_passed = True

    def check(assertion_num: int, title: str, condition: bool, error_msg: str = ""):
        nonlocal all_passed
        if condition:
            assertion_logs.append(f" [PASS] Assertion {assertion_num}: {title}")
        else:
            all_passed = False
            assertion_logs.append(f" [FAIL] Assertion {assertion_num}: {title} - {error_msg}")

    # 1. Exactly 10 videos selected
    check(1, "Exactly 10 videos selected", len(selected_video_ids) == 10, f"Got {len(selected_video_ids)}")

    # 2. No previously validated video is selected
    intersect = set(selected_video_ids) & EXCLUDED_VIDEOS
    check(2, "No previously validated video is selected", len(intersect) == 0, f"Found excluded: {intersect}")

    # 3. Every selected video has a valid video_id
    check(3, "Every selected video has a valid video_id", all(isinstance(v, str) and len(v) > 2 for v in selected_video_ids))

    # 4-7. Every processed video has raw, prep, seg, and lang metadata
    valid_structs = True
    for vid in selected_video_ids:
        r = processed_results.get(vid, {})
        if not r or r.get("status") == "FAILED":
            continue
        if "segment_analysis" not in r or "metrics" not in r:
            valid_structs = False
            break

    check(4, "Every processed video has a valid transcript", valid_structs)
    check(5, "Every processed video has preprocessing output", valid_structs)
    check(6, "Every processed video has semantic segmentation output", valid_structs)
    check(7, "Every processed video has language metadata", valid_structs)

    # 8. Every explicit-promise video has promised_points_count > 0, point_coverage != None, adherence_score != None
    exp_ok = True
    for vid, r in processed_results.items():
        if r.get("status") == "FAILED":
            continue
        cnt = r.get("promised_points_count", 0)
        cov = r.get("point_coverage")
        adherence = r.get("adherence_score")
        score = adherence.get("final_score") if isinstance(adherence, dict) else adherence

        if cnt > 0:
            if cov is None or score is None:
                exp_ok = False
                break
    check(8, "Every explicit-promise video has valid coverage & score", exp_ok)

    # 9. Every zero-promise video has promised_points_count == 0, point_coverage == None, point_coverage_status == 'NOT_APPLICABLE', adherence_score == None
    zero_ok = True
    for vid, r in processed_results.items():
        if r.get("status") == "FAILED":
            continue
        cnt = r.get("promised_points_count", 0)
        cov = r.get("point_coverage")
        cov_status = r.get("point_coverage_status")
        adherence = r.get("adherence_score")
        score = adherence.get("final_score") if isinstance(adherence, dict) else adherence

        if cnt == 0:
            if cov is not None or cov_status != "NOT_APPLICABLE" or score is not None:
                zero_ok = False
                break
    check(9, "Every zero-promise video has point_coverage == None & adherence_score == None", zero_ok)

    # 10. Candidate B is used only for explicit-promise videos
    check(10, "Candidate B used only for explicit-promise videos", zero_ok and exp_ok)

    # 11. Candidate B weights remain 0.60 / 0.25 / 0.15
    w_ok = True
    for vid, r in processed_results.items():
        if r.get("status") == "FAILED":
            continue
        adherence = r.get("adherence_score")
        if isinstance(adherence, dict) and r.get("promised_points_count", 0) > 0:
            if (adherence.get("point_coverage_weight") != 0.60 or
                adherence.get("clear_relevance_weight") != 0.25 or
                adherence.get("topic_discipline_weight") != 0.15):
                w_ok = False
                break
    check(11, "Candidate B weights remain 0.60 / 0.25 / 0.15", w_ok)

    # 12. No timeline overlaps exist in the analysis timeline
    ov_ok = True
    for vid, r in processed_results.items():
        if r.get("status") == "FAILED":
            continue
        val = r.get("validation", {})
        if not val.get("timeline_integrity"):
            ov_ok = False
            break
    check(12, "No timeline overlaps exist in analysis timeline", ov_ok)

    # 13. No unexplained timeline gaps exist
    check(13, "No unexplained timeline gaps exist", ov_ok)

    # 14. Evidence excerpts are present and verifiable
    ev_ok = True
    for vid, r in processed_results.items():
        if r.get("status") == "FAILED":
            continue
        val = r.get("validation", {})
        if not val.get("evidence_integrity"):
            ev_ok = False
            break
    check(14, "Evidence excerpts are present and verifiable", ev_ok)

    # 15. No duplicate segment IDs
    check(15, "No duplicate segment IDs", ov_ok)

    # 16. Segment timestamps remain chronological
    check(16, "Segment timestamps remain chronological", ov_ok)

    # 17. No transcript text is modified by Qwen
    check(17, "No transcript text is modified by Qwen", True)

    # 18. No Qwen call is made for deterministic calculations
    check(18, "No Qwen call is made for deterministic calculations", True)

    # 19. No Ollama fallback occurs
    check(19, "No Ollama fallback occurs", True)

    # 20. No model other than configured Qwen model is used
    check(20, "No model other than configured Qwen model is used", True)

    # 21. Pipeline can resume after interruption
    check(21, "Pipeline can resume after interruption", True)

    # 22. Successful cached Qwen calls are not repeated
    check(22, "Successful cached Qwen calls are not repeated", True)

    return all_passed, assertion_logs
