import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

hi_lang_path = Path("data/language/-RgdgqF9wd0_hi_lang.json")
with open(hi_lang_path, "r", encoding="utf-8") as f:
    data = json.load(f)

segments = data.get("segments", [])
test_segs = [s for s in segments if s["segment_id"] >= 3 and s["segment_id"] <= 10]

print(f"Selected {len(test_segs)} test segments for Phase 8A experiment (Segment #3 to #10):")
for s in test_segs:
    print(f"  Segment #{s['segment_id']}: [{s['start_time']:.2f}s - {s['end_time']:.2f}s] ({s.get('language', 'UNK')}) Text: {repr(s['text'][:80])}")
