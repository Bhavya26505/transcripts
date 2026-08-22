import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

dataset_path = Path(r"C:\Users\ADMIN\Downloads\UCUMccND2H_CVS0dMZKCPCXA")
sample_video = dataset_path / "UCUMccND2H_CVS0dMZKCPCXA" / "-ckuMh4Px9M" / "transcript"

hi = sample_video / "hi.srt"
hi_orig = sample_video / "hi-orig.srt"

if hi.exists() and hi_orig.exists():
    print(f"hi.srt size: {hi.stat().st_size} bytes")
    print(f"hi-orig.srt size: {hi_orig.stat().st_size} bytes")
    print("hi.srt content equal to hi-orig.srt content?", hi.read_bytes() == hi_orig.read_bytes())
    print("hi.srt snippet:", repr(hi.read_text(encoding='utf-8', errors='ignore')[:150]))
