#!/usr/bin/env python3
"""Bounded x264 slow/grain two-pass feasibility control; not an AV1 causal ablation."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from analyze import ROOT, x
from probe import sha
from packet_window import measure, audit

case,tag,request=sys.argv[1],sys.argv[2],int(sys.argv[3]);assert case in ('e04','e05-1440')
aq=float(sys.argv[4]) if len(sys.argv)>4 else .5
assert aq in (.5,1.0)
d=ROOT/'parent/crosscodec'/case/tag;d.mkdir(parents=True,exist_ok=False)
src=ROOT/'fixtures'/case/'input.mkv';ffmpeg='/usr/bin/ffmpeg'
source_stat=x.fingerprint(src)
hashes=[x.hashes([ffmpeg,'-v','error','-threads','4','-i',p,'-frames:v','336','-pix_fmt','yuv420p10le'])
        for p in (src,ROOT/'fixtures'/case/'input10.y4m')]
assert len(hashes[0])==336 and hashes[0]==hashes[1]
x.dump(d/'input-validation.json',{'all336_8bit_input_lift_matches_SVT_input':True,'hashes':hashes[0],
        'input':source_stat,'svt_input':x.fingerprint(ROOT/'fixtures'/case/'input10.y4m')})
common=['nice','-n','10','taskset','-c','0-7',ffmpeg,'-v','info','-threads','4','-i',str(src),
        '-map','0:v:0','-an','-sn','-frames:v','336','-fps_mode','passthrough',
        '-c:v','libx264','-preset','slow','-tune','grain','-b:v',str(request*1000),
        '-threads','4','-pix_fmt','yuv420p','-passlogfile',str(d/'pass'),*x.COLOR]
if aq!=.5:common+=['-x264-params',f'aq-strength={aq}']
records=[]
for phase in (1,2):
    cmd=common+['-pass',str(phase)]+(['-f','null','/dev/null'] if phase==1 else [str(d/'out.mkv')])
    start=time.monotonic()
    with (d/f'pass{phase}.log').open('wb') as log:
        p=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
    records.append({'argv':cmd,'seconds':time.monotonic()-start,'returncode':p.returncode})
    x.dump(d/'command.json',{'passes':records,'ffmpeg':x.fingerprint(ffmpeg),'input':source_stat,
            'aq_strength':aq,'script':x.fingerprint(__file__),
            'scope':'8-bit H264 conventional re-encode, two-pass slow/grain, no synthesis; 336-frame statistics only'})
    assert p.returncode==0,(d/f'pass{phase}.log').read_text()[-3000:]
assert x.fingerprint(src)==source_stat
rate,sel,first=measure(d/'out.mkv',x.CASES[case][2])
probe=x.probe(d/'out.mkv');s=probe['streams'][0]
assert s['codec_name']=='h264' and s['pix_fmt']=='yuv420p' and (s['width'],s['height'])==(1920,1080)
assert [s[k] for k in ['color_range','color_space','color_transfer','color_primaries']]==['tv','bt709','bt709','bt709']
x.dump(d/'validation.json',{'actual_mbps':rate,'selected_packets':sel,'probe':probe,
        'input':source_stat,'output':x.fingerprint(d/'out.mkv'),'seconds_total':sum(r['seconds'] for r in records)})
print(case,tag,'actual',rate,'Mbps; two-pass wall seconds',sum(r['seconds'] for r in records),flush=True)
audit(case,tag)  # A calibration receipt can be valid without passing the target-rate gate.
