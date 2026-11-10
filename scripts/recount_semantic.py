"""Recount the archived API judgments without contacting a model service."""
from pathlib import Path
from collections import Counter, defaultdict
import json
root = Path(__file__).resolve().parents[1] / "evaluation/semantic"
counts = defaultdict(Counter)
seen = set()
for line in (root / "labels.jsonl").read_text().splitlines():
    row = json.loads(line)
    assert row["blind_id"] not in seen
    seen.add(row["blind_id"])
    counts[row["method"]][row["label"]] += 1
expected = json.loads((root / "expected_counts.json").read_text())["by_method"]
assert {k: dict(v) for k, v in counts.items()} == expected
assert len(seen) == 4000
print(json.dumps({"items": len(seen), "by_method": counts}, indent=2))
