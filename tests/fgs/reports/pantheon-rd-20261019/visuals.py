#!/usr/bin/env python3
"""Native-pixel stills and exact, synchronized 10-bit source/candidate crop clips."""
import json
from pathlib import Path
import sys
from analyze import ROOT, x, BOXES

case,tag=sys.argv[1:];d=ROOT/'parent/visuals'/case/tag;d.mkdir(parents=True,exist_ok=False)
src=ROOT/'fixtures'/case/'ref.mkv';enc=ROOT/'parent/scores'/case/(tag+'-decoded.mkv')
timebase='1001/24000' if case=='e04' else '1/24'
frame=134 if case=='e04' else 120
boxes={**BOXES[case]}
if case=='e05-1440':boxes['face']=[160,600,500,480]
receipt={'playback_observed':False,'frame':frame,'paths':[str(src),str(enc)],'artifacts':{}}
for name,(cx,cy,w,h) in boxes.items():
    graph=[]
    for i,label in enumerate(['Original',tag]):
        graph.append(f'[{i}:v]trim=end_frame=240,settb={timebase},setpts=N,crop={w}:{h}:{cx}:{cy},format=yuv420p10le,pad=iw:ih+36:0:36:black,drawtext=expansion=none:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text={label}:fontcolor=white:fontsize=16:x=6:y=8[v{i}]')
    graph.append('[v0][v1]hstack=2[out]')
    clip=d/(name+'.mkv')
    cmd=['/usr/bin/ffmpeg','-v','error','-threads','4','-i',src,'-threads','4','-i',enc,
         '-filter_complex_threads','2','-filter_complex',';'.join(graph),'-map','[out]',
         '-frames:v','240','-an','-c:v','ffv1','-level','3','-coder','1','-context','1','-slices','16',
         '-threads','4','-pix_fmt','yuv420p10le',*x.COLOR,clip]
    x.run(cmd,d,name+'-clip')
    checks=[]
    for i,p in enumerate([src,enc]):
        a=x.hashes(['/usr/bin/ffmpeg','-v','error','-threads','4','-i',p,'-vf',f'crop={w}:{h}:{cx}:{cy}',
                    '-frames:v','240','-pix_fmt','yuv420p10le'])
        b=x.hashes(['/usr/bin/ffmpeg','-v','error','-threads','4','-i',clip,'-vf',f'crop={w}:{h}:{i*w}:36',
                    '-frames:v','240','-pix_fmt','yuv420p10le'])
        assert len(a)==240 and a==b
        checks.append({'label':['original',tag][i],'all240_10bit_crop_hashes_exact':True,'hashes':a})
    still=d/(name+'.png')
    x.run(['/usr/bin/ffmpeg','-v','error','-threads','4','-i',clip,'-vf',
           f'select=eq(n\\,{frame}),scale=in_color_matrix=bt709:in_range=tv:out_range=pc,format=rgb24',
           '-frames:v','1',still],d,name+'-still')
    receipt['artifacts'][name]={'xywh':[cx,cy,w,h],'panels':checks,'clip':x.fingerprint(clip),
                               'still':x.fingerprint(still),'still_conversion':'10-bit limited BT709 to8-bit RGB; native pixels'}
x.dump(d/'validation.json',receipt)
print(case,tag,'all panels/all240 frames exact10bit; no playback claimed')
