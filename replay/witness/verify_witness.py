"""Replay the saved 105-reference witness using only Python's standard library."""
from pathlib import Path
from itertools import combinations
from collections import Counter
import hashlib
import json

root = Path(__file__).resolve().parent
manifest = json.loads((root / 'MANIFEST.json').read_text())
for filename, expected in manifest['sha256'].items():
    assert hashlib.sha256((root / filename).read_bytes()).hexdigest() == expected, filename
data = json.loads((root / 'SCORES.json').read_text())
populations = data['populations']
models, domains = data['models'], data['domains']
flags = set(data['reference_risk_ids'])
assert len(flags) == 105
arrays, expected, index = {}, set(), {}
for name, rows in populations.items():
    index[name] = {row['id']: i for i, row in enumerate(rows)}
    assert len(index[name]) == len(rows)
    arrays[name] = [[pair[0] for pair in row['verified']] for row in rows]
    for row in rows:
        for j, pair in enumerate(row['verified']):
            assert pair in ([0, 0], [0, 1], [1, 1])
            if pair[0] != pair[1] or (name == 'reference' and row['id'] in flags):
                expected.add((name, row['id'], models[j]))
seen, assigned, changed = set(), Counter(), Counter()
for line in (root / 'ASSIGNMENT_06.jsonl').read_text().splitlines():
    cell = json.loads(line)
    name, item, model = (cell[k] for k in ('population', 'id', 'model'))
    key = (name, item, model)
    assert key in expected and key not in seen
    assert type(cell['value']) is int and cell['value'] in (0, 1)
    seen.add(key)
    i, j = index[name][item], models.index(model)
    before = populations[name][i]['verified'][j]
    arrays[name][i][j] = cell['value']
    assigned[name] += 1
    if before[0] == before[1] and cell['value'] != before[0]:
        changed[name] += 1
assert seen == expected
for name, rows in populations.items():
    for i, row in enumerate(rows):
        for j, bounds in enumerate(row['verified']):
            if (name, row['id'], models[j]) not in expected:
                assert bounds[0] == bounds[1] == arrays[name][i][j]

def accuracy(name):
    result = {}
    for domain in domains:
        values = [values for row, values in zip(populations[name], arrays[name])
                  if row['domain'] == domain]
        assert values
        result[domain] = [sum(row[j] for row in values) / len(values) for j in range(len(models))]
    return result

reference = accuracy('reference')
pairs = list(combinations(range(len(models)), 2))
def gap(name):
    target = accuracy(name)
    return sum(abs((reference[d][i] - reference[d][j]) - (target[d][i] - target[d][j]))
               for d in domains for i, j in pairs) / (len(domains) * len(pairs))

rewritten, original = gap('rewrite'), gap('refill')
delta = rewritten - original
assert abs(delta - 0.00003788904233684103) < 1e-12
assert assigned == {'reference': 1050, 'rewrite': 53}
assert changed == {'reference': 561}
print(json.dumps({
    'status': 'PASS',
    'rewritten_gap': rewritten,
    'original_refill_gap': original,
    'direct_difference': delta,
    'assigned_cells': dict(assigned),
    'changed_recorded_definite_cells': dict(changed),
    'scope': 'Saved binary score-model witness; no new search or semantic adjudication.'
}, indent=2))
