import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

lang_file = Path("data/language/-RgdgqF9wd0_hi_lang.json")
with open(lang_file, "r", encoding="utf-8") as f:
    data = json.load(f)

all_segs = data.get("segments", [])
remaining_segs = [s for s in all_segs if s["start_time"] >= 87.50]

print(f"Total segments in video: {len(all_segs)}")
print(f"Opening segments (Phase 7): {len(all_segs) - len(remaining_segs)}")
print(f"Remaining segments for Phase 8B: {len(remaining_segs)} segments\n")

for s in remaining_segs:
    print(f"Segment #{s['segment_id']:<2} | [{s['start_time']:>6.2f}s - {s['end_time']:>6.2f}s] ({s.get('language','UNK'):<8}) | Text: {repr(s['text'][:65])}")
