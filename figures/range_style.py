"""Single plotting rule for every bound in Figures 3--5.

No center marker or shape-based series coding. A collapsed bound is one cap.
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

LINE_WIDTH=1.6
CAP_LENGTH_PT=6.0
CAP_STROKE_PT=1.2
BLUE='#28658B';ORANGE='#C47730';GRAY='#929DA7';INK='#23384A';GRID='#E5EAEF'
PURPLE='#7963A2';TEAL='#2C807A'
calls=[]

def configure():
    from matplotlib import font_manager
    for f in ['/System/Library/Fonts/Supplemental/Arial.ttf','/System/Library/Fonts/Supplemental/Arial Bold.ttf']:
        from pathlib import Path
        if Path(f).exists(): font_manager.fontManager.addfont(f)
    try:
        font_manager.findfont('Arial',fallback_to_default=False)
        family = 'Arial'
    except ValueError:
        family = 'DejaVu Sans'
    plt.rcParams.update({'font.family':family,'font.size':8.5,'axes.titlesize':9.2,
      'axes.labelsize':8.5,'xtick.labelsize':8,'ytick.labelsize':8.5,'pdf.fonttype':42,
      'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,
      'axes.linewidth':.7,'savefig.facecolor':'white','figure.facecolor':'white'})

def bound(ax,values,position,color,scale=1,orientation='horizontal'):
    lo,hi=[float(v)*scale for v in values]
    assert lo<=hi+1e-12
    ends=[lo] if abs(hi-lo)<1e-12 else [lo,hi]
    if orientation=='horizontal':
        ax.hlines(position,lo,hi,color=color,lw=LINE_WIDTH,zorder=3)
        ax.plot(ends,[position]*len(ends),linestyle='none',marker='|',
          markersize=CAP_LENGTH_PT,markeredgewidth=CAP_STROKE_PT,color=color,zorder=5)
    elif orientation=='vertical':
        ax.vlines(position,lo,hi,color=color,lw=LINE_WIDTH,zorder=3)
        ax.plot([position]*len(ends),ends,linestyle='none',marker='_',
          markersize=CAP_LENGTH_PT,markeredgewidth=CAP_STROKE_PT,color=color,zorder=5)
    else:raise ValueError(orientation)
    calls.append({'bounds':list(values),'scale':scale,'orientation':orientation,
       'line_width_pt':LINE_WIDTH,'cap_length_pt':CAP_LENGTH_PT,'cap_stroke_pt':CAP_STROKE_PT,
       'collapsed':len(ends)==1})

def axes_style(ax,orientation='horizontal',zero=True):
    ax.set_axisbelow(True)
    ax.grid(axis='x' if orientation=='horizontal' else 'y',color=GRID,lw=.65)
    ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0)
    if zero and orientation=='horizontal':ax.axvline(0,color=INK,lw=.9,ls=(0,(3,3)),zorder=2)

def color_key(label,color):
    return Line2D([0],[0],color=color,lw=LINE_WIDTH,label=label)

def save(fig,path,preview=None):
    fig.canvas.draw();renderer=fig.canvas.get_renderer();texts=list(fig.texts)
    for legend in fig.legends:texts.extend(legend.get_texts())
    for ax in fig.axes:
        texts.extend(ax.texts);texts.extend([ax.title,ax._left_title,ax._right_title])
        if ax.get_legend():texts.extend(ax.get_legend().get_texts())
        if ax.axison:
            texts.extend([ax.xaxis.label,ax.yaxis.label])
            for axis,limits in [(ax.xaxis,ax.get_xlim()),(ax.yaxis,ax.get_ylim())]:
                for tick in axis.get_major_ticks()+axis.get_minor_ticks():
                    if min(limits)-1e-10<=tick.get_loc()<=max(limits)+1e-10:texts.extend([tick.label1,tick.label2])
    clipped=[]
    for t in texts:
        if not t.get_visible() or not t.get_text():continue
        b=t.get_window_extent(renderer)
        if b.x0<-.5 or b.y0<-.5 or b.x1>fig.bbox.width+.5 or b.y1>fig.bbox.height+.5:clipped.append(t.get_text())
    assert not clipped,clipped
    for ext in ['svg','pdf']:fig.savefig(path.with_suffix('.'+ext))
    if preview:
        preview.mkdir(parents=True,exist_ok=True)
        fig.savefig(preview/(path.name+'.png'),dpi=180)
    plt.close(fig)
    return {'text_outside_canvas':clipped}
