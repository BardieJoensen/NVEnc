#!/usr/bin/env python3
"""Calibrate only TBR for one absolute-q allocation, maximum six trials."""
import os,sys,json,subprocess
import numpy as np
from study import ROOT,HERE,x
case=sys.argv[1];qtarget=int(sys.argv[2]) if len(sys.argv)>2 else 16;prefix='budget' if qtarget==16 else f'budgetq{qtarget}';mapname='absolute-map.bin' if qtarget==16 else f'absolute{qtarget}-map.bin';d=ROOT/case;target=json.loads((d/'validity.json').read_text())['source_mbps'];request=target*1000
os.environ['PANTHEON_ABSOLUTE_Q_MAP']=str(d/mapname)
mask=np.fromfile(d/mapname,dtype='<i2').reshape(336,510)>=0
rows=[];selected=None;lo=None;hi=None
for i in range(6):
 tag=f'{prefix}{i}';request=max(1,min(100000,round(request)))
 argv=[sys.executable,str(HERE/'encode.py'),case,tag,f'rate:{request}']+(['--max-tx-size','32'] if case=='e05-1440' else [])
 subprocess.run(argv,check=True)
 # Verify realized SB q on EVERY scored frame, not just the diagnostic frame.
 realized=[]
 for n in range(96,336):
  a=np.loadtxt(d/(tag+'-trace')/f'sb-{n:04d}-a0-o0.csv',delimiter=',',ndmin=2)
  assert len(a)==510
  q=a[mask[n,a[:,0].astype(int)],4];assert np.all(q==qtarget),(tag,n,q.min(),q.max());realized.extend(q.tolist())
 actual=json.loads((d/(tag+'-encode.json')).read_text())['rate_mbps'];error=actual/target-1
 row={'tag':tag,'request_kbps':request,'actual_mbps':actual,'relative_error':error,'all240_target_sbs_at_requested_absolute_qindex':True,'absolute_qindex':qtarget};rows.append(row)
 x.dump(d/(prefix+'-calibration.json'),{'target_mbps':target,'trials':rows,'selected':selected})
 if abs(error)<=.01:selected=tag;break
 if error>0:hi=(request,actual)
 else:lo=(request,actual)
 if lo and hi:
  # Interpolate measured bracket; guard against rounding stagnation.
  request=lo[0]+(hi[0]-lo[0])*(target-lo[1])/(hi[1]-lo[1])
 else:request=request*target/actual
 if i>=2 and error>.15:request=max(1,request*.5)
 if request==1 and rows[-1]['request_kbps']==1:break
x.dump(d/(prefix+'-calibration.json'),{'target_mbps':target,'trials':rows,'selected':selected,'note':'Only TBR varied; one map and one encoder configuration. A nonmatched trial is not an equal-size comparison.'})
print(case,'budget selected',selected,flush=True)
