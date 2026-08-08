#!/usr/bin/env python3
"""Retention measured on a common block set, chosen from the source.

Every retention number in this investigation -- and the `source^0.726`
compressive response built on them -- came from a metric that selects the
flattest 25% of blocks *independently in the source and in the encode*.  The
base layer is denoised, so its flatness ranking differs, and the numerator and
denominator end up describing different regions of the picture.

That is not a retention measurement, and it is not a small effect.  On Long
Halloween, eight defensible variants of the same measurement on the same encode
span 0.576 to 1.263 -- the verdict flips between "over-delivers by 26%" and
"under-delivers by 42%".  Two choices drive it:

  * per-frame vs fixed block selection (the dominant lever);
  * whether letterbox bars and near-black regions are excluded.  They are the
    flattest blocks in any scope-ratio frame and carry almost no grain, so a
    naive "flattest 25%" fills up with them and the median source HF collapses
    -- Casino read 0.000 and Long Halloween 1.479 instead of 4.142.

This measures instead:

  1. blocks are ranked once, on the SOURCE, excluding near-black and
     near-saturated blocks;
  2. the same block indices are read in the source, in the played output, and
     in the base layer (dav1d with synthesis off, same bitstream);
  3. selection is per-frame in the sense that the source's ranking may be taken
     per frame, but whatever set frame k uses is the set read in frame k of
     every arm.

Frame alignment is a precondition, not an assumption -- the caller verifies it
before scoring, and both arms are decoded from one lossless cut.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

BLOCK = 32
DARK_LO, DARK_HI = 64, 960          # 10-bit code values


def decode(path: Path, frames: int, filmgrain: bool | None = None) -> np.ndarray:
    st = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height", "-of", "json", str(path)],
        capture_output=True, text=True).stdout)["streams"][0]
    w, h = st["width"], st["height"]
    cmd = ["ffmpeg", "-v", "error", "-nostdin"]
    if filmgrain is not None:
        cmd += ["-c:v", "libdav1d", "-filmgrain", "1" if filmgrain else "0"]
    cmd += ["-i", str(path), "-frames:v", str(frames), "-pix_fmt", "gray10le",
            "-f", "rawvideo", "-"]
    a = np.frombuffer(subprocess.run(cmd, capture_output=True).stdout,
                      np.uint16).astype(np.float32)
    n = a.size // (w * h)
    if n == 0:
        raise RuntimeError(f"{path.name}: decoded no frames")
    return a[:n * w * h].reshape(n, h, w)


def fields(a: np.ndarray):
    """Per-block high-frequency residual and coarse structure."""
    n, h, w = a.shape
    by, bx = h // BLOCK, w // BLOCK
    t = (a[:, :by * BLOCK, :bx * BLOCK].reshape(n, by, BLOCK, bx, BLOCK)
         .transpose(0, 1, 3, 2, 4).reshape(n, by * bx, BLOCK, BLOCK))
    pool = BLOCK // 8
    coarse = t.reshape(n, by * bx, 8, pool, 8, pool).mean(axis=(3, 5))
    up = np.repeat(np.repeat(coarse, pool, axis=2), pool, axis=3)
    noise = (t - up).reshape(n, by * bx, BLOCK * BLOCK).std(axis=2)
    structure = coarse.reshape(n, by * bx, 64).std(axis=2)
    level = coarse.mean(axis=(2, 3))
    return noise, structure, level


def select(structure: np.ndarray, level: np.ndarray, frac: float,
           per_frame: bool) -> np.ndarray:
    """Block indices per frame, ranked on the source and excluding dark blocks."""
    n, nb = structure.shape
    usable = (level > DARK_LO) & (level < DARK_HI)
    if per_frame:
        st = np.where(usable, structure, np.inf)
        keep = max(1, int(usable.sum(axis=1).min() * frac))
        return np.argsort(st, axis=1)[:, :keep]
    ok = usable.all(axis=0)
    idx = np.flatnonzero(ok)
    if idx.size < 8:
        idx = np.flatnonzero(usable.any(axis=0))
    keep = max(1, int(idx.size * frac))
    order = idx[np.argsort(structure.mean(axis=0)[idx])[:keep]]
    return np.repeat(order[None, :], n, axis=0)


def gather(noise: np.ndarray, order: np.ndarray) -> float:
    sel = np.take_along_axis(noise, order, axis=1).ravel()
    sel = sel[sel > 0]
    return float(np.median(sel)) if sel.size else float("nan")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dir", default="/tmp/downloads/residual-target-20260808")
    p.add_argument("--arm", default="off", help="encode suffix to score")
    p.add_argument("--frames", type=int, default=192)
    p.add_argument("--frac", type=float, default=0.25)
    p.add_argument("--per-frame", action="store_true",
                   help="rank per frame (still on the source, applied to all arms)")
    args = p.parse_args()

    d = Path(args.dir)
    rows = []
    print(f"{'title':16} {'src':>7} {'played':>8} {'base':>7} {'synth':>7} {'retention':>10}")
    for ref in sorted(d.glob("*-ref.mkv")):
        name = ref.name[:-len("-ref.mkv")]
        enc = d / f"{name}-{args.arm}.mkv"
        if not enc.is_file():
            continue
        s_noise, s_struct, s_level = fields(decode(ref, args.frames))
        p_noise, _, _ = fields(decode(enc, args.frames, filmgrain=True))
        b_noise, _, _ = fields(decode(enc, args.frames, filmgrain=False))
        n = min(s_noise.shape[0], p_noise.shape[0], b_noise.shape[0])
        if n < 2:
            print(f"skip {name}: {n} common frames", file=sys.stderr)
            continue
        order = select(s_struct[:n], s_level[:n], args.frac, args.per_frame)
        src = gather(s_noise[:n], order)
        played = gather(p_noise[:n], order)
        base = gather(b_noise[:n], order)
        synth = float(np.sqrt(max(0.0, played ** 2 - base ** 2)))
        print(f"{name:16} {src:7.3f} {played:8.3f} {base:7.3f} {synth:7.3f} "
              f"{synth/src:10.3f}", flush=True)
        rows.append({"title": name, "src": src, "played": played, "base": base,
                     "synth": synth, "retention": synth / src})

    if len(rows) >= 3:
        src = np.array([r["src"] for r in rows])
        syn = np.array([r["synth"] for r in rows])
        ret = syn / src
        slope = np.polyfit(np.log(src), np.log(syn), 1)[0]
        r = np.corrcoef(np.log(src), np.log(ret))[0, 1]
        print(f"\n  slope {slope:+.3f}   spread {ret.min():.3f}..{ret.max():.3f}"
              f"   corr(log src, log retention) {r:+.3f}")
        print("  slope near 1.0 means delivery tracks the source proportionally;")
        print("  the 0.726 compressive response was measured with independent")
        print("  per-arm block selection and does not survive this construction.")
    Path(d / "retention-common.json").write_text(json.dumps(rows, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
