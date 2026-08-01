#!/usr/bin/env python3
"""Spatial correlation of source grain versus the synthesised grain layer.

Companion to `ar_acf.py`. That one reports the correlation the fitted AR
coefficients IMPLY; this one reports what the decoder actually PRODUCES, so the
pair localises the loss:

    implied ~= source, produced ~= half  ->  downstream of the fit
    implied ~= produced ~= half          ->  the fit is under-correlated

METHOD: DETREND, DON'T HIGH-PASS
Two wrong estimators bracket the right one, and both were tried here first.

A 3x3 Laplacian high-pass (what `campaign.py` and the first pass of this work
used) is itself a decorrelating filter: it depresses lag-1 on whatever it
touches, so absolute numbers from it mean nothing.

Block mean-subtraction alone goes wrong the other way. "Flat" blocks are flat
relative to edges, not featureless, so what survives is grain plus slow
gradients -- and the gradients dominate the autocorrelation. Measured that way
Taxi Driver's source reads lag-1 0.868 against the synth layer's 0.571, but the
source's 0.868 is mostly picture: its lag-2 is 0.637 where a grain field's
should have collapsed.

So each block is detrended by subtracting a box mean of radius `--detrend`
(default 8). Structure coarser than the box goes; correlation at the lags of
interest survives. The synthesised layer is already pure grain -- it is
grain-on minus grain-off -- so it needs no treatment, and the fact that
detrending barely moves it is the control that the operator is not what
produces the gap. Sweep `--detrend` to confirm the answer is not an artifact of
the radius.

Blocks come from `flat_retention.source_flat_mask`, i.e. chosen once from the
source by gradient energy and applied unchanged to every arm.

Blocks come from `flat_retention.source_flat_mask`, i.e. chosen once from the
source by gradient energy and applied unchanged to every arm, so the comparison
is not biased toward whichever file is smoother.

Usage:
  python3 tests/fgs/layer_acf.py --source clip.mkv --encoded enc_fgs.mkv \
      [--frames 6,10,14] [--seek 0]
"""
import argparse
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from flat_retention import BLOCK, blocks, source_flat_mask  # noqa: E402


def decode(path, w, h, frames, filmgrain=None, decoder=None):
    need = max(frames) + 1
    cmd = ["ffmpeg", "-v", "error", "-y"]
    if decoder:
        cmd += ["-c:v", decoder]
    if filmgrain is not None:
        cmd += ["-filmgrain", str(filmgrain)]
    cmd += ["-i", path, "-frames:v", str(need), "-map", "0:v:0",
            "-pix_fmt", "yuv420p10le", "-vf", f"scale={w}:{h}",
            "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, check=True, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE).stdout
    fp = w * h * 3 // 2
    return [np.frombuffer(raw, np.uint16, count=w * h, offset=f * fp * 2)
            .reshape(h, w).astype(np.float32) for f in frames]


def box_mean(a, radius):
    """Separable box mean via cumulative sums, edges handled by shrinking the box."""
    if radius <= 0:
        return np.zeros_like(a)
    def one_axis(x):
        n = x.shape[-1]
        c = np.cumsum(x, axis=-1)
        c = np.concatenate([np.zeros(x.shape[:-1] + (1,), x.dtype), c], axis=-1)
        i = np.arange(n)
        lo = np.maximum(i - radius, 0)
        hi = np.minimum(i + radius + 1, n)
        return (c[..., hi] - c[..., lo]) / (hi - lo)
    return one_axis(one_axis(a.astype(np.float64)).swapaxes(-1, -2)).swapaxes(-1, -2)


def detrend(plane, radius):
    return plane.astype(np.float64) - box_mean(plane, radius)


def block_acf(plane, mask):
    """Lag-1/2 autocorrelation pooled over the masked blocks, mean-subtracted.

    Pooling the sums rather than averaging per-block correlations keeps blocks
    weighted by their grain energy instead of letting a nearly-empty block
    contribute a noisy ratio at full weight.
    """
    b = blocks(plane)[mask].astype(np.float64)
    if b.size == 0:
        return None
    b = b - b.mean(axis=(-2, -1), keepdims=True)
    var = (b * b).sum()
    if var <= 0:
        return None
    out = {
        "h1": float((b[:, :, 1:] * b[:, :, :-1]).sum() / var),
        "v1": float((b[:, 1:, :] * b[:, :-1, :]).sum() / var),
        "h2": float((b[:, :, 2:] * b[:, :, :-2]).sum() / var),
        "v2": float((b[:, 2:, :] * b[:, :-2, :]).sum() / var),
        "sigma": float(np.sqrt(var / b.size)),
    }
    # The lag-1/lag-2 sums cover fewer pairs than the variance covers samples;
    # rescale so an uncorrelated field reads 0 and a constant field reads 1.
    n = b.shape[-1]
    out["h1"] *= n / (n - 1.0)
    out["v1"] *= n / (n - 1.0)
    out["h2"] *= n / (n - 2.0)
    out["v2"] *= n / (n - 2.0)
    out["lag1"] = 0.5 * (out["h1"] + out["v1"])
    return out


def pooled(planes, masks):
    rows = [block_acf(p, m) for p, m in zip(planes, masks) if m.any()]
    rows = [r for r in rows if r]
    if not rows:
        return None
    return {k: float(np.mean([r[k] for r in rows])) for k in rows[0]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--encoded", default="",
                    help="AV1 encode carrying a film-grain model")
    ap.add_argument("--clean", default="",
                    help="the analyzer's emitted clean base; adds the residual "
                         "(source minus clean) that the AR fit is actually given")
    ap.add_argument("--frames", default="6,10,14")
    ap.add_argument("--decoder", default="libdav1d")
    ap.add_argument("--label", default="")
    ap.add_argument("--detrend", type=int, default=8,
                    help="box radius removed before measuring; 0 = block mean only")
    args = ap.parse_args()

    frames = [int(x) for x in args.frames.split(",")]
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height", "-of", "csv=p=0",
                        args.source], capture_output=True, text=True, check=True)
    w, h = (int(x) for x in r.stdout.strip().split(",")[:2])

    src = decode(args.source, w, h, frames)
    masks = source_flat_mask(src)
    cov = float(np.mean([m.mean() for m in masks]))

    layers = [("source", src)]
    if args.clean:
        clean = decode(args.clean, w, h, frames)
        layers.append(("clean base", clean))
        layers.append(("residual (src-clean)", [a - b for a, b in zip(src, clean)]))
    if args.encoded:
        on = decode(args.encoded, w, h, frames, filmgrain=1, decoder=args.decoder)
        off = decode(args.encoded, w, h, frames, filmgrain=0, decoder=args.decoder)
        layers.append(("decoded grain-off", off))
        layers.append(("decoded grain-on", on))
        layers.append(("synth layer (on-off)", [a - b for a, b in zip(on, off)]))

    label = args.label or os.path.basename(args.encoded or args.clean)
    print(f"{label}: {w}x{h}, flat mask covers {cov*100:.1f}% of blocks, "
          f"detrend radius {args.detrend}\n")
    print(f"{'layer':<22}{'sigma':>9}{'lag1':>8}{'h1':>8}{'v1':>8}{'h2':>8}{'v2':>8}")
    scale = float(1 << 2)  # report 8-bit-equivalent sigma
    for name, planes in layers:
        planes = [detrend(p, args.detrend) for p in planes]
        s = pooled(planes, masks)
        if not s:
            print(f"{name:<22}  no eligible blocks")
            continue
        print(f"{name:<22}{s['sigma']/scale:>9.3f}{s['lag1']:>8.3f}"
              f"{s['h1']:>8.3f}{s['v1']:>8.3f}{s['h2']:>8.3f}{s['v2']:>8.3f}")


if __name__ == "__main__":
    main()
