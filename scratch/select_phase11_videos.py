import json
from pathlib import Path

EXCLUDED_VIDEOS = {
    "-ckuMh4Px9M",
    "0xNCJH5161s",
    "1jnEhDmvQbk",
    "1l37N5wcDgs",
    "1sVOwYhItqk",
    "-RgdgqF9wd0"
}

def select_videos():
    index_path = Path("data/dataset_index.json")
    if not index_path.exists():
        raise FileNotFoundError(f"Dataset index file not found at {index_path}")

    with open(index_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    candidates = []
    for r in records:
        vid = r.get("video_id")
        if not vid or vid in EXCLUDED_VIDEOS:
            continue
        
        # Check raw or language file strictly exists on disk
        hi_raw = Path(f"data/raw/{vid}_hi_raw.json")
        en_raw = Path(f"data/raw/{vid}_en_raw.json")
        hi_lang = Path(f"data/language/{vid}_hi_lang.json")

        if hi_raw.exists() or en_raw.exists() or hi_lang.exists():
            candidates.append(r)

    print(f"Total verified available candidate videos: {len(candidates)}")

    candidates = sorted(candidates, key=lambda x: x["video_id"])
    selected = []

    # Pick 10 videos spaced evenly across the sorted candidate pool
    step = len(candidates) // 10
    for i in range(10):
        idx = min(i * step, len(candidates) - 1)
        selected.append(candidates[idx])

    selected_ids = [s["video_id"] for s in selected]

    assert len(selected_ids) == 10, f"Expected 10 videos, got {len(selected_ids)}"
    assert len(set(selected_ids) & EXCLUDED_VIDEOS) == 0, "Selected video includes an excluded video!"

    manifest_data = {
        "selection_phase": "PHASE_11_SMALL_BATCH_VALIDATION",
        "total_selected": 10,
        "excluded_videos": list(EXCLUDED_VIDEOS),
        "selected_videos": [
            {
                "video_id": s["video_id"],
                "duration_seconds": s.get("duration_seconds", 0.0),
                "title": s.get("title", ""),
                "channel": s.get("channel", "")
            }
            for s in selected
        ]
    }

    out_dir = Path("data/production_validation/phase11")
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "selected_videos.json"

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)

    print("\nSELECTED 10 NEW VERIFIED VIDEOS FOR PHASE 11 VALIDATION:")
    print("-" * 80)
    for idx, s in enumerate(selected, 1):
        print(f"{idx:2d}. ID: {s['video_id']:<15} | Title: {s.get('title', '')[:45]}")
    print("-" * 80)
    print(f"Saved selection manifest to {manifest_path.resolve()}")

    return selected_ids

if __name__ == "__main__":
    select_videos()
