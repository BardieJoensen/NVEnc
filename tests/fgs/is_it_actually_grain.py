#!/usr/bin/env python3
"""Is the thing FGS measures as grain actually grain?

The compressive response has survived nine falsified mechanisms.  This asks a
different question: not "is the amplitude right" but "is the *signal* grain at
all".

FGS measures high-frequency energy on flat luma blocks and models it as grain.
Nothing in the analyser distinguishes grain from the other things that live in
that band -- codec noise from the source's own compression, and fine picture
detail the flat-block selector failed to exclude.  On a clean digital or
animated source, most of that energy is not grain, and re-synthesizing it is
both wrong and a bitrate cost.

The discriminator is time.  Film grain is a per-exposure physical process, so at
a fixed pixel it is essentially independent frame to frame.  Static picture
detail is perfectly correlated in time; codec noise is strongly correlated,
because it is tied to block structure that persists across a GOP.

    real grain      temporal lag-1 of the HF residual  ~ 0
    detail / codec  temporal lag-1 of the HF residual  >> 0

Motion is the obvious confound -- everything decorrelates in a moving shot -- so
the coarse structure's own temporal lag-1 is measured on the same blocks as a
control.  A block whose coarse structure is still correlated is a still block,
and there the HF residual's correlation is meaningful.

This reads the *source* only.  No encode, no decode of an FGS stream, nothing
deployed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np


def decode(path: Path, frames: int) -> np.ndarray:
    st = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height", "-of", "json", str(path)],
        capture_output=True, text=True).stdout)["streams"][0]
    w, h = st["width"], st["height"]
    a = np.frombuffer(subprocess.run(
        ["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-frames:v", str(frames),
         "-pix_fmt", "gray10le", "-f", "rawvideo", "-"],
        capture_output=True).stdout, np.uint16).astype(np.float32)
    n = a.size // (w * h)
    if n < 2:
        raise RuntimeError(f"{path.name}: need at least 2 frames, got {n}")
    return a[:n * w * h].reshape(n, h, w)


def split(a: np.ndarray, block: int = 32):
    """Per-block HF residual field and coarse structure, the production selector."""
    n, h, w = a.shape
    by, bx = h // block, w // block
    t = (a[:, :by * block, :bx * block].reshape(n, by, block, bx, block)
         .transpose(0, 1, 3, 2, 4).reshape(n, by * bx, block, block))
    pool = block // 8
    coarse = t.reshape(n, by * bx, 8, pool, 8, pool).mean(axis=(3, 5))
    up = np.repeat(np.repeat(coarse, pool, axis=2), pool, axis=3)
    return t - up, coarse


def lag1(x: np.ndarray) -> np.ndarray:
    """Per-block temporal lag-1 correlation, averaged over frame pairs.

    x is (frames, blocks, ...) -- each block's samples are flattened and
    correlated against the same block in the next frame.
    """
    f = x.reshape(x.shape[0], x.shape[1], -1)
    a, b = f[:-1], f[1:]
    a = a - a.mean(axis=2, keepdims=True)
    b = b - b.mean(axis=2, keepdims=True)
    num = (a * b).sum(axis=2)
    den = np.sqrt((a * a).sum(axis=2) * (b * b).sum(axis=2))
    with np.errstate(invalid="ignore", divide="ignore"):
        r = np.where(den > 0, num / den, np.nan)
    return np.nanmean(r, axis=0)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("refs", nargs="+")
    p.add_argument("--frames", type=int, default=64)
    p.add_argument("--still", type=float, default=0.9,
                   help="coarse lag-1 above this counts the block as still")
    args = p.parse_args()

    print(f"{'title':16} {'src HF':>7} {'HF lag1':>9} {'coarse':>8} {'still':>7} "
          f"{'HF lag1':>9}")
    print(f"{'':16} {'':>7} {'(all)':>9} {'lag1':>8} {'frac':>7} {'(still)':>9}")
    rows = []
    for raw in args.refs:
        path = Path(raw)
        if not path.is_file():
            print(f"skip {path.name}: missing", file=sys.stderr)
            continue
        a = decode(path, args.frames)
        resid, coarse = split(a)
        # Letterbox bars are the flattest blocks in any scope-ratio clip, have
        # near-zero residual, and are perfectly correlated frame to frame -- so
        # a naive "flattest 25%" selector fills up with them and every temporal
        # statistic becomes a statistic about black.  Casino read source HF
        # 0.000 this way.  Exclude near-black and near-saturated blocks, and
        # blocks with no measurable residual, before ranking.
        level = coarse.mean(axis=(0, 2, 3))
        energy = np.median(resid.reshape(resid.shape[0], resid.shape[1], -1)
                           .std(axis=2), axis=0)
        lo, hi = 16 * 4, 240 * 4          # 10-bit code values
        usable = (level > lo) & (level < hi) & (energy > 1e-3)
        idx = np.flatnonzero(usable)
        if idx.size < 8:
            print(f"skip {path.name}: only {idx.size} usable blocks", file=sys.stderr)
            continue
        keep = max(1, int(idx.size * 0.25))
        # Flat-block selection on structure, held fixed over time so the same
        # blocks are compared frame to frame.
        order = idx[np.argsort(coarse[0].reshape(-1, 64).std(axis=1)[idx])[:keep]]
        r_hf = lag1(resid[:, order])
        r_co = lag1(coarse[:, order])
        hf_std = float(np.median(resid[:, order].reshape(-1, resid.shape[2] *
                                                         resid.shape[3]).std(axis=1)))
        still = r_co > args.still
        frac = float(still.mean())
        hf_still = float(np.nanmean(r_hf[still])) if still.any() else float("nan")
        name = path.name.replace("-ref.mkv", "")
        print(f"{name:16} {hf_std:7.3f} {np.nanmean(r_hf):9.3f} "
              f"{np.nanmean(r_co):8.3f} {frac:7.1%} {hf_still:9.3f}", flush=True)
        rows.append({"title": name, "src_hf": hf_std,
                     "hf_lag1": float(np.nanmean(r_hf)),
                     "coarse_lag1": float(np.nanmean(r_co)),
                     "still_frac": frac, "hf_lag1_still": hf_still})

    print("\n  HF lag-1 near 0 on still blocks  -> genuine grain")
    print("  HF lag-1 well above 0 on still blocks -> detail or codec noise,")
    print("  i.e. FGS is modelling something that is not grain.")
    Path("/tmp/downloads/is-it-grain.json").write_text(json.dumps(rows, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
