import os
from pathlib import Path
from collections import Counter

dataset_path = Path(r"C:\Users\ADMIN\Downloads\UCUMccND2H_CVS0dMZKCPCXA")

print(f"Scanning dataset root: {dataset_path}")

all_files = []
all_dirs = []
srt_files = []

for root, dirs, files in os.walk(dataset_path):
    rel_root = Path(root).relative_to(dataset_path)
    all_dirs.append(rel_root)
    for f in files:
        rel_file = rel_root / f
        all_files.append(rel_file)
        if f.endswith('.srt'):
            srt_files.append(rel_file)

print(f"Total subdirectories: {len(all_dirs)}")
print(f"Total files: {len(all_files)}")
print(f"Total .srt files: {len(srt_files)}")

# Print sample directory structures
print("\nSample subdirectories (first 10):")
for d in all_dirs[:10]:
    print(f" - {d}")

print("\nSample .srt files (first 20):")
for s in srt_files[:20]:
    print(f" - {s}")

# Check unique SRT filenames
srt_filenames = Counter([s.name for s in srt_files])
print("\nUnique SRT Filenames & Frequencies:")
for fname, count in srt_filenames.most_common(20):
    print(f" - {fname}: {count}")

# Check file extension types across all files
extensions = Counter([s.suffix.lower() for s in all_files])
print("\nFile Extensions Frequency:")
for ext, count in extensions.most_common():
    print(f" - {ext}: {count}")
