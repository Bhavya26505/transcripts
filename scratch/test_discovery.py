import os
import json
import sys
from pathlib import Path
from typing import Dict, List, Any

def discover_dataset(dataset_root_path: str) -> Dict[str, Any]:
    dataset_root = Path(dataset_root_path).resolve()
    if not dataset_root.exists():
        raise FileNotFoundError(f"Dataset root path does not exist: {dataset_root}")

    # We will search for all directories that are video directories.
    # In YouTube scraped format, video directories contain subdirectories like transcript, metadata, etc.
    # Or video directories contain transcript files.
    
    discovered_records = []
    
    # Tracking statistics
    total_video_dirs = 0
    videos_with_both = 0
    videos_with_hi_only = 0
    videos_with_en_only = 0
    videos_with_hi = 0
    videos_with_en = 0
    
    ignored_directories = set()
    ignored_transcript_files = []
    
    # Subdirectories within a video directory that should not be treated as video directories
    AUXILIARY_DIR_NAMES = {"audio", "comments", "frames", "metadata", "thumbnails", "transcript", "video"}
    
    # Find all potential video directories by looking for folders containing 'transcript' or srt files
    all_dirs = []
    for root, dirs, files in os.walk(dataset_root):
        rpath = Path(root)
        if rpath.name in AUXILIARY_DIR_NAMES:
            continue
        # Check if rpath has a transcript subfolder or srt files
        transcript_dir = rpath / "transcript"
        if transcript_dir.exists() and transcript_dir.is_dir():
            all_dirs.append(rpath)
        else:
            # Check if current directory directly contains srt files
            if any(f.endswith('.srt') for f in files):
                all_dirs.append(rpath)
    
    # Deduplicate video directories
    video_dirs = sorted(list(set(all_dirs)), key=lambda x: str(x))
    total_video_dirs = len(video_dirs)

    # Process each video directory
    for vdir in video_dirs:
        video_id = vdir.name
        
        # Look inside transcript folder if exists, else directly in vdir
        target_dir = vdir / "transcript" if (vdir / "transcript").exists() else vdir
        
        hi_path = None
        en_path = None
        
        dir_files = [f for f in target_dir.iterdir() if f.is_file()] if target_dir.exists() else []
        
        # Scan files for Hindi and English SRT matching
        # Priority for Hindi: hi.srt > hi-orig.srt
        # Priority for English: en.srt > en-orig.srt > en-IN.srt
        
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
                # File is ignored for initial dataset analysis (either non-SRT or other language SRT)
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
            continue # Do not include video with no valid transcripts
            
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

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    res = discover_dataset(r"C:\Users\ADMIN\Downloads\UCUMccND2H_CVS0dMZKCPCXA")
    print("Stats:")
    print(json.dumps(res["stats"], indent=2))
    print("\nFirst 5 Records:")
    print(json.dumps(res["records"][:5], indent=2))
