import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("data/language/-RgdgqF9wd0_hi_lang.json", "r", encoding="utf-8") as f:
    data = json.load(f)

seg7 = next(s for s in data["segments"] if s["segment_id"] == 7)
seg8 = next(s for s in data["segments"] if s["segment_id"] == 8)

print("Segment #7 Text:\n", seg7["text"])
print("\nSegment #8 Text:\n", seg8["text"])
