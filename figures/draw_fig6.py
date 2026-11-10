"""Keep the accepted weight regions; refine only size, spacing and labels."""
from pathlib import Path
import argparse,hashlib,json,math
from matplotlib.patches import Polygon,Patch
from matplotlib.lines import Line2D
import range_style as style

P=Path(__file__).resolve().parent
(P/'validation').mkdir(exist_ok=True)
parser=argparse.ArgumentParser();parser.add_argument('--preview',type=Path)
args=parser.parse_args();style.configure();plt=style.plt
read=lambda p:json.loads(p.read_text())
b=read(P/'data/BINDING.json')
assert hashlib.sha256((P/'data/weights.json').read_bytes()).hexdigest()==b['sha256']
D=read(P/'data/weights.json')['results']['verified']['comparisons']
fig=plt.figure(figsize=(7.16,2.0));height=math.sqrt(3)/2
GREEN='#A8D3C7';GRAY='#EEF0F2';AMBER='#E8BC8F'
plotted={}
for j,method in enumerate(['template','ring','omni','synth']):
    ax=fig.add_axes([.025+j*.247,.23,.235,.66]);ax.set_aspect('equal');ax.axis('off')
    ax.set(xlim=(-.12,1.12),ylim=(-.11,.97))
    fig.text(.1425+j*.247,.945,f'({chr(97+j)}) vs. {method.capitalize()}',
      ha='center',fontsize=9.2,fontweight='bold')
    triangle=[[0,0],[1,0],[.5,height]]
    ax.add_patch(Polygon(triangle,fc=GRAY,ec=style.INK,lw=.8))
    for status,color in [('favorable',GREEN),('unfavorable',AMBER)]:
        vertices=D[method][status+'_closure_vertices_w1_w2']
        xy=[]
        for x,y in vertices:
            w1=x/2.5;w2=y/2.5;w3=1-w1-w2
            xy.append([w2+.5*w3,height*w3])
        if len(xy)>=3:ax.add_patch(Polygon(xy,fc=color,ec='white',lw=.65))
        plotted[f'fig6/{method}/{status}']=vertices
    for q in [.25,.5,.75]:
        for ends in [((q,0),(q/2,height*q)),((q,0),((1+q)/2,height*(1-q))),
                     ((q/2,height*q),(1-q/2,height*q))]:
            ax.plot(*zip(*ends),color='white',lw=.35,alpha=.45)
    ax.add_patch(Polygon(triangle,fill=False,ec=style.INK,lw=.8))
    ax.plot(.5,.2*height,'*',ms=8,mec=style.INK,mfc='white',mew=.9,zorder=6)
    for x,y,label in [(-.03,-.07,'A'),(1.03,-.07,'C'),(.5,height+.055,'D')]:
        ax.text(x,y,label,ha='center',va='center',fontweight='bold',fontsize=8.5,color=style.INK)
fig.legend(handles=[Patch(fc=GREEN,label='Lower TEF'),Patch(fc=GRAY,label='Unresolved'),
 Patch(fc=AMBER,label='Higher TEF'),Line2D([0],[0],marker='*',ms=8,mec=style.INK,
 mfc='white',color=style.INK,lw=0,label='Main weights')],loc='center',bbox_to_anchor=(.5,.16),
 ncol=4,frameon=False,fontsize=8.5,handlelength=1.3,columnspacing=1.5)
assert plotted==read(P/'data/ORIGINAL_REGION_VERTICES.json')
report=style.save(fig,P/'Fig6',args.preview)
report.update({'region_polygon_sets_unchanged':len(plotted),'main_weights':[1,1,.5],
 'normalized_main_weights':[.4,.4,.2],'legend_labels':['Lower TEF','Unresolved','Higher TEF','Main weights'],
 'graphic_scope':'same regions and main-weight point; larger triangles and shorter labels',
 'size_inches':[7.16,2.0],'new_experiments':False})
(P/'FIG6_VALUES.json').write_text(json.dumps(plotted,indent=2)+'\n')
(P/'validation/FIG6_CHECK.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
