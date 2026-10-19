#!/usr/bin/env python3
"""Score the single rate-calibrated allocation intervention, plus whole-window controls."""
import sys,json
import numpy as np
from scipy.ndimage import gaussian_filter
import grain_model as g
from texture import analyze,desc
x=g.x
def evaluate(case):
    d=x.ROOT/case;sel=json.loads((d/'b-allocation-selection.json').read_text())
    x.score(case,sel['selected'],'b-allocation',grain=0)
    analyze(case,'b-allocation',d/'b-allocation-decoded.mkv')
    arrays={'source':g.mm(d/'source.yuv')}
    for tag in ('b-base','b-allocation'):
        p=d/(tag+'-control.yuv')
        if not p.exists():x.run(['ffmpeg','-v','error','-threads','4','-i',d/(tag+'-decoded.mkv'),'-pix_fmt','yuv420p10le','-f','rawvideo',p],d,tag+'-control')
        arrays[tag]=g.mm(p)
    rows=[]
    for n in range(8,240,16):
        vals={tag:g.planes(a,n)[0].astype(np.float32)/4 for tag,a in arrays.items()}
        sm=gaussian_filter(vals['source'],2);gy,gx=np.gradient(sm);grad=np.hypot(gx,gy)
        for yy in range(8,1040,48):
            for xx in range(8,1880,48):
                sl=np.s_[yy:yy+32,xx:xx+32];stats={tag:desc(a[sl]) for tag,a in vals.items()}
                edge=float(np.percentile(grad[sl],95));s=stats['source']['hf_sigma'];kind='edge' if edge>4 else 'quiet' if edge<.75 and s<.2 else 'flat_texture' if edge<.75 else 'other'
                rows.append({'frame':n,'x':xx,'y':yy,'kind':kind,**stats,
                    'mse':{tag:float(np.mean((vals[tag][sl]-vals['source'][sl])**2)) for tag in ('b-base','b-allocation')}})
    sums={}
    for kind in ('quiet','edge','flat_texture','other'):
        pool=[r for r in rows if r['kind']==kind];sums[kind]={'tiles':len(pool)}
        for tag in ('b-base','b-allocation'):
            ac=[abs(r[tag]['acf1']-r['source']['acf1']) for r in pool if r[tag]['acf1'] is not None and r['source']['acf1'] is not None]
            sums[kind][tag]={'mse':float(np.mean([r['mse'][tag] for r in pool])) if pool else None,'hf_abs_error':float(np.mean([abs(r[tag]['hf_sigma']-r['source']['hf_sigma']) for r in pool])) if pool else None,'acf1_abs_error':float(np.mean(ac)) if ac else None}
    x.dump(d/'b-whole-window-controls.json',{'frames':list(range(8,240,16)),'note':'Spatially distributed evaluation; allocation map used all source frames, so this is not a held-out encoder test. Luma controls supplement full-frame YUV metrics.','summary':sums,'tiles':rows})
    import visuals
    visuals.main(case,['b-base','b-allocation'])
    for name in ('comparison-crops.png','comparison-synchronized.mkv','texture-temporal.png','visuals.json'):
        (d/name).rename(d/('b-'+name))
if __name__=='__main__':evaluate(sys.argv[1])
