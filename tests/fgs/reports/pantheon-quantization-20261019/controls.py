#!/usr/bin/env python3
"""Whole-window spatial controls, plus region-specific faces/lines at diagnostic frame."""
import sys,json
import numpy as np
from scipy.ndimage import gaussian_filter
from study import ROOT,x
from texture import desc,corr,BOXES
W,H=1920,1080
case,*tags=sys.argv[1:];d=ROOT/case;base='detail' if case=='e04' else 'detail2'
source=np.memmap(d/'source.yuv',dtype='<u2',mode='r',shape=(240,W*H*3//2))
arrays={tag:np.memmap(d/(tag+'-recon.yuv'),dtype='<u2',mode='r',shape=(336,W*H*3//2)) for tag in [base]+tags}
roi=next(iter(BOXES[case].values()))
if (d/'absolute-map.json').exists():roi=json.loads((d/'absolute-map.json').read_text())['aligned_roi_xywh']
rx,ry,rw,rh=roi;rows=[]
for n in range(8,240,16):
 s=source[n,:W*H].reshape(H,W).astype(float)/4;vals={tag:a[n+96,:W*H].reshape(H,W).astype(float)/4 for tag,a in arrays.items()}
 sm=gaussian_filter(s,2);gy,gx=np.gradient(sm);grad=np.hypot(gx,gy)
 for yy in range(8,1040,48):
  for xx in range(8,1880,48):
   sl=np.s_[yy:yy+32,xx:xx+32];ss=s[sl];stats={'source':desc(ss),**{tag:desc(a[sl]) for tag,a in vals.items()}}
   edge=float(np.percentile(grad[sl],95));hf=stats['source']['hf_sigma'];kind='edge' if edge>4 else 'quiet' if edge<.75 and hf<.2 else 'flat_texture' if edge<.75 else 'other'
   stats.update({'frame':n,'x':xx,'y':yy,'kind':kind,'outside_target':not(xx<rx+rw and xx+32>rx and yy<ry+rh and yy+32>ry),'mse':{tag:float(np.mean((a[sl]-ss)**2)) for tag,a in vals.items()}});rows.append(stats)
summary={}
for kind in ['all','quiet','edge','flat_texture','other']:
 for outside in [False,True]:
  pool=[r for r in rows if (kind=='all' or r['kind']==kind) and (not outside or r['outside_target'])];key=kind+('_outside' if outside else '')
  summary[key]={'tiles':len(pool)}
  for tag in arrays:
   ac=[abs(r[tag]['acf1']-r['source']['acf1']) for r in pool if r[tag]['acf1'] is not None and r['source']['acf1'] is not None]
   summary[key][tag]={'mse_mean':float(np.mean([r['mse'][tag] for r in pool])) if pool else None,'mse_p95':float(np.percentile([r['mse'][tag] for r in pool],95)) if pool else None,'hf_abs_error':float(np.mean([abs(r[tag]['hf_sigma']-r['source']['hf_sigma']) for r in pool])) if pool else None,'acf1_abs_error':float(np.mean(ac)) if ac else None}
# Explicit face/line control is only semantically labeled at frame120.
face={}
if case=='e05-1440':
 n=120;sl=np.s_[600:1080,160:660];s=source[n,:W*H].reshape(H,W)[sl].astype(float)/4
 for tag,a in arrays.items():
  z=a[n+96,:W*H].reshape(H,W)[sl].astype(float)/4;sg=np.abs(np.diff(s,axis=1));zg=np.abs(np.diff(z,axis=1));mask=sg>12
  face[tag]={'mse':float(np.mean((z-s)**2)),'edge_gradient_mae':float(abs(zg[mask]-sg[mask]).mean()),'edge_gradient_ratio':float(zg[mask].sum()/sg[mask].sum())}
x.dump(d/'whole-window-controls.json',{'summary':summary,'tiles':rows,'face_frame120_xywh':[160,600,500,480] if face else None,'face':face,'evaluation_frames':list(range(8,240,16)),'note':'Original-defined spatial controls; all 240 frames separately covered by GPU metrics. Oracle target is not a held-out production classifier.'})
print(case,json.dumps(summary),flush=True)
