#!/usr/bin/env python3
"""GPU campaign, original-conditioned controls and independent H264 decoders."""
import json
import os
from pathlib import Path
import sys
import numpy as np
from score import ROOT, SCORES, x, texture
from analyze import desc, paired, W, H
from packet_window import measure, audit

case,tag=sys.argv[1:];d=ROOT/'parent/crosscodec'/case/tag;s=SCORES/case;s.mkdir(exist_ok=True)
rate_audit=audit(case,tag)
assert rate_audit['within_1pct'], 'Calibrate actual packet rate before scoring a decisive comparison.'
x.rate=lambda path,fps:measure(path,fps)[0]
for name in ('ref.mkv','source.yuv','validity.json'):
    dest=s/name;target=ROOT/'fixtures'/case/name
    if not dest.exists():os.link(target,dest)
    assert not dest.is_symlink() and os.path.samefile(dest,target)
enc=d/'out.mkv';result=x.score(case,enc,tag,grain=0)
decoded=s/(tag+'-decoded.mkv');texture.analyze(case,tag,decoded)
cpu=['ffmpeg','-v','error','-threads','4','-i',enc,'-frames:v','336','-pix_fmt','yuv420p10le']
gpu=['/usr/bin/ffmpeg','-v','error','-threads','4','-hwaccel','cuda','-hwaccel_output_format','cuda',
     '-c:v','h264_cuvid','-i',enc,'-vf','hwdownload,format=nv12,format=yuv420p10le',
     '-frames:v','336','-pix_fmt','yuv420p10le']
hashes=[x.hashes(c) for c in (cpu,gpu)]
assert len(hashes[0])==336 and hashes[0]==hashes[1]
oldpath=Path('/media/merged-storage/cold-storage/docker-apps/pantheon-quantization-20261019')/case/'whole-window-controls.json'
old=json.loads(oldpath.read_text());base='detail' if case=='e04' else 'detail2'
source=np.memmap(ROOT/'fixtures'/case/'source.yuv',dtype='<u2',mode='r',shape=(240,W*H*3//2))
byframe={}
for r in old['tiles']:byframe.setdefault(r['frame'],[]).append(r)
proc=texture.reader(decoded);rows=[];face={}
try:
    for n in range(240):
        raw=proc.stdout.read(W*H*3);assert len(raw)==W*H*3
        if n not in byframe and not(case=='e05-1440' and n==120):continue
        sy=source[n,:W*H].reshape(H,W).astype(float)/4
        ey=np.frombuffer(raw,dtype='<u2')[:W*H].reshape(H,W).astype(float)/4
        for oldrow in byframe.get(n,[]):
            xx,yy=oldrow['x'],oldrow['y'];sl=np.s_[yy:yy+32,xx:xx+32];sd=desc(sy[sl])
            assert all(oldrow['source'][k] is None and sd[k] is None or abs(oldrow['source'][k]-sd[k])<1e-10 for k in sd)
            rows.append({'frame':n,'x':xx,'y':yy,'kind':oldrow['kind'],'source':sd,
                'baseline':{**oldrow[base],'mse':oldrow['mse'][base]},'candidate':paired(sy[sl],ey[sl])})
        if case=='e05-1440' and n==120:
            sy=sy[600:1080,160:660];ey=ey[600:1080,160:660];sg=np.abs(np.diff(sy,axis=1));eg=np.abs(np.diff(ey,axis=1));mask=sg>12
            face={'baseline':old['face'][base],'candidate':{'mse':float(np.mean((sy-ey)**2)),
                  'edge_gradient_mae':float(np.abs(eg[mask]-sg[mask]).mean()),'edge_gradient_ratio':float(eg[mask].sum()/sg[mask].sum())}}
finally:proc.stdout.close();proc.wait()
assert proc.returncode==0
summary={}
for kind in ['all','quiet','edge','flat_texture','other']:
    pool=[r for r in rows if kind=='all' or r['kind']==kind];obj={'tiles':len(pool)}
    for arm in ['baseline','candidate']:
        obj[arm]={metric:float(np.mean(values)) if values else None for metric,values in {
          'mse_mean':[r[arm]['mse'] for r in pool],
          'hf_abs_error':[abs(r[arm]['hf_sigma']-r['source']['hf_sigma']) for r in pool],
          'acf1_abs_error':[abs(r[arm]['acf1']-r['source']['acf1']) for r in pool if r[arm]['acf1'] is not None and r['source']['acf1'] is not None]}.items()}
    summary[kind]=obj
x.dump(d/'controls.json',{'source_control_provenance':x.fingerprint(oldpath),'source_descriptors_match_prior':True,'summary':summary,'face':face,'tiles':rows})
x.dump(d/'decoder-validation.json',{'all336_allplanes_cpu_NVDEC_exact':True,'hashes':hashes[0],
    'commands':[list(map(str,cpu)),list(map(str,gpu))],'ffmpeg_CPU':x.fingerprint(x.shutil.which('ffmpeg')),
    'ffmpeg_GPU':x.fingerprint('/usr/bin/ffmpeg'),
    'output':x.fingerprint(enc),'scoring_script':x.fingerprint(__file__)})
print(case,tag,summary,flush=True)
