#!/usr/bin/env python3
"""Is the compressive response in what the encoder ASKS for, or in what the
decoder DELIVERS?

`base_floor.py` showed the compression survives after the base layer's own
high-frequency energy is removed, so it lives in the synthesized component.
That leaves exactly two places it can be, and they are cleanly separable:

    source  --[analyser]-->  emitted table  --[AV1 synthesis]-->  delivered

This measures the middle term.  The encoder writes its model as an AOM
`filmgrn1` table (`--film-grain-table-out`), so the request is readable without
inference.  Reconstructing the amplitude that table asks for requires the AV1
grain generation process:

    intended  =  ar_gain  *  scaling(luma)  /  2^scaling_shift

`ar_gain` is the standard deviation the auto-regressive filter produces from the
spec's gaussian sequence.  That sequence's own scale is a **constant** -- same
bit depth, same `grain_scale_shift` for every title here -- so driving the same
recursion with unit-variance white noise gives the correct gain *ratio* between
titles even though the absolute constant is unknown.  Ratios are all this test
needs, and it avoids hardcoding a 2048-entry table.

This also sidesteps the trap recorded in FINDINGS-2026-08-04-ADMISSION-GATE.md:
the emitted table's *mean scaling point* overstates strength roughly twofold, so
it is never used as an amplitude.  The scaling curve is evaluated against the
content's actual luma histogram and combined with the realised AR gain.

Reading:

  intended/src flat, delivered/intended compressive
      -> the analyser is faithful; synthesis or the decode path compresses.
  intended/src compressive
      -> the request is already wrong, and since every analyser mechanism has
         been falsified, the compression is in what the analyser measures --
         which points back at the source measurement itself.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np


class Segment:
    """One `E <start> <end>` block of a filmgrn1 table."""

    def __init__(self, start: int, end: int, params: list[int],
                 sy: list[int], cy: list[int]):
        self.start, self.end = start, end
        self.ar_lag = params[0]
        self.ar_shift = params[1]
        self.grain_scale_shift = params[2]
        self.scaling_shift = params[3]
        self.sy = sy            # [n, x0, y0, x1, y1, ...]
        self.cy = np.array(cy, dtype=np.float64)

    @property
    def duration(self) -> int:
        return max(0, self.end - self.start)

    def scaling_lut(self) -> np.ndarray:
        """Piecewise-linear scaling over the 8-bit luma index, per AV1 7.18.3.5."""
        n = self.sy[0]
        pts = np.array(self.sy[1:1 + 2 * n], dtype=np.float64).reshape(n, 2)
        x, y = pts[:, 0], pts[:, 1]
        idx = np.arange(256, dtype=np.float64)
        # np.interp clamps to the endpoints outside the point range, which is
        # what the spec does (values below x0 take y0, above xn take yn).
        return np.interp(idx, x, y)

    def taps(self) -> list[tuple[int, int, float]]:
        """Causal neighbourhood in the spec's raster order: rows -lag..0,
        cols -lag..lag, stopping at the current sample."""
        coeffs = self.cy / (1 << self.ar_shift)
        out, pos = [], 0
        for drow in range(-self.ar_lag, 1):
            for dcol in range(-self.ar_lag, self.ar_lag + 1):
                if drow == 0 and dcol == 0:
                    break
                out.append((drow, dcol, float(coeffs[pos])))
                pos += 1
        assert pos == len(coeffs), f"tap count {pos} != {len(coeffs)}"
        return out

    def ar_gain(self, n: int = 512) -> float:
        """std of the AR-filtered field for unit-variance white innovation.

        g[r,c] = e[r,c] + sum_taps a * g[r+dr, c+dc] is a recursive 2D filter,
        so simulating it would need a sample-by-sample loop.  Its gain has an
        exact closed form instead: G = E / (1 - A(w)), and the power gain is the
        mean of 1/|1 - A(w)|^2 over the frequency plane.

        The spec's gaussian sequence supplies the innovation, and its scale is
        the same constant for every segment here (same bit depth, same
        grain_scale_shift), so it cancels in the cross-title ratio this test
        actually uses.
        """
        w = 2.0 * np.pi * np.arange(n) / n
        w1, w2 = np.meshgrid(w, w, indexing="ij")
        a = np.zeros((n, n), dtype=np.complex128)
        for drow, dcol, c in self.taps():
            if c:
                a += c * np.exp(1j * (w1 * drow + w2 * dcol))
        denom = np.abs(1.0 - a) ** 2
        # A near-unstable fit drives the denominator toward zero; the encoder
        # rejects those, but guard so one bad segment cannot produce an inf.
        return float(np.sqrt(np.mean(1.0 / np.maximum(denom, 1e-9))))


def parse_table(path: Path) -> list[Segment]:
    segs, cur = [], None
    params = sy = cy = None
    for line in path.read_text().splitlines():
        f = line.split()
        if not f:
            continue
        if f[0] == "E":
            if cur is not None and params and sy and cy:
                segs.append(Segment(cur[0], cur[1], params, sy, cy))
            cur = (int(f[1]), int(f[2]))
            params = sy = cy = None
        elif f[0] == "p":
            params = [int(v) for v in f[1:]]
        elif f[0] == "sY":
            sy = [int(v) for v in f[1:]]
        elif f[0] == "cY":
            cy = [int(v) for v in f[1:]]
    if cur is not None and params and sy and cy:
        segs.append(Segment(cur[0], cur[1], params, sy, cy))
    return segs


def luma_hist(path: Path, frames: int) -> np.ndarray:
    """8-bit luma histogram of the content, to weight the scaling curve."""
    st = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height", "-of", "json", str(path)],
        capture_output=True, text=True).stdout)["streams"][0]
    w, h = st["width"], st["height"]
    a = np.frombuffer(subprocess.run(
        ["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-frames:v", str(frames),
         "-pix_fmt", "gray10le", "-f", "rawvideo", "-"],
        capture_output=True).stdout, np.uint16)
    n = a.size // (w * h)
    a = a[:n * w * h] >> 2          # 10-bit -> the table's 8-bit index
    hist = np.bincount(a, minlength=256)[:256].astype(np.float64)
    return hist / max(hist.sum(), 1.0)


def intended_amplitude(segs: list[Segment], hist: np.ndarray) -> float:
    """Duration-weighted amplitude the table asks for, in source HF units.

    Grain is scaled per pixel by scaling(luma)/2^scaling_shift, so the amplitude
    seen over a frame is the histogram-weighted RMS of that factor -- not its
    mean, since it multiplies a zero-mean field.
    """
    tot = sum(s.duration for s in segs) or len(segs)
    acc = 0.0
    for s in segs:
        lut = s.scaling_lut() / float(1 << s.scaling_shift)
        rms = float(np.sqrt((hist * lut ** 2).sum()))
        w = (s.duration or 1) / tot
        acc += w * (s.ar_gain() * rms) ** 2
    return float(np.sqrt(acc))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--frames", type=int, default=192)
    p.add_argument("--json", default="/tmp/downloads/base-floor-20260808/base-floor.json",
                   help="delivered measurements from base_floor.py")
    p.add_argument("--tables", default="/tmp/downloads",
                   help="directory holding base-floor-tbl-<title>.tbl")
    args = p.parse_args()

    delivered = json.loads(Path(args.json).read_text()) if Path(args.json).is_file() else {}
    tdir = Path(args.tables)

    rows = []
    for tbl in sorted(tdir.glob("base-floor-tbl-*.tbl")):
        name = tbl.name[len("base-floor-tbl-"):-len(".tbl")]
        ref = tbl.with_name(f"base-floor-tbl-{name}.mkv")
        # The reference cut, not the encode, defines the luma distribution.
        src_ref = None
        for cand in (Path("/tmp/downloads/base-floor-20260808") / f"{name}-ref.mkv",
                     Path("/tmp/downloads/measure-rank-20260808") / f"{name}-ref.mkv"):
            if cand.is_file():
                src_ref = cand
                break
        if src_ref is None:
            print(f"skip {name}: no reference cut", file=sys.stderr)
            continue
        segs = parse_table(tbl)
        if not segs:
            print(f"skip {name}: no segments parsed", file=sys.stderr)
            continue
        hist = luma_hist(src_ref, args.frames)
        want = intended_amplitude(segs, hist)
        d = delivered.get(name, {})
        rows.append({"title": name, "segments": len(segs), "intended": want,
                     "src": d.get("src"), "synth": d.get("synth")})
        print(f"{name:16} segments {len(segs):3d}  intended {want:9.4f}"
              + (f"   src {d['src']:6.3f}  synth {d['synth']:6.3f}" if d.get("src") else ""),
              flush=True)

    known = [r for r in rows if r.get("src")]
    if len(known) >= 3:
        src = np.array([r["src"] for r in known])
        want = np.array([r["intended"] for r in known])
        got = np.array([r["synth"] for r in known])
        # Scale-free: the AR gain carries an unknown constant, so normalise the
        # request by its own median ratio before comparing slopes.
        k = float(np.median(got / want))
        want_s = want * k
        print("\n=== where does the compression enter? ===")
        print(f"{'title':16} {'src':>8} {'intended':>10} {'delivered':>10} "
              f"{'int/src':>9} {'del/int':>9}")
        for r, ws in zip(known, want_s):
            print(f"{r['title']:16} {r['src']:8.3f} {ws:10.3f} {r['synth']:10.3f} "
                  f"{ws/r['src']:9.3f} {r['synth']/ws:9.3f}")
        ls, li, lg = np.log(src), np.log(want_s), np.log(got)
        print(f"\n  log-log slope  intended vs source   {np.polyfit(ls, li, 1)[0]:+.3f}"
              "   (1.0 = the request is faithful)")
        print(f"  log-log slope  delivered vs source  {np.polyfit(ls, lg, 1)[0]:+.3f}"
              "   (the measured compressive response)")
        print(f"  log-log slope  delivered vs intended {np.polyfit(li, lg, 1)[0]:+.3f}"
              "   (1.0 = synthesis honours the request)")
        print("\n  slope near 1 on the first line puts the defect after the analyser;"
              "\n  slope well below 1 puts it in the measurement feeding the table.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
