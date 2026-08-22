from pathlib import Path

metrics_dir = Path("data/metrics/phase9a")
prod_dir = Path("data/production_validation/phase10")

for p in metrics_dir.glob("*.json"):
    p.unlink()

for p in prod_dir.glob("*.json"):
    p.unlink()

print("Cleaned outdated metrics and production json files.")
