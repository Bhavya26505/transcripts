import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

TIMESTAMP_REGEX = re.compile(
    r'(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})'
)

def parse_timestamp_to_seconds(hours: str, minutes: str, seconds: str, millis: str) -> float:
    """Converts hours, minutes, seconds, milliseconds to total seconds float."""
    total = int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000.0
    return round(total, 3)

def clean_text(text: str) -> str:
    """Basic text cleanup: removes HTML tags, normalizes whitespace."""
    if not text:
        return ""
    # Strip HTML tags like <i>, <b>, <font color="...">, etc.
    cleaned = re.sub(r'<[^>]+>', '', text)
    # Replace zero-width spaces and non-breaking spaces
    cleaned = cleaned.replace('\u200b', '').replace('\xa0', ' ')
    # Normalize multiple whitespace characters
    cleaned = re.sub(r'[ \t]+', ' ', cleaned).strip()
    return cleaned

def parse_srt_string(srt_content: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Parses string content of an SRT file into a list of subtitle entry dictionaries.
    Returns (entries, parsing_issues).
    """
    entries = []
    issues = []
    
    # Standardize newline line endings
    normalized_content = srt_content.replace('\r\n', '\n').replace('\r', '\n')
    blocks = re.split(r'\n\s*\n', normalized_content)

    subtitle_counter = 1

    for block in blocks:
        block_str = block.strip()
        if not block_str:
            continue

        lines = [line.strip() for line in block_str.split('\n') if line.strip()]
        if not lines:
            continue

        # Look for timestamp line
        timestamp_line_idx = -1
        match = None

        for idx, line in enumerate(lines):
            match = TIMESTAMP_REGEX.search(line)
            if match:
                timestamp_line_idx = idx
                break

        if not match or timestamp_line_idx == -1:
            issues.append(f"Failed to find valid timestamp line in block: {repr(block_str[:60])}")
            continue

        h1, m1, s1, ms1, h2, m2, s2, ms2 = match.groups()
        start_sec = parse_timestamp_to_seconds(h1, m1, s1, ms1)
        end_sec = parse_timestamp_to_seconds(h2, m2, s2, ms2)

        # Extract subtitle text lines (everything after timestamp line)
        text_lines = lines[timestamp_line_idx + 1:]
        text_content = clean_text(" ".join(text_lines))

        # Try to parse subtitle index if available
        subtitle_id = subtitle_counter
        if timestamp_line_idx > 0 and lines[0].isdigit():
            subtitle_id = int(lines[0])

        entries.append({
            "subtitle_id": subtitle_id,
            "start": start_sec,
            "end": end_sec,
            "text": text_content
        })

        subtitle_counter += 1

    return entries, issues

def analyze_overlaps(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyzes timestamp overlaps between consecutive subtitle entries."""
    overlap_count = 0
    max_overlap_sec = 0.0

    for i in range(1, len(entries)):
        prev_end = entries[i - 1]["end"]
        curr_start = entries[i]["start"]
        if curr_start < prev_end:
            overlap_count += 1
            overlap_dur = round(prev_end - curr_start, 3)
            if overlap_dur > max_overlap_sec:
                max_overlap_sec = overlap_dur

    return {
        "overlap_count": overlap_count,
        "has_overlap": overlap_count > 0,
        "max_overlap_seconds": max_overlap_sec
    }

def parse_srt_file(file_path: str, video_id: str, language: str) -> Dict[str, Any]:
    """
    Reads and parses an SRT file from file_path, producing a normalized transcript dictionary.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"SRT file not found: {file_path}")

    # Read content with encoding fallback
    try:
        content = path.read_text(encoding='utf-8-sig')
    except UnicodeDecodeError:
        content = path.read_text(encoding='latin-1')

    entries, issues = parse_srt_string(content)

    start_time = entries[0]["start"] if entries else 0.0
    end_time = max((e["end"] for e in entries), default=0.0)
    duration = round(end_time - start_time, 3)

    overlap_info = analyze_overlaps(entries)

    return {
        "video_id": video_id,
        "source_type": "srt",
        "language": language.upper(),
        "file_path": str(path.resolve()),
        "total_entries": len(entries),
        "time_range": {
            "start": start_time,
            "end": end_time,
            "duration": duration
        },
        "overlap_summary": overlap_info,
        "parsing_issues": issues,
        "segments": entries
    }
