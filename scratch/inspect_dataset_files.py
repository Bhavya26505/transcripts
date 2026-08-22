import json
from pathlib import Path

index_file = Path("data/dataset_index.json")
with open(index_file, "r", encoding="utf-8") as f:
    videos = json.load(f)

print(f"Dataset Index count: {len(videos)}")
if videos:
    print("Sample entry keys:", list(videos[0].keys()))
    print("Sample entry:", videos[0])

raw_files = list(Path("data/raw").glob("*"))
prep_files = list(Path("data/preprocessed").glob("*"))
lang_files = list(Path("data/language").glob("*"))

print(f"\nFiles in data/raw: {len(raw_files)} files (Sample: {[f.name for f in raw_files[:5]]})")
print(f"Files in data/preprocessed: {len(prep_files)} files (Sample: {[f.name for f in prep_files[:5]]})")
print(f"Files in data/language: {len(lang_files)} files (Sample: {[f.name for f in lang_files[:5]]})")
