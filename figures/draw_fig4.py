"""Draw Figure 4 with the shared interval style.

python draw_fig4.py
python draw_fig4.py --preview /tmp/chart_check
"""
from pathlib import Path
import argparse,hashlib,json
from range_style import *

P=Path(__file__).resolve().parent
(P/'validation').mkdir(exist_ok=True)
parser=argparse.ArgumentParser();parser.add_argument('--preview',type=Path)
args=parser.parse_args();configure()
read=lambda p:json.loads(p.read_text())
B=read(P/'data/BINDINGS.json')
for name,b in B.items():
    assert hashlib.sha256((P/'data'/f'{name}.json').read_bytes()).hexdigest()==b['sha256']
D={k:read(P/'data'/f'{k}.json') for k in B}
domains=['california_schools','card_games','codebase_community','european_football_2','financial','formula_1','superhero','thrombosis_prediction']
short=['California','Card games','Codebase','Football','Financial','Formula 1','Superhero','Thrombosis']
plotted={};reports={}

# Figure 4: original interval layout and refined short labels.
name=D['name']['results']['verified'];depth=D['depth']['results']['verified']
rewrite=D['rewrite']['results']['verified']['original']
controls=[
 ('Column preference','on - off',PURPLE,name['full_minus_nohint_tef'],name['full_minus_nohint_macro_gap'],name['domain_gap_differences']),
 ('Value sampling','50 - 5 values',TEAL,depth['full_minus_nohint_tef'],depth['full_minus_nohint_macro_gap'],depth['domain_gap_differences']),
 ('Question wording','rewritten - original',ORANGE,rewrite['contrasts']['refill']['tef_rewrite_minus'],rewrite['contrasts']['refill']['gap_rewrite_minus'],{d:rewrite['domains'][d]['rewrite_minus_refill_gap'] for d in domains})]
fig=plt.figure(figsize=(7.16,3.75));ax=fig.add_axes([.28,.79,.68,.14]);axes_style(ax)
ax.set_title('(a) Source TEF',loc='left',fontweight='bold',pad=7)
for i,(label,contrast,color,tef,gap,per) in enumerate(controls):
    bound(ax,tef,2-i,color);plotted[f'fig4/{label}/tef']=tef
ax.set(ylim=(-.5,2.5),xlim=(-.03,.225),yticks=[2,1,0],yticklabels=[c[0] for c in controls],
 xticks=[-.02,0,.1,.2],xlabel='ΔTEF')
limits=[(-4.9,4.5),(-2.5,2.5),(-19.5,1)];ticks=[[-4,-2,0,2,4],[-2,-1,0,1,2],[-18,-12,-6,0]]
for j,((label,contrast,color,tef,gap,per),lim,tick) in enumerate(zip(controls,limits,ticks)):
    x=.205+j*.26
    fig.text(x,.668,f'({chr(98+j)}) {label}',fontweight='bold',fontsize=8.8)
    fig.text(x,.627,contrast,fontsize=8.2,color='#586674')
    ax=fig.add_axes([x,.13,.225,.46]);axes_style(ax)
    ax.axhspan(7.5,8.6,color='#F0F3F6',zorder=0)
    bound(ax,gap,8,INK,scale=100);plotted[f'fig4/{label}/gap']=gap
    for i,d in enumerate(domains):
        bound(ax,per[d],7-i,color,scale=100);plotted[f'fig4/{label}/{d}/gap']=per[d]
    ax.set(xlim=lim,ylim=(-.5,8.6),yticks=range(8,-1,-1),xticks=tick,xlabel='ΔG (pp)')
    ax.set_yticklabels(['All domains']+short if j==0 else [])
    if j==0:ax.get_yticklabels()[0].set_fontweight('bold')
reports['Fig4']=save(fig,P/'Fig4',args.preview)


expected={k:v for k,v in read(P/'data/ORIGINAL_INTERVAL_VALUES.json').items() if k.startswith('fig4/')}
assert {k.replace('Question wording','Question realization'):v for k,v in plotted.items()}==expected
(P/'validation/FIG4_CHECK.json').write_text(json.dumps({'bound_pairs_unchanged':len(plotted),'figures':reports},indent=2)+'\n')
(P/'FIG4_VALUES.json').write_text(json.dumps(plotted,indent=2)+'\n')
