#!/usr/bin/env python3
"""Audit private FP controls before interpreting intermediate quantizer effects."""
import json
import sys
import numpy as np
from analyze import ROOT, read_tu, paired, masked, BOXES, W, H

case=sys.argv[1];frame=int(sys.argv[2]);delta=int(sys.argv[3]) if len(sys.argv)>3 else 8
assert delta in (8,12)
tag='fp-private' if delta==8 else 'fp-q20-private'
control=ROOT/'worker'/(case+'-q32-control')
base=ROOT/'parent'/(case+f'-q32-control-frame{frame}')
saved=np.load(base.with_suffix('.npz'));src=saved['source'];valid=saved['quantizer_run']
maps={f'fp_minus{d}':saved['baseline'].copy() for d in (0,delta,16)}
counts=0;qs={};cover=np.zeros((H,W),np.int16)
for path in sorted((ROOT/'parent'/(case+'-'+tag)/'detail').glob(f'{frame+96:04d}-*.tu')):
    r=read_tu(path);old=read_tu(control/'detail'/path.name);m=r['meta']
    assert m==old['meta']
    for k in ['input','predictor','prediction_residual','private_forward','actual_recon']:
        assert np.array_equal(r[k],old[k]),k
    xx,yy,w,h=[m[k] for k in ['x','y','w','h']];sl=np.s_[yy:min(yy+h,H),xx:min(xx+w,W)];hh,ww=cover[sl].shape;cover[sl]+=1
    if 'actual_forward' not in r:continue
    assert np.array_equal(r['fp0_qcoeff'],r['initial_qcoeff'])
    assert np.array_equal(r['fp0_dqcoeff'],r['initial_dqcoeff'])
    assert np.array_equal(r['fp0_recon'],r['initial_recon'])
    assert r['fp0_meta']['eob']==int(r['initial_eob'][0]);counts+=1
    for k,offset in enumerate((0,delta,16)):
        q=r[f'fp{k}_meta']['q'];assert q==max(1,m['effective_qindex']-offset)
        qs.setdefault(f'fp_minus{offset}',set()).add(q)
        maps[f'fp_minus{offset}'][sl]=r[f'fp{k}_recon'].reshape(h,w)[:hh,:ww]/4
assert np.all(cover==1)
out={'case':case,'frame':frame,'private_FP_current_q_exact_initial_FP':True,'validated_tus':counts,
     'qindices':{k:sorted(v) for k,v in qs.items()},'roi':{},'controls':{}}
for name,(xx,yy,w,h) in BOXES[case].items():
    sl=np.s_[yy:yy+h,xx:xx+w];s=src[sl]
    out['roi'][name]={'whole_roi':{k:paired(s,z[sl]) for k,z in {'source':src,**maps}.items()},
                     'quantizer_run_neighborhoods':{k:masked(s,z[sl],valid[sl]) for k,z in {'source':src,**maps}.items()}}
controls=json.loads(base.with_suffix('.json').read_text())['control_tiles']
for kind in ('quiet','edge','flat_texture'):
    rows=[]
    for tile in controls:
        if tile['kind']!=kind:continue
        xx,yy,w,h=tile['xywh'];sl=np.s_[yy:yy+h,xx:xx+w];s=src[sl]
        rows.append({'xywh':tile['xywh'],'source':paired(s,s),**{k:paired(s,z[sl]) for k,z in maps.items()}})
    out['controls'][kind]=rows
dest=ROOT/'parent'/(case+f'-{tag}-frame{frame}.json')
with dest.open('x') as f:json.dump(out,f,indent=2);f.write('\n')
np.savez_compressed(dest.with_suffix('.npz'),source=src,**maps)
print(json.dumps({k:v for k,v in out.items() if k!='controls'},indent=2))
