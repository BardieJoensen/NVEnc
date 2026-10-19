#!/usr/bin/env python3
"""Complete held-out color safety/coverage checks without refitting the model."""
import sys,json
import numpy as np
from scipy.ndimage import gaussian_filter
import grain_model as g
from texture import desc
x=g.x
for case in ('e04','e05-1440','e05-1420','e05-1460'):
    d=x.ROOT/case;doc=json.loads((d/'grain-fit.json').read_text());active={}
    for n in range(240):
        m=next(m for m in doc['models'] if m['start']<=n<m['end'])
        active[n]=any(any(ch['scales']) for ch in m['channels'])
    arrays={tag:g.mm(d/(tag+'.yuv')) for tag in ('source','base','existing','model')};rows=[]
    for n in range(8,240,16):
        for c in (1,2):
            vals={tag:g.planes(a,n)[c].astype(np.float32)/4 for tag,a in arrays.items()};sm=gaussian_filter(vals['source'],2);gy,gx=np.gradient(sm);grad=np.hypot(gx,gy)
            for iy,yy in enumerate(range(8,500,48)):
                for ix,xx in enumerate(range(8,920,48)):
                    if (ix+iy)%2!=1:continue
                    sl=np.s_[yy:yy+32,xx:xx+32];stats={tag:desc(a[sl]) for tag,a in vals.items()};edge=float(np.percentile(grad[sl],95));sigma=stats['source']['hf_sigma']
                    kind='edge' if edge>4 else 'quiet' if edge<.75 and sigma<.2 else 'flat_texture' if edge<.75 else 'other'
                    rows.append({'frame':n,'plane':c,'x':xx,'y':yy,'kind':kind,'active_model':active[n],**stats})
    yrows=json.loads((d/'a-heldout-controls.json').read_text())['tiles']
    for row in yrows:row.update(plane=0,active_model=active[row['frame']])
    rows+=yrows;summaries={}
    for c in range(3):
        for state in ('all','active','inactive'):
            for kind in ('quiet','edge','flat_texture','other'):
                pool=[r for r in rows if r['plane']==c and r['kind']==kind and (state=='all' or r['active_model']==(state=='active'))];key=f'plane{c}-{state}-{kind}';summaries[key]={'tiles':len(pool)}
                for tag in ('base','existing','model'):
                    summaries[key][tag]={'hf_abs_error':float(np.mean([abs(r[tag]['hf_sigma']-r['source']['hf_sigma']) for r in pool])) if pool else None,'added_hf_sigma':float(np.mean([r[tag]['hf_sigma']-r['base']['hf_sigma'] for r in pool])) if pool else None,'acf_valid_pairs':sum(r[tag]['acf1'] is not None and r['source']['acf1'] is not None for r in pool)}
    x.dump(d/'a-color-controls.json',{'summary':summaries,'chroma_tiles':[r for r in rows if r['plane']>0],'active_model_frames':[n for n in range(240) if active[n]],'intervals':len(doc['models']),'nonzero_intervals':sum(any(any(c['scales']) for c in m['channels']) for m in doc['models']),'split_limit':'Frames/regions held out from covariance/amplitude fitting and calibration; all source thumbnails participate in shot segmentation.'})
    print(case,'active frames',sum(active.values()),'quiet chroma',{k:v for k,v in summaries.items() if 'active-quiet' in k and not k.startswith('plane0')},flush=True)
