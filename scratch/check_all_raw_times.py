import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

raw_dir = Path(r"C:\Users\ADMIN\OneDrive\Desktop\Transcript-2\data\raw")
sample_ids = ["-RgdgqF9wd0", "-SZBrXciDLg", "-XwsCHg9fEA", "-_E7at6WAlQ", "0LXDjMNLiWY"]

print("RAW TRANSCRIPT TIME RANGES FOR 5 SAMPLE VIDEOS:")
for v_id in sample_ids:
    hi_f = raw_dir / f"{v_id}_hi_raw.json"
    en_f = raw_dir / f"{v_id}_en_raw.json"
    
    hi_range = json.loads(hi_f.read_text(encoding='utf-8'))["time_range"] if hi_f.exists() else None
    en_range = json.loads(en_f.read_text(encoding='utf-8'))["time_range"] if en_f.exists() else None
    
    print(f"\nVideo ID: {v_id}")
    print(f"  HI Raw: Start={hi_range['start']}s | End={hi_range['end']}s | Duration={hi_range['duration']}s" if hi_range else "  HI Raw: N/A")
    print(f"  EN Raw: Start={en_range['start']}s | End={en_range['end']}s | Duration={en_range['duration']}s" if en_range else "  EN Raw: N/A")
