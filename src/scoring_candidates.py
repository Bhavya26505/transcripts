import json
from pathlib import Path
from typing import Dict, List, Any

def calculate_phase9b_candidate_scores(
    video_id: str,
    phase9a_metrics: Dict[str, Any]
) -> Dict[str, Any]:
    win = phase9a_metrics.get("analysis_window", {})
    rel_m = phase9a_metrics.get("relevance_metrics", {})
    cov_m = phase9a_metrics.get("point_coverage", {})
    ot_m = phase9a_metrics.get("off_topic", {})
    order_m = phase9a_metrics.get("point_order", {})
    ret_m = phase9a_metrics.get("point_returns", {})

    total_analyzed_duration = win.get("duration", 561.56)

    # ---------------------------------------------------------
    # SCORING DIMENSION A — POINT COVERAGE SCORE
    # ---------------------------------------------------------
    total_promised_points = len(cov_m)
    directly_covered_count = sum(1 for pt_info in cov_m.values() if pt_info.get("coverage_type") == "DIRECTLY_COVERED")
    supporting_only_count = sum(1 for pt_info in cov_m.values() if pt_info.get("coverage_type") == "SUPPORTING_ONLY")
    not_covered_count = sum(1 for pt_info in cov_m.values() if pt_info.get("coverage_type") == "NOT_COVERED")

    point_coverage_score = round((directly_covered_count / total_promised_points) * 100, 2) if total_promised_points > 0 else 0.0

    # ---------------------------------------------------------
    # SCORING DIMENSION B — CLEARLY RELEVANT DURATION SCORE
    # ---------------------------------------------------------
    clearly_relevant_dur = rel_m.get("clearly_relevant_duration", 0.0)
    clear_relevance_score = round((clearly_relevant_dur / total_analyzed_duration) * 100, 2) if total_analyzed_duration > 0 else 0.0

    # ---------------------------------------------------------
    # SCORING DIMENSION C — TOPIC DISCIPLINE SCORE
    # ---------------------------------------------------------
    off_topic_pct = rel_m.get("off_topic_percentage", 0.0)
    topic_discipline_score = round(100.0 - off_topic_pct, 2)

    # ---------------------------------------------------------
    # SCORING DIMENSION D — OFF-TOPIC EPISODES & DIAGNOSTIC METRICS
    # ---------------------------------------------------------
    episodes = ot_m.get("episodes", [])
    episode_count = len(episodes)
    longest_ep_info = ot_m.get("longest_episode", {})
    longest_ep_pct = longest_ep_info.get("percentage_of_analyzed_duration", 0.0)

    # Check midroll episode return
    midroll_episodes = [ep for ep in episodes if ep.get("end_segment") < 16]
    returned_to_topic_after_midroll = all(ep.get("returned_to_topic", False) for ep in midroll_episodes) if midroll_episodes else True

    # ---------------------------------------------------------
    # SCORING DIMENSION E — POINT DISTRIBUTION
    # ---------------------------------------------------------
    point_distribution = {}
    for pt_id, pt_info in cov_m.items():
        dur = pt_info.get("duration", 0.0)
        pct_of_relevant = round((dur / clearly_relevant_dur) * 100, 2) if clearly_relevant_dur > 0 else 0.0
        point_distribution[pt_id] = {
            "point_duration": dur,
            "percentage_of_clearly_relevant_duration": pct_of_relevant
        }

    # ---------------------------------------------------------
    # DIAGNOSTIC PENALTY METRICS
    # ---------------------------------------------------------
    missing_point_count = not_covered_count
    missing_point_percentage = round((missing_point_count / total_promised_points) * 100, 2) if total_promised_points > 0 else 0.0

    # ---------------------------------------------------------
    # CANDIDATE FORMULAS CALCULATION
    # ---------------------------------------------------------
    # Candidate A — Balanced (40% Coverage, 40% Relevance, 20% Discipline)
    score_A_raw = (0.40 * point_coverage_score) + (0.40 * clear_relevance_score) + (0.20 * topic_discipline_score)
    score_A = round(score_A_raw, 2)

    # Candidate B — Promise-First (60% Coverage, 25% Relevance, 15% Discipline)
    score_B_raw = (0.60 * point_coverage_score) + (0.25 * clear_relevance_score) + (0.15 * topic_discipline_score)
    score_B = round(score_B_raw, 2)

    # Candidate C — Focus-First (30% Coverage, 30% Relevance, 40% Discipline)
    score_C_raw = (0.30 * point_coverage_score) + (0.30 * clear_relevance_score) + (0.40 * topic_discipline_score)
    score_C = round(score_C_raw, 2)

    # Score Sanity Check Assertions (0 <= score <= 100)
    for s_name, s_val in [("Candidate A", score_A), ("Candidate B", score_B), ("Candidate C", score_C)]:
        if not (0.0 <= s_val <= 100.0):
            raise ValueError(f"SANITY CHECK FAILED: {s_name} ({s_val}) is outside [0, 100] range.")

    return {
        "video_id": video_id,
        "scoring_dimensions": {
            "point_coverage": {
                "score": point_coverage_score,
                "total_promised_points": total_promised_points,
                "directly_covered_count": directly_covered_count,
                "supporting_only_count": supporting_only_count,
                "not_covered_count": not_covered_count
            },
            "clear_relevance": {
                "score": clear_relevance_score,
                "clearly_relevant_duration": clearly_relevant_dur,
                "total_analyzed_duration": total_analyzed_duration
            },
            "topic_discipline": {
                "score": topic_discipline_score,
                "off_topic_duration": rel_m.get("off_topic_duration", 0.0),
                "off_topic_percentage": off_topic_pct
            },
            "off_topic_diagnostics": {
                "episode_count": episode_count,
                "longest_episode_percentage": longest_ep_pct,
                "returned_to_topic_after_midroll": returned_to_topic_after_midroll
            },
            "point_distribution": point_distribution,
            "diagnostic_penalties": {
                "missing_point_count": missing_point_count,
                "missing_point_percentage": missing_point_percentage
            }
        },
        "candidate_scores": {
            "Candidate_A_Balanced": {
                "score": score_A,
                "weights": {"coverage": 0.40, "relevance": 0.40, "discipline": 0.20},
                "formula_description": "40% Point Coverage + 40% Clear Relevance + 20% Topic Discipline"
            },
            "Candidate_B_PromiseFirst": {
                "score": score_B,
                "weights": {"coverage": 0.60, "relevance": 0.25, "discipline": 0.15},
                "formula_description": "60% Point Coverage + 25% Clear Relevance + 15% Topic Discipline"
            },
            "Candidate_C_FocusFirst": {
                "score": score_C,
                "weights": {"coverage": 0.30, "relevance": 0.30, "discipline": 0.40},
                "formula_description": "30% Point Coverage + 30% Clear Relevance + 40% Topic Discipline"
            }
        }
    }
