#!/usr/bin/env python3
"""Measure temporal drag (ghosting) in a separator's base, without a human.

Ghosting means the base at frame n carries content from frame n-1.  Regress
the base's error onto the previous-frame difference:

    err_n  = base_n - src_n
    prev_n = src_{n-1} - src_n
    beta   = sum(err*prev) / sum(prev*prev)

beta is directly the fraction of the previous frame bled into the base: a
base that equals (1-a)*src_n + a*src_{n-1} regresses to beta = a.  A purely
spatial denoiser has no mechanism to produce beta > 0.

The one confound that must be killed: both planes still carry grain.  err
contains roughly -grain_n and prev contains grain_{n-1} - grain_n, so
E[err*prev] picks up +E[grain_n^2] for ANY denoiser, in proportion to how
much grain it removes -- which would hand motion a spurious positive beta
precisely because it denoises harder.  Both fields are therefore box-averaged
8x8 first: temporally independent grain drops ~64x in variance while
displaced structure survives, so what is left is structure, not grain
removal.

beta is also reported in bins of |prev| (motion magnitude).  Real ghosting
concentrates where things move; a global offset would show up flat.
"""
import json, subprocess, sys
import numpy as np

import os
W, H = 1920, 1080
BS = int(os.environ.get("GHOST_BS", "8"))
BW, BH = W // BS, H // BS


def frames(path, n):
    """Yield n luma planes as float32, decoded to 10-bit gray."""
    p = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-nostdin", "-i", path, "-frames:v", str(n),
         "-pix_fmt", "gray10le", "-f", "rawvideo", "-"],
        stdout=subprocess.PIPE)
    size = W * H * 2
    try:
        for _ in range(n):
            buf = p.stdout.read(size)
            if len(buf) < size:
                return
            yield np.frombuffer(buf, np.uint16).reshape(H, W).astype(np.float32)
    finally:
        p.stdout.close()
        p.wait()


def box(a):
    return a.reshape(BH, BS, BW, BS).mean(axis=(1, 3))


def probe(ref, base, n):
    num = den = 0.0
    bins = [(0.0, 4.0), (4.0, 16.0), (16.0, 64.0), (64.0, 1e9)]
    bnum = [0.0] * len(bins)
    bden = [0.0] * len(bins)
    bcnt = [0] * len(bins)
    rg, bg = frames(ref, n), frames(base, n)
    prev_src = None
    for src, bas in zip(rg, bg):
        s, b = box(src), box(bas)
        if prev_src is not None:
            err = b - s
            prv = prev_src - s
            num += float((err * prv).sum())
            den += float((prv * prv).sum())
            mag = np.abs(prv)
            for i, (lo, hi) in enumerate(bins):
                m = (mag >= lo) & (mag < hi)
                if m.any():
                    bnum[i] += float((err[m] * prv[m]).sum())
                    bden[i] += float((prv[m] * prv[m]).sum())
                    bcnt[i] += int(m.sum())
        prev_src = s
    out = {"beta": num / den if den else None,
           "bins": [{"range": f"{lo:g}-{hi:g}" if hi < 1e9 else f">{lo:g}",
                     "blocks": bcnt[i],
                     "beta": (bnum[i] / bden[i]) if bden[i] else None}
                    for i, (lo, hi) in enumerate(bins)]}
    return out


if __name__ == "__main__":
    ref, base, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
    print(json.dumps(probe(ref, base, n)))
