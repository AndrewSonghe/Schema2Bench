from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class QueryPlan:
    plan_id: str
    operator: str
    difficulty: str
    needs_join: bool = False
    needs_numeric: bool = False
    needs_group: bool = False
    needs_order: bool = False
    target_result: str = "non_empty"


PROFILE_WEIGHTS: dict[str, dict[str, float]] = {
    "spider_like": {
        "select_filter": 0.35,
        "aggregation": 0.20,
        "join": 0.20,
        "group_by": 0.15,
        "top_k": 0.10,
    },
    "bird_like": {
        "select_filter": 0.25,
        "aggregation": 0.20,
        "join": 0.25,
        "group_by": 0.15,
        "top_k": 0.15,
    },
    "analytical": {
        "select_filter": 0.10,
        "aggregation": 0.25,
        "join": 0.25,
        "group_by": 0.25,
        "top_k": 0.15,
    },
    # Empirical profiles estimated from real Spider/BIRD gold SQL by
    # scripts/analyze_empirical_benchmark_profile.py. These profiles make the
    # benchmark construction target auditable rather than hand-specified.
    "spider_dev_empirical": {
        "select_filter": 0.2859,
        "aggregation": 0.2734,
        "join": 0.2059,
        "group_by": 0.1384,
        "top_k": 0.0965,
    },
    "spider_train_empirical": {
        "select_filter": 0.3204,
        "aggregation": 0.2491,
        "join": 0.2111,
        "group_by": 0.1352,
        "top_k": 0.0843,
    },
    "bird_dev_empirical": {
        "select_filter": 0.3841,
        "aggregation": 0.1866,
        "join": 0.3161,
        "group_by": 0.0333,
        "top_k": 0.0799,
    },
    "bird_train_empirical": {
        "select_filter": 0.3655,
        "aggregation": 0.1978,
        "join": 0.3181,
        "group_by": 0.0445,
        "top_k": 0.0741,
    },
    # Frozen final-evidence closure profile.  The existing candidate universe
    # is dominated by easy filters and unordered LIMIT queries.  This profile
    # intentionally oversamples operators that remain scarce after the strict
    # deterministic-LIMIT screen.  It is a candidate-support intervention,
    # not a replacement definition of the Spider target profile used by the
    # response-blind selector.
    "closure_complexity_refill": {
        "select_filter": 0.02,
        "aggregation": 0.08,
        "join": 0.45,
        "group_by": 0.35,
        "top_k": 0.10,
    },
    # Follow-up support profile used only when the deterministic closure pool
    # is infeasible after the first refill.  Unlike closure_complexity_refill,
    # this profile must also work for single-table databases, where join-heavy
    # planning otherwise spends most attempts on impossible plans.  Final
    # benchmark composition is still determined by the frozen Spider profile;
    # this profile only broadens the response-blind candidate universe.
    "closure_deficit_refill": {
        "select_filter": 0.30,
        "aggregation": 0.25,
        "join": 0.20,
        "group_by": 0.15,
        "top_k": 0.10,
    },
}


class BenchmarkPlannerAgent:
    def __init__(self, target_profile: str, seed: int = 0):
        if target_profile not in PROFILE_WEIGHTS:
            raise ValueError(f"Unknown target profile {target_profile}; choose one of {sorted(PROFILE_WEIGHTS)}")
        self.target_profile = target_profile
        self.rng = random.Random(seed)
        self.counter = 0

    def sample_plan(self, coverage_gap: dict[str, float] | None = None) -> QueryPlan:
        weights = dict(PROFILE_WEIGHTS[self.target_profile])
        if coverage_gap:
            for op, gap in coverage_gap.items():
                if op in weights:
                    weights[op] *= 1.0 + max(0.0, gap)
        operator = self._weighted_choice(weights)
        self.counter += 1
        return self._make_plan(operator, f"plan_{self.counter:08d}")

    def _weighted_choice(self, weights: dict[str, float]) -> str:
        total = sum(weights.values())
        pick = self.rng.random() * total
        acc = 0.0
        for key, weight in weights.items():
            acc += weight
            if pick <= acc:
                return key
        return next(iter(weights))

    def _make_plan(self, operator: str, plan_id: str) -> QueryPlan:
        if operator == "select_filter":
            return QueryPlan(plan_id, operator, "easy")
        if operator == "aggregation":
            return QueryPlan(plan_id, operator, "medium", needs_numeric=True)
        if operator == "join":
            return QueryPlan(plan_id, operator, "medium", needs_join=True)
        if operator == "group_by":
            return QueryPlan(plan_id, operator, "hard", needs_join=True, needs_numeric=True, needs_group=True)
        if operator == "top_k":
            return QueryPlan(plan_id, operator, "hard", needs_join=True, needs_numeric=True, needs_group=True, needs_order=True)
        raise ValueError(f"Unsupported operator {operator}")
