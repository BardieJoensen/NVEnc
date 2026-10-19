#!/usr/bin/env python3
"""Lossless10bit synchronized crop clips, with every panel independently verified."""
import sys,json
from study import ROOT,x
case=sys.argv[1];timebase='1001/24000' if case=='e04' else '1/24';d=ROOT/case;v=json.loads((d/'visuals.json').read_text());cx,cy,w,h=v['crop_xywh'];paths=v['paths'];labels=v['labels'];cmd=['/usr/bin/ffmpeg','-v','error','-y'];graph=[]
for p in paths:cmd+=['-threads','4','-i',p]
for i,label in enumerate(labels):graph.append(f'[{i}:v]trim=end_frame=240,settb={timebase},setpts=N,crop={w}:{h}:{cx}:{cy},format=yuv420p10le,pad=iw:ih+36:0:36:black,drawtext=expansion=none:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text={label}:fontcolor=white:fontsize=16:x=6:y=8[v{i}]')
graph+=['[v0][v1]hstack=2[top]','[v2][v3]hstack=2[bottom]','[top][bottom]vstack=2[out]']
out=d/'quantization-synchronized-10bit.mkv';cmd+=['-filter_complex_threads','2','-filter_complex',';'.join(graph),'-map','[out]','-frames:v','240','-an','-c:v','ffv1','-level','3','-coder','1','-context','1','-slices','16','-threads','4','-pix_fmt','yuv420p10le',*x.COLOR,out];x.run(cmd,d,'native-synchronized')
checks=[]
for i,p in enumerate(paths):
 a=x.hashes(['ffmpeg','-v','error','-threads','4','-i',p,'-vf',f'crop={w}:{h}:{cx}:{cy}','-frames:v','240','-pix_fmt','yuv420p10le'])
 ox=i%2*w;oy=i//2*(h+36)+36
 b=x.hashes(['ffmpeg','-v','error','-threads','4','-i',out,'-vf',f'crop={w}:{h}:{ox}:{oy}','-frames:v','240','-pix_fmt','yuv420p10le'])
 assert len(a)==240 and a==b,(case,i,len(a),len(b),next((j for j,(aa,bb) in enumerate(zip(a,b)) if aa!=bb),None));checks.append({'label':labels[i],'all240_10bit_crop_hashes_exact':True,'hashes':a})
x.dump(d/'native-clip-validation.json',{'panels':checks,'codec':'FFV1','pixel_format':'yuv420p10le','playback_observed':False});print(case,'all4 panels /240frames exact10bit')
