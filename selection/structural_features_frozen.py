#!/usr/bin/env python3
"""Deterministic SQL-only features for benchmark-generation v2.

The same functions are used for Spider-train profiling and target-domain
candidate selection.  No generator-provided difficulty label is consumed.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable


OPERATOR_KEYS = ("select_filter", "aggregation", "join", "group_by", "top_k")
DIFFICULTY_KEYS = ("easy", "medium", "hard")
SHAPE_KEYS = (
    "has_filter",
    "has_join",
    "has_group_by",
    "has_aggregation",
    "has_order_by",
    "has_limit",
)
BLOCK_KEYS = ("operators", "difficulty", "shapes", "joins", "tokens")
AGG_RE = re.compile(r"\b(?:count|sum|avg|min|max)\s*\(", re.IGNORECASE)


def compact_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", str(sql).strip()).strip()


def sql_operators(sql: str) -> list[str]:
    low = f" {compact_sql(sql).lower()} "
    operators: list[str] = []
    if " where " in low:
        operators.append("select_filter")
    if AGG_RE.search(low):
        operators.append("aggregation")
    if " join " in low:
        operators.append("join")
    if " group by " in low:
        operators.append("group_by")
    if " order by " in low and " limit " in low:
        operators.append("top_k")
    return operators or ["select_filter"]


def sql_shapes(sql: str) -> dict[str, int]:
    low = f" {compact_sql(sql).lower()} "
    return {
        "has_filter": int(" where " in low),
        "has_join": int(" join " in low),
        "has_group_by": int(" group by " in low),
        "has_aggregation": int(bool(AGG_RE.search(low))),
        "has_order_by": int(" order by " in low),
        "has_limit": int(" limit " in low),
    }


def sql_complexity_score(sql: str) -> int:
    """Return a transparent SQL-only complexity score.

    The score intentionally uses syntax available in both Spider and generated
    SQL.  It is a common analysis scale, not a claim to reproduce Spider's
    official hardness evaluator.
    """

    low = f" {compact_sql(sql).lower()} "
    joins = len(re.findall(r"\bjoin\b", low))
    nested_selects = max(len(re.findall(r"\bselect\b", low)) - 1, 0)
    set_operations = len(re.findall(r"\b(?:union|intersect|except)\b", low))
    conjunctions = len(re.findall(r"\b(?:and|or)\b", low))
    return (
        joins
        + 2 * nested_selects
        + 2 * set_operations
        + int(" group by " in low)
        + int(" having " in low)
        + int(bool(AGG_RE.search(low)))
        + int(" order by " in low)
        + int(" case " in low)
        + int(" distinct " in low)
        + int(conjunctions >= 2)
    )


def sql_difficulty(sql: str) -> str:
    score = sql_complexity_score(sql)
    if score <= 1:
        return "easy"
    if score <= 3:
        return "medium"
    return "hard"


def feature_vector(sql: str) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...], int, int]:
    operators = set(sql_operators(sql))
    difficulty = sql_difficulty(sql)
    shapes = sql_shapes(sql)
    return (
        tuple(int(key in operators) for key in OPERATOR_KEYS),
        tuple(int(difficulty == key) for key in DIFFICULTY_KEYS),
        tuple(shapes[key] for key in SHAPE_KEYS),
        len(re.findall(r"\bjoin\b", compact_sql(sql), flags=re.IGNORECASE)),
        len(compact_sql(sql).split()),
    )


def zero_totals() -> tuple[list[int], list[int], list[int], int, int]:
    return ([0] * len(OPERATOR_KEYS), [0] * len(DIFFICULTY_KEYS), [0] * len(SHAPE_KEYS), 0, 0)


def add_vector(
    totals: tuple[list[int], list[int], list[int], int, int],
    vector: tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...], int, int],
    sign: int = 1,
) -> tuple[list[int], list[int], list[int], int, int]:
    operators, difficulty, shapes, joins, tokens = totals
    v_operators, v_difficulty, v_shapes, v_joins, v_tokens = vector
    return (
        [value + sign * v_operators[index] for index, value in enumerate(operators)],
        [value + sign * v_difficulty[index] for index, value in enumerate(difficulty)],
        [value + sign * v_shapes[index] for index, value in enumerate(shapes)],
        joins + sign * v_joins,
        tokens + sign * v_tokens,
    )


def sum_vectors(
    indices: Iterable[int],
    vectors: list[tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...], int, int]],
) -> tuple[list[int], list[int], list[int], int, int]:
    totals = zero_totals()
    for index in indices:
        totals = add_vector(totals, vectors[index])
    return totals


def profile_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("cannot profile an empty row set")
    operator_counts: Counter[str] = Counter()
    difficulty_counts: Counter[str] = Counter()
    shape_counts: Counter[str] = Counter()
    joins = 0
    tokens = 0
    for row in rows:
        sql = str(row.get("sql") or row.get("query") or "")
        operators = sql_operators(sql)
        operator_counts.update(operators)
        difficulty_counts[sql_difficulty(sql)] += 1
        shape_counts.update({key: value for key, value in sql_shapes(sql).items() if value})
        joins += len(re.findall(r"\bjoin\b", compact_sql(sql), flags=re.IGNORECASE))
        tokens += len(compact_sql(sql).split())
    operator_total = max(sum(operator_counts.values()), 1)
    count = len(rows)
    return {
        "row_count": count,
        "operators": {key: operator_counts[key] / operator_total for key in OPERATOR_KEYS},
        "difficulty": {key: difficulty_counts[key] / count for key in DIFFICULTY_KEYS},
        "shapes": {key: shape_counts[key] / count for key in SHAPE_KEYS},
        "average_joins": joins / count,
        "average_tokens": tokens / count,
        "difficulty_definition": {
            "feature_source": "final_sql_only",
            "easy": "complexity_score <= 1",
            "medium": "2 <= complexity_score <= 3",
            "hard": "complexity_score >= 4",
        },
    }


def structural_metrics(
    totals: tuple[list[int], list[int], list[int], int, int],
    sample_count: int,
    target: dict[str, Any],
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    if sample_count <= 0:
        raise ValueError("sample_count must be positive")
    block_weights = {key: 1.0 for key in BLOCK_KEYS}
    if weights:
        block_weights.update({key: float(value) for key, value in weights.items()})
    operators, difficulty, shapes, joins, tokens = totals
    operator_total = max(sum(operators), 1)
    operator_l1 = sum(
        abs(operators[index] / operator_total - float(target["operators"][key]))
        for index, key in enumerate(OPERATOR_KEYS)
    )
    difficulty_l1 = sum(
        abs(difficulty[index] / sample_count - float(target["difficulty"][key]))
        for index, key in enumerate(DIFFICULTY_KEYS)
    )
    shape_l1 = sum(
        abs(shapes[index] / sample_count - float(target["shapes"][key]))
        for index, key in enumerate(SHAPE_KEYS)
    )
    average_joins = joins / sample_count
    average_tokens = tokens / sample_count
    blocks = {
        "operators": operator_l1 / 2.0,
        "difficulty": difficulty_l1 / 2.0,
        "shapes": shape_l1 / len(SHAPE_KEYS),
        "joins": abs(average_joins - float(target["average_joins"]))
        / max(float(target["average_joins"]), 1e-12),
        "tokens": abs(average_tokens - float(target["average_tokens"]))
        / max(float(target["average_tokens"]), 1e-12),
    }
    active_weight = sum(block_weights[key] for key in BLOCK_KEYS)
    if active_weight <= 0:
        raise ValueError("at least one structural block must have positive weight")
    score = sum(block_weights[key] * blocks[key] for key in BLOCK_KEYS) / active_weight
    return {
        "score": score,
        "block_weights": block_weights,
        "blocks": blocks,
        "raw": {
            "operator_l1": operator_l1,
            "difficulty_l1": difficulty_l1,
            "shape_l1": shape_l1,
            "average_join_delta": abs(average_joins - float(target["average_joins"])),
            "average_token_relative_delta": blocks["tokens"],
        },
        "observed": {
            "average_joins": average_joins,
            "average_tokens": average_tokens,
        },
    }
