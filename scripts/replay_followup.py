"""Recompute the BEAVER context contrasts and uniform semantic sensitivity."""
from pathlib import Path
import collections
import gzip
import importlib.util
import json
import statistics

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'evaluation/followup'
spec = importlib.util.spec_from_file_location('main_replay', ROOT / 'replay/main/replay.py')
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)


def read(path):
    return json.loads(path.read_text())


def rows(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def check(actual, expected, context):
    if isinstance(expected, dict):
        assert set(actual) == set(expected), context
        for key in expected:
            check(actual[key], expected[key], context + '/' + key)
    elif isinstance(expected, (list, tuple)):
        assert len(actual) == len(expected), context
        for i, (left, right) in enumerate(zip(actual, expected)):
            check(left, right, context + '/' + str(i))
    elif isinstance(expected, (int, float)):
        assert abs(actual - expected) < 1e-10, (context, actual, expected)
    else:
        assert actual == expected, (context, actual, expected)


def matrix(records, models):
    order = {model: i for i, model in enumerate(models)}
    result = {}
    for row in records:
        item = result.setdefault(row['id'], {
            'id': row['id'], 'domain': row['domain'], 'arm': row['arm'],
            'base': [None] * 10, 'verified': [None] * 10})
        index = order[row['model']]
        assert item['domain'] == row['domain'] and item['arm'] == row['arm']
        assert item['base'][index] is None, 'duplicate model/item'
        for mode in ('base', 'verified'):
            assert row[mode] in ([0, 0], [0, 1], [1, 1]), 'invalid score'
            item[mode][index] = row[mode]
    for item in result.values():
        for mode in ('base', 'verified'):
            assert None not in item[mode], 'missing model/item'
    return list(result.values())


def unknown(items, mode):
    return sum(value[0] != value[1] for row in items for value in row[mode])


def beaver(context):
    folder = DATA / 'beaver' / context
    expected = read(folder / 'expected.json')
    items = matrix(rows(folder / 'scores.jsonl.gz'), expected['models'])
    source = [row for row in items if row['arm'] == 'source']
    assert len(source) == 1034
    arms = {key: [row for row in items if row['arm'] == key]
            for key in ('template', 'refill', 'ring', 'reference')}
    for key, items in arms.items():
        counts = expected['reference_counts'] if key == 'reference' else expected['domains']
        assert collections.Counter(row['domain'] for row in items) == counts
    domains = list(expected['domains'])
    result = {}
    for mode in ('base', 'verified'):
        src = rp.coordinates(source, mode)
        refs = {d: rp.vector_mean([x for x in arms['reference'] if x['domain'] == d], mode)
                for d in domains}
        coords = {k: rp.coordinates(arms[k], mode) for k in ('template', 'refill', 'ring')}
        domain_means = {k: {d: rp.vector_mean([x for x in arms[k] if x['domain'] == d], mode)
                            for d in domains} for k in coords}
        tables, direct, per_domain = {}, {}, {}
        for k in coords:
            gap = [rp.gap(refs[d], domain_means[k][d]) for d in domains]
            tables[k] = {'gap_domain_macro': [statistics.mean(v[j] for v in gap) for j in (0, 1)],
                         'tef_original_pooling': rp.tef(src, coords[k]),
                         'score_unknown': unknown(arms[k], mode)}
        for k in ('template', 'ring'):
            gap = [rp.gap_diff(refs[d], domain_means['refill'][d], domain_means[k][d]) for d in domains]
            direct[k] = {'gap_refill_minus': [statistics.mean(v[j] for v in gap) for j in (0, 1)],
                         'tef_refill_minus': rp.tef_diff(src, coords['refill'], coords[k])}
            per_domain[k] = {}
            for i, d in enumerate(domains):
                a = rp.coordinates([x for x in arms['refill'] if x['domain'] == d], mode)
                b = rp.coordinates([x for x in arms[k] if x['domain'] == d], mode)
                per_domain[k][d] = {'gap_refill_minus': gap[i], 'tef_refill_minus': rp.tef_diff(src, a, b)}
        result[mode] = {'tables': tables, 'direct': direct, 'per_domain': per_domain,
                        'reference_unknown': unknown(arms['reference'], mode),
                        'source_unknown': unknown(source, mode)}
    check(result, expected['results'], 'BEAVER/' + context)
    return result


def semantic():
    folder = DATA / 'semantic'
    expected = read(folder / 'expected.json')
    labels = rows(folder / 'labels.jsonl.gz')
    assert len(labels) == 480
    assert len({(x['kind'], x['id']) for x in labels}) == 480
    counts = {k: dict(collections.Counter(x['label'] for x in labels if x['kind'] == k))
              for k in ('original', 'rewrite', 'reference')}
    check(counts, expected['counts'], 'semantic/counts')
    # Reparse all available response texts; no API calls are made.
    by_blind = {x['blind_id']: x for x in labels}
    responses = rows(folder / 'responses.jsonl.gz')
    assert len(responses) == 479 and len({x['blind_id'] for x in responses}) == 479
    for response in responses:
        label = json.loads(response['output_text'])
        assert response['model'] == 'gpt-6.1-terra'
        item = by_blind[response['blind_id']]
        assert label['label'] == item['label'], response['blind_id']
        assert response['raw_sha256'] == item['raw_sha256']
    originals = {x['id']: x['label'] for x in labels if x['kind'] == 'original'}
    pairs = collections.Counter(originals[x['id'].removeprefix('refill_rewrite::')] + '|' + x['label']
                                for x in labels if x['kind'] == 'rewrite')
    check(dict(pairs), expected['original_rewrite_pair_labels'], 'semantic/paired_labels')
    main = ROOT / 'replay/main/matrices'
    members = read(main / 'memberships.json')
    core = {x['id']: x for x in rows(main / 'core.jsonl')}
    panels = {'refill': [core[i] for i in members['releases'][0]['refill']],
              'ring': rows(main / 'ring.jsonl'),
              'rewrite': rows(folder / 'rewrite_matrix.jsonl.gz')}
    source, references = rows(main / 'source.jsonl'), rows(main / 'reference.jsonl')
    assert len(source) == 1034 and len(references) == 906
    assert all(len(p) == 2000 for p in panels.values())
    flags = collections.defaultdict(set, {k: set(v) for k, v in read(folder / 'prior_flags.json').items()})
    mapping = {'original': 'refill', 'rewrite': 'rewrite', 'reference': 'reference'}
    for row in labels:
        if row['label'] != 'supported':
            flags[mapping[row['kind']]].add(row['id'])
    for k, panel in {**panels, 'reference': references}.items():
        assert flags[k] <= {x['id'] for x in panel}, 'flag outside original denominator'
    check({k: len(v) for k, v in flags.items()}, expected['risk_counts'], 'semantic/risk_counts')
    result = {}
    for mode in ('base', 'verified'):
        def relax(panel, key):
            return [dict(x, **{mode: [[0, 1] for _ in range(10)]}) if x['id'] in flags[key] else x for x in panel]
        refs = relax(references, 'reference')
        current = {k: relax(v, k) for k, v in panels.items()}
        domains = members['domains']
        rv = {d: rp.vector_mean([x for x in refs if x['domain'] == d], mode) for d in domains}
        means = {k: {d: rp.vector_mean([x for x in v if x['domain'] == d], mode) for d in domains}
                 for k, v in current.items()}
        src = rp.coordinates(source, mode)
        coords = {k: rp.coordinates(v, mode) for k, v in current.items()}
        result[mode] = {}
        for k in ('refill', 'ring'):
            gap = [rp.gap_diff(rv[d], means['rewrite'][d], means[k][d]) for d in domains]
            result[mode][k] = {'gap_rewrite_minus': [statistics.mean(v[j] for v in gap) for j in (0, 1)],
                               'tef_rewrite_minus': rp.tef_diff(src, coords['rewrite'], coords[k])}
    check(result, expected['results'], 'semantic/contrasts')
    return result


if __name__ == '__main__':
    for context in ('retrieved', 'sufficient'):
        result = beaver(context)
        print('BEAVER', context, json.dumps(result['verified']['direct']))
    result = semantic()
    print('Semantic sensitivity', json.dumps(result['verified']))
    print('FOLLOWUP_REPLAY_VERIFIED')
