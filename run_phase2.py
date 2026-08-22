import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from src.parser import parse_srt_file

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 60)
    print(" PHASE 2: TRANSCRIPT PARSING & RAW PRESERVATION")
    print("=" * 60)

    # Ensure RAW storage directory exists
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)

    index_file = config.OUTPUT_INDEX_FILE
    if not index_file.exists():
        print(f"Error: Dataset index file not found at {index_file}. Run Phase 1 first.")
        sys.exit(1)

    with open(index_file, "r", encoding="utf-8") as f:
        records = json.load(f)

    print(f"Loaded {len(records)} video records from dataset index.\n")

    parsed_hi_count = 0
    parsed_en_count = 0
    total_issues = 0

    sample_hi_output = None
    sample_en_output = None

    for idx, record in enumerate(records):
        video_id = record["video_id"]
        
        # Parse Hindi transcript
        if record["hi_transcript"]:
            try:
                parsed_hi = parse_srt_file(record["hi_transcript"], video_id, "HINDI")
                raw_hi_file = config.RAW_DIR / f"{video_id}_hi_raw.json"
                with open(raw_hi_file, "w", encoding="utf-8") as f_out:
                    json.dump(parsed_hi, f_out, indent=2, ensure_ascii=False)
                parsed_hi_count += 1
                total_issues += len(parsed_hi["parsing_issues"])
                if idx == 0:
                    sample_hi_output = parsed_hi
            except Exception as e:
                print(f"[ERROR] Failed to parse Hindi transcript for video {video_id}: {e}")

        # Parse English transcript
        if record["en_transcript"]:
            try:
                parsed_en = parse_srt_file(record["en_transcript"], video_id, "ENGLISH")
                raw_en_file = config.RAW_DIR / f"{video_id}_en_raw.json"
                with open(raw_en_file, "w", encoding="utf-8") as f_out:
                    json.dump(parsed_en, f_out, indent=2, ensure_ascii=False)
                parsed_en_count += 1
                total_issues += len(parsed_en["parsing_issues"])
                if idx == 0:
                    sample_en_output = parsed_en
            except Exception as e:
                print(f"[ERROR] Failed to parse English transcript for video {video_id}: {e}")

    print("--- TRANSCRIPT PARSING RESULTS ---")
    print(f"Total Video Records Processed   : {len(records)}")
    print(f"Hindi Raw Transcripts Parsed    : {parsed_hi_count}")
    print(f"English Raw Transcripts Parsed  : {parsed_en_count}")
    print(f"Total Parsing Issues/Errors     : {total_issues}")
    print(f"Raw Transcripts Saved To        : {config.RAW_DIR}\n")

    if sample_hi_output:
        print("--- SAMPLE PARSED OUTPUT (HINDI - Video ID: " + sample_hi_output["video_id"] + ") ---")
        print(f"Language         : {sample_hi_output['language']}")
        print(f"Subtitle Entries : {sample_hi_output['total_entries']}")
        print(f"Timestamp Range  : {sample_hi_output['time_range']['start']}s to {sample_hi_output['time_range']['end']}s (Duration: {sample_hi_output['time_range']['duration']}s)")
        print(f"Overlaps Detected: {sample_hi_output['overlap_summary']['overlap_count']} overlaps (Max overlap: {sample_hi_output['overlap_summary']['max_overlap_seconds']}s)")
        print(f"Parsing Issues   : {len(sample_hi_output['parsing_issues'])}")
        print("\nFIRST 10 PARSED ENTRIES (HINDI):")
        for entry in sample_hi_output["segments"][:10]:
            print(f"  [{entry['subtitle_id']:3d}] {entry['start']:6.2f}s --> {entry['end']:6.2f}s | {entry['text']}")
        print("-" * 60)

    if sample_en_output:
        print("\n--- SAMPLE PARSED OUTPUT (ENGLISH - Video ID: " + sample_en_output["video_id"] + ") ---")
        print(f"Language         : {sample_en_output['language']}")
        print(f"Subtitle Entries : {sample_en_output['total_entries']}")
        print(f"Timestamp Range  : {sample_en_output['time_range']['start']}s to {sample_en_output['time_range']['end']}s (Duration: {sample_en_output['time_range']['duration']}s)")
        print(f"Overlaps Detected: {sample_en_output['overlap_summary']['overlap_count']} overlaps (Max overlap: {sample_en_output['overlap_summary']['max_overlap_seconds']}s)")
        print(f"Parsing Issues   : {len(sample_en_output['parsing_issues'])}")
        print("\nFIRST 10 PARSED ENTRIES (ENGLISH):")
        for entry in sample_en_output["segments"][:10]:
            print(f"  [{entry['subtitle_id']:3d}] {entry['start']:6.2f}s --> {entry['end']:6.2f}s | {entry['text']}")
        print("=" * 60)

if __name__ == "__main__":
    main()
