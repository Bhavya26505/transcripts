import json
from pathlib import Path

state_file = Path("data/production_validation/phase11/phase11_state.json")
if state_file.exists():
    state_file.unlink()
    print("Reset phase11_state.json")
