#!/usr/bin/env python3
"""Native legal grain seed ensemble on same-frame matched-input controls."""
import json,subprocess,sys,hashlib
import numpy as np
from scipy.ndimage import minimum_filter,maximum_filter
from study import ROOT,OLD,HERE,x
from representability import mm,y
from texture import desc
CASES=[('e05-1460',72,[1640,152],[1592,968],72),('e04',184,[536,392],[632,296],102)]
REPS=32

def build():
 src=(HERE.parent/'pantheon-causal-20261019/apply_grain.c').read_text()
 src=src.replace('if(frame_no>=skip && frame_no<skip+count){','if(frame_no>=skip && frame_no<skip+count){\n      for(int repeat=0;repeat<32;repeat++){')
 src=src.replace('    frame_no++;dav1d_picture_unref(p);','    }\n    frame_no++;dav1d_picture_unref(p);')
 (ROOT/'grain_probe.c').write_text(src)
 flags=subprocess.check_output(['pkg-config','--cflags','--libs','dav1d'],text=True).split()
 x.run(['cc','-O2','-Wall','-Wextra',ROOT/'grain_probe.c','-o',ROOT/'grain_probe',*flags],ROOT,'grain-probe-build')

def run():
 build();results=[]
 for case,n,q,t,code in CASES:
  d=ROOT/case;S=y(mm(case,'source'),n).astype(float)/4;B=y(mm(case,'base'),n).astype(float)/4
  sourcehp=x.high_pass(S);flat=(minimum_filter(B,3)==maximum_filter(B,3))&(B*4==code)
  yy,xx=np.indices(B.shape);flat&=(xx%32>=2)&(yy%32>=2) # omit overlap bands
  controls={}
  for name,(cx,cy) in [('quiet',q),('texture',t)]:
   sl=np.s_[cy+2:cy+30,cx+2:cx+30];mask=flat[sl];hs=sourcehp[cy+1:cy+29,cx+1:cx+29]
   controls[name]={'xy':[cx,cy],'matched_constant_neighborhood_pixels':int(mask.sum()),'source_conditional_hf':float(hs[mask].std()*np.sqrt(8/5)),'source_roi':desc(S[cy:cy+32,cx:cx+32]),'base_roi':desc(B[cy:cy+32,cx:cx+32])}
  old=json.loads((OLD/case/'grain-fit.json').read_text());m=next(m for m in old['models'] if m['start']<=n<m['end']);ar=m['channels'][0]['coeff']
  row={'case':case,'frame':n,'base_10bit_code':code,'controls':controls,'probes':[]}
  for shape,coeff,lag in [('white',[0]*24,0),('prior_ar',ar,3)]:
   for scale in [16,32,64]:
    tag=f'represent-{shape}-{scale}';model=d/(tag+'.txt');lines=[]
    for seed in range(REPS):
     v=[(12345+seed*7919)%65536,10,lag,7,0,2,0,scale,255,scale]+coeff+[0]+[0]*25+[0]+[0]*25
     lines.append(' '.join(map(str,v)))
    model.write_text('\n'.join(lines)+'\n');raw=d/(tag+'.yuv')
    x.run([ROOT/'grain_probe',d/'fixed-picture.ivf',raw,2,n+96,1,model],d,tag)
    log=(d/(tag+'.log')).read_text();assert 'base_before_after_exact=32' in log
    a=np.memmap(raw,dtype='<u2',mode='r',shape=(REPS,1920*1080*3//2));stats={name:[] for name in controls}
    for seed in range(REPS):
     A=a[seed,:1920*1080].reshape(1080,1920).astype(float)/4
     for name,(cx,cy) in [('quiet',q),('texture',t)]:
      sl=np.s_[cy+2:cy+30,cx+2:cx+30];mask=flat[sl];diff=A[cy:cy+32,cx:cx+32]-B[cy:cy+32,cx:cx+32]
      hp=x.high_pass(A[cy:cy+32,cx:cx+32])[1:-1,1:-1]
      stats[name].append({'roi':desc(A[cy:cy+32,cx:cx+32]),'isolated_grain':desc(diff),'conditional_hf':float(hp[mask].std()*np.sqrt(8/5)),'clip_fraction':float(np.mean((A[sl]<=16)|(A[sl]>=235))),'conditional_endpoint_occupancy':float(np.mean(((A[sl]<=16)|(A[sl]>=235))[mask]))})
    row['probes'].append({'shape':shape,'scale':scale,'seed_count':REPS,'stats':stats,'base_before_after_exact':True})
    # Raw 32-frame ensembles are reproducible; statistics and legal model retained.
    del a;raw.unlink()
  results.append(row);x.dump(d/'representability-native.json',row)
  print(case,json.dumps({'controls':controls,'ensemble_mean_conditional_hf':[{k:p[k] for k in ('shape','scale')}|{name:float(np.mean([r['conditional_hf'] for r in p['stats'][name]])) for name in controls} for p in row['probes']]}),flush=True)
 x.dump(ROOT/'representability-native.json',results)
if __name__=='__main__':run()
