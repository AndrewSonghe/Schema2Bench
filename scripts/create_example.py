"""Create a small local database from the included illustrative SQL fixture."""
from pathlib import Path
import argparse
import sqlite3
parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, default=Path("results/shop.sqlite"))
args = parser.parse_args()
if args.output.exists():
    parser.error("Output already exists.")
args.output.parent.mkdir(parents=True, exist_ok=True)
root = Path(__file__).resolve().parents[1]
with sqlite3.connect(args.output) as db:
    db.executescript((root / "examples/shop.sql").read_text())
print(args.output)
