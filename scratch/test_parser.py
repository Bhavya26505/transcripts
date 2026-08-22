import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from src.parser import parse_srt_file

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 60)
    print(" PHASE 2 TEST: TRANSCRIPT PARSING")
    print("=" * 60)

    # Load dataset index
    index_file = config.OUTPUT_INDEX_FILE
    if not index_file.exists():
        print(f"Error: {index_file} not found. Run Phase 1 first.")
        return

    with open(index_file, "r", encoding="utf-8") as f:
        records = json.load(f)

    if not records:
        print("No records found in dataset index.")
        return

    # Select first video record for detailed demonstration
    sample_rec = records[0]
    video_id = sample_rec["video_id"]
    hi_path = sample_rec["hi_transcript"]
    en_path = sample_rec["en_transcript"]

    print(f"Testing Video ID: {video_id}\n")

    # 1. Parse Hindi SRT
    if hi_path:
        hi_parsed = parse_srt_file(hi_path, video_id, "HINDI")
        print("--- HINDI TRANSCRIPT PARSE SUMMARY ---")
        print(f"File Path        : {hi_parsed['file_path']}")
        print(f"Language         : {hi_parsed['language']}")
        print(f"Subtitle Entries : {hi_parsed['total_entries']}")
        print(f"Time Range       : {hi_parsed['time_range']['start']}s to {hi_parsed['time_range']['end']}s (Duration: {hi_parsed['time_range']['duration']}s)")
        print(f"Overlaps Detected: {hi_parsed['overlap_summary']['overlap_count']} overlaps (Max overlap: {hi_parsed['overlap_summary']['max_overlap_seconds']}s)")
        print(f"Parsing Issues   : {len(hi_parsed['parsing_issues'])}")
        
        print("\nFIRST 10 PARSED HINDI ENTRIES:")
        for entry in hi_parsed['segments'][:10]:
            print(f"  [{entry['subtitle_id']:3d}] {entry['start']:6.2f}s --> {entry['end']:6.2f}s | {entry['text']}")
        print("-" * 60)

    # 2. Parse English SRT
    if en_path:
        en_parsed = parse_srt_file(en_path, video_id, "ENGLISH")
        print("\n--- ENGLISH TRANSCRIPT PARSE SUMMARY ---")
        print(f"File Path        : {en_parsed['file_path']}")
        print(f"Language         : {en_parsed['language']}")
        print(f"Subtitle Entries : {en_parsed['total_entries']}")
        print(f"Time Range       : {en_parsed['time_range']['start']}s to {en_parsed['time_range']['end']}s (Duration: {en_parsed['time_range']['duration']}s)")
        print(f"Overlaps Detected: {en_parsed['overlap_summary']['overlap_count']} overlaps (Max overlap: {en_parsed['overlap_summary']['max_overlap_seconds']}s)")
        print(f"Parsing Issues   : {len(en_parsed['parsing_issues'])}")
        
        print("\nFIRST 10 PARSED ENGLISH ENTRIES:")
        for entry in en_parsed['segments'][:10]:
            print(f"  [{entry['subtitle_id']:3d}] {entry['start']:6.2f}s --> {entry['end']:6.2f}s | {entry['text']}")
        print("-" * 60)

    # 3. Quick test across first 5 videos
    print("\n--- BATCH TEST SUMMARY ACROSS FIRST 5 VIDEOS ---")
    for rec in records[:5]:
        v_id = rec["video_id"]
        hi_entries = len(parse_srt_file(rec["hi_transcript"], v_id, "HINDI")["segments"]) if rec["hi_transcript"] else 0
        en_entries = len(parse_srt_file(rec["en_transcript"], v_id, "ENGLISH")["segments"]) if rec["en_transcript"] else 0
        print(f"Video {v_id:15s} | Hindi Entries: {hi_entries:4d} | English Entries: {en_entries:4d}")

    print("=" * 60)

if __name__ == "__main__":
    main()
