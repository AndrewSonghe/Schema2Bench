"""Proportional quotas and deterministic quota-stratified anchors."""
import hashlib
import random

def quota_sizes(counts,n):
 total=sum(counts.values());base={k:(n*v)//total for k,v in counts.items()};remain=n-sum(base.values())
 order=sorted(counts,key=lambda k:(-((n*counts[k])%total),k))
 for k in order[:remain]:base[k]+=1
 if sum(base.values())!=n or any(base[k]>counts[k] for k in counts):raise ValueError('QUOTA_INFEASIBLE')
 return base

def anchor_for(pool,seed,per_domain):
 quotas={}
 for d in sorted({g[0] for g in pool.group_names}):
  sizes={g:len(pool.group_indices[g]) for g in pool.group_names if g[0]==d};quotas.update(quota_sizes(sizes,per_domain))
 seed_bytes=hashlib.sha256(('anchor|'+str(seed)).encode()).digest();rng=random.Random(int.from_bytes(seed_bytes[:8],'big'));selected=[]
 for group,count in sorted(quotas.items()):selected.extend(rng.sample([pool.ids[i] for i in pool.group_indices[group]],count))
 return sorted(selected),quotas
