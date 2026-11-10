"""Generate bounded candidates on a supplied SQLite database without model calls.

This entry point demonstrates the retained construction components. It does not
recreate the paper's historically screened candidate population.
"""
from pathlib import Path
from dataclasses import asdict
import argparse
import json
import sqlite3
import sys
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
from schema2bench.schema import SchemaProfilerAgent
from schema2bench.planner import BenchmarkPlannerAgent
from schema2bench.generators import DiverseDeterministicRefillAgenticGenerator, TemplateGenerator
from schema2bench.canonical import canonical_candidate
from schema2bench.llm import NoLlmProvider
parser = argparse.ArgumentParser()
parser.add_argument("--database", type=Path, required=True)
parser.add_argument("--method", choices=["refill", "template"], default="refill")
parser.add_argument("--attempts", type=int, default=100)
parser.add_argument("--seed", type=int, default=0)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
if not args.database.is_file():
    parser.error("The supplied SQLite file does not exist.")
if not 1 <= args.attempts <= 10000:
    parser.error("Choose between 1 and 10000 attempts.")
profile = SchemaProfilerAgent(sample_values_per_column=50, count_rows=True, enhanced_join_inference=True).profile(args.database)
planner = BenchmarkPlannerAgent("closure_complexity_refill", seed=args.seed)
generator = DiverseDeterministicRefillAgenticGenerator(provider=NoLlmProvider(), seed=args.seed) if args.method == "refill" else TemplateGenerator(seed=args.seed)
seen, accepted = set(), []
for _ in range(args.attempts):
    candidate = canonical_candidate(generator.generate(profile, planner.sample_plan(None)))
    if candidate is None or candidate.sql in seen:
        continue
    seen.add(candidate.sql)
    accepted.append(asdict(candidate))
args.output.parent.mkdir(parents=True, exist_ok=True)
with args.output.open("x") as out:
    for candidate in accepted:
        out.write(json.dumps(candidate, ensure_ascii=False) + "\n")
print(json.dumps({"attempts": args.attempts, "candidates": len(accepted), "output": str(args.output), "note": "Candidates require execution and semantic assessment before use as benchmark tasks."}))
