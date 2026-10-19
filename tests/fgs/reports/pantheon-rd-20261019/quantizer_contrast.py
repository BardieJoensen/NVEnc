#!/usr/bin/env python3
"""Round2: fixed exercised-transform FP/B/unquantized reconstruction contrast."""
import json
from pathlib import Path
import sys
import numpy as np
from analyze import ROOT, read_tu, paired, masked, BOXES, W, H

case = sys.argv[1]
frame = 134 if case == 'e04' else 120
base = ROOT/'parent'/(case+f'-q32-control-frame{frame}')
saved = np.load(base.with_suffix('.npz'))
source = saved['source']
maps = {k: saved[v].copy() for k,v in [('final','baseline'), ('initial_FP','retained')]}
maps.update({k:saved['baseline'].copy() for k in ['regular_B_same_q','unquantized_exercised']})
coverage = np.zeros((H,W),np.int16)
for path in sorted((ROOT/'worker'/(case+'-q32-control')/'detail').glob(f'{frame+96:04d}-*.tu')):
    r=read_tu(path); m=r['meta']; xx,yy,w,h=[m[k] for k in ['x','y','w','h']]
    sl=np.s_[yy:min(yy+h,H),xx:min(xx+w,W)]; hh,ww=coverage[sl].shape
    coverage[sl]+=1
    if 'actual_forward' not in r: continue
    assert r['scalar0_meta']['q']==m['effective_qindex']==32
    assert w<=32 and h<=32
    for name,key in [('regular_B_same_q','scalar0_recon'),('unquantized_exercised','unquantized')]:
        maps[name][sl]=r[key].reshape(h,w)[:hh,:ww]/4
assert np.all(coverage==1)
result={'case':case,'frame':frame,'question':'Initial FP versus regular B at identical actual q32; no optimization in either alternative. Unquantized is a diagnostic inverse, not a deployable stream.', 'roi':{}}
for name,(xx,yy,w,h) in BOXES[case].items():
    sl=np.s_[yy:yy+h,xx:xx+w]; s=source[sl]; valid=saved['quantizer_run'][sl]
    result['roi'][name]={'whole_roi':{k:paired(s,z[sl]) for k,z in {'source':source,**maps}.items()},
        'quantizer_run_neighborhoods':{k:masked(s,z[sl],valid) for k,z in {'source':source,**maps}.items()}}
dest=ROOT/'parent'/(case+'-quantizer-contrast.json')
with dest.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
np.savez_compressed(dest.with_suffix('.npz'),source=source,**maps)
print(json.dumps(result,indent=2))
