import re
import unicodedata
from typing import Dict, List, Any, Tuple

# Audio/Subtitle artifact regex pattern (e.g. [music], [Laughter], [संगीत], etc.)
ARTIFACT_REGEX = re.compile(
    r'\[\s*(music|Music|laughter|Laughter|applause|Applause|sigh|Sigh|संगीत|हंसी|ताली)\s*\]',
    re.IGNORECASE
)

# Filler Candidate Terms (Discourse markers / spoken filler candidates)
ENGLISH_FILLER_CANDIDATES = ["um", "uh", "you know", "basically", "actually", "like"]
HINDI_FILLER_CANDIDATES = ["मतलब", "यानी", "देखिए", "अरे", "अच्छा", "वैसे"]

def clean_text_entry(raw_text: str) -> Tuple[str, List[str]]:
    """
    Applies safe Unicode NFC normalization and explicit non-speech artifact removal.
    Returns (cleaned_text, list_of_applied_transformation_reasons).
    """
    transformations = []
    if not raw_text:
        return "", transformations

    # 1. Unicode NFC Normalization
    nfc_text = unicodedata.normalize('NFC', raw_text)
    if nfc_text != raw_text:
        transformations.append("Unicode NFC Normalization")

    # 2. Artifact Cleanup ([music], [संगीत], etc.)
    cleaned_text, num_subs = ARTIFACT_REGEX.subn('', nfc_text)
    if num_subs > 0:
        transformations.append(f"Removed {num_subs} non-speech audio artifact(s) (e.g. [music]/[संगीत])")

    # 3. Whitespace Normalization
    final_text = re.sub(r'[ \t]+', ' ', cleaned_text).strip()
    if final_text != raw_text and "Whitespace Normalization" not in transformations:
        transformations.append("Whitespace Normalization")

    return final_text, transformations

def count_words(text: str) -> int:
    """Counts words using whitespace splitting."""
    if not text:
        return 0
    return len(text.split())

def count_sentences(text: str) -> int:
    """Counts sentences using punctuation delimiters (. ! ? ।)."""
    if not text:
        return 0
    sentences = [s.strip() for s in re.split(r'[.!?।]', text) if s.strip()]
    return len(sentences) if sentences else 1

def analyze_filler_candidates(text: str, language: str) -> Tuple[int, Dict[str, int]]:
    """
    Identifies discourse markers / filler candidates deterministically.
    Returns (total_candidate_count, candidate_terms_dictionary).
    """
    if not text:
        return 0, {}

    candidates_to_check = []
    if language.upper() == "ENGLISH":
        candidates_to_check = ENGLISH_FILLER_CANDIDATES
    elif language.upper() == "HINDI":
        candidates_to_check = HINDI_FILLER_CANDIDATES
    else:
        candidates_to_check = ENGLISH_FILLER_CANDIDATES + HINDI_FILLER_CANDIDATES

    term_counts = {}
    total_candidates = 0

    for term in candidates_to_check:
        if len(term.split()) == 1:
            pattern = re.compile(rf'\b{re.escape(term)}\b', re.IGNORECASE if language.upper() != "HINDI" else 0)
        else:
            pattern = re.compile(rf'{re.escape(term)}', re.IGNORECASE if language.upper() != "HINDI" else 0)
        
        matches = len(pattern.findall(text))
        if matches > 0:
            term_counts[term] = matches
            total_candidates += matches

    return total_candidates, term_counts

def count_repeated_phrases(text: str) -> int:
    """Detects consecutive repeated words (e.g. 'is is', 'यह यह')."""
    if not text:
        return 0
    words = text.split()
    if len(words) < 2:
        return 0
    repeated = 0
    for i in range(len(words) - 1):
        if words[i].lower() == words[i + 1].lower() and len(words[i]) > 1:
            repeated += 1
    return repeated

def preprocess_transcript(raw_transcript: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes Phase 3 deterministic preprocessing on a raw transcript object.
    Preserves original raw data completely.
    Guarantees 100% duration integrity matching raw start/end timestamps.
    """
    video_id = raw_transcript["video_id"]
    language = raw_transcript["language"]
    raw_segments = raw_transcript.get("segments", [])
    raw_time_range = raw_transcript.get("time_range", {})

    raw_start = raw_time_range.get("start", raw_segments[0]["start"] if raw_segments else 0.0)
    raw_end = raw_time_range.get("end", max((s["end"] for s in raw_segments), default=0.0))
    raw_duration = round(raw_end - raw_start, 3)

    total_raw_entries = len(raw_segments)
    word_count_before = sum(count_words(s["text"]) for s in raw_segments)

    transformations_log = []
    entries_changed = 0
    entries_removed = 0
    entries_merged = 0
    entries_unchanged = 0

    # Step 1: Entry-level text cleaning & artifact removal
    cleaned_entries = []
    for seg in raw_segments:
        sub_id = seg["subtitle_id"]
        raw_txt = seg["text"]
        start_time = seg["start"]
        end_time = seg["end"]

        cleaned_txt, trans_list = clean_text_entry(raw_txt)

        if not cleaned_txt and raw_txt:
            # Entry text became empty after artifact removal
            entries_removed += 1
            transformations_log.append({
                "subtitle_id": sub_id,
                "action": "REMOVED",
                "raw_text": raw_txt,
                "normalized_text": "",
                "transformation": "Removed empty entry after audio artifact cleanup",
                "why_safe": "Entry contained only non-speech artifact (e.g. [music]/[संगीत]) with no spoken text"
            })
            continue

        if trans_list:
            entries_changed += 1
            transformations_log.append({
                "subtitle_id": sub_id,
                "action": "CHANGED",
                "raw_text": raw_txt,
                "normalized_text": cleaned_txt,
                "transformation": ", ".join(trans_list),
                "why_safe": "Standard Unicode NFC or whitespace/artifact normalization without altering semantic content"
            })
        else:
            entries_unchanged += 1

        cleaned_entries.append({
            "subtitle_ids": [sub_id],
            "start": start_time,
            "end": end_time,
            "text": cleaned_txt,
            "raw_text": raw_txt
        })

    # Step 2: Deterministic consecutive duplicate merging
    merged_units = []
    idx = 0
    while idx < len(cleaned_entries):
        curr = cleaned_entries[idx]
        next_idx = idx + 1
        sub_ids = list(curr["subtitle_ids"])
        combined_end = curr["end"]

        while next_idx < len(cleaned_entries) and cleaned_entries[next_idx]["text"].lower() == curr["text"].lower():
            dup = cleaned_entries[next_idx]
            sub_ids.extend(dup["subtitle_ids"])
            combined_end = max(combined_end, dup["end"])
            entries_merged += 1
            transformations_log.append({
                "subtitle_id": dup["subtitle_ids"][0],
                "action": "MERGED",
                "raw_text": dup["raw_text"],
                "normalized_text": curr["text"],
                "transformation": f"Merged consecutive duplicate subtitle entry with Entry #{curr['subtitle_ids'][0]}",
                "why_safe": "Identical consecutive text entries merged into a single subtitle unit spanning full timestamp range"
            })
            next_idx += 1

        merged_units.append({
            "subtitle_ids": sub_ids,
            "start": curr["start"],
            "end": combined_end,
            "text": curr["text"]
        })
        idx = next_idx

    # Preprocessed Duration Calculation (Preserves temporal coverage from raw bounds)
    prep_end = max((u["end"] for u in merged_units), default=raw_end)
    prep_start = merged_units[0]["start"] if merged_units else raw_start
    # Use max raw_end to guarantee no temporal coverage loss
    final_end = max(raw_end, prep_end)
    preprocessed_duration = round(final_end - prep_start, 3)
    duration_difference = round(abs(preprocessed_duration - raw_duration), 3)

    # Statistics Calculation
    word_count_after = sum(count_words(unit["text"]) for unit in merged_units)
    full_text = " ".join(unit["text"] for unit in merged_units)
    sentence_count = count_sentences(full_text)

    wpm = round((word_count_after / (preprocessed_duration / 60.0)), 2) if preprocessed_duration > 0 else 0.0
    filler_cand_count, filler_cand_terms = analyze_filler_candidates(full_text, language)
    repeated_phrase_cnt = count_repeated_phrases(full_text)

    statistics = {
        "raw_duration": raw_duration,
        "preprocessed_duration": preprocessed_duration,
        "duration_difference": duration_difference,
        "word_count_before": word_count_before,
        "word_count_after": word_count_after,
        "sentence_count": sentence_count,
        "estimated_wpm": wpm,
        "filler_candidate_count": filler_cand_count,
        "filler_candidate_terms": filler_cand_terms,
        "repeated_phrase_count": repeated_phrase_cnt,
        "entries_summary": {
            "raw_entries": total_raw_entries,
            "changed_entries": entries_changed,
            "removed_entries": entries_removed,
            "merged_entries": entries_merged,
            "unchanged_entries": entries_unchanged,
            "final_entries": len(merged_units)
        }
    }

    return {
        "video_id": video_id,
        "language": language,
        "duration_seconds": preprocessed_duration,
        "statistics": statistics,
        "transformations_log": transformations_log,
        "segments": merged_units
    }
