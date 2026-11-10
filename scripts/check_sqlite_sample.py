"""Repeat 32 retained cache checks on user-supplied matching SQLite snapshots."""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json
import sqlite3
import time

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--database-root', type=Path, required=True)
args = parser.parse_args()
record = json.loads((root / 'evaluation/cache_check/queries.json').read_text())
paths = {}
for row in record['queries']:
    domain = row['database']
    if domain in paths:
        continue
    choices = [args.database_root / (domain + '.sqlite'), args.database_root / domain / (domain + '.sqlite')]
    paths[domain] = next((p for p in choices if p.is_file()), None)
    if paths[domain] is None:
        parser.error('Database not found: ' + domain)
    h = hashlib.sha256()
    with paths[domain].open('rb') as f:
        for chunk in iter(lambda: f.read(4194304), b''):
            h.update(chunk)
    if h.hexdigest() != row['database_sha256']:
        parser.error('Snapshot hash differs: ' + domain)

def atom(value):
    if isinstance(value, bytes):
        return ('blob', value.hex())
    if isinstance(value, dict) and set(value) == {'blob_hex'}:
        return ('blob', value['blob_hex'])
    return (type(value).__name__ if value is None or isinstance(value, str) else 'number', value)

def bag(rows):
    return Counter(tuple(atom(v) for v in row) for row in rows)

for row in record['queries']:
    path = paths[row['database']].resolve()
    with sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True, timeout=1) as db:
        db.execute('PRAGMA query_only=ON')
        start = time.monotonic()
        db.set_progress_handler(lambda: int(time.monotonic() - start > 30), 1000)
        cursor = db.execute(row['sql'])
        values = cursor.fetchmany(1001)
        assert len(values) <= 1000, row['query_key']
        assert len(cursor.description or []) == row['expected_columns'], row['query_key']
        assert bag(values) == bag(row['expected_rows']), row['query_key']
print('Matched 32 SQLite query results against the retained cache sample.')
