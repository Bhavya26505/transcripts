import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

hi_lang_path = Path("data/language/-RgdgqF9wd0_hi_lang.json")
with open(hi_lang_path, "r", encoding="utf-8") as f:
    data = json.load(f)

segments = data.get("segments", [])
print(f"Total segments in transcript: {len(segments)}")

test_segs = []
for s in segments:
    if s["start_time"] >= 87.50 and s["start_time"] <= 270.0:
        test_segs.append(s)

print(f"Test segments in range [87.52s -> ~270s]: {len(test_segs)} segments")
for s in test_segs:
    print(f"  Segment #{s['segment_id']}: [{s['start_time']:.2f}s - {s['end_time']:.2f}s] ({s.get('language', 'UNK')}) Text: {s['text'][:70]}...")
