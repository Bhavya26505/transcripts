from pathlib import Path

bad_file = Path(r"C:\Users\ADMIN\Downloads\UCUMccND2H_CVS0dMZKCPCXA\UCUMccND2H_CVS0dMZKCPCXA\1sVOwYhItqk\transcript\en.srt")
print("Bad File Content:")
print(bad_file.read_text(encoding='utf-8', errors='ignore'))
