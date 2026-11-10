from __future__ import annotations

import json
import re
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .generators import AgenticGenerator, BaseGenerator, Candidate, ControlledAgenticGenerator, DeterministicRefillAgenticGenerator, DiverseDeterministicRefillAgenticGenerator, LlmPairGenerator, LlmSqlFirstAgenticGenerator, RandomSqlGenerator, RingSqlReimplementationGenerator, SemanticRefillAgenticGenerator, SingSqlReimplementationGenerator, TemplateGenerator, repair_empty_result, repair_result_bound
from .judge import SemanticJudgeAgent
from .llm import LlmProvider
from .manifest import DomainSpec, append_jsonl, write_json
from .memory import MemoryManager
from .planner import BenchmarkPlannerAgent, PROFILE_WEIGHTS
from .schema import SchemaProfilerAgent
from .verifier import ExecutionVerifierAgent, normalize_sql_signature


METHODS = {
    "random_sql",
    "template",
    "single_llm",
    "single_llm_repair",
    "self_refine",
    "schema2bench_no_memory",
    "schema2bench_full",
    "schema2bench_llm_full",
    "schema2bench_agent_controlled",
    "schema2bench_agent_semantic_refill",
    "schema2bench_agent_deterministic_refill",
    "schema2bench_agent_diverse_deterministic_refill",
    "schema2bench_agent_calibrated",
    "schema2bench_agent_no_realizer",
    "schema2bench_agent_no_repair",
    "schema2bench_agent_no_semantic_judge",
    "schema2bench_agent_no_memory",
    "ringsql_reimpl",
    "singsql_reimpl",
}


class GoldConstructionPipeline:
    def __init__(
        self,
        domain: DomainSpec,
        method: str,
        target_profile: str,
        output_dir: str | Path,
        attempts: int,
        accepted_target: int,
        max_repair_rounds: int,
        seed: int,
        llm_provider: LlmProvider | None = None,
        timeout_s: float = 30.0,
        row_limit: int = 1000,
    ):
        if method not in METHODS:
            raise ValueError(f"Unknown method {method}; choose from {sorted(METHODS)}")
        self.domain = domain
        self.method = method
        self.target_profile = target_profile
        self.output_dir = Path(output_dir) / domain.domain_id / method
        self.attempts = attempts
        self.accepted_target = accepted_target
        self.max_repair_rounds = max_repair_rounds
        self.seed = seed
        self.llm_provider = llm_provider
        self.schema_sample_values_per_column = (
            50
            if method == "schema2bench_agent_diverse_deterministic_refill"
            else 5
        )
        self.profiler = SchemaProfilerAgent(
            sample_values_per_column=self.schema_sample_values_per_column,
            enhanced_join_inference=method
            in {
                "schema2bench_agent_semantic_refill",
                "schema2bench_agent_deterministic_refill",
                "schema2bench_agent_diverse_deterministic_refill",
            }
        )
        self.planner = BenchmarkPlannerAgent(target_profile, seed=seed)
        self.verifier = ExecutionVerifierAgent(timeout_s=timeout_s, row_limit=row_limit)
        self.judge = SemanticJudgeAgent()
        self.memory = MemoryManager(self.output_dir / "memory.json")
        self.stats: Counter[str] = Counter()
        self.last_generation_error: str | None = None

    def run(self) -> dict[str, Any]:
        start = time.perf_counter()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._clear_outputs()
        profile = self.profiler.profile(self.domain.db_path)
        generator = self._build_generator()
        accepted = 0
        attempts_done = 0
        for attempt_idx in range(1, self.attempts + 1):
            if accepted >= self.accepted_target:
                break
            attempts_done = attempt_idx
            gap = self._planning_gap()
            plan = self.planner.sample_plan(gap)
            candidate = self._safe_generate(generator, profile, plan)
            if candidate is None:
                self._reject(None, attempt_idx, "generation_failed", {"plan": asdict(plan), "generation_error": self.last_generation_error})
                continue
            candidate_row = self._candidate_row(candidate, attempt_idx)
            append_jsonl(self.output_dir / "candidates.jsonl", candidate_row)
            admission = self._admit(candidate)
            row = {**candidate_row, **admission}
            if admission["admitted"]:
                accepted += 1
                append_jsonl(self.output_dir / "verified_gold.jsonl", row)
                self.memory.record_accept(admission["sql_signature"], candidate.operators, self._join_path(candidate))
                self.stats["accepted"] += 1
            else:
                append_jsonl(self.output_dir / "rejected_candidates.jsonl", row)
                self.memory.record_failure(admission["failure_type"])
                self.stats[f"failure:{admission['failure_type']}"] += 1
        self.memory.save()
        summary = self._summary(profile, attempts_done, accepted, time.perf_counter() - start)
        write_json(self.output_dir / "summary.json", summary)
        return summary

    def _build_generator(self) -> BaseGenerator:
        if self.method == "random_sql":
            return RandomSqlGenerator(seed=self.seed)
        if self.method == "template":
            return TemplateGenerator(seed=self.seed)
        if self.method == "schema2bench_no_memory":
            return AgenticGenerator(seed=self.seed, use_memory=False)
        if self.method == "schema2bench_full":
            return AgenticGenerator(seed=self.seed, use_memory=True)
        if self.method == "schema2bench_llm_full":
            if not self.llm_provider:
                raise RuntimeError(f"{self.method} requires an LLM provider")
            return LlmSqlFirstAgenticGenerator(self.llm_provider, seed=self.seed)
        if self.method == "schema2bench_agent_controlled":
            if not self.llm_provider:
                raise RuntimeError(f"{self.method} requires an LLM provider")
            return ControlledAgenticGenerator(self.llm_provider, seed=self.seed)
        if self.method == "schema2bench_agent_calibrated":
            if not self.llm_provider:
                raise RuntimeError(f"{self.method} requires an LLM provider")
            return ControlledAgenticGenerator(self.llm_provider, seed=self.seed, method_name=self.method)
        if self.method == "schema2bench_agent_semantic_refill":
            if not self.llm_provider:
                raise RuntimeError(f"{self.method} requires an LLM provider")
            return SemanticRefillAgenticGenerator(self.llm_provider, seed=self.seed)
        if self.method == "schema2bench_agent_deterministic_refill":
            if not self.llm_provider:
                raise RuntimeError(f"{self.method} requires an LLM provider")
            return DeterministicRefillAgenticGenerator(self.llm_provider, seed=self.seed)
        if self.method == "schema2bench_agent_diverse_deterministic_refill":
            if not self.llm_provider:
                raise RuntimeError(f"{self.method} requires an LLM provider")
            return DiverseDeterministicRefillAgenticGenerator(
                self.llm_provider, seed=self.seed
            )
        if self.method == "schema2bench_agent_no_realizer":
            if not self.llm_provider:
                raise RuntimeError(f"{self.method} requires an LLM provider")
            return ControlledAgenticGenerator(
                self.llm_provider,
                seed=self.seed,
                method_name=self.method,
                use_realizer=False,
            )
        if self.method in {
            "schema2bench_agent_no_repair",
            "schema2bench_agent_no_semantic_judge",
            "schema2bench_agent_no_memory",
        }:
            if not self.llm_provider:
                raise RuntimeError(f"{self.method} requires an LLM provider")
            return ControlledAgenticGenerator(self.llm_provider, seed=self.seed, method_name=self.method)
        if self.method == "ringsql_reimpl":
            return RingSqlReimplementationGenerator(self.llm_provider, seed=self.seed)
        if self.method == "singsql_reimpl":
            if not self.llm_provider:
                raise RuntimeError(f"{self.method} requires an LLM provider")
            return SingSqlReimplementationGenerator(self.llm_provider, seed=self.seed)
        if self.method in {"single_llm", "single_llm_repair", "self_refine"}:
            if not self.llm_provider:
                raise RuntimeError(f"{self.method} requires an LLM provider")
            return LlmPairGenerator(self.method, self.llm_provider, seed=self.seed)
        raise ValueError(self.method)

    def _safe_generate(self, generator: BaseGenerator, profile, plan) -> Candidate | None:
        self.last_generation_error = None
        try:
            return generator.generate(profile, plan)
        except Exception as exc:
            self.stats[f"generation_exception:{type(exc).__name__}"] += 1
            self.last_generation_error = f"{type(exc).__name__}: {exc}"
            return None

    def _admit(self, candidate: Candidate) -> dict[str, Any]:
        repair_trace = []
        current_sql = candidate.sql
        final_question = candidate.question
        verification = self.verifier.verify(self.domain.db_path, current_sql)
        repair_rounds = 0
        allow_repair = self.method in {
            "single_llm_repair",
            "self_refine",
            "schema2bench_no_memory",
            "schema2bench_full",
            "schema2bench_llm_full",
            "schema2bench_agent_controlled",
            "schema2bench_agent_calibrated",
            "schema2bench_agent_semantic_refill",
            "schema2bench_agent_deterministic_refill",
            "schema2bench_agent_diverse_deterministic_refill",
            "schema2bench_agent_no_realizer",
            "schema2bench_agent_no_semantic_judge",
            "schema2bench_agent_no_memory",
            "ringsql_reimpl",
            "singsql_reimpl",
        }
        while allow_repair and (not verification.ok) and repair_rounds < self.max_repair_rounds:
            repaired = None
            if verification.failure_type == "empty_result" and self.method != "schema2bench_agent_semantic_refill":
                repaired = repair_empty_result(current_sql)
            elif verification.failure_type in {"result_too_large", "timeout"}:
                repaired = repair_result_bound(current_sql, limit=100)
            if not repaired:
                break
            repair_rounds += 1
            repair_trace.append({"round": repair_rounds, "from": current_sql, "to": repaired, "reason": verification.failure_type})
            current_sql = repaired
            verification = self.verifier.verify(self.domain.db_path, current_sql)
        if self.method in {
            "schema2bench_agent_deterministic_refill",
            "schema2bench_agent_diverse_deterministic_refill",
        }:
            deterministic = self._determinize_terminal_limit(current_sql, final_question)
            if deterministic is None:
                signature = normalize_sql_signature(current_sql)
                return self._admission(
                    False,
                    verification,
                    signature,
                    repair_rounds,
                    repair_trace,
                    "unordered_limit_unrepairable",
                    current_sql,
                    final_question=final_question,
                )
            deterministic_sql, deterministic_question = deterministic
            if deterministic_sql != current_sql:
                repair_trace.append(
                    {
                        "round": "deterministic_limit_policy",
                        "from": current_sql,
                        "to": deterministic_sql,
                        "reason": "LIMIT without ORDER BY",
                    }
                )
                current_sql = deterministic_sql
                final_question = deterministic_question
                verification = self.verifier.verify(self.domain.db_path, current_sql)
        final_question = self._synchronize_question_with_sql(final_question, current_sql)
        signature = normalize_sql_signature(current_sql)
        if self.method != "schema2bench_agent_no_memory" and self.memory.has_signature(signature):
            return self._admission(False, verification, signature, repair_rounds, repair_trace, "duplicate_sql", current_sql, final_question=final_question)
        if not verification.ok:
            return self._admission(False, verification, signature, repair_rounds, repair_trace, verification.failure_type or "verification_failed", current_sql, final_question=final_question)
        judge = None
        if self.method != "schema2bench_agent_no_semantic_judge":
            judge = self.judge.judge(final_question, current_sql, candidate.operators)
            if not judge.ok:
                return self._admission(False, verification, signature, repair_rounds, repair_trace, "semantic_mismatch", current_sql, judge, final_question)
        profile_failure = self._profile_admission_failure(candidate)
        if profile_failure:
            return self._admission(False, verification, signature, repair_rounds, repair_trace, profile_failure, current_sql, judge, final_question)
        return self._admission(True, verification, signature, repair_rounds, repair_trace, None, current_sql, judge, final_question)

    def _determinize_terminal_limit(
        self, sql: str, question: str
    ) -> tuple[str, str] | None:
        match = re.search(r"\s+LIMIT\s+(\d+)\s*;?\s*$", sql, re.IGNORECASE)
        if not match or re.search(r"\border\s+by\b", sql, re.IGNORECASE):
            return sql, question
        select_match = re.match(
            r"\s*SELECT\s+(.+?)\s+FROM\s+",
            sql,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not select_match:
            return None
        projected = [part.strip() for part in select_match.group(1).split(",")]
        if not projected or len(projected) > 2 or any(not part for part in projected):
            return None
        order_keys = [
            re.sub(r"\s+AS\s+[\w\"]+\s*$", "", part, flags=re.IGNORECASE).strip()
            for part in projected
        ]
        if any(re.search(r"\b(?:SELECT|FROM)\b", part, re.I) for part in order_keys):
            return None
        limit = int(match.group(1))
        base_sql = sql[: match.start()].rstrip().rstrip(";")
        ordered_sql = (
            f"{base_sql} ORDER BY "
            + ", ".join(f"{part} ASC" for part in order_keys)
            + f" LIMIT {limit}"
        )
        labels = [re.sub(r'"', "", part).strip() for part in order_keys]
        base_question = re.sub(
            rf"\s*Return\s+up\s+to\s+{limit}\s+rows\.?\s*$",
            "",
            question,
            flags=re.IGNORECASE,
        ).rstrip().rstrip(".?")
        ordered_question = (
            f"{base_question}, ordered by {' and then '.join(labels)} in ascending "
            f"order and limited to the first {limit} rows?"
        )
        return ordered_sql, ordered_question

    def _synchronize_question_with_sql(self, question: str, sql: str) -> str:
        sql_limit = re.search(r"\bLIMIT\s+(\d+)\b", sql, flags=re.IGNORECASE)
        if not sql_limit:
            return question
        limit = int(sql_limit.group(1))
        mentioned = {
            int(match.group(1))
            for pattern in (
                re.compile(r"\b(?:first|top|up to|at most|no more than)\s+(\d+)\b", re.IGNORECASE),
                re.compile(
                    r"\blimit(?:ed|ing)?\b.{0,35}?\bto\s+(?:the\s+)?(?:first\s+)?(\d+)\b",
                    re.IGNORECASE,
                ),
            )
            for match in pattern.finditer(question)
        }
        if limit in mentioned:
            return question
        return question.rstrip().rstrip(".?") + f". Return up to {limit} rows."

    def _planning_gap(self) -> dict[str, float] | None:
        if self.method == "schema2bench_full":
            return self.memory.coverage_gap(PROFILE_WEIGHTS[self.target_profile])
        if self.method in {
            "schema2bench_agent_calibrated",
            "schema2bench_agent_semantic_refill",
            "schema2bench_agent_deterministic_refill",
        }:
            # Empirical benchmark calibration needs stronger feedback than the
            # original mild coverage gap. The admitted pool is naturally biased
            # toward easy executable filters, so we amplify under-covered
            # operators at planning time.
            raw_gap = self.memory.coverage_gap(PROFILE_WEIGHTS[self.target_profile])
            return {op: gap * 6.0 for op, gap in raw_gap.items()}
        return None

    def _profile_admission_failure(self, candidate: Candidate) -> str | None:
        if self.method not in {
            "schema2bench_agent_calibrated",
            "schema2bench_agent_semantic_refill",
            "schema2bench_agent_deterministic_refill",
        }:
            return None
        target = PROFILE_WEIGHTS[self.target_profile]
        total = sum(self.memory.operator_counts.values())
        if total < 50:
            return None
        primary = self._primary_operator(candidate.operators)
        if primary not in target:
            return None
        observed = self.memory.operator_counts[primary] / max(total, 1)
        undercovered_exists = any((self.memory.operator_counts[op] / max(total, 1)) < weight * 0.75 for op, weight in target.items())
        # Reject only clear over-representation. This keeps the gate from
        # overfitting small-sample noise while still countering the accepted-pool
        # bias toward simple filters.
        if undercovered_exists and observed > max(target[primary] * 1.35, target[primary] + 0.10):
            return f"profile_overrepresented_{primary}"
        return None

    def _primary_operator(self, operators: list[str]) -> str:
        for op in ("top_k", "group_by", "join", "aggregation", "select_filter"):
            if op in operators:
                return op
        return operators[0] if operators else "unknown"

    def _admission(
        self,
        admitted: bool,
        verification,
        signature: str,
        repair_rounds: int,
        repair_trace: list[dict[str, Any]],
        failure_type: str | None,
        final_sql: str,
        judge=None,
        final_question: str | None = None,
    ) -> dict[str, Any]:
        result = {
            "admitted": admitted,
            "final_sql": final_sql,
            "sql_signature": signature,
            "failure_type": failure_type,
            "repair_rounds": repair_rounds,
            "repair_trace": repair_trace,
            "verification": asdict(verification),
            "semantic_judge": asdict(judge) if judge else None,
        }
        if final_question is not None:
            result["question"] = final_question
        return result

    def _candidate_row(self, candidate: Candidate, attempt_idx: int) -> dict[str, Any]:
        return {
            "id": f"{self.domain.domain_id}_{self.method}_{attempt_idx:08d}",
            "domain": self.domain.domain_id,
            "db_path": str(self.domain.db_path),
            "question": candidate.question,
            "candidate_sql": candidate.sql,
            "generation_method": candidate.generation_method,
            "target_profile": self.target_profile,
            "difficulty": candidate.difficulty,
            "operators": candidate.operators,
            "plan_id": candidate.plan_id,
            "agent_trace": candidate.agent_trace,
        }

    def _reject(self, candidate: Candidate | None, attempt_idx: int, failure_type: str, extra: dict[str, Any]) -> None:
        row = {
            "id": f"{self.domain.domain_id}_{self.method}_{attempt_idx:08d}",
            "domain": self.domain.domain_id,
            "generation_method": self.method,
            "target_profile": self.target_profile,
            "admitted": False,
            "failure_type": failure_type,
            **extra,
        }
        append_jsonl(self.output_dir / "rejected_candidates.jsonl", row)
        self.stats[f"failure:{failure_type}"] += 1
        self.memory.record_failure(failure_type)

    def _summary(self, profile, attempts_done: int, accepted: int, elapsed_s: float) -> dict[str, Any]:
        failures = {k.split("failure:", 1)[1]: v for k, v in self.stats.items() if k.startswith("failure:")}
        operator_counts = dict(self.memory.operator_counts)
        return {
            "domain": self.domain.domain_id,
            "db_path": str(self.domain.db_path),
            "method": self.method,
            "target_profile": self.target_profile,
            "attempts_done": attempts_done,
            "accepted": accepted,
            "accepted_per_1000": round(accepted / max(attempts_done, 1) * 1000, 3),
            "failure_counts": failures,
            "operator_counts": operator_counts,
            "table_count": len(profile.tables),
            "join_edge_count": len(profile.join_edges),
            "elapsed_s": round(elapsed_s, 3),
            "schema_sample_values_per_column": self.schema_sample_values_per_column,
            "output_dir": str(self.output_dir),
        }

    def _join_path(self, candidate: Candidate) -> str | None:
        trace = candidate.agent_trace
        join = trace.get("join")
        if isinstance(join, dict):
            return f"{join.get('left_table')}.{join.get('left_column')}={join.get('right_table')}.{join.get('right_column')}"
        return None

    def _clear_outputs(self) -> None:
        for name in ("candidates.jsonl", "verified_gold.jsonl", "rejected_candidates.jsonl", "summary.json"):
            path = self.output_dir / name
            if path.exists():
                path.unlink()


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows = []
    p = Path(path)
    if not p.exists():
        return rows
    with p.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows
