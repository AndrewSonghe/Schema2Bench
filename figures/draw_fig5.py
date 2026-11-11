"""Refine Figure 5 using the same range_style module as Figures 3 and 4."""
from pathlib import Path
import argparse,hashlib,json
import range_style as style

def draw_fig5(data,output,preview=None):
    style.configure()
    plt=style.plt
    risk=data['risk']['results']['verified']
    lookup={(r['scenario'],r['comparison'].split('_minus_')[1],r['metric']):r for r in data['witnesses']['results']}
    states=['no_risk','construction_only','reference_71_only','reference_105_only','construction_plus_reference_71','construction_plus_reference_105']
    labels=['No added concerns','Construction','Reference (71)','Reference (105)','Both (71)','Both (105)']
    plotted={};statuses={}
    fig=plt.figure(figsize=(7.16,3.1))

    def status_column(ax,state,other,metric,y):
        rec=lookup.get((state,other,metric))
        symbol='' if rec is None else ('W' if rec['found_reverse'] else '?')
        statuses[f'{state}/{other}/{metric}']=symbol
        if symbol:
            ax.text(1.085,y,symbol,transform=ax.get_yaxis_transform(),ha='center',va='center',
              fontsize=8.2,color=style.INK,fontweight='bold',clip_on=False)

    def status_rule(ax):
        ax.plot([1.035,1.035],[0,1],transform=ax.transAxes,color=style.GRID,lw=.65,clip_on=False)

    for j,other in enumerate(['refill','ring']):
        left=.215+j*.41
        fig.text(left,.945,f'({chr(97+j)}) Rewrite - {"S2B" if other=="refill" else "Ring"}',
          fontsize=9.2,fontweight='bold')
        ax=fig.add_axes([left,.52,.32,.34]);style.axes_style(ax)
        ax.axhspan(4.5,5.5,color='#F0F3F6',zorder=0)
        for y in [3.5,1.5]:ax.axhline(y,color=style.GRID,lw=.55,zorder=0)
        for i,state in enumerate(states):
            value=risk[state][other]['gap_rewrite_minus']
            style.bound(ax,value,5-i,style.BLUE,scale=100)
            status_column(ax,state,other,'gap',5-i)
            plotted[f'fig5/{state}/{other}/gap']=value
        ax.set(xlim=(-15.5,9),ylim=(-.5,5.5),yticks=range(5,-1,-1),
          xticks=[-15,-10,-5,0,5],xlabel='ΔG (pp)')
        ax.set_yticklabels(labels if j==0 else [],fontsize=8.3)
        status_rule(ax)

        ax=fig.add_axes([left,.18,.32,.114]);style.axes_style(ax)
        ax.axhspan(.5,1.5,color='#F0F3F6',zorder=0)
        for i,state in enumerate(['no_risk','construction_only']):
            value=risk[state][other]['tef_rewrite_minus']
            style.bound(ax,value,1-i,style.ORANGE)
            status_column(ax,state,other,'tef',1-i)
            plotted[f'fig5/{state}/{other}/tef']=value
        ax.set(xlim=(-.11,.25),ylim=(-.5,1.5),yticks=[1,0],xticks=[-.1,0,.1,.2],xlabel='ΔTEF')
        ax.set_yticklabels(['No added concerns','Construction'] if j==0 else [],fontsize=8.3)
        status_rule(ax)

    fig.text(.025,.865,'Target gap',fontsize=9.2,fontweight='bold')
    fig.text(.025,.337,'Source TEF',fontsize=9.2,fontweight='bold')
    fig.text(.58,.043,'W  Feasible reversal       ?  Unresolved',ha='center',va='center',fontsize=8.3)
    report=style.save(fig,output,preview)
    report.update({'layout':'fixed comparison columns; gap above TEF','scenario_count':6,
      'plotted_bound_pairs':len(plotted),'status_markers':statuses,
      'legend_labels':['Feasible reversal','Unresolved']})
    return plotted,report

if __name__=='__main__':
    P=Path(__file__).resolve().parent
    (P/'validation').mkdir(exist_ok=True)
    parser=argparse.ArgumentParser();parser.add_argument('--preview',type=Path)
    args=parser.parse_args()
    read=lambda p:json.loads(p.read_text())
    bindings=read(P/'data/BINDINGS.json');data={}
    for name in ['risk','witnesses']:
        f=P/'data'/f'{name}.json'
        assert hashlib.sha256(f.read_bytes()).hexdigest()==bindings[name]['sha256']
        data[name]=read(f)
    plotted,report=draw_fig5(data,P/'Fig5',args.preview)
    expected={k:v for k,v in read(P/'data/ORIGINAL_INTERVAL_VALUES.json').items() if k.startswith('fig5/')}
    assert plotted==expected
    assert len(style.calls)==16
    report.update({'values_equal_accepted_figure':True})
    (P/'validation/FIG5_CHECK.json').write_text(json.dumps(report,indent=2)+'\n')
    (P/'validation/FIG5_BOUND_DRAW_CALLS.json').write_text(json.dumps(style.calls,indent=2)+'\n')
    (P/'FIG5_VALUES.json').write_text(json.dumps(plotted,indent=2)+'\n')
    print(json.dumps(report,indent=2))
