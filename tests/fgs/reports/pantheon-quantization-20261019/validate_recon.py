#!/usr/bin/env python3
"""All-plane all-frame independent final decoder verification, no rescoring."""
import subprocess,sys,json
import numpy as np
from study import ROOT,x
case,tag=sys.argv[1:];d=ROOT/case
cmd=['ffmpeg','-v','error','-threads','4','-c:v','libdav1d','-filmgrain','0','-i',str(d/(tag+'.mkv')),'-vf','trim=start_frame=96','-frames:v','240','-pix_fmt','yuv420p10le','-f','rawvideo','-']
p=subprocess.Popen(cmd,stdout=subprocess.PIPE);a=np.memmap(d/(tag+'-recon.yuv'),dtype='<u2',mode='r',shape=(336,1920*1080*3//2));hashes=[]
import hashlib
for n in range(240):
 b=p.stdout.read(1920*1080*3);assert len(b)==1920*1080*3;assert np.array_equal(np.frombuffer(b,dtype='<u2'),a[n+96]);hashes.append(hashlib.sha256(b).hexdigest())
p.stdout.close();assert p.wait()==0
x.dump(d/(tag+'-decoder-validation.json'),{'argv':cmd,'all240_allplanes_exact':True,'app_to_dav1d':True,'frame_sha256':hashes})
print(case,tag,'independent final reconstruction exact all240/allplanes')
