"""Recompute the main difficulty-TV certificate from candidate SQL and quotas."""
from pathlib import Path
from collections import Counter
import json
import sys
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "selection"))
from structural_features_frozen import feature_vector
rows = [json.loads(x) for x in (root / "selection/PAIR_METADATA.jsonl").read_text().splitlines()]
profile = json.loads((root / "selection/SOURCE_PROFILE.json").read_text())
release = json.loads((root / "selection/expected.json").read_text())[0]
easy = Counter()
for row in rows:
    difficulty = feature_vector(row["sql"])[1]
    if difficulty[0]:
        easy[row["domain"] + "|" + row["provenance_group"]] += 1
capacity = sum(min(n, easy[g]) for g, n in release["quotas"].items())
n = len(release["method"])
p = profile["difficulty"]["easy"]
bound = p - capacity / n
assert capacity == 173 and abs(bound - 0.3775) < 1e-12
print(json.dumps({"release_size": n, "easy_capacity": capacity, "difficulty_tv_lower_bound": bound, "additional_easy_items_needed": round(p * n) - capacity}, indent=2))
