#!/usr/bin/env python3
import sys,json,numpy as np
from study import ROOT,x
import texture
case,tag=sys.argv[1:];d=ROOT/case
r=x.score(case,d/(tag+'.mkv'),tag,grain=0)
texture.analyze(case,tag,d/(tag+'-decoded.mkv'))
# Independent decoded final samples must equal application reconstruction, all planes/frames.
a=np.memmap(d/(tag+'-recon.yuv'),dtype='<u2',mode='r',shape=(336,1920*1080*3//2))
p=texture.reader(d/(tag+'-decoded.mkv'));exact=[]
try:
 for n in range(240):
  b=p.stdout.read(1920*1080*3);assert len(b)==1920*1080*3;exact.append(bool(np.array_equal(np.frombuffer(b,dtype='<u2'),a[n+96])))
finally:p.stdout.close();p.wait()
assert all(exact)
x.dump(d/(tag+'-decoder-validation.json'),{'all240_allplanes_exact':True,'app_to_dav1d':True})
