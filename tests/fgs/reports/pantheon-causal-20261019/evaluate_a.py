#!/usr/bin/env python3
"""Score offline synthesis and source-defined held-out/edge/quiet controls."""
import sys,json,hashlib,shutil
from pathlib import Path
import numpy as np
from scipy.ndimage import gaussian_filter
import grain_model as g
x=g.x
from texture import analyze,desc

def evaluate(case):
    d=x.ROOT/case;fps=x.CASES[case][2]
    arrays={t:g.mm(d/(t+'.yuv')) for t in ('source','base','existing','model')}
    # Held-out tile parity and frames never used for fitting or stationarity tests.
    controls=[]
    for n in range(8,240,16):
        vals={tag:g.planes(a,n)[0].astype(np.float32)/4 for tag,a in arrays.items()}
        sm=gaussian_filter(vals['source'],2);gy,gx=np.gradient(sm);grad=np.hypot(gx,gy)
        for iy,yy in enumerate(range(8,1040,48)):
            for ix,xx in enumerate(range(8,1880,48)):
                if (ix+iy)%2!=1:continue
                sl=np.s_[yy:yy+32,xx:xx+32];stats={tag:desc(a[sl]) for tag,a in vals.items()}
                edge=float(np.percentile(grad[sl],95));s=stats['source']['hf_sigma'];kind='edge' if edge>4 else 'quiet' if edge<.75 and s<.2 else 'flat_texture' if edge<.75 else 'other'
                controls.append({'frame':n,'x':xx,'y':yy,'kind':kind,'source':stats['source'],**{tag:stats[tag] for tag in ('base','existing','model')}})
    sums={}
    for kind in ('quiet','edge','flat_texture','other'):
        pool=[r for r in controls if r['kind']==kind];sums[kind]={'tiles':len(pool)}
        for tag in ('base','existing','model'):
            sums[kind][tag]={'hf_abs_error':float(np.mean([abs(r[tag]['hf_sigma']-r['source']['hf_sigma']) for r in pool])) if pool else None,'acf1_abs_error':float(np.mean([abs(r[tag]['acf1']-r['source']['acf1']) for r in pool if r[tag]['acf1'] is not None and r['source']['acf1'] is not None])) if any(r[tag]['acf1'] is not None and r['source']['acf1'] is not None for r in pool) else None,'added_hf_sigma':float(np.mean([r[tag]['hf_sigma']-r['base']['hf_sigma'] for r in pool])) if pool else None}
    x.dump(d/'a-heldout-controls.json',{'fit_frames':'16k and their immediate neighbors; spatial checkerboard even; diagnostic ROIs excluded','evaluation_frames':list(range(8,240,16)),'spatial_parity':'odd','summary':sums,'tiles':controls})
    p=d/'model-render.mkv'
    if not p.exists():x.run(['ffmpeg','-v','error','-f','rawvideo','-s','1920x1080','-pix_fmt','yuv420p10le','-r',str(fps),*x.COLOR,'-i',d/'model.yuv','-c:v','ffvhuff','-threads','4',*x.COLOR,p],d,'model-render')
    x.score(case,p,'a-model',pre=0,grain=0)
    for tag,path in [('a-model',d/'a-model-decoded.mkv'),('a-base',d/'base-decoded.mkv'),('a-existing',d/'existing-decoded.mkv')]:
        if tag!='a-model':shutil.copy2(path,d/(tag+'-decoded.mkv'))
        analyze(case,tag,d/(tag+'-decoded.mkv'),d/'base-decoded.mkv')
    x.dump(d/'a-rate.json',{'fixed_picture_mbps':x.rate(d/'fixed-picture.mkv',fps),'offline_render':'Uncompressed synthesis after decoding; no rewritten AV1 stream; no measured new signaling overhead.','encoded_picture_sha256':hashlib.sha256((d/'fixed-picture.mkv').read_bytes()).hexdigest(),'source_mbps':json.loads((d/'validity.json').read_text())['source_mbps']})

if __name__=='__main__':evaluate(sys.argv[1])
