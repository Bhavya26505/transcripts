import os
import json
from pathlib import Path
from typing import Dict, List, Any, Tuple

def discover_dataset(dataset_root_path: str) -> Dict[str, Any]:
    """
    Phase 1: Dataset Discovery
    Recursively scans dataset directory, identifies Hindi and English transcripts,
    pairs them by video ID, and classifies ignored directories and files.
    """
    dataset_root = Path(dataset_root_path).resolve()
    if not dataset_root.exists():
        raise FileNotFoundError(f"Dataset root path does not exist: {dataset_root}")

    discovered_records: List[Dict[str, Any]] = []
    ignored_directories: set = set()
    ignored_transcript_files: List[str] = []

    AUXILIARY_DIR_NAMES = {"audio", "comments", "frames", "metadata", "thumbnails", "transcript", "video"}

    all_dirs: List[Path] = []
    for root, dirs, files in os.walk(dataset_root):
        rpath = Path(root)
        if rpath.name in AUXILIARY_DIR_NAMES:
            continue
        transcript_dir = rpath / "transcript"
        if transcript_dir.exists() and transcript_dir.is_dir():
            all_dirs.append(rpath)
        else:
            if any(f.endswith('.srt') for f in files):
                all_dirs.append(rpath)

    video_dirs = sorted(list(set(all_dirs)), key=lambda x: str(x))
    total_video_dirs = len(video_dirs)

    videos_with_hi = 0
    videos_with_en = 0
    videos_with_both = 0
    videos_with_hi_only = 0
    videos_with_en_only = 0

    for vdir in video_dirs:
        video_id = vdir.name
        target_dir = vdir / "transcript" if (vdir / "transcript").exists() else vdir

        hi_path = None
        en_path = None

        dir_files = [f for f in target_dir.iterdir() if f.is_file()] if target_dir.exists() else []

        for f in dir_files:
            fname = f.name.lower()
            if fname == "hi.srt":
                hi_path = str(f.resolve())
            elif fname == "hi-orig.srt" and not hi_path:
                hi_path = str(f.resolve())
            elif fname == "en.srt":
                en_path = str(f.resolve())
            elif fname in ("en-orig.srt", "en-in.srt") and not en_path:
                en_path = str(f.resolve())
            else:
                ignored_transcript_files.append(str(f.resolve()))

        has_hi = hi_path is not None
        has_en = en_path is not None

        if has_hi:
            videos_with_hi += 1
        if has_en:
            videos_with_en += 1

        if has_hi and has_en:
            videos_with_both += 1
        elif has_hi and not has_en:
            videos_with_hi_only += 1
        elif not has_hi and has_en:
            videos_with_en_only += 1
        else:
            ignored_directories.add(str(vdir.resolve()))
            continue

        record = {
            "video_id": video_id,
            "hi_transcript": hi_path,
            "en_transcript": en_path,
            "has_hindi": has_hi,
            "has_english": has_en
        }
        discovered_records.append(record)

    stats = {
        "dataset_root": str(dataset_root),
        "total_video_directories_discovered": total_video_dirs,
        "videos_indexed": len(discovered_records),
        "videos_with_hindi": videos_with_hi,
        "videos_with_english": videos_with_en,
        "videos_with_both": videos_with_both,
        "videos_with_only_hindi": videos_with_hi_only,
        "videos_with_only_english": videos_with_en_only,
        "ignored_directories_count": len(ignored_directories),
        "ignored_transcript_files_count": len(ignored_transcript_files)
    }

    return {
        "stats": stats,
        "records": discovered_records,
        "ignored_directories": sorted(list(ignored_directories)),
        "ignored_transcript_files": ignored_transcript_files
    }
