"""Portable, standard-library replay of the five-method interval tables."""
import collections,hashlib,itertools,json,pathlib,statistics
P=pathlib.Path(__file__).resolve().parent
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4194304),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(p.read_text())
def load(p):
 with p.open() as f:return [json.loads(x) for x in f]
def close(a,b):return abs(a-b)<1e-10
def vector_mean(rows,mode):
 return [[statistics.mean(x[mode][m][i] for x in rows) for i in (0,1)] for m in range(10)]
def coordinates(rows,mode):
 domains=sorted({x['domain'] for x in rows});by={d:[x for x in rows if x['domain']==d] for d in domains};av=[vector_mean(by[d],mode) for d in domains]
 acc=[[statistics.mean(v[m][i] for v in av) for i in (0,1)] for m in range(10)]
 cdf=[]
 for k in range(10):
  cdf.append([sum(sum(z[1] for z in x[mode])<=k for x in rows)/len(rows),sum(sum(z[0] for z in x[mode])<=k for x in rows)/len(rows)])
 dis=[]
 for a,b in itertools.combinations(range(10),2):
  lower=sum(x[mode][a][0]>x[mode][b][1] or x[mode][b][0]>x[mode][a][1] for x in rows)/len(rows)
  upper=sum(not(x[mode][a][0]==x[mode][a][1]==x[mode][b][0]==x[mode][b][1]) for x in rows)/len(rows)
  dis.append([lower,upper])
 return [(1,acc),(1,cdf),(.5,dis)]
def distance(a,b):return [max(a[0]-b[1],b[0]-a[1],0),max(abs(a[0]-b[1]),abs(a[1]-b[0]))]
def shared(r,a,b):
 points={r[0],r[1]}
 for k in (a[0],a[1],b[0],b[1],sum(a)/2,sum(b)/2):
  if r[0]<=k<=r[1]:points.add(k)
 vals=[]
 for k in points:
  x=distance((k,k),a);y=distance((k,k),b);vals.append([x[0]-y[1],x[1]-y[0]])
 return [min(x[0] for x in vals),max(x[1] for x in vals)]
def tef(s,t):
 out=[0.,0.]
 for (w,a),(_,b) in zip(s,t):
  dist=[distance(x,y) for x,y in zip(a,b)]
  for i in (0,1):out[i]+=w*statistics.mean(x[i] for x in dist)
 return out
def tef_diff(s,a,b):
 out=[0.,0.]
 for (w,r),(_,t),(_,u) in zip(s,a,b):
  vals=[shared(x,y,z) for x,y,z in zip(r,t,u)]
  for i in (0,1):out[i]+=w*statistics.mean(x[i] for x in vals)
 return out
def diff(v,i,j):return [v[i][0]-v[j][1],v[i][1]-v[j][0]]
def gap(r,t):
 vals=[distance(diff(r,i,j),diff(t,i,j)) for i,j in itertools.combinations(range(10),2)]
 return [statistics.mean(x[k] for x in vals) for k in (0,1)]
def gap_diff(r,a,b):
 vals=[shared(diff(r,i,j),diff(a,i,j),diff(b,i,j)) for i,j in itertools.combinations(range(10),2)]
 return [statistics.mean(x[k] for x in vals) for k in (0,1)]
def checksums():
 manifest=read(P/'MANIFEST.json')
 for item in manifest['files']:
  f=P/item['path']
  if not f.is_file() or f.stat().st_size!=item['bytes'] or sha(f)!=item['sha256']:raise ValueError('FILE_CHANGED:'+str(f))
 return len(manifest['files'])
def main():
 nfiles=checksums();M=P/'matrices';source=load(M/'source.jsonl');refs=load(M/'reference.jsonl');core={x['id']:x for x in load(M/'core.jsonl')};other={k:load(M/(k+'.jsonl')) for k in ('ring','omni','synth')};sel=read(M/'memberships.json');expected=read(P/'EXPECTED.json');domains=sorted({x['domain'] for x in refs})
 if len(source)!=1034 or len(refs)!=906 or len(domains)!=8 or len(sel['releases'])!=10 or any(len(v)!=2000 for v in other.values()):raise ValueError('COVERAGE')
 for dataset in [source,refs,list(core.values()),*other.values()]:
  if len({x['id'] for x in dataset})!=len(dataset):raise ValueError('DUPLICATE_ID')
  for x in dataset:
   for mode in ('base','verified'):
    if len(x[mode])!=10 or any(z not in ([0,0],[0,1],[1,1]) for z in x[mode]):raise ValueError('BAD_BOUNDS')
 summary={};results=[]
 for release in sel['releases']:
  selected={k:[core[i] for i in release[k]] for k in ('template','refill')};selected.update(other)
  if any(len(x)!=2000 or collections.Counter(z['domain'] for z in x)!={d:250 for d in domains} for x in selected.values()):raise ValueError('TARGET_QUOTAS')
  entry={'seed':release['seed']}
  for mode,outmode in [('base','base'),('verified','verified_evidence')]:
   s=coordinates(source,mode);ref={d:vector_mean([x for x in refs if x['domain']==d],mode) for d in domains};ts={k:coordinates(v,mode) for k,v in selected.items()};by={k:{d:vector_mean([x for x in v if x['domain']==d],mode) for d in domains} for k,v in selected.items()};tables={};comp={}
   for k,v in selected.items():
    vals=[gap(ref[d],by[k][d]) for d in domains]
    tables[k]={'target_unknown':sum(z[0]!=z[1] for x in v for z in x[mode]),'gap_bounds':[statistics.mean(x[i] for x in vals) for i in (0,1)],'tef_bounds':tef(s,ts[k])}
   for k in ('template','ring','omni','synth'):
    vals=[gap_diff(ref[d],by['refill'][d],by[k][d]) for d in domains]
    comp[k]={'tef_refill_minus_method':tef_diff(s,ts['refill'],ts[k]),'gap_refill_minus_method':[statistics.mean(x[i] for x in vals) for i in (0,1)]}
   entry[outmode]={'tables':tables,'contrasts':comp,'source_unknown':sum(z[0]!=z[1] for x in source for z in x[mode]),'reference_unknown':sum(z[0]!=z[1] for x in refs for z in x[mode])}
  results.append(entry)
 for entry,old in zip(results,expected['seeds']):
  if entry['seed']!=old['seed']:raise ValueError('SEED')
  for mode in ('base','verified_evidence'):
   for k in ('template','refill','ring','omni','synth'):
    for metric in ('gap_bounds','tef_bounds'):
     if not all(close(a,b) for a,b in zip(entry[mode]['tables'][k][metric],old[mode]['tables'][k][metric])):raise ValueError('TABLE_REPLAY:'+mode+':'+k+':'+metric)
    if entry[mode]['tables'][k]['target_unknown']!=old[mode]['tables'][k]['target_unknown']:raise ValueError('UNKNOWN')
   for k in ('template','ring','omni','synth'):
    for metric in ('tef_refill_minus_method','gap_refill_minus_method'):
     if not all(close(a,b) for a,b in zip(entry[mode]['contrasts'][k][metric],old[mode]['contrasts'][k][metric])):raise ValueError('DIFF_REPLAY:'+mode+':'+k+':'+metric)
   for metric in ('source_unknown','reference_unknown'):
    if entry[mode][metric]!=old[mode][metric]:raise ValueError('SOURCE_REFERENCE_UNKNOWN')
  print('REPLAY_SEED_PASSED',entry['seed'],flush=True)
 for mode in ('base','verified_evidence'):
  summary[mode]={}
  for k in ('template','ring','omni','synth'):
   vv=[x[mode]['contrasts'][k]['tef_refill_minus_method'] for x in results]
   summary[mode][k]={'mean_bounds':[statistics.mean(x[i] for x in vv) for i in (0,1)],'favorable':sum(x[1]<0 for x in vv),'cross_zero':sum(x[0]<=0<=x[1] for x in vv),'unfavorable':sum(x[0]>0 for x in vv)}
 result={'status':'PORTABLE_FIVE_METHOD_TEN_SEED_REPLAY_VERIFIED','manifest_files':nfiles,'seeds':len(results),'source_items':len(source),'reference_items':len(refs),'summary':summary,'scope':'Replays fixed stored interval matrices; does not regenerate models, recreate databases, certify semantics, establish independent domains, or change original results.'}
 (P/'REPLAY_RESULT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
