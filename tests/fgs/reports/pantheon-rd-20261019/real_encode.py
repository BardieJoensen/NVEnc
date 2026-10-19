#!/usr/bin/env python3
"""Real diagnostic allocation+FP-retention arm; actual video packets determine rate."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import numpy as np
from probe import ROOT, sha
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'pantheon-independent-20261019'))
import investigate as x
from texture import BOXES

case,tag,request,q=sys.argv[1],sys.argv[2],int(sys.argv[3]),int(sys.argv[4])
assert case in ('e04','e05-1440') and q in (20,24)
out=ROOT/'parent/real'/case/tag;out.mkdir(parents=True,exist_ok=False)
(out/'trace').mkdir();(out/'detail').mkdir()
xx,yy,w,h=next(iter(BOXES[case].values()))
alloc=np.full((336,17,30),-1,dtype='<i2')
alloc[:,yy//64:(yy+h+63)//64,xx//64:(xx+w+63)//64]=q
alloc.tofile(out/'absolute-map.bin')
mapmeta={'shape':list(alloc.shape),'dtype':'<i2','qindex':q,'scored_roi_xywh':[xx,yy,w,h],
         'aligned_roi_xywh':[xx//64*64,yy//64*64,((xx+w+63)//64-xx//64)*64,((yy+h+63)//64-yy//64)*64],
         'all336_frames':True,'production_classifier':False,'keep_FP_same_selected_SBs':True}
x.dump(out/'absolute-map.json',mapmeta)
old=Path('/media/merged-storage/cold-storage/docker-apps/pantheon-causal-20261019')
cmd=json.loads((old/case/'b-trace-command.json').read_text())['argv']
cmd[6]=str(ROOT/'parent-source/Bin/Release/SvtAv1EncApp')
cmd[cmd.index('-i')+1]=str(ROOT/'fixtures'/case/'input10.y4m')
cmd[cmd.index('-b')+1]=str(out/'out.ivf');cmd[cmd.index('-o')+1]=str(out/'recon.yuv')
cmd[cmd.index('--tbr')+1]=str(request);cmd+=['--max-tx-size','32']
extra={'PANTHEON_ABSOLUTE_Q_MAP':str(out/'absolute-map.bin'),'PANTHEON_KEEP_FP_MAP':str(out/'absolute-map.bin'),
       'PANTHEON_KEEP_FP_LOG':str(out/'retention.csv'),'PANTHEON_TRACE_DIR':str(out/'trace'),
       'PANTHEON_TRACE_IMAGES_OFF':'1','PANTHEON_DETAIL_DIR':str(out/'detail'),
       'PANTHEON_DETAIL_POC':',184,216,222,228,230,234,240,' if case=='e04' else ',120,212,214,216,218,220,'}
env={k:v for k,v in os.environ.items() if not k.startswith('PANTHEON_')};env.update(extra)
start=time.monotonic()
with (out/'encode.log').open('wb') as log:r=subprocess.run(cmd,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT)
record={'argv':cmd,'cwd':str(out),'env':extra,'seconds':time.monotonic()-start,'returncode':r.returncode,
        'binary_sha256':sha(Path(cmd[6])),'map_sha256':sha(out/'absolute-map.bin')}
x.dump(out/'command.json',record)
assert r.returncode==0,(out/'encode.log').read_text()[-4000:]
# Every selected final block must realize the absolute target, over all scored frames.
selected=0
for poc in range(96,336):
    target_count=0
    for line in (out/'trace'/f'blocks-{poc:04d}-a0-o0.csv').read_text().splitlines():
        v=list(map(int,line.split(',')))
        if alloc[poc,v[2]//64,v[1]//64]>=0:
            assert v[7]==q,(poc,v)
            target_count+=1
    assert target_count>0
    selected+=target_count
logs=[list(map(int,line.split(','))) for line in (out/'retention.csv').read_text().splitlines()]
assert logs and all(v[3]==q and v[6]==v[7] for v in logs)
assert all(alloc[v[0],v[2]//64,v[1]//64]==q for v in logs)
x.run(['ffmpeg','-v','error','-i',out/'out.ivf','-c','copy',out/'out.mkv'],out,'remux')
fps=json.loads((ROOT/'fixtures'/case/'validity.json').read_text())['fps']
packets=x.packets(out/'out.mkv');selected_packets=[p for p in packets if 96<=round(float(p['pts_time'])*fps)<336]
assert len(packets)==336 and len(selected_packets)==240
mbps=sum(int(p['size']) for p in selected_packets)*8/(240/fps)/1e6
x.dump(out/'validation.json',{'all240_selected_blocks_actual_qindex':q,'selected_blocks_checked':selected,
       'FP_retention_calls':len(logs),'all_FP_coefficient_and_dequant_hashes_equal':True,
       'actual_mbps':mbps,'selected_packets':selected_packets,'ivf_sha256':sha(out/'out.ivf')})
print(case,tag,'actual Mbps',mbps,'realized qindex',q,'retention calls',len(logs),flush=True)
