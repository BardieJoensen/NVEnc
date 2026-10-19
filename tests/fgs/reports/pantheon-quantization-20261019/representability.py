#!/usr/bin/env python3
"""Same-frame held-out matched-input screen; no new estimator is fitted."""
import sys,json
import numpy as np
from scipy.ndimage import gaussian_filter
from study import ROOT,OLD,x
from texture import desc,corr
W,H=1920,1080
def mm(case,name):return np.memmap(ROOT/case/(name+'.yuv'),dtype='<u2',mode='r',shape=(240,W*H*3//2))
def y(m,n):return m[n,:W*H].reshape(H,W)
def screen(case):
 s,b=mm(case,'source'),mm(case,'base');old=json.loads((OLD/case/'a-heldout-controls.json').read_text())['tiles'];out=[]
 for n in sorted(set(r['frame'] for r in old)):
  rows=[r for r in old if r['frame']==n];qs=[r for r in rows if r['kind']=='quiet'];ts=[r for r in rows if r['kind']=='flat_texture' and r['source']['hf_sigma']>.4 and r['base']['hf_sigma']<r['source']['hf_sigma']*.5]
  sy=y(s,n).astype(float)/4;by=y(b,n)
  def stats(r):
   xx,yy=r['x'],r['y'];z=by[yy:yy+32,xx:xx+32];h=np.bincount(z.flatten(),minlength=1024)/z.size;return h
  hist={id(r):stats(r) for r in qs+ts}
  for a in qs:
   for t in ts:
    if abs(a['base']['mean']-t['base']['mean'])>.5:continue
    overlap=float(np.minimum(hist[id(a)],hist[id(t)]).sum())
    if overlap<.5:continue
    pair={'frame':n,'quiet':a,'texture':t,'exact_10bit_luma_histogram_overlap':overlap}
    for label,r in [('quiet',a),('texture',t)]:
     xx,yy=r['x'],r['y'];sl=np.s_[yy:yy+32,xx:xx+32];ss=sy[sl];bb=by[sl].astype(float)/4
     z=gaussian_filter(ss,2);prev=y(s,max(0,n-1)).astype(float)[sl]/4;next=y(s,min(239,n+1)).astype(float)[sl]/4
     pair[label+'_diagnostic']={'source':desc(ss),'base':desc(bb),'source_temporal_hf_corr':[corr(x.high_pass(ss),x.high_pass(prev)),corr(x.high_pass(ss),x.high_pass(next))], 'source_smoothed_motion':[float(np.abs(z-gaussian_filter(prev,2)).mean()),float(np.abs(z-gaussian_filter(next,2)).mean())], 'base_codes':{str(i):float(v) for i,v in enumerate(hist[id(r)]) if v},'base_near_clipping_fraction':float(np.mean((bb<17)|(bb>234)))}
    out.append(pair)
 out.sort(key=lambda p:(p['exact_10bit_luma_histogram_overlap'],p['texture']['source']['hf_sigma']/max(.01,p['quiet']['source']['hf_sigma'])),reverse=True)
 x.dump(ROOT/case/'representability-pairs.json',out)
 print(case,'pairs',len(out),json.dumps(out[:2]),flush=True)
if __name__=='__main__':
 for c in ('e05-1440','e05-1460','e04','e05-1420'):screen(c)
