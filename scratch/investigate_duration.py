import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

raw_en_file = Path(r"C:\Users\ADMIN\OneDrive\Desktop\Transcript-2\data\raw\-XwsCHg9fEA_en_raw.json")
with open(raw_en_file, "r", encoding="utf-8") as f:
    data = json.load(f)

print("Video -XwsCHg9fEA English Raw Time Range:")
print(data.get("time_range"))

segments = data.get("segments", [])
print(f"Total raw segments: {len(segments)}")

print("\nLast 15 raw segments:")
for seg in segments[-15:]:
    print(f"  [{seg['subtitle_id']}] {seg['start']}s --> {seg['end']}s | {repr(seg['text'])}")
