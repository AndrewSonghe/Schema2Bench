"""Response-blind selection. This module never reads evaluator responses."""
from collections import Counter
from fractions import Fraction
import random
import hashlib

import numpy as np

from structural_features_frozen import feature_vector, OPERATOR_KEYS, DIFFICULTY_KEYS, SHAPE_KEYS


class Pool:
    def __init__(self, rows, profile):
        forbidden = {'responses', 'correct', 'predictions', 'model_outputs', 'response'}
        if any(forbidden.intersection(r) for r in rows):
            raise ValueError('RESPONSE_FIELDS_IN_SELECTOR_INPUT')
        self.rows = sorted(rows, key=lambda r: r['canonical_candidate_id'])
        self.ids = [r['canonical_candidate_id'] for r in self.rows]
        if len(set(self.ids)) != len(self.ids):
            raise ValueError('DUPLICATE_CANDIDATE_ID')
        self.index = {k: i for i, k in enumerate(self.ids)}
        self.groups = [(r['domain'], r['provenance_group']) for r in self.rows]
        self.group_names = sorted(set(self.groups))
        self.group_indices = {g: np.array([i for i, q in enumerate(self.groups) if q == g]) for g in self.group_names}
        self.X = np.array([sum((list(x) if isinstance(x, tuple) else [x] for x in feature_vector(r['sql'])), []) for r in self.rows], dtype=float)
        self.target = np.array([profile['operators'][k] for k in OPERATOR_KEYS] + [profile['difficulty'][k] for k in DIFFICULTY_KEYS] + [profile['shapes'][k] for k in SHAPE_KEYS])
        self.joins = float(profile['average_joins'])
        self.tokens = float(profile['average_tokens'])
        if min(self.joins, self.tokens) <= 0:
            raise ValueError('SOURCE_MEANS_MUST_BE_POSITIVE')

    def mask(self, ids):
        if len(set(ids)) != len(ids) or not set(ids) <= set(self.ids):
            raise ValueError('INVALID_RELEASE_IDS')
        out = np.zeros(len(self.ids), dtype=bool)
        out[[self.index[k] for k in ids]] = True
        return out

    def loss(self, totals, n):
        v = np.asarray(totals)
        return (np.abs(v[..., :5] / np.maximum(v[..., :5].sum(axis=-1, keepdims=True), 1) - self.target[:5]).sum(axis=-1) / 2
                + np.abs(v[..., 5:8] / n - self.target[5:8]).sum(axis=-1) / 2
                + np.abs(v[..., 8:14] / n - self.target[8:14]).sum(axis=-1) / 6
                + np.abs(v[..., 14] / n - self.joins) / self.joins
                + np.abs(v[..., 15] / n - self.tokens) / self.tokens) / 5

    def structural_loss(self, ids):
        return float(self.loss(self.X[self.mask(ids)].sum(axis=0), len(ids)))

    def quotas(self, ids):
        return Counter(self.groups[self.index[k]] for k in ids)

    def stability(self, anchor, selected):
        if self.quotas(anchor) != self.quotas(selected):
            raise ValueError('QUOTAS_CHANGED')
        nd = Counter(g[0] for g, n in self.quotas(anchor).items() for _ in range(n))
        removed = Counter(self.rows[self.index[k]]['domain'] for k in set(anchor) - set(selected))
        n, d = len(anchor), len(nd)
        return sum((Fraction(r, n) + Fraction(r, d * nd[k]) for k, r in removed.items()), Fraction())


def bounded_exchange(pool, anchor, tau='1/100', max_swaps=25, rule='cost_aware', tile=64):
    """Monotone original-anchor to original-complement swaps; exact H budget."""
    if rule not in {'cost_aware', 'absolute_gain', 'largest_domain'}:
        raise ValueError('UNKNOWN_RULE')
    tau = Fraction(tau)
    if tau < 0 or max_swaps < 0:
        raise ValueError('NEGATIVE_BUDGET')
    original = pool.mask(anchor)
    selected = original.copy()
    n = len(anchor)
    nd = Counter(pool.rows[i]['domain'] for i in np.flatnonzero(original))
    d = len(nd)
    largest = min(nd, key=lambda k: (-nd[k], k))
    costs = {k: Fraction(1, n) + Fraction(1, d * q) for k, q in nd.items()}
    totals = pool.X[selected].sum(axis=0)
    h, trace = Fraction(), []
    for step in range(max_swaps):
        current = float(pool.loss(totals, n))
        best = None
        for group in pool.group_names:
            domain = group[0]
            if domain not in costs or (rule == 'largest_domain' and domain != largest):
                continue
            cost = costs[domain]
            if h + cost > tau:
                continue
            idx = pool.group_indices[group]
            rem = idx[selected[idx] & original[idx]]
            add = idx[~selected[idx] & ~original[idx]]
            if not len(rem) or not len(add):
                continue
            group_best = None
            for start in range(0, len(rem), tile):
                rr = rem[start:start + tile]
                values = pool.loss(totals - pool.X[rr, None, :] + pool.X[add[None, :], :], n)
                a, b = np.unravel_index(np.argmin(values), values.shape)
                candidate = (float(values[a, b]), int(rr[a]), int(add[b]))
                if group_best is None or candidate < group_best:
                    group_best = candidate
            loss, removed, added = group_best
            gain = current - loss
            if gain <= 1e-12:
                continue
            rank = (-gain / float(cost), loss, removed, added) if rule == 'cost_aware' else (loss, removed, added)
            if best is None or rank < best[0]:
                best = (rank, removed, added, cost, loss)
        if best is None:
            break
        _, removed, added, cost, loss = best
        selected[removed], selected[added] = False, True
        totals += pool.X[added] - pool.X[removed]
        h += cost
        trace.append({'step': step + 1, 'domain': pool.rows[removed]['domain'], 'removed': pool.ids[removed], 'added': pool.ids[added], 'structural_loss': loss, 'H': str(h)})
    ids = [pool.ids[i] for i in np.flatnonzero(selected)]
    assert pool.quotas(ids) == pool.quotas(anchor)
    assert h == pool.stability(anchor, ids) and h <= tau
    assert pool.structural_loss(ids) <= pool.structural_loss(anchor) + 1e-12
    return {'ids': ids, 'trace': trace, 'H': str(h), 'swaps': len(trace), 'largest_domain': largest, 'structural_loss': pool.structural_loss(ids)}


def matched_random(pool, anchor, treatment, seed, draw):
    """Condition on response-free treatment allocation, never on its scores."""
    removed = set(anchor) - set(treatment)
    counts = pool.quotas(sorted(removed))
    anchor_set = set(anchor)
    out = set(anchor)
    rng = random.Random(int.from_bytes(hashlib.sha256(f'matched-random-v1|{seed}|{draw}'.encode()).digest()[:8], 'big'))
    for group, count in sorted(counts.items()):
        inside = [pool.ids[i] for i in pool.group_indices[group] if pool.ids[i] in anchor_set]
        outside = [pool.ids[i] for i in pool.group_indices[group] if pool.ids[i] not in anchor_set]
        out.difference_update(rng.sample(inside, count))
        out.update(rng.sample(outside, count))
    out = sorted(out)
    assert pool.stability(anchor, out) == pool.stability(anchor, treatment)
    return out
