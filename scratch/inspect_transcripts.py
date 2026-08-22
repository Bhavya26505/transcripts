import os
from pathlib import Path

dataset_path = Path(r"C:\Users\ADMIN\Downloads\UCUMccND2H_CVS0dMZKCPCXA")

video_dirs = []
# Find all directories that contain a 'transcript' subfolder or are video folders
for root, dirs, files in os.walk(dataset_path):
    if "transcript" in dirs:
        video_dirs.append(Path(root))

print(f"Discovered video directories containing 'transcript': {len(video_dirs)}")

# Inspect transcripts in first 10 video dirs
for vdir in video_dirs[:10]:
    t_dir = vdir / "transcript"
    t_files = [f.name for f in t_dir.iterdir() if f.is_file()]
    print(f"\nVideo ID: {vdir.name}")
    print(f"  Path: {vdir}")
    print(f"  Transcript files: {t_files}")
