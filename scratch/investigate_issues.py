import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from src.parser import parse_srt_file

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("--- INVESTIGATING PARSING ISSUES ---")
    
    with open(config.OUTPUT_INDEX_FILE, "r", encoding="utf-8") as f:
        records = json.load(f)

    issue_count = 0
    for rec in records:
        v_id = rec["video_id"]
        for lang, path in [("HINDI", rec["hi_transcript"]), ("ENGLISH", rec["en_transcript"])]:
            if not path:
                continue
            res = parse_srt_file(path, v_id, lang)
            if res["parsing_issues"]:
                print(f"\nVideo ID: {v_id} | Language: {lang} | File: {path}")
                for issue in res["parsing_issues"]:
                    issue_count += 1
                    print(f" - Issue: {issue}")

    print(f"\nTotal Issues Found across all files: {issue_count}")

if __name__ == "__main__":
    main()
