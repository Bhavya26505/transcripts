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

candidate_videos = []
for v in videos:
    vid = v.get("video_id")
    if vid and vid not in excluded_video_ids:
        # Check if Hindi transcript exists in data/raw or data/preprocessed or data/language
        hi_raw = Path(f"data/raw/{vid}_hi.srt")
        hi_prep = Path(f"data/preprocessed/{vid}_hi.json")
        hi_lang = Path(f"data/language/{vid}_hi_lang.json")

        if hi_raw.exists() or hi_prep.exists() or hi_lang.exists():
            candidate_videos.append(v)

print(f"Total videos in dataset: {len(videos)}")
print(f"Excluded video count: {len(excluded_video_ids)}")
print(f"Candidate NEW videos with Hindi transcript: {len(candidate_videos)}\n")

for idx, cv in enumerate(candidate_videos[:10], 1):
    print(f"{idx:<2}. ID: {cv.get('video_id'):<15} | Title: {repr(cv.get('title',''))[:50]}")
