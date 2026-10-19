#!/usr/bin/env python3
"""Prepare blinded native-pixel loops and a full original-derived reference."""
import hashlib
import json
import os
import random
import sys
from analyze import ROOT, BOXES, x

case=sys.argv[1];assert case in ('e04','e05-1440')
d=ROOT/'parent/playback'/case;d.mkdir(parents=True,exist_ok=False)
tag='x264-search11-4x1';scores=ROOT/'parent/scores'/case
arms={'source':ROOT/'fixtures'/case/'ref.mkv',tag:scores/(tag+'-decoded.mkv')}
if case=='e05-1440':arms['x264-search11-3x1']=scores/'x264-search11-3x1-decoded.mkv'
fresh=ROOT/'fixtures'/case/'fresh-validation.json'
fresh_data=json.loads(fresh.read_text())
assert fresh_data['all240_allplanes_match_archived_original']
source_hashes=x.hashes(['/usr/bin/ffmpeg','-v','error','-threads','4','-i',arms['source'],
                       '-frames:v','240','-pix_fmt','yuv420p10le'])
assert len(source_hashes)==240 and source_hashes==fresh_data['frames']['ref.mkv']
upstream={'source':{'input':x.fingerprint(arms['source']),'fresh_validation':x.fingerprint(fresh),
                    'all240_allplanes_exact':True}}
full_candidates={}
for name in arms:
    if name!='source':
        receipt_path=ROOT/'parent/crosscodec'/case/name/'decoder-validation.json'
        receipt=json.loads(receipt_path.read_text())
        assert receipt['all336_allplanes_cpu_NVDEC_exact']
        identity_path=scores/(name+'-score-identity.json')
        identity=json.loads(identity_path.read_text())
        assert x.fingerprint(arms[name])==identity['distorted']
        assert x.fingerprint(arms['source'])['sha256']==identity['reference']['sha256']
        full_candidates[name]=x.fingerprint(ROOT/'parent/crosscodec'/case/name/'out.mkv')
        assert full_candidates[name]==receipt['output']
        decoded_hashes=x.hashes(['/usr/bin/ffmpeg','-v','error','-threads','4','-i',arms[name],
                                '-frames:v','240','-pix_fmt','yuv420p10le'])
        assert len(decoded_hashes)==240 and decoded_hashes==receipt['hashes'][96:336]
        upstream[name]={'input':x.fingerprint(arms[name]),'score_identity':x.fingerprint(identity_path),
                        'decoder_validation':x.fingerprint(receipt_path),'all240_allplanes_exact':True}
names=list(arms);random.Random(int(hashlib.sha256(case.encode()).hexdigest()[:8],16)).shuffle(names)
mapping={chr(65+i):name for i,name in enumerate(names)}
fps=24000/1001 if case=='e04' else 24;tb='1001/24000' if case=='e04' else '1/24'
quiet_frame=88 if case=='e04' else 24
frozen=ROOT/'parent'/f'{case}-frame{quiet_frame}-frozen-controls.json'
q=next(r for r in json.loads(frozen.read_text())['tiles'] if r['kind']=='quiet')
qx,qy,_,_=q['xywh'];cx=max(0,min(1664,(qx-96)//2*2));cy=max(0,min(952,(qy-48)//2*2))
boxes={**BOXES[case],'quiet-context':[cx,cy,256,128]}
if case=='e05-1440':boxes['face']=[160,600,500,480]
checks={}
for region,(xx,yy,w,h) in boxes.items():
    argv=['/usr/bin/ffmpeg','-v','error']
    for name in names:argv+=['-threads','4','-i',arms[name]]
    graph=[]
    for i,label in enumerate(mapping):
        graph.append(f'[{i}:v]trim=end_frame=240,settb={tb},setpts=N,crop={w}:{h}:{xx}:{yy},format=yuv420p10le,pad=iw:ih+36:0:36:black,drawtext=expansion=none:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text={label}:fontcolor=white:fontsize=18:x=8:y=8[v{i}]')
    graph.append(''.join(f'[v{i}]' for i in range(len(names)))+f'hstack=inputs={len(names)}[out]')
    clip=d/(region+'.mkv')
    argv+=['-filter_complex_threads','2','-filter_complex',';'.join(graph),'-map','[out]',
           '-frames:v','240','-an','-c:v','ffv1','-level','3','-coder','1','-context','1',
           '-slices','16','-threads','4','-pix_fmt','yuv420p10le',*x.COLOR,clip]
    x.run(argv,d,region+'-clip')
    panel_checks=[]
    for i,name in enumerate(names):
        original=x.hashes(['/usr/bin/ffmpeg','-v','error','-threads','4','-i',arms[name],'-vf',f'crop={w}:{h}:{xx}:{yy}','-frames:v','240','-pix_fmt','yuv420p10le'])
        rendered=x.hashes(['/usr/bin/ffmpeg','-v','error','-threads','4','-i',clip,'-vf',f'crop={w}:{h}:{i*w}:36','-frames:v','240','-pix_fmt','yuv420p10le'])
        assert len(original)==240 and original==rendered
        panel_checks.append({'label':chr(65+i),'all240_allplanes_exact':True,'hashes':original})
    checks[region]={'clip':x.fingerprint(clip),'xywh':[xx,yy,w,h],'panels':panel_checks}
full=ROOT/'fixtures'/case/'input.mkv';os.link(full,d/'source-full336.mkv')
assert os.path.samefile(full,d/'source-full336.mkv')
x.dump(d/'viewer-key.json',mapping)
x.dump(d/'validation.json',{'playback_observed':False,'all_native_panels_exact':True,'artifacts':checks,
    'quiet_source_only_selection':{'source':x.fingerprint(frozen),'frame':quiet_frame,'tile':q['xywh'],'seconds':quiet_frame/fps},
    'upstream':upstream,'full_reference':x.fingerprint(d/'source-full336.mkv'),'full_candidates':full_candidates,
    'source_hardlink':{'samefile_before_retirement':True,'source':str(full),'link_count':full.stat().st_nlink},
    'source_frames_preroll':96,'script':x.fingerprint(__file__)})
(d/'README.md').write_text(f'''# {case} playback packet

No playback has been observed by the investigators. Record A/B{'/C' if len(names)==3 else ''} judgments before opening viewer-key.json.

The crop loops contain 240 synchronized frames, with native pixels and 10-bit lossless encoding. Every original/candidate panel has exact frame hashes. Use 100% zoom for close inspection; these are reference loops, not a decoder-compatibility test of the original candidate codec. Quiet-context was selected from original-only controls; inspect around {quiet_frame/fps:.3f}s. It includes surrounding context, not an entirely source-clean rectangle.

1. Which panel retains natural fine texture through motion, without freezing, boiling or pumping?
2. Are there new grid boundaries, ringing, lost lines/scratches, banding or noise in the quiet tile?
3. For E05, is the difference between the two encodes visible at normal viewing distance?

For normal full-picture playback, compare source-full336.mkv with these retained actual H264 streams:

{chr(10).join('- '+name+': ../../crosscodec/'+case+'/'+name+'/out.mkv' for name in full_candidates)}

All have 336 frames; scored content begins after 96 frames ({96/fps:.3f}s). This additionally tests the real coded candidates in the user's player/display. State player, display, scaling and any processing used. Source-full336 is a lossless original-derived reference. Record blind crop judgments before opening these named full streams.

Passing numerical screens does not answer these perceptual questions or approve the approximately 4x source bitrate cost.
''')
print(case,'blinded loops and full reference verified; no playback observed')
