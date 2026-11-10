"""Rebuild a saved release using structural features, then compare its IDs."""
from pathlib import Path
import argparse
import json
import sys
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "selection"))
from algorithm import Pool, bounded_exchange
from anchors import anchor_for
parser = argparse.ArgumentParser()
parser.add_argument("--release", type=int, default=0, choices=range(10))
args = parser.parse_args()
rows = [json.loads(x) for x in (root / "selection/PAIR_METADATA.jsonl").read_text().splitlines()]
profile = json.loads((root / "selection/SOURCE_PROFILE.json").read_text())
expected = json.loads((root / "selection/expected.json").read_text())[args.release]
pool = Pool(rows, profile)
anchor, quotas = anchor_for(pool, expected["seed"], 250)
actual = bounded_exchange(pool, anchor, tau="1/100", max_swaps=25)
assert anchor == expected["anchor"]
assert actual["ids"] == expected["method"]
assert actual["H"] == expected["H"]
assert abs(actual["structural_loss"] - expected["method_structural_loss"]) < 1e-10
print(json.dumps({"seed": expected["seed"], "tasks": len(actual["ids"]), "swaps": actual["swaps"], "H": actual["H"], "structural_loss": actual["structural_loss"]}, indent=2))
