"""Recount the earlier seven-database study from archived summaries."""
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from statistics import mean
import csv
import json
import math

root = Path(__file__).resolve().parents[1] / "evaluation" / "historical"
read = lambda name: json.loads((root / name).read_text())
exact = read("selection_exact.json")
groups = defaultdict(dict)
for row in exact:
    value = float(Fraction(row["tef_exact"]))
    assert math.isclose(value, row["tef_float"], abs_tol=1e-14)
    groups[row["method"]][row["seed"]] = value
anchor, cost = groups["anchor"], groups["cost_aware"]
assert len(anchor) == len(cost) == 10 and anchor.keys() == cost.keys()
relative = 100 * (mean(anchor.values()) - mean(cost.values())) / mean(anchor.values())
assert round(relative, 2) == 5.67
assert all(cost[seed] < anchor[seed] for seed in anchor)

baselines = read("selection_baselines.json")["means"]
cost_summary = read("selection_cost.json")["means"]["ratio"]
for key, structure, tef in [
    ("quota_random", 0.269519, 0.050071),
    ("structural_greedy", 0.213055, 0.048692),
]:
    assert round(baselines[key]["structural_loss"], 6) == structure
    assert round(baselines[key]["loss"], 6) == tef
assert round(cost_summary["structural_loss"], 6) == 0.260790
assert math.isclose(cost_summary["loss"], mean(cost.values()), abs_tol=1e-14)

with (root / "generation_jobs.csv").open(newline="") as f:
    jobs = list(csv.DictReader(f))
assert len(jobs) == 147
assert all(row["status"] == "complete" and int(row["attempts"]) == 500 for row in jobs)
methods = defaultdict(dict)
for row in jobs:
    key = (row["seed"], row["domain"])
    assert key not in methods[row["method"]]
    methods[row["method"]][key] = row
assert len(methods) == 7 and all(len(rows) == 21 for rows in methods.values())
controlled = methods["schema2bench_agent_controlled"]
no_repair = methods["schema2bench_agent_no_repair"]
assert controlled.keys() == no_repair.keys()
assert all(float(row["accepted_exact_duplicate_rate"]) == 0 for row in [*controlled.values(), *no_repair.values()])
yield_mean = lambda rows: mean(1000 * int(r["accepted"]) / int(r["attempts"]) for r in rows.values())
wins = sum(int(controlled[k]["accepted"]) > int(no_repair[k]["accepted"]) for k in controlled)
ties = sum(int(controlled[k]["accepted"]) == int(no_repair[k]["accepted"]) for k in controlled)
assert wins == 20 and ties == 1
assert round(yield_mean(controlled), 2) == 417.90
assert yield_mean(no_repair) == 396.0
with (root / "generation_summary.csv").open(newline="") as f:
    summary = {r["method"]: r for r in csv.DictReader(f)}
c, ring = summary["schema2bench_agent_controlled"], summary["ringsql_reimpl"]
assert float(c["profile_l1_pooled_mean"]) < float(ring["profile_l1_pooled_mean"])
assert float(c["total_tokens_mean"]) > float(ring["total_tokens_mean"])
assert yield_mean(controlled) < yield_mean(methods["ringsql_reimpl"])
print(f"Selection: TEF {mean(anchor.values()):.6f} -> {mean(cost.values()):.6f}; reduction {relative:.2f}%; 10/10 favorable seeds.")
print(f"Repair: unique SQL/1,000 attempts {yield_mean(no_repair):.2f} -> {yield_mean(controlled):.2f}; {wins}/21 wins, {ties} tie.")
print("Earlier seven-model study; overlapping releases. Recount uses saved summaries, not new model evaluations.")
