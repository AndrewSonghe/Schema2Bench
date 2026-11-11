"""Integrated Figure 3: capped contrasts and hatched selection-regret bounds.

python draw_fig3.py
python draw_fig3.py --preview /tmp/fig3_candidate
"""
from pathlib import Path
import argparse,hashlib,json
from matplotlib.patches import Patch
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
plotted={};bars=[]

# A/B use exactly the same range renderer, limits and layout as the current set.
fig=plt.figure(figsize=(7.16,3.2));first=D['main']['seeds'][0]
for j,(metric,title,scale,limits,ticks) in enumerate([
 ('tef_refill_minus_method','(a) Source TEF',1,(-.77,.24),[-.6,-.4,-.2,0,.2]),
 ('gap_refill_minus_method','(b) Target gap',100,(-22,22),[-20,-10,0,10,20])]):
    ax=fig.add_axes([.125+j*.48,.61,.35,.29]);axes_style(ax)
    for i,method in enumerate(['template','ring','omni','synth']):
        for layer,offset,color in [('base',.21,GRAY),('verified_evidence',-.21,BLUE)]:
            value=first[layer]['contrasts'][method][metric]
            bound(ax,value,3-i+offset,color,scale)
            plotted[f'fig3/{metric}/{method}/{layer}']=value
    ax.set(xlim=limits,ylim=(-.5,3.5),yticks=[3,2,1,0],xticks=ticks,xlabel='ΔTEF' if j==0 else 'ΔG (pp)')
    ax.set_yticklabels(['Template','Ring','Omni','Synth'] if j==0 else [])
    ax.set_title(title,loc='left',fontweight='bold',pad=7)
fig.legend(handles=[color_key('Base',GRAY),color_key('Verified',BLUE)],loc='center',
 bbox_to_anchor=(.55,.978),ncol=2,frameon=False,fontsize=8.5,handlelength=1.8,columnspacing=1.8)

# C shows nonnegative loss magnitude: solid to lower bound; hatching to upper.
ax=fig.add_axes([.10,.135,.87,.295]);axes_style(ax,orientation='vertical',zero=False)
ax.set_title('(c) Selection regret',loc='left',fontweight='bold',pad=8)
for method,offset,color in [('refill',-.17,BLUE),('ring',.17,ORANGE)]:
    for i,d in enumerate(domains):
        value=D['regret']['domains'][d][method]['regret_pp'];lo,hi=value;x=i+offset
        assert 0<=lo<=hi
        ax.bar(x,lo,width=.27,color=color,edgecolor=color,lw=.6,zorder=3)
        if hi-lo>1e-12:
            ax.bar(x,hi-lo,bottom=lo,width=.27,facecolor='white',edgecolor=color,
              hatch='////',lw=.8,zorder=3)
        if abs(hi)<1e-12:ax.plot([x-.135,x+.135],[0,0],color=color,lw=1.6,zorder=4)
        plotted[f'fig3/regret/{method}/{d}']=value
        bars.append({'method':method,'domain':d,'solid_height':lo,'hatched_height':hi-lo,'total_height':hi})
ax.set(xlim=(-.6,7.6),ylim=(0,16.2),xticks=range(8),yticks=[0,5,10,15],ylabel='Regret (pp)')
ax.set_xticklabels(short,fontsize=8.1);ax.tick_params(axis='x',length=0,pad=6)
ax.legend(handles=[Patch(fc=BLUE,label='S2B'),Patch(fc=ORANGE,label='Ring'),
 Patch(fc='white',ec=INK,hatch='////',label='Bounds')],loc='lower right',
 bbox_to_anchor=(1,1.025),borderaxespad=0,ncol=3,frameon=False,fontsize=8.3,
 handletextpad=.4,columnspacing=1.4,handlelength=1.4)

assert plotted==read(P/'data/ORIGINAL_FIG3_VALUES.json')
assert len(calls)==16 and len(bars)==16
report=save(fig,P/'Fig3',args.preview)
report.update({'status':'INTEGRATED_V8','bound_pairs_unchanged':len(plotted),
 'ab_shared_range_style_unchanged':True,'selection_range_bars':len(bars),
 'filled_height':'lower bound','hatched_extension':'upper minus lower bound',
 'zero_origin_for_loss_axis':True,'manuscript_integration':True})
(P/'FIG3_VALUES.json').write_text(json.dumps(plotted,indent=2)+'\n')
(P/'validation/SELECTION_BARS.json').write_text(json.dumps(bars,indent=2)+'\n')
(P/'validation/FIG3_CHECK.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
