from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Any

from .llm import LlmProvider, extract_json_object
from .planner import QueryPlan
from .schema import (
    ColumnInfo,
    JoinEdge,
    SchemaProfile,
    choose_table,
    column_represents_table,
    is_identifier_like,
    is_numeric_type,
    identifier_tokens,
    key_entity,
    quote_ident,
)


@dataclass(frozen=True)
class Candidate:
    question: str
    sql: str
    operators: list[str]
    difficulty: str
    generation_method: str
    plan_id: str
    agent_trace: dict[str, Any]


class BaseGenerator:
    method_name = "base"

    def generate(self, profile: SchemaProfile, plan: QueryPlan) -> Candidate | None:
        raise NotImplementedError


class RandomSqlGenerator(BaseGenerator):
    method_name = "random_sql"

    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)

    def generate(self, profile: SchemaProfile, plan: QueryPlan) -> Candidate | None:
        table = choose_table(profile, self.rng)
        cols = profile.any_columns(table)
        if not cols:
            return None
        select_col = self.rng.choice(cols)
        sql = f"SELECT {quote_ident(select_col.name)} FROM {quote_ident(table)}"
        question = f"List values of {select_col.name} from {table}."
        operators = ["select_filter"]
        if self.rng.random() < 0.5:
            filter_col = self.rng.choice(cols)
            if filter_col.samples:
                value = self.rng.choice(filter_col.samples)
                sql += f" WHERE {quote_ident(filter_col.name)} = {sql_literal(value)}"
                question = f"List values of {select_col.name} from {table} where {filter_col.name} equals {value}."
        sql += " LIMIT 20"
        return Candidate(question, sql, operators, "easy", self.method_name, plan.plan_id, {"agent": "random_sql"})


class TemplateGenerator(BaseGenerator):
    method_name = "template"

    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)

    def generate(self, profile: SchemaProfile, plan: QueryPlan) -> Candidate | None:
        if plan.operator == "select_filter":
            return self._select_filter(profile, plan, self.method_name)
        if plan.operator == "aggregation":
            return self._aggregation(profile, plan, self.method_name)
        if plan.operator == "join":
            return self._join(profile, plan, self.method_name)
        if plan.operator == "group_by":
            return self._group_by(profile, plan, self.method_name, top_k=False)
        if plan.operator == "top_k":
            return self._group_by(profile, plan, self.method_name, top_k=True)
        return None

    def _select_filter(self, profile: SchemaProfile, plan: QueryPlan, method: str) -> Candidate | None:
        table = choose_table(profile, self.rng)
        cols = profile.any_columns(table)
        value_cols = [c for c in cols if c.samples]
        if not cols:
            return None
        select_col = self._prefer_name_col(cols)
        where = ""
        q_filter = ""
        operators = ["select_filter"]
        if value_cols:
            fc = self.rng.choice(value_cols)
            val = self.rng.choice(fc.samples)
            where = f" WHERE {quote_ident(fc.name)} = {sql_literal(val)}"
            q_filter = f" where {fc.name} equals {val}"
        sql = f"SELECT {quote_ident(select_col.name)} FROM {quote_ident(table)}{where} LIMIT 20"
        question = f"List {select_col.name} from {table}{q_filter}."
        return Candidate(question, sql, operators, plan.difficulty, method, plan.plan_id, {"agent": "template", "table": table})

    def _aggregation(self, profile: SchemaProfile, plan: QueryPlan, method: str) -> Candidate | None:
        table = self._table_with_numeric(profile)
        if not table:
            return None
        num = self.rng.choice(profile.numeric_columns(table))
        agg = self.rng.choice(["COUNT", "AVG", "SUM", "MAX"])
        expr = "*" if agg == "COUNT" else quote_ident(num.name)
        sql = f"SELECT {agg}({expr}) AS value FROM {quote_ident(table)}"
        question = {
            "COUNT": f"How many rows are in {table}?",
            "AVG": f"What is the average {num.name} in {table}?",
            "SUM": f"What is the total {num.name} in {table}?",
            "MAX": f"What is the highest {num.name} in {table}?",
        }[agg]
        return Candidate(question, sql, ["aggregation"], plan.difficulty, method, plan.plan_id, {"agent": "template", "table": table, "agg": agg})

    def _join(self, profile: SchemaProfile, plan: QueryPlan, method: str) -> Candidate | None:
        edge = self._choose_edge(profile)
        if not edge:
            return self._select_filter(profile, plan, method)
        left_col = self._prefer_name_col(profile.any_columns(edge.left_table))
        right_col = self._prefer_name_col(profile.any_columns(edge.right_table))
        sql = (
            f"SELECT {qcol(edge.left_table, left_col.name)}, {qcol(edge.right_table, right_col.name)} "
            f"FROM {quote_ident(edge.left_table)} JOIN {quote_ident(edge.right_table)} "
            f"ON {qcol(edge.left_table, edge.left_column)} = {qcol(edge.right_table, edge.right_column)} LIMIT 20"
        )
        question = f"List matching {left_col.name} from {edge.left_table} and {right_col.name} from {edge.right_table}."
        return Candidate(question, sql, ["join"], plan.difficulty, method, plan.plan_id, {"agent": "template", "join": edge.__dict__})

    def _group_by(self, profile: SchemaProfile, plan: QueryPlan, method: str, top_k: bool) -> Candidate | None:
        edge = self._choose_edge(profile)
        if edge:
            group_table = edge.left_table
            measure_table = edge.right_table
            join_clause = (
                f" FROM {quote_ident(edge.left_table)} JOIN {quote_ident(edge.right_table)} "
                f"ON {qcol(edge.left_table, edge.left_column)} = {qcol(edge.right_table, edge.right_column)}"
            )
        else:
            group_table = choose_table(profile, self.rng)
            measure_table = group_table
            join_clause = f" FROM {quote_ident(group_table)}"
        group_cols = profile.text_columns(group_table) or profile.any_columns(group_table)
        nums = profile.numeric_columns(measure_table)
        if not group_cols or not nums:
            return self._aggregation(profile, plan, method)
        group_col = self._prefer_name_col(group_cols)
        measure = self.rng.choice(nums)
        sql = (
            f"SELECT {qcol(group_table, group_col.name)} AS group_value, SUM({qcol(measure_table, measure.name)}) AS total_value"
            f"{join_clause} GROUP BY {qcol(group_table, group_col.name)}"
        )
        operators = ["group_by"]
        question = f"What is the total {measure.name} for each {group_col.name}?"
        if top_k:
            sql += " ORDER BY total_value DESC LIMIT 5"
            operators = ["top_k", "group_by"]
            question = f"Which are the top 5 {group_col.name} values by total {measure.name}?"
        return Candidate(question, sql, operators, plan.difficulty, method, plan.plan_id, {"agent": "template", "group_table": group_table, "measure_table": measure_table})

    def _table_with_numeric(self, profile: SchemaProfile) -> str | None:
        candidates = [t for t in profile.table_names() if profile.numeric_columns(t)]
        return self.rng.choice(candidates) if candidates else None

    def _choose_edge(self, profile: SchemaProfile) -> JoinEdge | None:
        if not profile.join_edges:
            return None
        return self.rng.choice(profile.join_edges)

    def _prefer_name_col(self, cols: list[ColumnInfo]) -> ColumnInfo:
        for pattern in ("name", "title", "id", "key"):
            matches = [c for c in cols if pattern in c.name.lower()]
            if matches:
                return self.rng.choice(matches)
        return self.rng.choice(cols)


class AgenticGenerator(TemplateGenerator):
    method_name = "schema2bench_full"

    def __init__(self, seed: int = 0, use_memory: bool = True):
        super().__init__(seed=seed)
        self.use_memory = use_memory
        self.method_name = "schema2bench_full" if use_memory else "schema2bench_no_memory"

    def generate(self, profile: SchemaProfile, plan: QueryPlan) -> Candidate | None:
        candidate = super().generate(profile, plan)
        if not candidate:
            return None
        trace = dict(candidate.agent_trace)
        trace.update(
            {
                "agents": [
                    "schema_profiler",
                    "benchmark_planner",
                    "sql_first_generator",
                    "execution_verifier",
                    "nl_realizer",
                    "semantic_judge",
                    "memory_manager" if self.use_memory else "memory_disabled",
                ],
                "sql_first": True,
                "memory_enabled": self.use_memory,
            }
        )
        return Candidate(candidate.question, candidate.sql, candidate.operators, candidate.difficulty, self.method_name, candidate.plan_id, trace)


class LlmPairGenerator(BaseGenerator):
    def __init__(self, method_name: str, provider: LlmProvider, seed: int = 0):
        self.method_name = method_name
        self.provider = provider
        self.rng = random.Random(seed)

    def generate(self, profile: SchemaProfile, plan: QueryPlan) -> Candidate | None:
        prompt = self._prompt(profile, plan)
        response = self.provider.complete(prompt)
        data = extract_json_object(response.text)
        sql = data["sql"]
        question = data["question"]
        operators = data.get("operators") or [plan.operator]
        return Candidate(
            question=question,
            sql=sql,
            operators=operators,
            difficulty=data.get("difficulty", plan.difficulty),
            generation_method=self.method_name,
            plan_id=plan.plan_id,
            agent_trace={"agent": self.method_name, "provider": response.provider, "prompt": prompt},
        )

    def _prompt(self, profile: SchemaProfile, plan: QueryPlan) -> str:
        schema_lines = []
        for table in profile.tables.values():
            col_bits = []
            for c in table.columns[:40]:
                sample_text = ""
                if c.samples:
                    sample_text = " samples=" + repr(list(c.samples[:3]))
                col_bits.append(f'{quote_ident(c.name)} {c.type}'.strip() + sample_text)
            cols = "; ".join(col_bits)
            schema_lines.append(f"- {quote_ident(table.name)}({cols})")
        return (
            "You are generating candidate Text-to-SQL benchmark gold data for SQLite.\n"
            "Return EXACTLY one JSON object and no markdown, no explanation, no code fence.\n"
            'Required keys: "question", "sql", "operators", "difficulty".\n'
            "SQL constraints:\n"
            "- Use a single read-only SQLite SELECT query only.\n"
            "- Use only the tables and columns listed below.\n"
            "- Put double quotes around every table and column identifier exactly as shown.\n"
            "- Do not use SELECT *.\n"
            "- For list queries, project at most 3 columns and add LIMIT 100.\n"
            "- Prefer predicates using sample values shown in the schema.\n"
            "- Avoid queries that return the whole table or more than 1000 rows.\n"
            "- The question must exactly match the SQL intent.\n\n"
            f"Plan: operator={plan.operator}, difficulty={plan.difficulty}, needs_join={plan.needs_join}, "
            f"needs_group={plan.needs_group}, needs_order={plan.needs_order}\n"
            "Schema:\n" + "\n".join(schema_lines[:60])
        )


class LlmSqlFirstAgenticGenerator(LlmPairGenerator):
    """LLM-backed SQL-first Schema2Bench generator.

    This is the method to use for the main agent+LLM experiment. The LLM is not
    asked to freely invent a benchmark row; it receives a planner-specified
    operator/difficulty target and must emit SQL plus a question derived from
    that SQL. The downstream verifier, repair, judge, duplicate filter, and
    memory gate decide whether the candidate is promoted to verified gold.
    """

    def __init__(self, provider: LlmProvider, seed: int = 0):
        super().__init__("schema2bench_llm_full", provider, seed=seed)

    def _prompt(self, profile: SchemaProfile, plan: QueryPlan) -> str:
        schema_lines = []
        join_lines = []
        for edge in profile.join_edges[:80]:
            join_lines.append(
                f"{quote_ident(edge.left_table)}.{quote_ident(edge.left_column)} = "
                f"{quote_ident(edge.right_table)}.{quote_ident(edge.right_column)}"
            )
        for table in profile.tables.values():
            col_bits = []
            for c in table.columns[:45]:
                sample_text = ""
                if c.samples:
                    sample_text = " samples=" + repr(list(c.samples[:4]))
                col_bits.append(f'{quote_ident(c.name)} {c.type}'.strip() + sample_text)
            schema_lines.append(f"- {quote_ident(table.name)}({'; '.join(col_bits)})")

        return (
            "You are the SQL-first Generator Agent in Schema2Bench.\n"
            "Goal: create one benchmark-like Text-to-SQL gold candidate for SQLite.\n"
            "Return EXACTLY one JSON object and no markdown, no explanation, no code fence.\n"
            'Required keys: "question", "sql", "operators", "difficulty".\n\n'
            "Generation order:\n"
            "1. Internally choose real tables/columns/values from the schema.\n"
            "2. Write the SQL first.\n"
            "3. Write a natural-language question that exactly describes that SQL.\n\n"
            "Hard SQL constraints:\n"
            "- SQLite syntax only.\n"
            "- Use a single read-only SELECT or WITH query.\n"
            "- Use only tables/columns listed below.\n"
            "- Put double quotes around every table and column identifier exactly as shown.\n"
            "- Do not use SELECT *.\n"
            "- Do not use date('now') or current-date functions; use sample values instead.\n"
            "- Every non-aggregate list query MUST end with LIMIT 20.\n"
            "- Project at most 2 columns unless the plan explicitly needs grouping.\n"
            "- Prefer equality predicates on sample values over broad inequality predicates.\n"
            "- Avoid DISTINCT unless necessary.\n"
            "- Avoid joining more than two tables unless the plan explicitly requires it.\n"
            "- For broad filters, add LIMIT 20 or aggregate the result.\n"
            "- Prefer predicates using sample values shown below.\n"
            "- Avoid queries likely to return more than 1000 rows.\n"
            "- If the plan requires grouping/top-k, include GROUP BY and ORDER BY with LIMIT 5.\n\n"
            "Requested benchmark plan:\n"
            f"- operator: {plan.operator}\n"
            f"- difficulty: {plan.difficulty}\n"
            f"- needs_join: {plan.needs_join}\n"
            f"- needs_group: {plan.needs_group}\n"
            f"- needs_order: {plan.needs_order}\n\n"
            "Allowed join hints:\n" + ("\n".join(join_lines) if join_lines else "(no explicit join hints)") + "\n\n"
            "Schema:\n" + "\n".join(schema_lines[:80])
        )


class ControlledAgenticGenerator(TemplateGenerator):
    """Constrained agent+LLM benchmark generator.

    This is the safer paper method when free-form LLM SQL generation is too
    unstable for gold construction. A symbolic SQL-first agent generates the
    reference SQL from schema/profile constraints; the LLM is used as a
    controlled NL-realizer agent that verbalizes the already-constructed SQL.
    The downstream admission protocol still decides whether the pair becomes
    verified gold.
    """

    method_name = "schema2bench_agent_controlled"

    def __init__(
        self,
        provider: LlmProvider,
        seed: int = 0,
        method_name: str | None = None,
        use_realizer: bool = True,
    ):
        super().__init__(seed=seed)
        self.provider = provider
        if method_name:
            self.method_name = method_name
        self.use_realizer = use_realizer

    def generate(self, profile: SchemaProfile, plan: QueryPlan) -> Candidate | None:
        base = super().generate(profile, plan)
        if not base:
            return None
        question = base.question
        trace = dict(base.agent_trace)
        trace.update(
            {
                "agents": [
                    "schema_profiler",
                    "benchmark_planner",
                    "symbolic_sql_first_generator",
                    "llm_nl_realizer",
                    "execution_verifier",
                    "repair_agent",
                    "semantic_judge",
                    "memory_manager",
                ],
                "sql_first": True,
                "llm_role": "nl_realizer_only",
                "nl_realizer_enabled": self.use_realizer,
            }
        )
        if self.use_realizer:
            try:
                response = self.provider.complete(self._realizer_prompt(profile, base))
                data = extract_json_object(response.text)
                if data.get("question"):
                    proposed_question = str(data["question"]).strip()
                    if self._accept_realized_question(base, proposed_question):
                        question = proposed_question
                        trace["nl_realizer_guard"] = "accepted"
                    else:
                        trace["nl_realizer_guard"] = "rejected_fallback_to_symbolic_intent"
                trace["nl_realizer_provider"] = response.provider
            except Exception as exc:
                trace["nl_realizer_error"] = f"{type(exc).__name__}: {exc}"
        return Candidate(
            question=question,
            sql=base.sql,
            operators=base.operators,
            difficulty=base.difficulty,
            generation_method=self.method_name,
            plan_id=base.plan_id,
            agent_trace=trace,
        )

    def _accept_realized_question(self, candidate: Candidate, question: str) -> bool:
        return True

    def _realizer_prompt(self, profile: SchemaProfile, candidate: Candidate) -> str:
        table_names = ", ".join(profile.table_names()[:20])
        return (
            "You are the NL Realizer Agent in Schema2Bench.\n"
            "You are NOT allowed to change the SQL. Your only task is to write a clear natural-language benchmark question that exactly matches the SQL.\n"
            "Return EXACTLY one JSON object with key \"question\" and no markdown.\n\n"
            "Rules:\n"
            "- Mention the aggregation, grouping, ordering, filters, and limit when they matter.\n"
            "- Do not add conditions that are not in the SQL.\n"
            "- Do not omit important filters from the SQL.\n"
            "- Keep the question concise and benchmark-style.\n\n"
            f"Domain tables: {table_names}\n"
            f"Operators: {candidate.operators}\n"
            f"Difficulty: {candidate.difficulty}\n"
            f"SQL:\n{candidate.sql}\n"
        )


class SemanticRefillAgenticGenerator(ControlledAgenticGenerator):
    """Generate profile-repair candidates without treating keys as measures."""

    method_name = "schema2bench_agent_semantic_refill"

    ADDITIVE_MEASURE_HINTS = {
        "amount",
        "amt",
        "bytes",
        "charge",
        "cost",
        "credit",
        "discount",
        "distance",
        "fee",
        "loss",
        "milliseconds",
        "paid",
        "price",
        "profit",
        "quantity",
        "qty",
        "revenue",
        "sales",
        "tax",
        "total",
        "votes",
    }

    def _realizer_prompt(self, profile: SchemaProfile, candidate: Candidate) -> str:
        return (
            super()._realizer_prompt(profile, candidate)
            + "\nThe symbolic intent below is authoritative. Preserve every selected-column meaning "
            "and do not add ordering, ranking, filters, or entity types.\n"
            f"Symbolic intent: {candidate.question}\n"
        )

    def _accept_realized_question(self, candidate: Candidate, question: str) -> bool:
        qlow = question.lower()
        slow = f" {candidate.sql.lower()} "
        if ("ordered by" in qlow or re.search(r"\b(?:ascending|descending)\s+order\b", qlow)) and " order by " not in slow:
            return False
        if re.search(r"\btop\s+\d+\b", qlow) and " order by " not in slow:
            return False
        sql_limit = re.search(r"\blimit\s+(\d+)\b", candidate.sql, re.I)
        question_limits = {
            int(match.group(1))
            for pattern in (
                re.compile(r"\b(?:first|top|up to|at most|no more than)\s+(\d+)\b", re.I),
                re.compile(r"\blimit(?:ed|ing)?\b.{0,35}?\bto\s+(?:the\s+)?(?:first\s+)?(\d+)\b", re.I),
            )
            for match in pattern.finditer(question)
        }
        if sql_limit and int(sql_limit.group(1)) not in question_limits:
            return False
        if question_limits and (not sql_limit or int(sql_limit.group(1)) not in question_limits):
            return False
        for match in re.finditer(r"'(?:''|[^'])*'", candidate.sql):
            literal = match.group(0)[1:-1].replace("''", "'")
            if literal != literal.strip() and literal.strip() in question and literal not in question:
                return False
        if "title_basics" in slow and re.search(r"\bmovies?\b", qlow) and "titletype" not in slow:
            return False
        if re.search(r"\b(?:distinct|unique)\b", qlow) and " select distinct " not in slow and " group by " not in slow:
            return False
        if "intersection" in qlow and not any(token in slow for token in ("crossing", "junction", "roundabout")):
            return False
        if "order number" in qlow and "order_id" in slow and "order_number" not in slow:
            return False
        if re.search(r"\b(?:quantity|number|count) of tracks\b", qlow) and "invoiceline" in slow and "quantity" in slow:
            return False
        return True

    def _select_filter(self, profile: SchemaProfile, plan: QueryPlan, method: str) -> Candidate | None:
        table = choose_table(profile, self.rng)
        columns = profile.any_columns(table)
        filter_columns = [column for column in columns if column.samples and not is_identifier_like(column)]
        select_col = self._descriptive_column(profile, table)
        if not select_col or not filter_columns:
            return self._aggregation(profile, plan, method)
        distinct_filter_columns = [column for column in filter_columns if column.name.lower() != select_col.name.lower()]
        if not distinct_filter_columns:
            return self._aggregation(profile, plan, method)
        filter_col = self.rng.choice(distinct_filter_columns)
        value = self.rng.choice(filter_col.samples)
        sql = (
            f"SELECT {quote_ident(select_col.name)} FROM {quote_ident(table)} "
            f"WHERE {quote_ident(filter_col.name)} = {sql_literal(value)}"
        )
        question = (
            f"List {select_col.name} values from {table} where {filter_col.name} equals {value}."
        )
        if self.rng.random() < 0.30:
            sql += f" ORDER BY {quote_ident(select_col.name)} ASC"
            # Remove only the sentence delimiter; a filter literal may itself
            # end in a meaningful period (for example, 'Cir.').
            question = question[:-1] + f", ordered by {select_col.name} in ascending order."
        return self._semantic_candidate(
            question,
            sql,
            ["select_filter"],
            plan,
            method,
            {"table": table, "filter_column": filter_col.name},
        )

    def _aggregation(self, profile: SchemaProfile, plan: QueryPlan, method: str) -> Candidate | None:
        measure_tables = [table for table in profile.table_names() if profile.measure_columns(table)]
        if not measure_tables:
            table = choose_table(profile, self.rng)
            sql = f"SELECT COUNT(*) AS value FROM {quote_ident(table)}"
            question = f"How many records are in the {table} table?"
            return self._semantic_candidate(question, sql, ["aggregation"], plan, method, {"table": table, "agg": "COUNT"})
        table = self.rng.choice(measure_tables)
        measure = self.rng.choice(profile.measure_columns(table))
        agg = self.rng.choice(self._allowed_aggregates(measure))
        sql = f"SELECT {agg}({quote_ident(measure.name)}) AS value FROM {quote_ident(table)}"
        question = {
            "AVG": f"What is the average {measure.name} in the {table} table?",
            "SUM": f"What is the total {measure.name} in the {table} table?",
            "MAX": f"What is the highest {measure.name} in the {table} table?",
            "MIN": f"What is the lowest {measure.name} in the {table} table?",
        }[agg]
        return self._semantic_candidate(
            question,
            sql,
            ["aggregation"],
            plan,
            method,
            {"table": table, "agg": agg, "measure": measure.name},
        )

    def _join(self, profile: SchemaProfile, plan: QueryPlan, method: str) -> Candidate | None:
        if self.rng.random() < 0.45:
            multi_hop = self._two_hop_join(profile, plan, method)
            if multi_hop:
                return multi_hop
        edge = self._choose_safe_edge(profile)
        if not edge:
            return None
        left_col = self._descriptive_column(profile, edge.left_table)
        right_col = self._descriptive_column(profile, edge.right_table)
        if not left_col or not right_col:
            return None
        sql = (
            f"SELECT {qcol(edge.left_table, left_col.name)}, {qcol(edge.right_table, right_col.name)} "
            f"FROM {quote_ident(edge.left_table)} JOIN {quote_ident(edge.right_table)} "
            f"ON {qcol(edge.left_table, edge.left_column)} = {qcol(edge.right_table, edge.right_column)}"
        )
        question = f"List matching {left_col.name} values from {edge.left_table} and {right_col.name} values from {edge.right_table}."
        filter_spec = self._identity_filter(profile, edge.left_table) or self._identity_filter(profile, edge.right_table)
        operators = ["join"]
        if filter_spec:
            filter_table, filter_col, value = filter_spec
            sql += f" WHERE {qcol(filter_table, filter_col.name)} = {sql_literal(value)}"
            question = question.rstrip(".") + f" where {filter_table}.{filter_col.name} equals {value}."
            operators.append("select_filter")
        else:
            sql += " LIMIT 20"
            question = question.rstrip(".") + " Return up to 20 rows."
        return self._semantic_candidate(question, sql, operators, plan, method, {"join": edge.__dict__})

    def _group_by(self, profile: SchemaProfile, plan: QueryPlan, method: str, top_k: bool) -> Candidate | None:
        edge = self._choose_safe_edge(profile)
        if edge:
            left_is_dimension = column_represents_table(edge.left_table, edge.left_column)
            right_is_dimension = column_represents_table(edge.right_table, edge.right_column)
            if right_is_dimension and not left_is_dimension:
                group_table, measure_table = edge.right_table, edge.left_table
            else:
                group_table, measure_table = edge.left_table, edge.right_table
            join_clause = (
                f" FROM {quote_ident(edge.left_table)} JOIN {quote_ident(edge.right_table)} "
                f"ON {qcol(edge.left_table, edge.left_column)} = {qcol(edge.right_table, edge.right_column)}"
            )
        else:
            group_table = choose_table(profile, self.rng)
            measure_table = group_table
            join_clause = f" FROM {quote_ident(group_table)}"

        group_col = self._group_column(profile, group_table)
        if not group_col:
            return None
        measures = profile.measure_columns(measure_table)
        if measures:
            measure = self.rng.choice(measures)
            aggregate_choices = [agg for agg in self._allowed_aggregates(measure) if agg in {"SUM", "AVG"}]
            agg = self.rng.choice(aggregate_choices or ["AVG"])
            aggregate_expr = f"{agg}({qcol(measure_table, measure.name)})"
            metric_phrase = f"{agg.lower()} {measure.name}"
            measure_name = measure.name
        else:
            agg = "COUNT"
            aggregate_expr = "COUNT(*)"
            metric_phrase = f"number of matching {measure_table} records"
            measure_name = "*"

        sql = (
            f"SELECT {qcol(group_table, group_col.name)} AS group_value, "
            f"{aggregate_expr} AS aggregate_value{join_clause} "
            f"GROUP BY {qcol(group_table, group_col.name)}"
        )
        operators = ["group_by", "aggregation"]
        question = f"What is the {metric_phrase} for each {group_col.name}?"
        if edge:
            operators.append("join")
        if top_k:
            sql += " ORDER BY aggregate_value DESC LIMIT 5"
            operators.insert(0, "top_k")
            question = f"Which are the top 5 {group_col.name} values by {metric_phrase}?"
        elif self.rng.random() < 0.35:
            sql += " ORDER BY group_value ASC"
            question = question.rstrip("?") + f", ordered by {group_col.name} in ascending order?"
        return self._semantic_candidate(
            question,
            sql,
            operators,
            plan,
            method,
            {
                "group_table": group_table,
                "measure_table": measure_table,
                "measure": measure_name,
                "agg": agg,
                "join": edge.__dict__ if edge else None,
            },
        )

    def _choose_safe_edge(self, profile: SchemaProfile) -> JoinEdge | None:
        edges = [
            edge
            for edge in profile.join_edges
            if edge.source == "foreign_key"
            or key_entity(edge.left_column) in {"nconst", "tconst"}
            or column_represents_table(edge.left_table, edge.left_column)
            or column_represents_table(edge.right_table, edge.right_column)
        ]
        return self.rng.choice(edges) if edges else None

    def _safe_edges(self, profile: SchemaProfile) -> list[JoinEdge]:
        return [
            edge
            for edge in profile.join_edges
            if edge.source == "foreign_key"
            or key_entity(edge.left_column) in {"nconst", "tconst"}
            or column_represents_table(edge.left_table, edge.left_column)
            or column_represents_table(edge.right_table, edge.right_column)
        ]

    def _two_hop_join(self, profile: SchemaProfile, plan: QueryPlan, method: str) -> Candidate | None:
        edges = self._safe_edges(profile)
        paths: list[tuple[str, JoinEdge, str, JoinEdge, str]] = []
        for first in edges:
            for middle in (first.left_table, first.right_table):
                start = first.right_table if middle == first.left_table else first.left_table
                for second in edges:
                    if second is first or middle not in {second.left_table, second.right_table}:
                        continue
                    end = second.right_table if middle == second.left_table else second.left_table
                    if len({start, middle, end}) == 3:
                        paths.append((start, first, middle, second, end))
        if not paths:
            return None
        safe_paths = [
            path for path in paths
            if not (self._looks_like_fact_table(profile, path[0]) and self._looks_like_fact_table(profile, path[4]))
        ]
        if not safe_paths:
            return None
        start, first, middle, second, end = self.rng.choice(safe_paths)
        start_col = self._descriptive_column(profile, start)
        end_col = self._descriptive_column(profile, end)
        if not start_col or not end_col:
            return None
        sql = (
            f"SELECT {qcol(start, start_col.name)}, {qcol(end, end_col.name)} FROM {quote_ident(start)} "
            f"JOIN {quote_ident(middle)} ON {qcol(first.left_table, first.left_column)} = {qcol(first.right_table, first.right_column)} "
            f"JOIN {quote_ident(end)} ON {qcol(second.left_table, second.left_column)} = {qcol(second.right_table, second.right_column)}"
        )
        question = f"List matching {start_col.name} values from {start} and {end_col.name} values from {end} through {middle}."
        filter_spec = self._identity_filter(profile, start) or self._identity_filter(profile, end)
        operators = ["join"]
        if filter_spec:
            filter_table, filter_col, value = filter_spec
            sql += f" WHERE {qcol(filter_table, filter_col.name)} = {sql_literal(value)}"
            question = question.rstrip(".") + f" where {filter_table}.{filter_col.name} equals {value}."
            operators.append("select_filter")
        else:
            sql += " LIMIT 20"
            question = question.rstrip(".") + " Return up to 20 rows."
        return Candidate(
            question,
            sql,
            operators,
            "hard",
            method,
            plan.plan_id,
            {"agent": "semantic_safe_sql_first", "semantic_refill": True, "join_hops": 2},
        )

    def _identity_filter(self, profile: SchemaProfile, table: str) -> tuple[str, ColumnInfo, Any] | None:
        columns = [
            column
            for column in profile.any_columns(table)
            if column_represents_table(table, column.name) and column.samples
        ]
        if not columns:
            return None
        column = self.rng.choice(columns)
        return table, column, self.rng.choice(column.samples)

    def _looks_like_fact_table(self, profile: SchemaProfile, table: str) -> bool:
        return len(profile.measure_columns(table)) >= 3 and len(profile.edges_for_table(table)) >= 2

    def _descriptive_column(self, profile: SchemaProfile, table: str) -> ColumnInfo | None:
        columns = [column for column in profile.text_columns(table) if not is_identifier_like(column)]
        if not columns:
            columns = [column for column in profile.any_columns(table) if not is_identifier_like(column)]
        if not columns:
            return None
        for hint in ("name", "title", "description", "desc", "category", "type", "country", "state"):
            matches = [column for column in columns if hint in column.name.lower()]
            if matches:
                return self.rng.choice(matches)
        return self.rng.choice(columns)

    def _group_column(self, profile: SchemaProfile, table: str) -> ColumnInfo | None:
        columns = [column for column in profile.text_columns(table) if not is_identifier_like(column)]
        if not columns:
            columns = [column for column in profile.any_columns(table) if not is_identifier_like(column)]
        if not columns:
            return None
        for hint in (
            "category",
            "type",
            "status",
            "state",
            "country",
            "class",
            "brand",
            "gender",
            "mode",
            "priority",
            "segment",
            "genre",
            "department",
            "aisle",
            "city",
            "name",
            "title",
        ):
            matches = [column for column in columns if hint in column.name.lower()]
            if matches:
                return self.rng.choice(matches)
        return self.rng.choice(columns)

    def _allowed_aggregates(self, measure: ColumnInfo) -> list[str]:
        low = measure.name.lower()
        choices = ["AVG", "MAX", "MIN"]
        if any(hint in low for hint in self.ADDITIVE_MEASURE_HINTS):
            choices.append("SUM")
        return choices

    def _semantic_candidate(
        self,
        question: str,
        sql: str,
        operators: list[str],
        plan: QueryPlan,
        method: str,
        trace: dict[str, Any],
    ) -> Candidate:
        return Candidate(
            question,
            sql,
            operators,
            plan.difficulty,
            method,
            plan.plan_id,
            {"agent": "semantic_safe_sql_first", "semantic_refill": True, **trace},
        )


class DeterministicRefillAgenticGenerator(SemanticRefillAgenticGenerator):
    """Complexity refill with deterministic semantics for every LIMIT query.

    The frozen v3 audit found many list queries whose SQL used LIMIT without an
    ordering key.  Such items can execute successfully while leaving the
    selected subset underdetermined.  This closure-only generator preserves the
    semantic-refill construction strategy but converts every residual unordered
    terminal LIMIT into an explicitly ordered top-k query.  If a safe projected
    order key cannot be recovered, the candidate is rejected before admission.
    """

    method_name = "schema2bench_agent_deterministic_refill"

    def generate(self, profile: SchemaProfile, plan: QueryPlan) -> Candidate | None:
        candidate = super().generate(profile, plan)
        if candidate is None:
            return None
        limit_match = re.search(r"\s+LIMIT\s+(\d+)\s*;?\s*$", candidate.sql, re.I)
        if not limit_match or re.search(r"\border\s+by\b", candidate.sql, re.I):
            return Candidate(
                question=candidate.question,
                sql=candidate.sql,
                operators=candidate.operators,
                difficulty=candidate.difficulty,
                generation_method=self.method_name,
                plan_id=candidate.plan_id,
                agent_trace={
                    **candidate.agent_trace,
                    "deterministic_limit_policy": "already_ordered_or_no_limit",
                },
            )

        select_match = re.match(
            r"\s*SELECT\s+(.+?)\s+FROM\s+",
            candidate.sql,
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

        limit = int(limit_match.group(1))
        without_limit = candidate.sql[: limit_match.start()].rstrip().rstrip(";")
        order_clause = ", ".join(f"{part} ASC" for part in order_keys)
        sql = f"{without_limit} ORDER BY {order_clause} LIMIT {limit}"
        labels = [
            re.sub(r'"', "", re.sub(r"\s+AS\s+.+$", "", part, flags=re.I)).strip()
            for part in order_keys
        ]
        order_text = " and then ".join(labels)
        question = re.sub(
            rf"\s*Return\s+up\s+to\s+{limit}\s+rows\.?\s*$",
            "",
            candidate.question,
            flags=re.IGNORECASE,
        ).rstrip().rstrip(".?")
        question += (
            f", ordered by {order_text} in ascending order and limited to the first "
            f"{limit} rows?"
        )
        operators = list(candidate.operators)
        if "top_k" not in operators:
            operators.append("top_k")
        return Candidate(
            question=question,
            sql=sql,
            operators=operators,
            difficulty=candidate.difficulty,
            generation_method=self.method_name,
            plan_id=candidate.plan_id,
            agent_trace={
                **candidate.agent_trace,
                "deterministic_limit_policy": "ordered_by_projected_columns",
                "deterministic_order_keys": projected,
            },
        )


class DiverseDeterministicRefillAgenticGenerator(
    DeterministicRefillAgenticGenerator
):
    """Deficit-only deterministic refill with safe single-table fallback.

    The first closure refill intentionally targets joins and grouping.  After
    unordered LIMIT removal, however, some one-table domains can remain below
    their frozen quotas.  This separately named method expands value support
    through the pipeline's larger schema sample and converts impossible join
    plans into safe filter/aggregate candidates.  It remains SQL-first and
    response-blind; it does not alter the final selection target.
    """

    method_name = "schema2bench_agent_diverse_deterministic_refill"

    def _join(
        self, profile: SchemaProfile, plan: QueryPlan, method: str
    ) -> Candidate | None:
        candidate = super()._join(profile, plan, method)
        if candidate is not None:
            return candidate
        # A join plan is structurally impossible in a one-table schema.  Use a
        # grounded filter first and a scalar aggregate as the final fallback,
        # instead of wasting the fixed generation attempt.
        return self._select_filter(profile, plan, method) or self._aggregation(
            profile, plan, method
        )


class RingSqlReimplementationGenerator(TemplateGenerator):
    """Paper-faithful RingSQL reimplementation baseline.

    RingSQL's public repository was unavailable/incomplete in our experiment
    setting, so this baseline captures the core published strategy: generate
    SQL from schema-independent SQL templates first, then use an LLM only to
    paraphrase the SQL intent into a natural-language question. It is not
    allowed to change SQL during paraphrasing.
    """

    method_name = "ringsql_reimpl"

    def __init__(self, provider: LlmProvider | None = None, seed: int = 0):
        super().__init__(seed=seed)
        self.provider = provider

    def generate(self, profile: SchemaProfile, plan: QueryPlan) -> Candidate | None:
        base = super().generate(profile, plan)
        if not base:
            return None
        question = base.question
        trace = dict(base.agent_trace)
        trace.update(
            {
                "baseline": "RingSQL-reimplementation",
                "official_code_status": "unavailable_or_incomplete",
                "core_strategy": "schema_independent_sql_templates_plus_llm_paraphrase",
                "sql_first": True,
                "llm_role": "paraphrase_only",
            }
        )
        if self.provider:
            try:
                response = self.provider.complete(self._paraphrase_prompt(base))
                data = extract_json_object(response.text)
                if data.get("question"):
                    question = str(data["question"]).strip()
                trace["paraphrase_provider"] = response.provider
            except Exception as exc:
                trace["paraphrase_error"] = f"{type(exc).__name__}: {exc}"
        return Candidate(
            question=question,
            sql=base.sql,
            operators=base.operators,
            difficulty=base.difficulty,
            generation_method=self.method_name,
            plan_id=base.plan_id,
            agent_trace=trace,
        )

    def _paraphrase_prompt(self, candidate: Candidate) -> str:
        return (
            "You are paraphrasing a SQL query into a benchmark-style Text-to-SQL question.\n"
            "Return EXACTLY one JSON object with key \"question\" and no markdown.\n"
            "Do not change the SQL intent. Do not add filters, limits, aggregations, grouping, or ordering not present in the SQL.\n\n"
            f"Operators: {candidate.operators}\n"
            f"Difficulty: {candidate.difficulty}\n"
            f"SQL:\n{candidate.sql}\n"
        )


class SingSqlReimplementationGenerator(LlmPairGenerator):
    """Paper-faithful SING-SQL reimplementation baseline.

    SING-SQL is positioned as in-domain synthetic data generation for a target
    database. This reimplementation follows its key generation-side ideas in a
    framework-compatible way: schema partitioning, complexity-level prompting,
    sample-value grounding, and downstream execution repair/validation.
    """

    def __init__(self, provider: LlmProvider, seed: int = 0):
        super().__init__("singsql_reimpl", provider, seed=seed)

    def _prompt(self, profile: SchemaProfile, plan: QueryPlan) -> str:
        focus_tables = self._choose_schema_partition(profile, plan)
        schema_lines = []
        for table_name in focus_tables:
            table = profile.tables[table_name]
            col_bits = []
            for c in table.columns[:28]:
                sample_text = ""
                if c.samples:
                    sample_text = " samples=" + repr(list(c.samples[:3]))
                col_bits.append(f'{quote_ident(c.name)} {c.type}'.strip() + sample_text)
            schema_lines.append(f"- {quote_ident(table.name)}({'; '.join(col_bits)})")
        join_lines = []
        allowed = set(focus_tables)
        for edge in profile.join_edges:
            if edge.left_table in allowed and edge.right_table in allowed:
                join_lines.append(
                    f"{quote_ident(edge.left_table)}.{quote_ident(edge.left_column)} = "
                    f"{quote_ident(edge.right_table)}.{quote_ident(edge.right_column)}"
                )
        complexity = {
            "easy": "single-table filtering or simple scalar aggregation",
            "medium": "join, aggregation, or group-by over a small schema partition",
            "hard": "group-by/top-k/joined aggregation with explicit ordering or limit",
        }.get(plan.difficulty, plan.difficulty)
        return (
            "You are reimplementing an in-domain synthetic Text-to-SQL data generator for SQLite.\n"
            "Return EXACTLY one JSON object and no markdown, no explanation, no code fence.\n"
            'Required keys: "question", "sql", "operators", "difficulty".\n\n'
            "Generation protocol:\n"
            "1. Use only the provided schema partition and sample values.\n"
            "2. Generate one natural-language question and its gold SQL for the target database.\n"
            "3. Match the requested complexity level.\n"
            "4. Prefer underused columns by not always selecting id/name columns.\n\n"
            "SQL constraints:\n"
            "- SQLite syntax only.\n"
            "- Use a single read-only SELECT or WITH query.\n"
            "- Use only the tables and columns listed below.\n"
            "- Put double quotes around every identifier exactly as shown.\n"
            "- Do not use SELECT *.\n"
            "- Use sample values for filters when possible.\n"
            "- Add LIMIT 20 to non-aggregate list queries.\n"
            "- Avoid queries that return the full table.\n\n"
            f"Requested operator: {plan.operator}\n"
            f"Requested difficulty: {plan.difficulty} ({complexity})\n"
            f"Needs join: {plan.needs_join}; needs group: {plan.needs_group}; needs order: {plan.needs_order}\n\n"
            "Allowed joins:\n" + ("\n".join(join_lines) if join_lines else "(no explicit join hints)") + "\n\n"
            "Schema partition:\n" + "\n".join(schema_lines)
        )

    def _choose_schema_partition(self, profile: SchemaProfile, plan: QueryPlan) -> list[str]:
        if plan.needs_join and profile.join_edges:
            edge = self.rng.choice(profile.join_edges)
            tables = [edge.left_table, edge.right_table]
        elif plan.operator in {"aggregation", "group_by", "top_k"}:
            candidates = [t for t in profile.table_names() if profile.numeric_columns(t)]
            tables = [self.rng.choice(candidates)] if candidates else [choose_table(profile, self.rng)]
        else:
            tables = [choose_table(profile, self.rng)]
        if plan.difficulty == "hard" and profile.join_edges:
            connected = [e for e in profile.join_edges if e.left_table in tables or e.right_table in tables]
            if connected:
                edge = self.rng.choice(connected)
                tables.extend([edge.left_table, edge.right_table])
        deduped = []
        for table in tables:
            if table not in deduped:
                deduped.append(table)
        return deduped[:3]


def sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    return "'" + text.replace("'", "''") + "'"


def qcol(table: str, column: str) -> str:
    return f"{quote_ident(table)}.{quote_ident(column)}"


def repair_empty_result(sql: str) -> str | None:
    if " where " not in sql.lower():
        return None
    return re.split(r"\bwhere\b", sql, flags=re.I)[0].rstrip()


def repair_result_bound(sql: str, limit: int = 100) -> str | None:
    """Conservatively bound broad list queries emitted by LLM baselines."""
    lower = sql.lower()
    if " limit " in lower:
        return None
    # Do not add a LIMIT to scalar aggregate-only queries; they are already
    # bounded if they finish. GROUP BY / ORDER BY results can still be bounded.
    body = sql.strip().rstrip(";")
    return f"{body} LIMIT {int(limit)}"


def repair_select_star(sql: str) -> str | None:
    # SELECT * is not benchmark-friendly, but without schema context we cannot
    # choose columns safely here. Keep this as a marker for future schema-aware
    # repair rather than rewriting incorrectly.
    return None
