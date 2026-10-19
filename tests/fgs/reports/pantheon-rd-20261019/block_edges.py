#!/usr/bin/env python3
"""Source-conditioned 8/16-grid discontinuity diagnostics, not a perceptual gate."""
import json
import sys
from pathlib import Path
import numpy as np
from analyze import ROOT, W, H, x
from score import texture

case,tag=sys.argv[1:]
d=ROOT/'parent/crosscodec'/case/tag
controls=json.loads((d/'controls.json').read_text())
assert controls['source_descriptors_match_prior'] and len(controls['tiles'])==12870
byframe={}
for r in controls['tiles']:byframe.setdefault(r['frame'],[]).append(r)
assert len(byframe)==15 and len({(r['frame'],r['x'],r['y']) for r in controls['tiles']})==12870
source_prov=x.fingerprint(ROOT/'fixtures'/case/'source.yuv')
assert source_prov==json.loads((ROOT/'fixtures'/case/'fresh-validation.json').read_text())['source_raw']
source=np.memmap(ROOT/'fixtures'/case/'source.yuv',dtype='<u2',mode='r',shape=(240,W*H*3//2))
decoded=ROOT/'parent/scores'/case/(tag+'-decoded.mkv');proc=texture.reader(decoded)
rows=[]
try:
    for n in range(240):
        raw=proc.stdout.read(W*H*3);assert len(raw)==W*H*3
        if n not in byframe:continue
        sy=source[n,:W*H].reshape(H,W).astype(float)/4
        ey=np.frombuffer(raw,dtype='<u2')[:W*H].reshape(H,W).astype(float)/4
        for r in byframe[n]:
            xx,yy=r['x'],r['y'];sl=np.s_[yy:yy+32,xx:xx+32]
            for axis,origin in [(1,xx),(0,yy)]:
                sg=np.diff(sy[sl],axis=axis);eg=np.diff(ey[sl],axis=axis)
                for grid in (8,16):
                    boundary=(np.arange(1,32)+origin)%grid==0
                    if axis==1:mask=np.broadcast_to(boundary[None,:],sg.shape)
                    else:mask=np.broadcast_to(boundary[:,None],sg.shape)
                    v={}
                    for name,m in [('boundary',mask),('interior',~mask)]:
                        v[name]={'pixels':int(m.sum()),'source_abs_gradient':float(np.abs(sg[m]).mean()),
                                 'target_abs_gradient':float(np.abs(eg[m]).mean()),
                                 'gradient_error_mse':float(((eg[m]-sg[m])**2).mean())}
                    b,i=v['boundary'],v['interior']
                    rows.append({'frame':n,'x':xx,'y':yy,'kind':r['kind'],'axis':axis,'grid':grid,**v,
                        'source_compensated_boundary_excess':(b['target_abs_gradient']-b['source_abs_gradient'])-(i['target_abs_gradient']-i['source_abs_gradient'])})
finally:proc.stdout.close();proc.wait()
assert proc.returncode==0
assert len(rows)==4*len(controls['tiles'])
summary={}
for kind in ('all','quiet','flat_texture','edge','other'):
    summary[kind]={}
    for grid in (8,16):
        pool=[r for r in rows if (kind=='all' or r['kind']==kind) and r['grid']==grid]
        values=[r['source_compensated_boundary_excess'] for r in pool]
        summary[kind][grid]={'tile_axis_samples':len(pool),'boundary_excess_mean':float(np.mean(values)),
            'boundary_excess_p95':float(np.percentile(values,95)),
            **{name:{metric:float(np.average([r[name][metric] for r in pool],weights=[r[name]['pixels'] for r in pool]))
                     for metric in ('source_abs_gradient','target_abs_gradient','gradient_error_mse')}
               for name in ('boundary','interior')}}
x.dump(d/'block-edges.json',{'scope':'Frozen source-defined tiles at15 frames; global8/16grid alignment is descriptive, not proof of a visible block artifact or a new acceptance gate.',
    'controls':x.fingerprint(d/'controls.json'),'source':source_prov,'decoded':x.fingerprint(decoded),
    'script':x.fingerprint(__file__),'summary':summary,'tiles':rows,
    'grid16_caveat':'The16-grid interior includes8-grid boundaries; not an independent16-only estimate.'})
print(case,tag,'source-compensated grid diagnostics complete')
