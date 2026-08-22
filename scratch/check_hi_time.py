import json
from pathlib import Path

raw_hi_file = Path(r"C:\Users\ADMIN\OneDrive\Desktop\Transcript-2\data\raw\-XwsCHg9fEA_hi_raw.json")
with open(raw_hi_file, "r", encoding="utf-8") as f:
    data_hi = json.load(f)

print("Video -XwsCHg9fEA Hindi Raw Time Range:")
print(data_hi.get("time_range"))
