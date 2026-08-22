import json
from pathlib import Path

index_file = Path("data/dataset_index.json")
with open(index_file, "r", encoding="utf-8") as f:
    videos = json.load(f)

excluded_video_ids = {
    "-RgdgqF9wd0",
    "-SZBrXciDLg",
    "-XwsCHg9fEA",
    "-_E7at6WAlQ",
    "0LXDjMNLiWY"
}

new_candidate_videos = []
for v in videos:
    vid = v.get("video_id")
    if vid and vid not in excluded_video_ids:
        has_hi = v.get("has_hindi", False)
        has_en = v.get("has_english", False)
        hi_path = v.get("hi_transcript")
        raw_hi_json = Path(f"data/raw/{vid}_hi_raw.json")

        if (has_hi and hi_path and Path(hi_path).exists()) or raw_hi_json.exists():
            new_candidate_videos.append(v)

print(f"Total videos in index: {len(videos)}")
print(f"Excluded video IDs: {len(excluded_video_ids)}")
print(f"NEW candidate videos available: {len(new_candidate_videos)}\n")

for idx, cv in enumerate(new_candidate_videos[:10], 1):
    vid = cv["video_id"]
    has_hi = cv.get("has_hindi")
    has_en = cv.get("has_english")
    hi_p = cv.get("hi_transcript")
    p_exists = Path(hi_p).exists() if hi_p else False
    print(f"{idx:<2}. ID: {vid:<15} | Has HI: {has_hi} | Has EN: {has_en} | SRT Exists: {p_exists}")
