import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

prep_file = Path(r"C:\Users\ADMIN\OneDrive\Desktop\Transcript-2\data\preprocessed\-_E7at6WAlQ_hi_preprocessed.json")
if prep_file.exists():
    with open(prep_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    print("Removed entry log in -_E7at6WAlQ (Hindi):")
    for log in data.get("transformations_log", []):
        if log["action"] == "REMOVED":
            print(json.dumps(log, indent=2, ensure_ascii=False))
