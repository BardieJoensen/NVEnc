#!/usr/bin/env python3
"""Compile/run QP-state export with bounded-memory, exact-population audit."""
from array import array
import csv
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time

here=Path(__file__).resolve().parent
src=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve();d=out.parent;d.mkdir(parents=True,exist_ok=False)
def sha(p):
    with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
records=[]
def run(cmd,name):
    start=time.monotonic();p=subprocess.run(cmd,capture_output=True,text=True)
    (d/(name+'.stdout')).write_text(p.stdout);(d/(name+'.stderr')).write_text(p.stderr)
    records.append({'argv':list(map(str,cmd)),'seconds':time.monotonic()-start,'returncode':p.returncode})
    assert p.returncode==0,p.stderr
    return p.stdout
flags=shlex.split(run(['pkg-config','--cflags','--libs','libavformat','libavcodec','libavutil'],'compile-flags'))
versions={lib:run(['pkg-config','--modversion',lib],lib+'-version').strip() for lib in ['libavformat','libavcodec','libavutil']}
include=Path(run(['pkg-config','--variable=includedir','libavutil'],'include-dir').strip())
header=include/'libavutil/video_enc_params.h'
binary=d/'h264_qp';input_hash=sha(src)
run(['cc','-O2','-Wall','-Wextra',str(here/'h264_qp.c'),'-o',str(binary),*flags],'compile')
run(['ldd',str(binary)],'linked-libraries')
run([str(binary),str(src),str(out)],'export')
probe=json.loads(run(['ffprobe','-v','error','-select_streams','v:0','-show_streams','-show_frames',
    '-show_entries','stream=codec_name,width,height,pix_fmt,time_base,avg_frame_rate:frame=pts,key_frame,pict_type',
    '-of','json',str(src)],'frame-probe'))
s=probe['streams'][0];assert (s['codec_name'],s['width'],s['height'],s['pix_fmt'])==('h264',1920,1080,'yuv420p')
assert len(probe['frames'])==336
qp=array('b',[0])*(336*8160);seen=bytearray(336*8160);pts={};rows=0
with out.open() as f:
    for r in csv.DictReader(f):
        fi,p,q,dq,xx,yy,w,h,eff,typ,nb=[int(r[k]) for k in ['frame','pts','qp','delta_qp','src_x','src_y','w','h','effective_qp','type','nb_blocks']]
        assert 0<=fi<336 and (w,h,typ,nb)==(16,16,1,8160)
        assert 0<=xx<1920 and 0<=yy<1088 and xx%16==yy%16==0
        assert eff==q+dq and 0<=eff<=51
        k=fi*8160+(yy//16)*120+xx//16;assert not seen[k];seen[k]=1;qp[k]=eff;rows+=1
        if fi in pts:assert pts[fi]==p
        else:pts[fi]=p
assert rows==336*8160 and all(seen) and set(pts)==set(range(336))
fps=Fraction(s['avg_frame_rate']);tb=Fraction(s['time_base'])
assert all(pts[i]==probe['frames'][i]['pts'] and abs(float((pts[i]-pts[0])*tb*fps)-i)<.03 for i in range(336))
assert sha(src)==input_hash
with (d/'qp-state.i8').open('wb') as f:qp.tofile(f)
receipt={'commands':records,'input':{'path':str(src),'sha256':input_hash},'source_sha256':sha(here/'h264_qp.c'),
    'wrapper_sha256':sha(__file__),'binary_sha256':sha(binary),'header':{'path':str(header),'sha256':sha(header)},
    'library_versions':versions,'rows':rows,'frames':336,'unique_complete_grids':True,'blocks_per_frame':8160,
    'map':{'path':str(d/'qp-state.i8'),'shape':[336,68,120],'dtype':'int8','sha256':sha(d/'qp-state.i8')},
    'probe':probe,'scope':'QP_Y decoder state; skipped MBs do not establish residual quantization execution. Crop padded bottom8 rows to visible1080 for area statistics.'}
(d/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print('Validated',rows,'unique MB states; all336 display-order frames and padded grids complete')
