import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

sample_hi = Path(r"C:\Users\ADMIN\Downloads\UCUMccND2H_CVS0dMZKCPCXA\UCUMccND2H_CVS0dMZKCPCXA\-ckuMh4Px9M\transcript\hi.srt")
sample_en = Path(r"C:\Users\ADMIN\Downloads\UCUMccND2H_CVS0dMZKCPCXA\UCUMccND2H_CVS0dMZKCPCXA\-ckuMh4Px9M\transcript\en.srt")

print("--- HINDI SRT SAMPLE (First 50 lines) ---")
print(sample_hi.read_text(encoding='utf-8', errors='ignore')[:1000])

print("\n--- ENGLISH SRT SAMPLE (First 50 lines) ---")
print(sample_en.read_text(encoding='utf-8', errors='ignore')[:1000])
