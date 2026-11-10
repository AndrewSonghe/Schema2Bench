"""CPU-only result contracts. No model, network, or historical writes."""
import math
import re
import sqlite3
import sys
import time
from collections import Counter
from fractions import Fraction
from pathlib import Path

import sqlglot
from sqlglot import exp

FORBIDDEN = {'random', 'rand', 'randomblob', 'changes', 'total_changes',
             'last_insert_rowid', 'load_extension', 'readfile', 'writefile'}


def atom(v, rounded=False):
    if v is None:
        return ('null',)
    if type(v) is int:
        return ('number', Fraction(v))
    if type(v) is float:
        if not math.isfinite(v):
            raise ValueError('NONFINITE_NUMERIC')
        return ('number', Fraction.from_float(round(v, 8) if rounded else v))
    if type(v) is str:
        return ('text', v)
    if isinstance(v, dict) and set(v) == {'blob_hex'}:
        return ('blob', bytes.fromhex(v['blob_hex']))
    raise ValueError('UNSUPPORTED_CELL')


def rows(values, rounded=False):
    return [tuple(atom(v, rounded) for v in row) for row in values]


def parse_query(sql):
    parsed = [x for x in sqlglot.parse(sql, read='sqlite') if x is not None]
    if len(parsed) != 1 or not isinstance(parsed[0], exp.Query):
        raise ValueError('NOT_ONE_QUERY')
    tree = parsed[0]
    if any(isinstance(n, (exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop))
           for n in tree.walk()):
        raise ValueError('MUTATING_QUERY')
    for n in tree.find_all(exp.Func):
        if n.sql_name().lower() in FORBIDDEN or getattr(n, 'name', '').lower() in FORBIDDEN:
            raise ValueError('NONDETERMINISTIC_OR_EXTERNAL_FUNCTION')
        if n.sql_name().lower().startswith('current'):
            raise ValueError('CURRENT_TIME_FUNCTION')
        if n.sql_name().lower() in {'date', 'time', 'datetime', 'strftime', 'julianday', 'unixepoch'}:
            if any(isinstance(x, exp.Literal) and x.is_string and x.this.lower() in {'now', 'localtime', 'utc'} for x in n.walk()):
                raise ValueError('CURRENT_TIME_FUNCTION')
    return tree


def expr_key(x):
    x = x.this if isinstance(x, exp.Alias) else x
    return x.sql(dialect='sqlite', normalize=True).lower()


def order_contract(sql):
    try:
        tree = parse_query(sql)
    except Exception as e:
        return {'kind': 'unresolved', 'reason': 'GOLD_AST:' + type(e).__name__}
    ordering = tree.args.get('order')
    limit = tree.args.get('limit')
    if ordering is None:
        return {'kind': 'unresolved', 'reason': 'LIMIT_WITHOUT_ORDER'} if limit is not None else {'kind': 'bag'}
    selected = list(tree.selects)
    indexes = []
    for term in ordering.expressions:
        key = term.this
        index = None
        if isinstance(key, exp.Literal) and key.is_int:
            position = int(key.this) - 1
            if 0 <= position < len(selected):
                index = position
        else:
            matches = []
            for i, projected in enumerate(selected):
                alias = projected.alias
                base = projected.this if isinstance(projected, exp.Alias) else projected
                equal = expr_key(base) == expr_key(key)
                if isinstance(key, exp.Column):
                    equal = equal or (bool(alias) and not key.table and alias.lower() == key.name.lower())
                    equal = equal or (isinstance(base, exp.Column) and not key.table and base.name.lower() == key.name.lower())
                if equal:
                    matches.append(i)
            if len(matches) == 1:
                index = matches[0]
        if index is None:
            return {'kind': 'ordered_unknown', 'reason': 'ORDER_KEY_NOT_PROJECTED', 'has_limit': limit is not None}
        indexes.append(index)
    result = {'kind': 'ordered', 'keys': indexes, 'projection_width': len(selected), 'has_limit': limit is not None}
    # Only a top-level projection wildcard changes the output-column count.
    # A star nested inside COUNT(*) or another expression is not a projection.
    def is_projection_wildcard(s):
        s = s.this if isinstance(s, exp.Alias) else s
        return isinstance(s, exp.Star) or (isinstance(s, exp.Column) and isinstance(s.this, exp.Star))
    if any(is_projection_wildcard(s) for s in selected):
        return {'kind': 'ordered_unknown', 'reason': 'STAR_PROJECTION', 'has_limit': limit is not None}
    if limit is None or set(indexes) == set(range(len(selected))):
        return result
    try:
        n = limit.expression
        offset_node = tree.args.get('offset')
        offset = offset_node.expression if offset_node is not None else exp.Literal.number(0)
        if not isinstance(n, exp.Literal) or not n.is_int or not isinstance(offset, exp.Literal) or not offset.is_int:
            raise ValueError('NONLITERAL_LIMIT')
        count, start = int(n.this), int(offset.this)
        if count < 0 or start < 0 or count > 1000:
            raise ValueError('UNSUPPORTED_LIMIT')
        shift = int(start > 0)
        probe = tree.copy()
        probe.set('limit', exp.Limit(expression=exp.Literal.number(count + 1 + shift)))
        if offset_node is not None:
            probe.set('offset', exp.Offset(expression=exp.Literal.number(max(0, start - 1))))
        result.update(probe_sql=probe.sql(dialect='sqlite'), probe_cap=count + 1 + shift, probe_shift=shift)
    except Exception as e:
        result['boundary_unresolved'] = type(e).__name__
    return result


def encode(v):
    return {'blob_hex': v.hex()} if isinstance(v, bytes) else v


def execute(db, sql, timeout=30, cap=1000, allowed=()):
    path = Path(db).resolve()
    if path not in {Path(x).resolve() for x in allowed}:
        raise ValueError('DB_NOT_ALLOWLISTED')
    started = time.monotonic()
    if not path.is_file():
        return {'status': 'MISSING_DB', 'seconds': 0, 'rows': []}
    wal = Path(str(path) + '-wal')
    if Path(str(path) + '-journal').exists() or (wal.exists() and wal.stat().st_size != 0):
        return {'status': 'SIDECAR_UNRESOLVED', 'seconds': 0, 'rows': []}
    if not re.match(r'\s*(?:SELECT|WITH)\b', sql, re.I):
        return {'status': 'INVALID_SQL', 'seconds': 0, 'rows': []}
    try:
        parse_query(sql)
    except Exception as exc:
        return {'status': 'AST_REJECTED', 'seconds': time.monotonic()-started, 'rows': [], 'error': str(exc)[:180]}
    conn = sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True, timeout=1)
    conn.execute('PRAGMA query_only=ON')
    conn.execute('PRAGMA cache_size=-8192')
    conn.execute('PRAGMA temp_store=FILE')
    deadline = started + timeout
    conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
    allowed_actions = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}
    def authorize(action, a, b, _db, _trigger):
        if action not in allowed_actions:
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_FUNCTION and str(b).lower() in FORBIDDEN:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    conn.set_authorizer(authorize)
    try:
        cur = conn.execute(sql)
        raw = cur.fetchmany(cap + 1)
        status = 'COMPLETE' if len(raw) <= cap else 'ROW_CAP'
        result = {'status': status, 'rows': [[encode(v) for v in row] for row in raw[:cap]],
                  'columns': [d[0] for d in (cur.description or [])]}
    except sqlite3.Error as exc:
        status = 'TIMEOUT' if time.monotonic() >= deadline else 'SQL_ERROR'
        result = {'status': status, 'rows': [], 'error': str(exc)[:220]}
    finally:
        conn.close()
    result['seconds'] = time.monotonic() - started
    return result


def boundary_ambiguous(contract, gold, probe, rounded=False):
    if contract.get('boundary_unresolved'):
        return True
    if 'probe_sql' not in contract:
        return False
    if probe is None or probe['status'] != 'COMPLETE':
        return True
    gold_rows, probe_rows = rows(gold['rows'], rounded), rows(probe['rows'], rounded)
    if not gold_rows:
        return False
    keys = contract['keys']
    key = lambda r: tuple(r[i] for i in keys)
    shift = contract['probe_shift']
    if shift and len(probe_rows) >= 2 and key(probe_rows[0]) == key(probe_rows[1]) and probe_rows[0] != probe_rows[1]:
        return True
    end = shift + len(gold_rows)
    return (end < len(probe_rows) and key(probe_rows[end-1]) == key(probe_rows[end])
            and probe_rows[end-1] != probe_rows[end])


def compare(contract, gold, pred, probe=None, rounded=False):
    result = {'lower': 0, 'upper': 1, 'reason': 'UNRESOLVED', 'bag': None, 'sequence': None}
    if gold['status'] != 'COMPLETE':
        result['reason'] = 'GOLD_' + gold['status']
        return result
    if pred['status'] in {'INVALID_SQL', 'SQL_ERROR'}:
        result.update(upper=0, reason='PRED_' + pred['status'])
        return result
    if pred['status'] != 'COMPLETE':
        result['reason'] = 'PRED_' + pred['status']
        return result
    try:
        left, right = rows(gold['rows'], rounded), rows(pred['rows'], rounded)
        bag, sequence = Counter(left) == Counter(right), left == right
        result.update(bag=int(bag), sequence=int(sequence))
        kind = contract['kind']
        if kind == 'bag':
            answer = bag
        elif kind == 'unresolved':
            result['reason'] = contract['reason']
            return result
        elif kind == 'ordered_unknown':
            if sequence:
                answer = True
            elif not bag and not contract.get('has_limit'):
                answer = False
            else:
                result['reason'] = contract['reason']
                return result
        else:
            if any(len(r) != contract['projection_width'] for r in left + right):
                answer = False
            elif boundary_ambiguous(contract, gold, probe, rounded) and not sequence:
                result['reason'] = 'LIMIT_BOUNDARY_TIE_OR_PROBE_UNRESOLVED'
                return result
            else:
                keys = contract['keys']
                answer = bag and [tuple(r[i] for i in keys) for r in left] == [tuple(r[i] for i in keys) for r in right]
        result.update(lower=int(answer), upper=int(answer), reason='MATCH' if answer else 'MISMATCH')
    except (TypeError, ValueError, IndexError) as exc:
        result['reason'] = 'RESULT_TYPE_UNRESOLVED:' + type(exc).__name__
    return result
