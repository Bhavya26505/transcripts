import re
import sys
import json
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

# Inspect preprocessed units around Entry 10 in -RgdgqF9wd0_hi_preprocessed.json
prep_file = Path(r"C:\Users\ADMIN\OneDrive\Desktop\Transcript-2\data\preprocessed\-RgdgqF9wd0_hi_preprocessed.json")
with open(prep_file, "r", encoding="utf-8") as f:
    prep_data = json.load(f)

units = prep_data["segments"]
print("Units 8 to 13 in -RgdgqF9wd0 (Hindi):")
for u in units[7:13]:
    print(f"  IDs {u['subtitle_ids']} | {u['start']}s --> {u['end']}s | {repr(u['text'])}")
