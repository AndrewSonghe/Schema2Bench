from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


class MemoryManager:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.accepted_signatures: set[str] = set()
        self.failure_counts: Counter[str] = Counter()
        self.operator_counts: Counter[str] = Counter()
        self.join_paths: Counter[str] = Counter()
        if self.path and self.path.exists():
            self._load()

    def has_signature(self, signature: str) -> bool:
        return signature in self.accepted_signatures

    def record_accept(self, signature: str, operators: list[str], join_path: str | None = None) -> None:
        self.accepted_signatures.add(signature)
        for op in operators:
            self.operator_counts[op] += 1
        if join_path:
            self.join_paths[join_path] += 1

    def record_failure(self, failure_type: str | None) -> None:
        self.failure_counts[failure_type or "unknown"] += 1

    def coverage_gap(self, target_weights: dict[str, float]) -> dict[str, float]:
        total = sum(self.operator_counts.values())
        if total == 0:
            return {k: 1.0 for k in target_weights}
        gaps: dict[str, float] = {}
        for op, target in target_weights.items():
            observed = self.operator_counts[op] / total
            gaps[op] = max(0.0, target - observed) / max(target, 1e-9)
        return gaps

    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "accepted_signatures": sorted(self.accepted_signatures),
            "failure_counts": dict(self.failure_counts),
            "operator_counts": dict(self.operator_counts),
            "join_paths": dict(self.join_paths),
        }
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    def _load(self) -> None:
        data: dict[str, Any] = json.loads(self.path.read_text())
        self.accepted_signatures = set(data.get("accepted_signatures", []))
        self.failure_counts = Counter(data.get("failure_counts", {}))
        self.operator_counts = Counter(data.get("operator_counts", {}))
        self.join_paths = Counter(data.get("join_paths", {}))

