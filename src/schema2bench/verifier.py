from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|create|attach|detach|pragma|vacuum|replace)\b", re.I)


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    executable: bool
    non_empty: bool
    row_count: int
    column_count: int
    elapsed_ms: float
    failure_type: str | None = None
    error: str | None = None
    result_preview: tuple[tuple[Any, ...], ...] = ()


class ExecutionVerifierAgent:
    def __init__(self, timeout_s: float = 30.0, row_limit: int = 1000, max_progress_steps: int = 250_000):
        self.timeout_s = timeout_s
        self.row_limit = row_limit
        self.max_progress_steps = max_progress_steps

    def verify(self, db_path: str | Path, sql: str) -> VerificationResult:
        start = time.perf_counter()
        safety = self._safety_failure(sql)
        if safety:
            return VerificationResult(False, False, False, 0, 0, 0.0, safety, safety)
        con = sqlite3.connect(Path(db_path))
        con.row_factory = sqlite3.Row
        steps = 0

        def progress() -> int:
            nonlocal steps
            steps += 1
            if steps > self.max_progress_steps or (time.perf_counter() - start) > self.timeout_s:
                return 1
            return 0

        try:
            con.execute("pragma query_only=on")
            con.set_progress_handler(progress, 100)
            cur = con.execute(sql)
            rows = cur.fetchmany(self.row_limit + 1)
            elapsed = (time.perf_counter() - start) * 1000
            col_count = len(cur.description or [])
            row_count = len(rows)
            if row_count > self.row_limit:
                return VerificationResult(False, True, True, row_count, col_count, elapsed, "result_too_large", f"result exceeds row limit {self.row_limit}")
            non_empty = row_count > 0
            ok = non_empty
            return VerificationResult(ok, True, non_empty, row_count, col_count, elapsed, None if ok else "empty_result", None, tuple(tuple(r) for r in rows[:5]))
        except sqlite3.OperationalError as exc:
            elapsed = (time.perf_counter() - start) * 1000
            msg = str(exc)
            failure = "timeout" if "interrupted" in msg.lower() else self._classify_error(msg)
            return VerificationResult(False, False, False, 0, 0, elapsed, failure, msg)
        except sqlite3.Error as exc:
            elapsed = (time.perf_counter() - start) * 1000
            msg = str(exc)
            return VerificationResult(False, False, False, 0, 0, elapsed, self._classify_error(msg), msg)
        finally:
            con.close()

    def _safety_failure(self, sql: str) -> str | None:
        stripped = sql.strip()
        if not stripped:
            return "empty_sql"
        if FORBIDDEN.search(stripped):
            return "unsafe_sql"
        if not re.match(r"^(select|with)\b", stripped, re.I):
            return "not_select"
        body = stripped[:-1] if stripped.endswith(";") else stripped
        if ";" in body:
            return "multi_statement"
        return None

    def _classify_error(self, msg: str) -> str:
        lower = msg.lower()
        if "no such table" in lower or "no such column" in lower:
            return "schema_error"
        if "ambiguous" in lower:
            return "schema_error"
        if "syntax" in lower:
            return "syntax_error"
        if "datatype" in lower or "mismatch" in lower:
            return "type_mismatch"
        return "execution_error"


def normalize_sql_signature(sql: str) -> str:
    sql = re.sub(r"\s+", " ", sql.strip().lower())
    sql = re.sub(r"\s*;\s*$", "", sql)
    return sql

