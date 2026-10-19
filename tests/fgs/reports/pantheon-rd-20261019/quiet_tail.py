#!/usr/bin/env python3
"""Outcome-selected quiet stress crops; preserve the separate source-only control."""
import json
import sys
from analyze import ROOT, x

case=sys.argv[1];assert case in ('e04','e05-1440')
d=ROOT/'parent/playback'/case
prior=json.loads((d/'validation.json').read_text())
mapping=json.loads((d/'viewer-key.json').read_text())
summary=ROOT/'parent/summary/results.json'
rows=json.loads(summary.read_text())['arms']
r=next(r for r in rows if r['case']==case and r['tag']=='x264-search11-4x1')
tile=r['quiet_hf_signed_delta']['worst_tile']
cx=max(0,min(1664,(tile['x']-96)//2*2));cy=max(0,min(952,(tile['y']-48)//2*2))
w,h=256,128;clip=d/'quiet-tail-context.mkv';assert not clip.exists()
arms={name:ROOT/'parent/scores'/case/(name+'-decoded.mkv') for name in mapping.values() if name!='source'}
arms['source']=ROOT/'fixtures'/case/'ref.mkv'
for name,p in arms.items():assert x.fingerprint(p)==prior['upstream'][name]['input']
fps=24000/1001 if case=='e04' else 24;tb='1001/24000' if case=='e04' else '1/24'
argv=['/usr/bin/ffmpeg','-v','error'];graph=[]
for i,(label,name) in enumerate(mapping.items()):
    argv+=['-threads','4','-i',arms[name]]
    graph.append(f'[{i}:v]trim=end_frame=240,settb={tb},setpts=N,crop={w}:{h}:{cx}:{cy},format=yuv420p10le,pad=iw:ih+36:0:36:black,drawtext=expansion=none:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text={label}:fontcolor=white:fontsize=18:x=8:y=8[v{i}]')
graph.append(''.join(f'[v{i}]' for i in range(len(mapping)))+f'hstack=inputs={len(mapping)}[out]')
argv+=['-filter_complex_threads','2','-filter_complex',';'.join(graph),'-map','[out]',
       '-frames:v','240','-an','-c:v','ffv1','-level','3','-coder','1','-context','1',
       '-slices','16','-threads','4','-pix_fmt','yuv420p10le',*x.COLOR,clip]
x.run(argv,d,'quiet-tail-context-clip')
checks=[]
for i,(label,name) in enumerate(mapping.items()):
    a=x.hashes(['/usr/bin/ffmpeg','-v','error','-threads','4','-i',arms[name],'-vf',f'crop={w}:{h}:{cx}:{cy}','-frames:v','240','-pix_fmt','yuv420p10le'])
    b=x.hashes(['/usr/bin/ffmpeg','-v','error','-threads','4','-i',clip,'-vf',f'crop={w}:{h}:{i*w}:36','-frames:v','240','-pix_fmt','yuv420p10le'])
    assert len(a)==240 and a==b
    checks.append({'label':label,'all240_allplanes_exact':True,'hashes':a})
x.dump(d/'quiet-tail-validation.json',{'selection':'outcome-selected maximum signed quiet HF excess; post-hoc stress diagnostic, not a new gate or confirmatory sample',
    'summary':x.fingerprint(summary),'prior_playback_validation':x.fingerprint(d/'validation.json'),
    'tile':tile,'scored_frame':tile['frame'],'scored_seconds':tile['frame']/fps,
    'full_stream_seconds':(96+tile['frame'])/fps,'context_xywh':[cx,cy,w,h],
    'tile_position_in_each_panel':[tile['x']-cx,tile['y']-cy+36,32,32],
    'clip':x.fingerprint(clip),'panels':checks,'script':x.fingerprint(__file__),'playback_observed':False})
with (d/'README.md').open('a') as f:
    f.write(f'\nAdditional stress clip: quiet-tail-context.mkv. This is explicitly post-hoc: the maximum signed quiet HF excess among the frozen source-quiet tiles. It is not a new acceptance gate or an unbiased confirmation. Inspect around {tile["frame"]/fps:.3f}s (scored frame {tile["frame"]}), tile ({tile["x"]},{tile["y"]}); within each labeled panel the tile starts ({tile["x"]-cx},{tile["y"]-cy+36}). The same blind labels apply. Assess new noise, boiling or grid structure, retaining the original quiet-context comparison too.\n')
print(case,'post-hoc quiet-tail panels verified; no playback observed')
