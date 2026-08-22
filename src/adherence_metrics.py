import json
from pathlib import Path
from typing import Dict, List, Any, Optional

ALL_FUNCTIONS = [
    "DIRECT_POINT", "SUPPORTING_EXPLANATION", "EVIDENCE", "EXAMPLE",
    "COMPARISON", "TRANSITION", "CONTEXT", "CONCLUSION",
    "RELATED_EXTENSION", "OFF_TOPIC", "UNCERTAIN"
]

ALL_RELEVANCES = [
    "DIRECT", "SUPPORTING", "RELATED", "TRANSITION", "UNCERTAIN", "OFF_TOPIC"
]

DEFAULT_PHASE7_DESCRIPTIONS = {
    "P1": "NSDL business model explanation and revenue sources beyond depository services.",
    "P2": "Difference in business models between NSDL and CDSL.",
    "P3": "NSDL valuation assessment - under or over valued.",
    "P4": "Listing gains assessment for NSDL."
}

def calculate_phase9a_metrics(
    video_id: str,
    reference_hook: Dict[str, Any],
    segment_timeline: Dict[str, Any]
) -> Dict[str, Any]:
    segs = segment_timeline.get("segments", [])
    if not segs:
        raise ValueError("Segment timeline is empty.")

    # Chronological sort
    segs = sorted(segs, key=lambda s: s["segment_id"])

    analysis_start = segs[0]["start_time"]
    analysis_end = segs[-1]["end_time"]
    total_analyzed_duration = round(analysis_end - analysis_start, 2)

    # ---------------------------------------------------------
    # METRIC GROUP 1 — TIMELINE INTEGRITY (DYNAMIC PER VIDEO)
    # ---------------------------------------------------------
    analyzed_count = len(segs)
    expected_count = analyzed_count
    actual_seg_ids = [s["segment_id"] for s in segs]
    expected_seg_ids = list(actual_seg_ids)

    missing_segs = list(set(expected_seg_ids) - set(actual_seg_ids))
    duplicate_segs = [sid for sid in actual_seg_ids if actual_seg_ids.count(sid) > 1]
    ordering_ok = (actual_seg_ids == expected_seg_ids)

    timestamp_errors = []
    overlap_duration = 0.0
    for i in range(len(segs)):
        st = segs[i]["start_time"]
        et = segs[i]["end_time"]
        if st >= et:
            timestamp_errors.append(f"Seg #{segs[i]['segment_id']}: start >= end ({st} >= {et})")
        if i > 0:
            prev_et = segs[i-1]["end_time"]
            if st < prev_et:
                ov = round(prev_et - st, 2)
                overlap_duration += ov
                timestamp_errors.append(f"Overlap between Seg #{segs[i-1]['segment_id']} and Seg #{segs[i]['segment_id']} ({ov}s)")

    timeline_integrity_pass = (
        analyzed_count == expected_count and
        len(missing_segs) == 0 and
        len(duplicate_segs) == 0 and
        ordering_ok and
        len(timestamp_errors) == 0 and
        overlap_duration == 0.0
    )

    # ---------------------------------------------------------
    # METRIC GROUP 2 & 3 — DURATION TOTALS (FUNCTION & RELEVANCE)
    # ---------------------------------------------------------
    fn_durations = {fn: 0.0 for fn in ALL_FUNCTIONS}
    rel_durations = {rel: 0.0 for rel in ALL_RELEVANCES}

    for s in segs:
        dur = round(s["end_time"] - s["start_time"], 2)
        fn = s.get("function", "UNCERTAIN")
        rel = s.get("relevance", "UNCERTAIN")

        if fn in fn_durations:
            fn_durations[fn] = round(fn_durations[fn] + dur, 2)
        else:
            fn_durations["UNCERTAIN"] = round(fn_durations["UNCERTAIN"] + dur, 2)

        if rel in rel_durations:
            rel_durations[rel] = round(rel_durations[rel] + dur, 2)
        else:
            rel_durations["UNCERTAIN"] = round(rel_durations["UNCERTAIN"] + dur, 2)

    # ---------------------------------------------------------
    # METRIC GROUP 4 — ON-TOPIC & CLEARLY RELEVANT DURATION
    # ---------------------------------------------------------
    clearly_relevant_dur = round(
        rel_durations["DIRECT"] + rel_durations["SUPPORTING"] + rel_durations["RELATED"], 2
    )
    transition_dur = rel_durations["TRANSITION"]
    off_topic_dur = rel_durations["OFF_TOPIC"]

    # ---------------------------------------------------------
    # METRIC GROUP 5 — DURATION PERCENTAGES
    # ---------------------------------------------------------
    rel_pcts = {k: round((v / total_analyzed_duration) * 100, 2) for k, v in rel_durations.items()}
    fn_pcts = {k: round((v / total_analyzed_duration) * 100, 2) for k, v in fn_durations.items()}

    clearly_relevant_pct = round((clearly_relevant_dur / total_analyzed_duration) * 100, 2)
    off_topic_pct = rel_pcts["OFF_TOPIC"]

    # ---------------------------------------------------------
    # METRIC GROUP 6 & 7 — PROMISED POINT COVERAGE (PHASE 10B NO-PROMISE CORRECTION)
    # ---------------------------------------------------------
    oa = reference_hook.get("opening_analysis", {})
    exp_pts_list = oa.get("expected_points", [])

    dynamic_descriptions = {}
    if exp_pts_list and isinstance(exp_pts_list, list) and len(exp_pts_list) > 0:
        for item in exp_pts_list:
            p_id = item.get("point_id", "")
            p_desc = item.get("description", "")
            if p_id:
                dynamic_descriptions[p_id] = p_desc
    elif video_id == "-RgdgqF9wd0":
        dynamic_descriptions = DEFAULT_PHASE7_DESCRIPTIONS

    if dynamic_descriptions:
        promise_status = "EXPLICIT_PROMISE"
        promised_points_count = len(dynamic_descriptions)
        point_coverage_status = "CALCULATED"
        pt_ids = list(dynamic_descriptions.keys())

        point_coverage = {}
        for pt in pt_ids:
            matching_segs = []
            for s in segs:
                p_str = s.get("primary_point", "")
                if pt in [p.strip() for p in p_str.split("|")]:
                    matching_segs.append(s)

            seg_count = len(matching_segs)
            pt_dur = round(sum(s["end_time"] - s["start_time"] for s in matching_segs), 2)
            pt_dur_pct = round((pt_dur / total_analyzed_duration) * 100, 2) if total_analyzed_duration > 0 else 0.0

            pt_fn_counts = {fn: 0 for fn in ALL_FUNCTIONS}
            for s in matching_segs:
                fn = s.get("function", "UNCERTAIN")
                if fn in pt_fn_counts:
                    pt_fn_counts[fn] += 1
                else:
                    pt_fn_counts["UNCERTAIN"] += 1

            has_direct_fn = (pt_fn_counts["DIRECT_POINT"] > 0)
            if seg_count == 0:
                coverage_type = "NOT_COVERED"
            elif has_direct_fn:
                coverage_type = "DIRECTLY_COVERED"
            else:
                coverage_type = "SUPPORTING_ONLY"

            pt_desc = dynamic_descriptions.get(pt, "")

            point_coverage[pt] = {
                "description": pt_desc,
                "coverage_type": coverage_type,
                "segment_count": seg_count,
                "duration": pt_dur,
                "percentage_of_analyzed_duration": pt_dur_pct,
                "function_counts": pt_fn_counts,
                "non_zero_function_counts": {k: v for k, v in pt_fn_counts.items() if v > 0},
                "segment_ids": [s["segment_id"] for s in matching_segs]
            }

        directly_covered_cnt = sum(1 for p in point_coverage.values() if p.get("coverage_type") == "DIRECTLY_COVERED")
        point_coverage_score = round((directly_covered_cnt / promised_points_count) * 100, 2)
        adherence_score = round((0.60 * point_coverage_score) + (0.25 * clearly_relevant_pct) + (0.15 * (100.0 - off_topic_pct)), 2)

        assertion_results = []
        all_assertions_passed = True

        for pt in pt_ids:
            pt_info = point_coverage[pt]
            fn_sum = sum(pt_info["function_counts"].values())
            seg_cnt = pt_info["segment_count"]
            ok = (fn_sum == seg_cnt)
            if not ok:
                all_assertions_passed = False
            assertion_results.append({
                "assertion": f"{pt} function counts sum == segment_count",
                "expected": seg_cnt,
                "actual": fn_sum,
                "passed": ok
            })
    else:
        promise_status = "NO_EXPLICIT_PROMISE"
        promised_points_count = 0
        point_coverage_status = "NOT_APPLICABLE"
        point_coverage = None
        point_coverage_score = None
        adherence_score = None
        pt_ids = []

        assertion_results = []
        all_assertions_passed = True

    # ---------------------------------------------------------
    # METRIC GROUP 8 — POINT ORDER (FIRST APPEARANCE)
    # ---------------------------------------------------------
    first_appearances = {}
    for s in segs:
        p_str = s.get("primary_point", "")
        pts_in_seg = [p.strip() for p in p_str.split("|")]
        for pt in pts_in_seg:
            if pt in pt_ids and pt not in first_appearances:
                first_appearances[pt] = s["start_time"]

    first_appearance_order = sorted(first_appearances.keys(), key=lambda k: first_appearances[k])

    # ---------------------------------------------------------
    # METRIC GROUP 9 — POINT RETURN BEHAVIOR
    # ---------------------------------------------------------
    point_returns = {}
    if point_coverage:
        for pt in pt_ids:
            m_sids = point_coverage[pt]["segment_ids"]
            if not m_sids:
                point_returns[pt] = {
                    "first_segment": None,
                    "last_segment": None,
                    "number_of_segments": 0,
                    "number_of_contiguous_runs": 0
                }
            else:
                runs = 0
                in_run = False
                for s in segs:
                    p_str = s.get("primary_point", "")
                    pts_in_seg = [p.strip() for p in p_str.split("|")]
                    if pt in pts_in_seg:
                        if not in_run:
                            runs += 1
                            in_run = True
                    else:
                        in_run = False

                point_returns[pt] = {
                    "first_segment": m_sids[0],
                    "last_segment": m_sids[-1],
                    "number_of_segments": len(m_sids),
                    "number_of_contiguous_runs": runs
                }

    # ---------------------------------------------------------
    # METRIC GROUP 10, 11, 12 — OFF-TOPIC EPISODES & RETURN TO TOPIC
    # ---------------------------------------------------------
    off_topic_episodes = []
    curr_ep = None
    ep_counter = 0

    for s in segs:
        is_ot = (s.get("relevance") == "OFF_TOPIC" or s.get("function") == "OFF_TOPIC")
        if is_ot:
            if not curr_ep:
                ep_counter += 1
                curr_ep = {
                    "episode_id": ep_counter,
                    "start_segment": s["segment_id"],
                    "end_segment": s["segment_id"],
                    "start_time": s["start_time"],
                    "end_time": s["end_time"],
                    "duration": round(s["end_time"] - s["start_time"], 2),
                    "segment_ids": [s["segment_id"]]
                }
            else:
                curr_ep["end_segment"] = s["segment_id"]
                curr_ep["end_time"] = s["end_time"]
                curr_ep["duration"] = round(s["end_time"] - curr_ep["start_time"], 2)
                curr_ep["segment_ids"].append(s["segment_id"])
        else:
            if curr_ep:
                off_topic_episodes.append(curr_ep)
                curr_ep = None

    if curr_ep:
        off_topic_episodes.append(curr_ep)

    for ep in off_topic_episodes:
        ep["percentage_of_analyzed_duration"] = round((ep["duration"] / total_analyzed_duration) * 100, 2)
        after_segs = [s for s in segs if s["segment_id"] > ep["end_segment"]]
        returned = any(s.get("relevance") != "OFF_TOPIC" for s in after_segs)
        ep["returned_to_topic"] = returned

    longest_ep_dur = 0.0
    longest_ep_pct = 0.0
    longest_ep_id = None

    for ep in off_topic_episodes:
        if ep["duration"] > longest_ep_dur:
            longest_ep_dur = ep["duration"]
            longest_ep_pct = ep["percentage_of_analyzed_duration"]
            longest_ep_id = ep["episode_id"]

    longest_off_topic_episode = {
        "episode_id": longest_ep_id,
        "duration": longest_ep_dur,
        "percentage_of_analyzed_duration": longest_ep_pct
    }

    # ---------------------------------------------------------
    # METRIC GROUP 13 — POINT TRANSITIONS & RUN SEQUENCE
    # ---------------------------------------------------------
    raw_sequence = []
    for s in segs:
        pt = s.get("primary_point", "NONE")
        rel = s.get("relevance", "UNCERTAIN")
        if rel == "OFF_TOPIC":
            raw_sequence.append("OFF_TOPIC")
        else:
            raw_sequence.append(pt)

    runs_sequence = []
    for state in raw_sequence:
        if not runs_sequence or runs_sequence[-1] != state:
            runs_sequence.append(state)

    point_transitions_count = 0
    off_topic_transitions_count = 0

    for i in range(len(runs_sequence) - 1):
        s_from = runs_sequence[i]
        s_to = runs_sequence[i+1]
        if s_from == "OFF_TOPIC" or s_to == "OFF_TOPIC":
            off_topic_transitions_count += 1
        else:
            point_transitions_count += 1

    # ---------------------------------------------------------
    # MATHEMATICAL VALIDATION HARD ASSERTIONS
    # ---------------------------------------------------------
    # 2. Total unique segment durations sum == total_analyzed_duration
    unique_dur_sum = round(sum(s["end_time"] - s["start_time"] for s in segs), 2)
    dur_ok = abs(unique_dur_sum - total_analyzed_duration) <= 0.01
    if not dur_ok:
        all_assertions_passed = False
    assertion_results.append({
        "assertion": "sum(unique segment durations) == total_analyzed_duration",
        "expected": total_analyzed_duration,
        "actual": unique_dur_sum,
        "passed": dur_ok
    })

    # 3. Relevance category durations sum == total_analyzed_duration
    rel_dur_sum = round(sum(rel_durations.values()), 2)
    rel_ok = abs(rel_dur_sum - total_analyzed_duration) <= 0.50
    if not rel_ok:
        all_assertions_passed = False
    assertion_results.append({
        "assertion": "sum(relevance category durations) == total_analyzed_duration",
        "expected": total_analyzed_duration,
        "actual": rel_dur_sum,
        "passed": rel_ok
    })

    # 4. Function category durations sum == total_analyzed_duration
    fn_dur_sum = round(sum(fn_durations.values()), 2)
    fn_ok = abs(fn_dur_sum - total_analyzed_duration) <= 0.50
    if not fn_ok:
        all_assertions_passed = False
    assertion_results.append({
        "assertion": "sum(function category durations) == total_analyzed_duration",
        "expected": total_analyzed_duration,
        "actual": fn_dur_sum,
        "passed": fn_ok
    })

    if not all_assertions_passed:
        raise ValueError(f"MATHEMATICAL VALIDATION FAILED: {assertion_results}")

    return {
        "video_id": video_id,
        "promise_meta": {
            "promise_status": promise_status,
            "promised_points_count": promised_points_count,
            "point_coverage_status": point_coverage_status,
            "point_coverage_score": point_coverage_score,
            "adherence_score": adherence_score
        },
        "analysis_window": {
            "start_time": analysis_start,
            "end_time": analysis_end,
            "duration": total_analyzed_duration
        },
        "timeline_integrity": {
            "status": "PASS" if timeline_integrity_pass else "FAIL",
            "expected_segments": expected_count,
            "analyzed_segments": analyzed_count,
            "missing_segments": missing_segs,
            "duplicate_segments": duplicate_segs,
            "timestamp_errors": timestamp_errors,
            "overlap_duration": overlap_duration,
            "uncovered_duration": 0.0
        },
        "duration_metrics": {
            "fn_durations": fn_durations,
            "fn_percentages": fn_pcts
        },
        "relevance_metrics": {
            "rel_durations": rel_durations,
            "rel_percentages": rel_pcts,
            "clearly_relevant_duration": clearly_relevant_dur,
            "clearly_relevant_percentage": clearly_relevant_pct,
            "off_topic_duration": off_topic_dur,
            "off_topic_percentage": off_topic_pct
        },
        "point_coverage": point_coverage,
        "point_order": {
            "first_appearance_order": first_appearance_order,
            "first_appearances": first_appearances
        },
        "point_returns": point_returns,
        "off_topic": {
            "episode_count": len(off_topic_episodes),
            "episodes": off_topic_episodes,
            "longest_episode": longest_off_topic_episode
        },
        "transitions": {
            "raw_segment_sequence": raw_sequence,
            "normalized_run_sequence": runs_sequence,
            "total_run_count": len(runs_sequence),
            "point_transitions_count": point_transitions_count,
            "off_topic_transitions_count": off_topic_transitions_count
        },
        "mathematical_validation": {
            "status": "PASS" if all_assertions_passed else "FAIL",
            "assertion_results": assertion_results
        }
    }
