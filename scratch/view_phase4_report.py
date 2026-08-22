import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

seg_dir = Path(r"C:\Users\ADMIN\OneDrive\Desktop\Transcript-2\data\segmented")
sample_ids = ["-RgdgqF9wd0", "-SZBrXciDLg", "-XwsCHg9fEA", "-_E7at6WAlQ", "0LXDjMNLiWY"]

print("=" * 80)
print(" PHASE 4 FULL METRICS REPORT (5 SAMPLE VIDEOS)")
print("=" * 80)

for v_id in sample_ids:
    print(f"\nVIDEO ID: {v_id}")
    print("-" * 70)
    for lang in ["HINDI", "ENGLISH"]:
        fpath = seg_dir / f"{v_id}_{'hi' if lang=='HINDI' else 'en'}_segments.json"
        if not fpath.exists():
            continue
        data = json.loads(fpath.read_text(encoding='utf-8'))
        st = data["statistics"]
        print(f"  Language                 : {lang}")
        print(f"  Total Duration           : {data['duration_seconds']}s")
        print(f"  Source Subtitle Count    : {st['source_subtitle_count']}")
        print(f"  Semantic Segments Count  : {st['semantic_segment_count']}")
        print(f"  Segment Duration (s)     : Avg: {st['average_segment_duration']}s | Med: {st['median_segment_duration']}s | Min: {st['min_segment_duration']}s | Max: {st['max_segment_duration']}s")
        print(f"  Average Words / Segment  : {st['average_words_per_segment']} words")
        print(f"  Short Segments (<10s)    : {len(st['short_duration_segments'])} (IDs: {st['short_duration_segments']})")
        print(f"  High Word Count Segs     : {len(st['high_word_count_segments'])} (IDs: {st['high_word_count_segments']})")
        print(f"  Word Count Integrity     : {'PASS' if st['word_count_integrity'] else 'FAIL'}")

print("=" * 80)
