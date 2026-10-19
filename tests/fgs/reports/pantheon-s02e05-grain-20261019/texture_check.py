#!/usr/bin/env python3
"""Paired luma HF/ACF and isolated decoder grain; no encoding or library edits."""
import json, os, pathlib, subprocess, sys
import numpy as np
sys.path.insert(0, '/home/bardie/git-repos/NVEnc/tests/fgs')
from matched_rate_sweep import high_pass, autocorr
ROOT=pathlib.Path(os.environ.get('PANTHEON_AUDIT_DIR','/tmp/downloads/codex-work/pantheon-s02e05-grain-20261019'))
frames=sorted(set(range(0,240,24))|{116,118,120,122,124})
rois={1420:{'shirt':[500,800,200,150],'background':[1400,100,300,300]},1440:{'shirt':[1200,650,200,100],'background':[950,50,250,180]},1460:{'shirt':[800,430,100,80],'forearm':[800,790,150,60]}}
def stats(a):
    r=high_pass(a)
    return {'mean_luma':float(a.mean()),'hf_sigma':float(r.std()*(8/5)**.5),**{f'acf{k}':float(autocorr(r,k)) if r.std()>1e-9 else None for k in (1,2,3)}}
def read(path):
    b=subprocess.check_output(['ffmpeg','-v','error','-threads','4','-i',str(path),'-vf','select='+ '+'.join(f'eq(n\\,{n})' for n in frames),'-frames:v',str(len(frames)),'-fps_mode','passthrough','-pix_fmt','yuv420p10le','-f','rawvideo','-'])
    a=np.frombuffer(b,np.uint16).reshape(len(frames),1920*1080*3//2)
    return a[:,:1920*1080].reshape(len(frames),1080,1920).astype(np.float32)/4
out={'note':'8-bit luma units. HF sigma and residual ACF must be read together. Whole frame includes edges. ROIs averaged over frames 116,118,120,122,124 around window midpoint; their motion can affect values. Decoder grain = on minus off, not an FGS-disabled encode.','windows':{}}
for ts,boxes in rois.items():
    d=ROOT/str(ts)
    planes={arm:read(d/name) for arm,name in [('source','ref.mkv'),('on','on.mkv'),('off','off.mkv')]}
    row={'roi_xywh':boxes,'frames':frames,'arms':{}}
    for arm,a in planes.items():
        per=[dict(frame=n,**stats(f)) for n,f in zip(frames,a)]
        row['arms'][arm]={'whole_frame':per,'roi':{}}
        for label,(x,y,w,h) in boxes.items():
            vals=[stats(a[frames.index(n),y:y+h,x:x+w]) for n in (116,118,120,122,124)]
            row['arms'][arm]['roi'][label]={k:float(np.mean([v[k] for v in vals])) for k in vals[0]}
    added=planes['on']-planes['off']
    row['added_grain']=[{'frame':n,'sigma':float(f.std()),**stats(f)} for n,f in zip(frames,added)]
    out['windows'][str(ts)]=row
    print(ts,json.dumps({a:v['roi'] for a,v in row['arms'].items()}),flush=True)
(ROOT/'texture-check.json').write_text(json.dumps(out,indent=2))
