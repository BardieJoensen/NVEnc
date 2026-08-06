#!/usr/bin/env python3
"""Does flat-block selection bias explain the encoder's compressive measurement?

`FINDINGS-2026-08-06-MEASUREMENT-COMPRESSION.md` establishes that `curve *
arGain` -- which is the encoder's own measured sigma by construction -- tracks
an independent source measurement as `source^0.630` rather than `source^1`.

This probes the named suspect.  Ranking blocks by a metric that grain inflates
selects the least-grainy regions of grainy content, which under-measures them:
a compressive measurement.  `NVEncFilterFilmGrain.cu:2400` documents exactly
this and takes the top score decile to mitigate it.

Read the result with its limitation in view: selecting least-grainy blocks
necessarily shrinks measured sigma more on grainy titles, so the direction of
the effect is guaranteed and only its magnitude at the encoder's actual
selection strength is informative.  The companion control -- varying breadth on
a grain-*insensitive* metric -- is what shows the effect follows grain
sensitivity rather than block count.
"""

import json, sys
sys.path.insert(0,"/home/bardie/git-repos/NVEnc/tests/fgs")
import numpy as np, subprocess
from emission_exponent import SOURCES, OUT, fit_loglog, active_crop

d=json.load(open(OUT/"argain-attribution.json"))
rows={r["title"]: r for r in d["rows"]}

def stats(path, frames=24, block=32):
    crop=active_crop(path); vf=["-vf",f"crop={crop}"] if crop else []
    if crop: w,h=(int(v) for v in crop.split(":")[:2])
    else:
        pr=subprocess.run(["ffprobe","-v","error","-select_streams","v:0",
            "-show_entries","stream=width,height","-of","json",str(path)],
            capture_output=True,text=True)
        st=json.loads(pr.stdout)["streams"][0]; w,h=st["width"],st["height"]
    r=subprocess.run(["ffmpeg","-v","error","-nostdin","-i",str(path)]+vf+
        ["-frames:v",str(frames),"-pix_fmt","gray10le","-f","rawvideo","-"],
        capture_output=True)
    a=np.frombuffer(r.stdout,np.uint16).astype(np.float64)
    n=min(frames,a.size//(w*h)); a=a[:n*w*h].reshape(n,h,w)
    by,bx=h//block,w//block
    t=(a[:,:by*block,:bx*block].reshape(n,by,block,bx,block)
        .transpose(0,1,3,2,4).reshape(n,by*bx,block,block))
    pool=block//8
    coarse=t.reshape(n,by*bx,8,pool,8,pool).mean(axis=(3,5))
    up=np.repeat(np.repeat(coarse,pool,axis=2),pool,axis=3)
    noise=(t-up).reshape(n,by*bx,block*block).std(axis=2).ravel()
    # the grain-sensitive metric: raw pixel-to-pixel gradient, which is what
    # NVEncFilterFilmGrain.cu:2400 says strong grain inflates
    grad=np.abs(np.diff(t.reshape(n,by*bx,block*block),axis=2)).mean(axis=2).ravel()
    return grad, noise

cache={}
for title,src in SOURCES.items():
    if title not in rows or not src.is_file(): continue
    cache[title]=stats(src)
    print(f"cached {title}",flush=True)

print("\nRanking by the GRAIN-SENSITIVE metric (raw pixel gradient), among blocks")
print("that clear admission.  This is what the encoder's strict threshold does,")
print("and the bias its own comment warns about: it samples the least-grainy")
print("regions of grainy content, under-measuring them.\n")
print(f"{'kept quantile':>14} {'n':>3} {'b':>8} {'r':>8}   interpretation")
for frac in (0.05,0.10,0.25,0.50,1.00):
    xs,ys=[],[]
    for title,(grad,noise) in cache.items():
        ok=noise>=2.0
        g,nz=grad[ok],noise[ok]
        if g.size==0: continue
        keep=max(1,int(g.size*frac))
        order=np.argsort(g)[:keep]
        xs.append(float(np.median(nz[order]))); ys.append(rows[title]["product"])
    if len(xs)<6:
        print(f"{frac:14.2f}    (too few)"); continue
    b,r,t=fit_loglog(xs,ys)
    note="MATCHES encoder (b~1)" if 0.9<=b<=1.1 else ("compressive" if b<0.9 else "expansive")
    print(f"{frac:14.2f} {len(xs):3} {b:8.3f} {r:8.3f}   {note}")
