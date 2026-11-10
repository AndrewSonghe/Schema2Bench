from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JudgeResult:
    ok: bool
    score: float
    rationale: str
    judge: str = "heuristic"


class SemanticJudgeAgent:
    """Heuristic judge used for offline admission.

    LLM judging should be added as an additional reviewer in final experiments,
    but this conservative local judge keeps the pipeline executable without a
    model server.
    """

    def judge(self, question: str, sql: str, operators: list[str]) -> JudgeResult:
        q = question.lower()
        s = sql.lower()
        checks = []
        if "count(" in s:
            checks.append(any(x in q for x in ("how many", "count", "number of")))
        if any(x in s for x in ("sum(", "avg(", "max(", "min(")):
            checks.append(any(x in q for x in ("total", "average", "avg", "mean", "highest", "lowest", "maximum", "minimum", "sum", "largest", "smallest")))
        if " order by " in s:
            checks.append(any(x in q for x in ("top", "highest", "lowest", "largest", "smallest", "ordered", "rank")))
        if " group by " in s:
            checks.append(any(x in q for x in ("by", "per", "for each", "group")))
        if " where " in s:
            checks.append(any(x in q for x in (
                "where",
                " in ",
                " from ",
                " for ",
                "with",
                "whose",
                "that have",
                "that has",
                "greater",
                "less",
                "above",
                "below",
                "over",
                "under",
                "at least",
                "at most",
                "no less",
                "no more",
                "after",
                "before",
                "equal",
                "matching",
                "include",
                "includes",
                "containing",
            )))
        if not checks:
            checks.append(bool(question.strip()) and bool(sql.strip()))
        passed = sum(1 for c in checks if c)
        score = passed / len(checks)
        return JudgeResult(score >= 0.75, score, f"{passed}/{len(checks)} heuristic checks passed")
