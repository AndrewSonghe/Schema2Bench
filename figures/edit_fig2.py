"""Revise only labels in the retained vector diagram. Requires PyMuPDF."""
from pathlib import Path
import json
import pymupdf

P = Path(__file__).resolve().parent
(P/'validation').mkdir(exist_ok=True)
replacements = {
    'Quota release': 'Workload Selection',
    'Grounded construction': 'Benchmark Construction',
    'Measurement': 'Benchmark Evaluation',
    'Historical screen': 'Candidate eligibility',
    'Output availability': 'Resolved model outputs',
    'Response-blind selector': 'Select using SQL features',
    'anchor': 'sample',
    'realization': 'generation',
    'Frozen release IDs': 'Selected task IDs',
    'Saved outputs + SQL proofs': 'Outputs + execution evidence',
    'Pool support diagnostic': 'Candidate-pool coverage',
}
doc = pymupdf.open(P/'Fig2_base.pdf')
page = doc[0]
spans = [s for b in page.get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans']]
selected = [s for s in spans if s['text'] in replacements]
assert len(selected)==len(replacements)
fonts = {False:pymupdf.Font('helv'), True:pymupdf.Font('hebo')}
for s in selected:
    page.add_redact_annot(s['bbox'],fill=False)
page.apply_redactions(images=0,graphics=0)
for bold, font in fonts.items():
    page.insert_font(fontname='revisionBold' if bold else 'revisionRegular',fontbuffer=font.buffer)
report=[]
for s in selected:
    bold=bool(s['flags'] & 16)
    new=replacements[s['text']]
    size=s['size']
    width=fonts[bold].text_length(new,fontsize=size)
    rect=pymupdf.Rect(s['bbox'])
    center=(rect.x0+rect.x1)/2
    color=tuple(((s['color'] >> shift) & 255)/255 for shift in [16,8,0])
    page.insert_text((center-width/2,s['origin'][1]),new,fontsize=size,
        fontname='revisionBold' if bold else 'revisionRegular',color=color)
    report.append({'before':s['text'],'after':new,'font_size':size})
doc.subset_fonts()
doc.save(P/'Fig2.pdf',garbage=4,deflate=True)
page.get_pixmap(matrix=pymupdf.Matrix(1,1)).save(P/'validation/Fig2.png')
(P/'validation/FIG2_CHECK.json').write_text(json.dumps({'label_replacements':report,
    'scope':'Text labels only; original diagram paths and images retained.'},indent=2)+'\n')
