import os
import sys
from pathlib import Path

candidate_paths = [
    r"C:\Users\ADMIN\Downloads\UCUMccND2H_CVS0dMZKCPCXA.zip\UCUMccND2H_CVS0dMZKCPCXA",
    r"C:\Users\ADMIN\Downloads\UCUMccND2H_CVS0dMZKCPCXA",
    r"C:\Users\ADMIN\Downloads\UCUMccND2H_CVS0dMZKCPCXA.zip"
]

print("Checking paths:")
for p in candidate_paths:
    exists = os.path.exists(p)
    is_dir = os.path.isdir(p) if exists else False
    is_file = os.path.isfile(p) if exists else False
    print(f"Path: {p} | Exists: {exists} | IsDir: {is_dir} | IsFile: {is_file}")

# Let's list C:\Users\ADMIN\Downloads for folders starting with UCUM
downloads = r"C:\Users\ADMIN\Downloads"
if os.path.exists(downloads):
    print("\nMatching items in Downloads:")
    for item in os.listdir(downloads):
        if "UCUM" in item or "transcript" in item.lower():
            full = os.path.join(downloads, item)
            print(f" - {item} ({'DIR' if os.path.isdir(full) else 'FILE'})")
