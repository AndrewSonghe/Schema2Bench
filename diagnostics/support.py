#!/usr/bin/env python3
"""Bounded four-block support certificate. Never reads model responses."""
import argparse,collections,fractions,hashlib,json,pathlib,sys
import numpy as np
from scipy.optimize import Bounds,LinearConstraint,linprog,milp

def read(p):return json.loads(pathlib.Path(p).read_text())
def load(p):return [json.loads(x) for x in pathlib.Path(p).read_text().splitlines() if x.strip()]
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def solve(rows,profile,anchor,quota,tau,seconds):
 forbidden={'responses','response','correct','predictions','model_outputs'}
 if any(forbidden.intersection(x) for x in rows):raise ValueError('RESPONSE_FIELDS_FORBIDDEN')
 ids=[x['canonical_candidate_id'] for x in rows];lookup={x['canonical_candidate_id']:x for x in rows}
 if len(ids)!=len(set(ids)) or len(anchor)!=len(set(anchor)) or not set(anchor)<=set(ids):raise ValueError('BAD_IDENTITIES')
 n=len(anchor);groups=collections.Counter((lookup[x]['domain'],lookup[x]['provenance_group']) for x in anchor)
 q={(x['domain'],x['provenance_group']):int(x['count']) for x in quota}
 if not n or groups!=q or len(q)!=len(quota):raise ValueError('QUOTAS_NOT_EQUAL_TO_ANCHOR')
 ds=collections.Counter(lookup[x]['domain'] for x in anchor);d=len(ds);tau=fractions.Fraction(tau)
 if tau<0 or any(x['domain'] not in ds for x in rows):raise ValueError('INVALID_H_OR_DOMAIN')
 import structural_features_frozen as feat
 targets=[profile['difficulty'][k] for k in feat.DIFFICULTY_KEYS]+[profile['shapes'][k] for k in feat.SHAPE_KEYS]+[profile['average_joins'],profile['average_tokens']]
 if min(targets[-2:])<=0:raise ValueError('INVALID_SOURCE_MEANS')
 coeff=np.array([.1]*3+[1/30]*6+[.2/targets[-2],.2/targets[-1]])
 buckets=collections.defaultdict(list); aset=set(anchor)
 for x in rows:
  v=feat.feature_vector(x['sql']);flat=tuple(y for z in v for y in (z if isinstance(z,tuple) else (z,)))
  if len(flat)!=16:raise ValueError('FEATURE_VERSION_MISMATCH')
  buckets[(x['domain'],x['provenance_group'],flat[5:],x['canonical_candidate_id'] in aset)].append(x['canonical_candidate_id'])
 keys=sorted(buckets); ng=len(keys); nc=11; ksort=sorted(q); X=np.array([k[2] for k in keys],float);eq=np.zeros((len(q),ng+nc)); Q=np.array([q[k] for k in ksort],float)
 for j,g in enumerate(ksort):
  for i,k in enumerate(keys):eq[j,i]=int((k[0],k[1])==g)
 ub=np.zeros((2*nc+1,ng+nc));rhs=np.zeros(2*nc+1)
 for i in range(nc):
  ub[i,:ng]=X[:,i]/n;ub[i,ng+i]=-1;rhs[i]=targets[i]
  ub[nc+i,:ng]=-X[:,i]/n;ub[nc+i,ng+i]=-1;rhs[nc+i]=-targets[i]
 costs={v:fractions.Fraction(1,n)+fractions.Fraction(1,d*size) for v,size in ds.items()}
 total=sum((costs[lookup[x]['domain']] for x in anchor),fractions.Fraction())
 ub[-1,:ng]=[-float(costs[k[0]]) if k[3] else 0 for k in keys];rhs[-1]=float(tau-total)
 upper=np.r_[[len(buckets[k]) for k in keys],np.full(nc,np.inf)];obj=np.r_[np.zeros(ng),coeff];lb=np.zeros(ng+nc)
 lp=linprog(obj,A_ub=ub,b_ub=rhs,A_eq=eq,b_eq=Q,bounds=list(zip(lb,upper)),method='highs',options={'time_limit':seconds})
 out={'lp_status':int(lp.status),'lp_message':str(lp.message),'lp_lower_bound':float(lp.fun) if lp.success else None,'lp_dual_inequality':lp.ineqlin.marginals.tolist() if lp.success else None,'lp_dual_quota':lp.eqlin.marginals.tolist() if lp.success else None,'lp_dual_bounds_lower':lp.lower.marginals.tolist() if lp.success else None,'lp_dual_bounds_upper':lp.upper.marginals.tolist() if lp.success else None,'integer_status':None,'integer_optimum':None,'integer_proven_optimal':False,'selected':None,'H_exact':None,'n':n,'quota_groups':len(q),'features':'difficulty,shape,joins,tokens; omitted nonnegative operator block; lower bound only'}
 if not lp.success:return out
 res=milp(obj,integrality=np.r_[np.ones(ng,dtype=int),np.zeros(nc)],bounds=Bounds(lb,upper),constraints=[LinearConstraint(eq,Q,Q),LinearConstraint(ub,np.full(2*nc+1,-np.inf),rhs)],options={'time_limit':seconds})
 out.update(integer_status=int(res.status),integer_message=str(res.message),integer_proven_optimal=bool(res.success),integer_solver_bound=float(res.mip_dual_bound) if getattr(res,'mip_dual_bound',None) is not None else None)
 if res.x is not None:
  counts=np.rint(res.x[:ng]).astype(int)
  if np.any(counts<0) or np.any(counts>upper[:ng]) or not np.array_equal(eq[:,:ng]@counts,Q):raise ValueError('INVALID_INTEGER_WITNESS')
  selected=[i for z,k in zip(counts,keys) for i in sorted(buckets[k])[:int(z)]]
  h=sum((costs[lookup[i]['domain']] for i in aset-set(selected)),fractions.Fraction())
  if len(selected)!=n or h>tau:raise ValueError('EXACT_H_WITNESS_FAILED')
  out.update(integer_optimum=float(res.fun),selected=selected,H_exact=str(h),integer_gap=(float(res.fun)-float(lp.fun)))
 return out
def main():
 p=argparse.ArgumentParser();p.add_argument('--candidates',required=True);p.add_argument('--profile',required=True);p.add_argument('--anchor',required=True);p.add_argument('--quotas',required=True);p.add_argument('--tau',required=True);p.add_argument('--output',required=True);p.add_argument('--seconds',type=int,default=30);a=p.parse_args()
 if not 1<=a.seconds<=300:raise ValueError('SECONDS_OUTSIDE_BOUND')
 files=[a.candidates,a.profile,a.anchor,a.quotas];r=solve(load(a.candidates),read(a.profile),read(a.anchor),read(a.quotas),a.tau,a.seconds);r.update(input_sha256={x:sha(x) for x in files},tau=a.tau,scope='Input schema and fixed weights must be known; LP dual and integer objective apply to four-block lower bound, not full operator objective or TEF. Solver limit may leave optimum unproved.')
 with open(a.output,'x') as f:json.dump(r,f,indent=2);f.write('\n')
if __name__=='__main__':main()
