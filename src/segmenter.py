import re
import statistics
from pathlib import Path
from typing import Dict, List, Any, Tuple

import config

# Common Discourse Transition Phrase Starters (English & Hindi)
TRANSITION_STARTERS_REGEX = re.compile(
    r'^(तो आज|आज के इस|सो आज|अब बात|बात करते हैं|आगे बढ़ते|निष्कर्ष|संक्षेप|so today|today in this|let\'s talk|now let\'s|moving on|in conclusion|to summarize|firstly|secondly|thirdly)',
    re.IGNORECASE
)

def count_words(text: str) -> int:
    """Counts words using whitespace splitting."""
    if not text:
        return 0
    return len(text.split())

def ends_with_complete_sentence(text: str) -> bool:
    """Checks if text ends with sentence termination punctuation (. ! ? ।)."""
    if not text:
        return False
    trimmed = text.strip()
    return trimmed.endswith(('.', '!', '?', '।'))

def is_transition_starter(text: str) -> bool:
    """Checks if text starts with a discourse transition phrase."""
    if not text:
        return False
    return bool(TRANSITION_STARTERS_REGEX.search(text.strip()))

def segment_transcript(preprocessed_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase 4: Deterministic Non-Overlapping Semantic Segmentation Engine
    
    Architectural Guarantees:
    1. NON-OVERLAPPING ANALYSIS TIMELINE: segment[i].end_time == segment[i+1].start_time.
    2. SENTENCE & THOUGHT PRESERVATION: Will not split across incomplete sentences unless MAX_SEGMENT_DURATION is breached.
    3. FULL TRACEABILITY: Preserves complete list of source_subtitle_ids for every segment.
    """
    video_id = preprocessed_data["video_id"]
    language = preprocessed_data["language"]
    raw_duration = preprocessed_data["duration_seconds"]
    subtitle_units = preprocessed_data.get("segments", [])

    if not subtitle_units:
        return {
            "video_id": video_id,
            "language": language,
            "duration_seconds": raw_duration,
            "statistics": {
                "source_subtitle_count": 0,
                "semantic_segment_count": 0,
                "average_segment_duration": 0.0,
                "median_segment_duration": 0.0,
                "min_segment_duration": 0.0,
                "max_segment_duration": 0.0,
                "average_words_per_segment": 0.0,
                "overlapping_semantic_segments_count": 0,
                "word_count_integrity": True
            },
            "segments": []
        }

    min_dur = config.MIN_SEGMENT_DURATION
    max_dur = config.MAX_SEGMENT_DURATION
    target_dur = config.TARGET_SEGMENT_DURATION
    max_words = config.MAX_WORDS_PER_SEGMENT
    max_gap = config.MAX_GAP_SECONDS

    raw_chunks = []
    current_chunk = []
    sentence_boundary_splits = 0

    for i, unit in enumerate(subtitle_units):
        if not current_chunk:
            current_chunk.append(unit)
            continue

        chunk_start = current_chunk[0]["start"]
        chunk_end = max(u["end"] for u in current_chunk)
        current_dur = round(chunk_end - chunk_start, 3)
        current_word_count = sum(count_words(u["text"]) for u in current_chunk)

        unit_start = unit["start"]
        unit_words = count_words(unit["text"])
        gap = round(unit_start - chunk_end, 3)

        # Check trailing text of current chunk for sentence completion
        chunk_text_so_far = " ".join(u["text"] for u in current_chunk).strip()
        is_complete_sentence = ends_with_complete_sentence(chunk_text_so_far)

        trigger_boundary = False

        # Rule 1: Pause Gap > MAX_GAP_SECONDS (if min duration reached and sentence complete or gap is large)
        if gap > max_gap and current_dur >= min_dur:
            trigger_boundary = True
            if is_complete_sentence:
                sentence_boundary_splits += 1

        # Rule 2: Hard Safeguard Max Duration / Words limit reached
        elif (current_dur + (unit["end"] - unit["start"])) > max_dur or (current_word_count + unit_words) > max_words:
            trigger_boundary = True
            if is_complete_sentence:
                sentence_boundary_splits += 1

        # Rule 3: Target Duration preference reached AND current chunk ends with a complete sentence
        elif current_dur >= target_dur and is_complete_sentence:
            trigger_boundary = True
            sentence_boundary_splits += 1

        # Rule 4: Min Duration reached AND next unit is a discourse transition starter AND current chunk ends with complete sentence
        elif current_dur >= min_dur and is_transition_starter(unit["text"]) and is_complete_sentence:
            trigger_boundary = True
            sentence_boundary_splits += 1

        if trigger_boundary:
            raw_chunks.append(current_chunk)
            current_chunk = [unit]
        else:
            current_chunk.append(unit)

    if current_chunk:
        raw_chunks.append(current_chunk)

    # Step 2: Construct NON-OVERLAPPING Timeline for Semantic Segments
    semantic_segments = []
    num_chunks = len(raw_chunks)
    timeline_cursor = subtitle_units[0]["start"] if subtitle_units else 0.0

    for idx, chunk in enumerate(raw_chunks):
        seg_id = idx + 1
        seg_start = timeline_cursor

        flat_sub_ids = []
        for u in chunk:
            flat_sub_ids.extend(u["subtitle_ids"])

        chunk_text = " ".join(u["text"] for u in chunk)
        chunk_text = re.sub(r'[ \t]+', ' ', chunk_text).strip()

        chunk_raw_end = max(u["end"] for u in chunk)

        if idx == num_chunks - 1:
            # Last segment reaches full transcript end duration
            seg_end = max(raw_duration, chunk_raw_end)
        else:
            next_chunk_start = raw_chunks[idx + 1][0]["start"]
            if next_chunk_start >= chunk_raw_end:
                seg_end = next_chunk_start
            else:
                # Overlapping source subtitle boundary: set boundary to midpoint or chunk_raw_end
                seg_end = round((chunk_raw_end + next_chunk_start) / 2.0, 3)

        seg_end = round(max(seg_start + 0.1, seg_end), 3)
        seg_dur = round(seg_end - seg_start, 3)

        semantic_segments.append({
            "segment_id": seg_id,
            "start_time": seg_start,
            "end_time": seg_end,
            "duration": seg_dur,
            "source_subtitle_ids": flat_sub_ids,
            "language": language,
            "text": chunk_text
        })

        timeline_cursor = seg_end

    # Step 3: Compute Validation & Quality Statistics
    source_sub_count = len(subtitle_units)
    seg_count = len(semantic_segments)

    durations = [s["duration"] for s in semantic_segments]
    word_counts = [count_words(s["text"]) for s in semantic_segments]

    # Check for overlapping semantic segments
    overlapping_segments_count = 0
    for i in range(len(semantic_segments) - 1):
        if semantic_segments[i]["end_time"] > semantic_segments[i + 1]["start_time"]:
            overlapping_segments_count += 1

    avg_dur = round(sum(durations) / seg_count, 2) if seg_count > 0 else 0.0
    med_dur = round(statistics.median(durations), 2) if seg_count > 0 else 0.0
    min_dur_found = round(min(durations), 2) if seg_count > 0 else 0.0
    max_dur_found = round(max(durations), 2) if seg_count > 0 else 0.0
    avg_words = round(sum(word_counts) / seg_count, 2) if seg_count > 0 else 0.0

    high_word_count_segs = [s["segment_id"] for s in semantic_segments if count_words(s["text"]) > max_words]
    short_duration_segs = [s["segment_id"] for s in semantic_segments if s["duration"] < 10.0]

    preprocessed_words_sum = sum(count_words(u["text"]) for u in subtitle_units)
    segmented_words_sum = sum(word_counts)
    word_count_integrity = (preprocessed_words_sum == segmented_words_sum)

    # Covered timeline calculation
    timeline_coverage = round(semantic_segments[-1]["end_time"] - semantic_segments[0]["start_time"], 3) if semantic_segments else 0.0
    uncovered_timeline = round(abs(timeline_coverage - raw_duration), 3)

    stats = {
        "source_subtitle_count": source_sub_count,
        "semantic_segment_count": seg_count,
        "average_segment_duration": avg_dur,
        "median_segment_duration": med_dur,
        "min_segment_duration": min_dur_found,
        "max_segment_duration": max_dur_found,
        "average_words_per_segment": avg_words,
        "overlapping_semantic_segments_count": overlapping_segments_count,
        "sentence_boundary_splits": sentence_boundary_splits,
        "uncovered_timeline_seconds": uncovered_timeline,
        "high_word_count_segments": high_word_count_segs,
        "short_duration_segments": short_duration_segs,
        "word_count_integrity": word_count_integrity
    }

    return {
        "video_id": video_id,
        "language": language,
        "duration_seconds": raw_duration,
        "statistics": stats,
        "segments": semantic_segments
    }
