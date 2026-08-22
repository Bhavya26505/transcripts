import json
from pathlib import Path

state_file = Path("data/production_validation/phase11/phase11_state.json")
if state_file.exists():
    with open(state_file, "r", encoding="utf-8") as f:
        st = json.load(f)
    st["video_states"]["OIis7tvpQPc"] = "PENDING"
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=2)
    print("Set Video OIis7tvpQPc state to PENDING")
