#!/usr/bin/env python3
"""Does loosening the emission cadence fix over-synthesis, and at what cost?

Every spatial hypothesis for the compressive response has been falsified
(FINDINGS-2026-08-08-COMPRESSION-ELIMINATIONS.md).  What survives is temporal:
FGS_MODEL_MIN_UPDATE_FRAMES = 24 holds the signalled model to a third of the
rate the 8-frame rolling fit moves at, and measured intervals sit exactly on
that floor.

Two measurements, because unlike the other candidates this one has a known cost:

  retention  delivered grain / source grain.  Weak-grain titles (below the
             source HF ~3.95 crossover) should fall toward 1.0; strong-grain
             titles must not move.
  twinkle    frame-to-frame variation of delivered grain amplitude.  The
             cadence exists to stop the grain character flickering, so a
             retention win bought with visible twinkle is a trade, not a fix.

Twinkle is measured as the standard deviation of per-frame high-frequency
energy divided by its mean, on the decoded output, minus the same quantity on
the source -- the source's own variation is not the encoder's fault.
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys
from pathlib import Path
import numpy as np
from animation_bucket_calibration import cut
from deployed_verification import aligned
from measure_rank_gate import resolve, CASES, ARGS, OUT as _OLD

OUT = Path("/tmp/downloads/cadence-sweep-20260808")
CAD = (24, 12, 8)

def encode(binary, ref, out, qvbr, frames_cadence):
    if out.is_file(): return out.stat().st_size
    env = dict(os.environ)
    env["NVENC_FGS_TEST_UPDATE_FRAMES"] = str(frames_cadence)
    r = subprocess.run([str(binary), "--avsw", "-i", str(ref)] + ARGS.split()
                       + ["--qvbr", str(qvbr), "-o", str(out)],
                       capture_output=True, text=True, env=env)
    if r.returncode != 0: raise RuntimeError(f"{out.name}:\n{r.stderr[-900:]}")
    if "update cadence" not in (r.stderr + r.stdout):
        raise RuntimeError(f"{out.name}: cadence override did not take effect")
    return out.stat().st_size

def per_frame_hf(path, decoder, frames, block=32):
    st = json.loads(subprocess.run(["ffprobe","-v","error","-select_streams","v:0",
        "-show_entries","stream=width,height","-of","json",str(path)],
        capture_output=True,text=True).stdout)["streams"][0]
    w,h = st["width"], st["height"]
    cmd = ["ffmpeg","-v","error","-nostdin"] + (["-c:v",decoder] if decoder else []) + \
          ["-i",str(path),"-frames:v",str(frames),"-pix_fmt","gray10le","-f","rawvideo","-"]
    a = np.frombuffer(subprocess.run(cmd,capture_output=True).stdout,np.uint16).astype(np.float64)
    n = a.size//(w*h); a = a[:n*w*h].reshape(n,h,w)
    by,bx = h//block, w//block
    t = (a[:,:by*block,:bx*block].reshape(n,by,block,bx,block)
         .transpose(0,1,3,2,4).reshape(n,by*bx,block,block))
    pool = block//8
    coarse = t.reshape(n,by*bx,8,pool,8,pool).mean(axis=(3,5))
    up = np.repeat(np.repeat(coarse,pool,axis=2),pool,axis=3)
    noise = (t-up).reshape(n,by*bx,block*block).std(axis=2)
    struct = coarse.reshape(n,by*bx,64).std(axis=2)
    keep = max(1,int(struct.shape[1]*0.25))
    o = np.argsort(struct,axis=1)[:,:keep]
    return np.array([np.median(r[r>0]) if (r>0).any() else 0.0
                     for r in np.take_along_axis(noise,o,axis=1)])

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--binary", required=True)
    p.add_argument("--seek", type=float, default=1500.0)
    p.add_argument("--frames", type=int, default=192)
    a = p.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    rows=[]
    for cls,name,raw,qvbr in CASES:
        src = resolve(raw)
        if src is None:
            print(f"skip {name}: no source", file=sys.stderr); continue
        ref = OUT/f"{name}-ref.mkv"; cut(src, ref, a.seek, a.frames)
        sf = per_frame_hf(ref, None, a.frames)
        if sf.mean() <= 0: continue
        src_tw = float(sf.std()/sf.mean())
        print(f"\n### [{cls}] {name} qvbr{qvbr}  src HF {np.median(sf):.3f}  "
              f"src variation {src_tw:.3f}", flush=True)
        row={"class":cls,"src_hf":float(np.median(sf)),"src_tw":src_tw,"arms":{}}
        for c in CAD:
            enc = OUT/f"{name}-c{c}.mkv"
            try: size = encode(Path(a.binary), ref, enc, qvbr, c)
            except RuntimeError as e: print(f"  cadence {c}: {e}"); continue
            ok,l0,l1 = aligned(ref, enc)
            if not ok:
                print(f"  cadence {c}: MISALIGNED"); continue
            ef = per_frame_hf(enc, "libdav1d", a.frames)
            ret = float(np.median(ef)/np.median(sf))
            tw = float(ef.std()/ef.mean()) - src_tw
            row["arms"][c] = {"bytes":size,"retention":ret,"excess_twinkle":tw}
            print(f"  cadence {c:2}  {size/1e6:7.2f}MB  retention {ret:.3f}  "
                  f"excess twinkle {tw:+.3f}", flush=True)
        if row["arms"]: rows.append((name,row))
    (OUT/"cadence.json").write_text(json.dumps({n:r for n,r in rows},indent=2)+"\n")
    print("\n=== retention by cadence (1.0 correct) ===")
    print(f"{'title':16} {'class':7} " + " ".join(f"{c:>8}" for c in CAD))
    for n,r in rows:
        print(f"{n:16} {r['class']:7} " + " ".join(
            f"{r['arms'][c]['retention']:8.3f}" if c in r["arms"] else "       -" for c in CAD))
    print("\n=== excess twinkle (cost side; higher = more flicker) ===")
    for n,r in rows:
        print(f"{n:16} {r['class']:7} " + " ".join(
            f"{r['arms'][c]['excess_twinkle']:+8.3f}" if c in r["arms"] else "       -" for c in CAD))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
