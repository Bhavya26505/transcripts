import json
import time
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from src.llm_client import LMStudioClient
from src.parser import parse_srt_file
from src.preprocessor import preprocess_transcript
from src.segmenter import segment_transcript
from src.language_detector import enrich_segmented_transcript_with_language
from src.hook_analyzer import analyze_video_hook

vid = "-ckuMh4Px9M"
entry = {
    "video_id": vid,
    "hi_transcript": "C:\\Users\\ADMIN\\Downloads\\UCUMccND2H_CVS0dMZKCPCXA\\UCUMccND2H_CVS0dMZKCPCXA\\-ckuMh4Px9M\\transcript\\hi.srt"
}

client = LMStudioClient()

print(f"Testing Phase 7 hook analysis for video: {vid}")

raw_parsed = parse_srt_file(entry["hi_transcript"], vid, "hi")
prep_data = preprocess_transcript(raw_parsed)
segmented_data = segment_transcript(prep_data)
lang_data = enrich_segmented_transcript_with_language(segmented_data)

lang_file = config.DATA_DIR / "language" / f"{vid}_hi_lang.json"
lang_file.parent.mkdir(parents=True, exist_ok=True)
with open(lang_file, "w", encoding="utf-8") as f:
    json.dump(lang_data, f, indent=2, ensure_ascii=False)

t0 = time.time()
try:
    res = analyze_video_hook(vid, str(lang_file), client, target_window=90.0, max_window=120.0, temperature=0.1)
    dur = round(time.time() - t0, 2)
    print(f"[SUCCESS] Completed hook analysis in {dur} seconds!")
    print("Parsed Analysis:")
    print(json.dumps(res["parsed_analysis"], indent=2, ensure_ascii=False)[:500])
except Exception as e:
    print(f"[FAIL] Error during hook analysis: {e}")
