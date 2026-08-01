#!/usr/bin/env python3
"""Grain retention measured in flat blocks, with the mask taken from the source.

`campaign.py::hf_sigma` high-passes the whole frame, so it also measures edges
and encoder ringing. Two consequences, both of which bias comparisons:

  * A plain encode's ringing and blocking are high-frequency energy counted as
    grain, so its retention reads higher than it is.
  * Selecting flat blocks per-file biases toward whichever file is smoother.

So the mask is derived once from the source and applied unchanged to every
candidate, and only blocks that are flat *in the source* contribute.

  retention = flat-block HF sigma of candidate / flat-block HF sigma of source

Usage:
  python3 tests/fgs/flat_retention.py --source clip.mkv \
      --candidate plain=enc_plain.mkv --candidate fgs=enc_fgs.mkv \
      [--frames 6,10,14] [--width W --height H]
"""
import argparse
import os
import subprocess
import sys

import numpy as np

BLOCK = 32
# Blocks flatter than this fraction of the source's own structure distribution
# are eligible; the rest contain edges or texture.
FLAT_QUANTILE = 0.40
# A block with no measurable source grain cannot report a meaningful ratio, and
# dividing by a near-zero source sigma is the divisor artifact that makes
# retention read high on clean content. This floor excludes those (letterboxing
# reads exactly 0.0) without excluding genuinely light grain: Casino and The
# Shining top out around 0.37 per block, so anything at 0.5 rejects them wholly.
MIN_SOURCE_SIGMA_8BIT = 0.10


def decode(path, w, h, frames, decoder=None):
    """Decode the requested frame indices as 10-bit luma planes."""
    need = max(frames) + 1
    cmd = ["ffmpeg", "-v", "error", "-y"]
    if decoder:
        cmd += ["-c:v", decoder]
    cmd += ["-i", path, "-frames:v", str(need), "-map", "0:v:0",
            "-pix_fmt", "yuv420p10le", "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, check=True, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE).stdout
    fp = w * h * 3 // 2
    out = []
    for f in frames:
        off = f * fp * 2
        out.append(np.frombuffer(raw, np.uint16, count=w * h,
                                 offset=off).reshape(h, w).astype(np.float32))
    return out


def blocks(plane):
    h, w = plane.shape
    bh, bw = h // BLOCK, w // BLOCK
    return (plane[:bh * BLOCK, :bw * BLOCK]
            .reshape(bh, BLOCK, bw, BLOCK).swapaxes(1, 2))


def highpass(a):
    b = (a[0:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, 0:-2] + a[1:-1, 2:]
         + a[1:-1, 1:-1] * 4) / 8
    return a[1:-1, 1:-1] - b


def block_hp_sigma(plane):
    """Per-block high-pass sigma, on the same 8/5 normalisation as campaign.py."""
    hp = np.zeros_like(plane)
    hp[1:-1, 1:-1] = highpass(plane)
    return np.sqrt((blocks(hp) ** 2).mean(axis=(-2, -1))) * (8 / 5.0) ** 0.5


def source_flat_mask(src_planes, bits=10):
    """Blocks that are flat in the SOURCE, by gradient energy, with grain present.

    Structure is measured from the gradient magnitude rather than the high-pass
    residual: grain raises the high-pass everywhere, so ranking on it would
    select the least grainy blocks instead of the least structured ones.
    """
    scale = float(1 << (bits - 8))
    masks = []
    for p in src_planes:
        gx = np.zeros_like(p); gy = np.zeros_like(p)
        gx[:, 1:-1] = (p[:, 2:] - p[:, :-2]) * 0.5
        gy[1:-1, :] = (p[2:, :] - p[:-2, :]) * 0.5
        # Gradient energy at grain scale is isotropic and small; edges are large.
        structure = np.sqrt((blocks(gx) ** 2).mean(axis=(-2, -1))
                            + (blocks(gy) ** 2).mean(axis=(-2, -1)))
        sigma8 = block_hp_sigma(p) / scale
        cutoff = np.quantile(structure, FLAT_QUANTILE)
        masks.append((structure <= cutoff) & (sigma8 >= MIN_SOURCE_SIGMA_8BIT))
    return masks


def flat_sigma(planes, masks, bits=10):
    scale = float(1 << (bits - 8))
    vals = []
    for p, m in zip(planes, masks):
        if not m.any():
            continue
        vals.append(float(block_hp_sigma(p)[m].mean()) / scale)
    return float(np.mean(vals)) if vals else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--candidate", action="append", default=[],
                    help="label=path, repeatable")
    ap.add_argument("--frames", default="6,10,14")
    ap.add_argument("--width", type=int, default=0)
    ap.add_argument("--height", type=int, default=0)
    ap.add_argument("--decoder", default="libdav1d")
    ap.add_argument("--min-sigma", type=float, default=MIN_SOURCE_SIGMA_8BIT,
                    help="per-block source sigma floor, 8-bit units")
    args = ap.parse_args()

    frames = [int(x) for x in args.frames.split(",")]
    w, h = args.width, args.height
    if not (w and h):
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=width,height", "-of", "csv=p=0",
                            args.source], capture_output=True, text=True, check=True)
        w, h = (int(x) for x in r.stdout.strip().split(",")[:2])

    globals()["MIN_SOURCE_SIGMA_8BIT"] = args.min_sigma
    src = decode(args.source, w, h, frames)
    masks = source_flat_mask(src)
    cov = float(np.mean([m.mean() for m in masks]))
    s = flat_sigma(src, masks)
    print(f"source flat-block HF sigma {s:.3f} (8-bit units), "
          f"mask covers {cov*100:.1f}% of blocks")
    whole = float(np.mean([float(highpass(p).std()) * (8 / 5.0) ** 0.5 / 4.0
                           for p in src]))
    print(f"  whole-frame HF sigma       {whole:.3f}   <- what campaign.py measures\n")
    print(f"{'candidate':<14}{'flat HF':>9}{'retention':>11}")
    for spec in args.candidate:
        label, path = spec.split("=", 1)
        c = decode(path, w, h, frames, decoder=args.decoder)
        cs = flat_sigma(c, masks)
        print(f"{label:<14}{cs:>9.3f}{cs/s:>11.3f}")


if __name__ == "__main__":
    main()
