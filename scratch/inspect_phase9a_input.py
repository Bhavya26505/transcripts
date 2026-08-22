import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

seg_file = "data/analysis_segments/-RgdgqF9wd0_segment_analysis.json"
with open(seg_file, "r", encoding="utf-8") as f:
    data = json.load(f)

segs = data.get("segments", [])
print(f"Total Segments Loaded: {len(segs)}\n")
for s in segs:
    dur = s['end_time'] - s['start_time']
    print(f"Seg #{s['segment_id']:<2} | [{s['start_time']:>6.2f}s-{s['end_time']:>6.2f}s] ({dur:>5.2f}s) | Point: {s['primary_point']:<10} | Fn: {s['function']:<22} | Rel: {s['relevance']:<10} | Ev: {s['evidence_validation']}")
