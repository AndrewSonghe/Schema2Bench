"""Canonical value and ordering policy used by the paired construction."""
from dataclasses import replace
import re
from .generators import Candidate

def _projection_keys(sql):
    select = re.match(r"\s*SELECT\s+(.+?)\s+FROM\s+", sql, re.I | re.S)
    if not select:
        return None
    projected = [part.strip() for part in select.group(1).split(",")]
    if not 1 <= len(projected) <= 2:
        return None
    keys = [re.sub(r"\s+AS\s+[\w\"]+\s*$", "", part, flags=re.I).strip() for part in projected]
    # Only plain projected columns can be used as a portable, explicit tie rule.
    if any(not re.fullmatch(r'(?:"[^"]+"|[A-Za-z_]\w*)(?:\.(?:"[^"]+"|[A-Za-z_]\w*))?', key) for key in keys):
        return None
    return keys

def _ordered_question(question, keys, count, already_ordered):
    base = re.sub(rf"\s*Return\s+up\s+to\s+{count}\s+rows\.?(?:\s*)$", "", question, flags=re.I).rstrip()
    # Template values such as 'Cir.' produce 'Cir..': remove only the extra
    # sentence delimiter, never the period belonging to the SQL literal.
    if base.endswith(".."):
        base = base[:-1]
    if base.endswith("?"):
        base = base[:-1] + "."
    elif not base.endswith("."):
        base += "."
    if already_ordered:
        return base + f" Return the first {count} rows in that order."
    labels = [key.replace('"', '') for key in keys]
    return base + f" Return the first {count} rows ordered by {' and then '.join(labels)} ascending."

def canonical_candidate(candidate):
    """Apply the same bounded, explicit-value and order policy to both arms."""
    if candidate is None:
        return None
    sql, question = candidate.sql, candidate.question
    literals = [m.group(0)[1:-1].replace("''", "'") for m in re.finditer(r"'(?:''|[^'])*'", sql)]
    if any(not value or value != value.strip() or value not in question for value in literals):
        return None
    limit = re.search(r"\s+LIMIT\s+(\d+)\s*;?\s*$", sql, re.I)
    ordered = bool(re.search(r"\bORDER\s+BY\b", sql, re.I))
    keys = _projection_keys(sql)
    flags = []
    if limit and not ordered:
        if not keys:
            return None
        count = int(limit.group(1))
        sql = sql[:limit.start()].rstrip().rstrip(";") + " ORDER BY " + ", ".join(key + " ASC" for key in keys) + f" LIMIT {count}"
        question = _ordered_question(question, keys, count, False)
        flags.append("ordered_existing_limit")
    elif not limit and not re.search(r"\b(?:JOIN|GROUP\s+BY|HAVING|UNION|INTERSECT|EXCEPT|DISTINCT|OFFSET)\b|\b(?:COUNT|SUM|AVG|MIN|MAX)\s*\(", sql, re.I) and keys:
        # Restrict alignment to one-table, plain SELECT lists. Apply it to both
        # methods before verification or semantic judgments; do not rebalance
        # the pool using observed labels.
        sql = sql.rstrip().rstrip(";")
        if not ordered:
            sql += " ORDER BY " + ", ".join(key + " ASC" for key in keys)
        sql += " LIMIT 20"
        question = _ordered_question(question, keys, 20, ordered)
        flags.append("bounded_plain_list")
    if any(value not in question for value in literals):
        return None
    return Candidate(question, sql, list(candidate.operators), candidate.difficulty, candidate.generation_method, candidate.plan_id, {**candidate.agent_trace, "common_v5_policy": flags})
