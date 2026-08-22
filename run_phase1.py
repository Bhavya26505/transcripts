import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from src.discovery import discover_dataset

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 60)
    print(" PHASE 1: DATASET DISCOVERY")
    print("=" * 60)

    dataset_root = config.DATASET_ROOT
    print(f"Scanning Dataset Root: {dataset_root}\n")

    result = discover_dataset(dataset_root)
    stats = result["stats"]
    records = result["records"]

    # Ensure output data directory exists
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Save dataset_index.json
    with open(config.OUTPUT_INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print("--- DISCOVERY REPORT ---")
    print(f"Total video directories discovered : {stats['total_video_directories_discovered']}")
    print(f"Videos with Hindi transcript        : {stats['videos_with_hindi']}")
    print(f"Videos with English transcript      : {stats['videos_with_english']}")
    print(f"Videos with both (HI + EN)          : {stats['videos_with_both']}")
    print(f"Videos with ONLY Hindi              : {stats['videos_with_only_hindi']}")
    print(f"Videos with ONLY English            : {stats['videos_with_only_english']}")
    print(f"Ignored video directories (no HI/EN): {stats['ignored_directories_count']}")
    print(f"Ignored transcript files            : {stats['ignored_transcript_files_count']}")
    print(f"\nSaved index to: {config.OUTPUT_INDEX_FILE}\n")

    print("--- SAMPLE RECORDS (FIRST 10) ---")
    print(json.dumps(records[:10], indent=2, ensure_ascii=False))
    print("=" * 60)

if __name__ == "__main__":
    main()
