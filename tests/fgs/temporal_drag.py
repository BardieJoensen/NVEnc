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
from review_score import FFMPEG, aligned_frame_count

BS = int(os.environ.get("GHOST_BS", "8"))


def _read_exact(stream, size):
    chunks = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def frames(path, n, width, height):
    """Yield n luma planes as float32, decoded to 10-bit gray."""
    p = subprocess.Popen(
        [FFMPEG, "-v", "error", "-nostdin", "-i", path, "-frames:v", str(n),
         "-pix_fmt", "gray10le", "-f", "rawvideo", "-"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    size = width * height * 2
    completed = False
    try:
        for index in range(n):
            buf = _read_exact(p.stdout, size)
            if len(buf) < size:
                stderr = p.stderr.read().decode(errors="replace")
                p.wait()
                raise RuntimeError(
                    f"{path}: short decode at frame {index}/{n}: {stderr[-2000:]}")
            yield np.frombuffer(buf, np.uint16).reshape(height, width).astype(np.float32)
        p.stdout.close()
        stderr = p.stderr.read().decode(errors="replace")
        status = p.wait()
        completed = True
        if status != 0:
            raise RuntimeError(f"{path}: decoder exited {status}: {stderr[-2000:]}")
    finally:
        if not completed:
            if p.stdout:
                p.stdout.close()
            p.kill()
            p.wait()


def box(a, width, height):
    return a.reshape(height // BS, BS, width // BS, BS).mean(axis=(1, 3))


def probe(ref, base, n):
    available, ref_info, base_info = aligned_frame_count(ref, base, limit=n)
    if available != n:
        raise RuntimeError(
            f"requested {n} frames but the aligned pair contains {available}; "
            "pass the exact count rather than allowing a silent short decode")
    width, height = ref_info["width"], ref_info["height"]
    if width % BS or height % BS:
        raise RuntimeError(
            f"{width}x{height} is not divisible by GHOST_BS={BS}")
    num = den = 0.0
    bins = [(0.0, 4.0), (4.0, 16.0), (16.0, 64.0), (64.0, 1e9)]
    bnum = [0.0] * len(bins)
    bden = [0.0] * len(bins)
    bcnt = [0] * len(bins)
    rg = frames(ref, n, width, height)
    bg = frames(base, n, width, height)
    prev_src = None
    consumed = 0
    for src, bas in zip(rg, bg):
        consumed += 1
        s, b = box(src, width, height), box(bas, width, height)
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
    if consumed != n:
        raise RuntimeError(f"decoded {consumed} paired frames, expected {n}")
    out = {"frames": consumed, "box_size": BS,
           "beta": num / den if den else None,
           "bins": [{"range": f"{lo:g}-{hi:g}" if hi < 1e9 else f">{lo:g}",
                     "blocks": bcnt[i],
                     "beta": (bnum[i] / bden[i]) if bden[i] else None}
                    for i, (lo, hi) in enumerate(bins)]}
    return out


if __name__ == "__main__":
    ref, base, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
    print(json.dumps(probe(ref, base, n)))
