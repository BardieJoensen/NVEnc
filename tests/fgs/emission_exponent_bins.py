#!/usr/bin/env python3
"""Pin down the emission exponent using the analyser's own luma bins.

`emission_exponent.py` fitted one point per title and got `b = 0.666`
(`r = 0.701`, `t = 2.60`, `n = 9`), whose implied ratio slope `-0.334`
replicates `FINDINGS-2026-08-06-ONE-DEFECT.md`'s `-0.414` on a completely
different instrument.  But at `n = 9` the 95% interval on `b` spans roughly
`0.06`--`1.27`, so correct tracking (`b = 1`) is not excluded.  The relationship
is established; the exponent is not.

The strength curve is built per luma bin
(`NVEncFilmGrainModel.cpp:179`, `strength[bin] = sqrt(binVariance) / templateGain`),
so every bin is an independent (source sigma, emitted amplitude) observation
from the same estimator.  That turns 9 points into ~8 per title.

Fitted **within** title, then pooled across titles.  Fitting the union directly
would confound the within-title response with between-title differences in
`templateGain` -- which for luma is `arGain`, a variance *ratio* describing
grain correlation structure and therefore free to differ per title without any
defect being present.  A within-title fit holds `templateGain` fixed by
construction, so its slope isolates the response to source amplitude alone.

This measures the estimator's response shape.  It is not a quality claim and no
coefficient here should be applied as a correction; a global compensating curve
is the corpus-derived scalar this project has already rejected six times.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
import sys
from pathlib import Path

import numpy as np

import filmgrn
from emission_exponent import SOURCES, OUT, active_crop, fit_loglog


def block_stats(path: Path, frames: int, block: int = 32):
    """Per-block luma mean, structure and noise, on the active picture."""
    crop = active_crop(path)
    if crop:
        w, h = (int(v) for v in crop.split(":")[:2])
        vf = ["-vf", f"crop={crop}"]
    else:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "json", str(path)],
            capture_output=True, text=True)
        stream = json.loads(probe.stdout)["streams"][0]
        w, h = stream["width"], stream["height"]
        vf = []
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-nostdin", "-i", str(path)] + vf
        + ["-frames:v", str(frames), "-pix_fmt", "gray10le", "-f", "rawvideo", "-"],
        capture_output=True)
    data = np.frombuffer(result.stdout, np.uint16).astype(np.float64)
    n = min(frames, data.size // (w * h))
    if n < 1:
        raise RuntimeError(f"{path.name}: no frames decoded")
    data = data[:n * w * h].reshape(n, h, w)
    by, bx = h // block, w // block
    tiles = (data[:, :by * block, :bx * block]
             .reshape(n, by, block, bx, block)
             .transpose(0, 1, 3, 2, 4)
             .reshape(n, by * bx, block, block))
    pool = block // 8
    coarse = tiles.reshape(n, by * bx, 8, pool, 8, pool).mean(axis=(3, 5))
    structure = coarse.reshape(n, by * bx, 64).std(axis=2)
    upsampled = np.repeat(np.repeat(coarse, pool, axis=2), pool, axis=3)
    noise = (tiles - upsampled).reshape(n, by * bx, block * block).std(axis=2)
    mean = tiles.reshape(n, by * bx, block * block).mean(axis=2)
    return mean.ravel(), structure.ravel(), noise.ravel()


def emitted_curve(table: Path) -> tuple[np.ndarray, float]:
    """Mean luma scaling curve across updating entries, and its shift."""
    entries = filmgrn.load(table)
    ups = [e for e in entries if e["apply_grain"] and e["update_parameters"]]
    curves, shifts = [], []
    for entry in ups:
        pts = entry["scaling_points"]["y"]
        if not pts:
            continue
        curves.append(filmgrn._curve(pts))
        shifts.append(entry["params"]["scaling_shift"]
                      + entry["params"]["grain_scale_shift"])
    if not curves:
        raise RuntimeError(f"{table.name}: no luma scaling points")
    return np.mean(np.array(curves, dtype=float), axis=0), statistics.mode(shifts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=24)
    parser.add_argument("--bins", type=int, default=8)
    parser.add_argument("--admission", type=float, default=2.0)
    parser.add_argument("--flat-fraction", type=float, default=0.25)
    parser.add_argument("--min-bin-blocks", type=int, default=40)
    args = parser.parse_args()

    print(f"{'title':17} {'bins':>5} {'b':>8} {'r':>7} {'t':>7}")
    fits, report = [], {}
    for title, source in SOURCES.items():
        table = OUT / f"{title}.tbl"
        if not (source.is_file() and table.is_file()):
            print(f"skip {title}: missing source or table", file=sys.stderr)
            continue
        mean, structure, noise = block_stats(source, args.frames)
        curve, shift = emitted_curve(table)

        keep = max(1, int(structure.size * args.flat_fraction))
        flat = np.argsort(structure)[:keep]
        mean, noise = mean[flat], noise[flat]
        ok = noise >= args.admission
        mean, noise = mean[ok], noise[ok]
        if mean.size < args.min_bin_blocks:
            print(f"skip {title}: only {mean.size} admitted flat blocks",
                  file=sys.stderr)
            continue

        # Bin by luma over the range actually present, so bins are populated.
        lo, hi = np.percentile(mean, 2), np.percentile(mean, 98)
        if not (hi > lo):
            print(f"skip {title}: degenerate luma range", file=sys.stderr)
            continue
        edges = np.linspace(lo, hi, args.bins + 1)
        xs, ys = [], []
        for i in range(args.bins):
            sel = (mean >= edges[i]) & (mean < edges[i + 1])
            if sel.sum() < args.min_bin_blocks:
                continue
            sigma = float(np.median(noise[sel]))
            centre = 0.5 * (edges[i] + edges[i + 1])
            # curve is indexed over the 8-bit luma range the table uses
            idx = int(np.clip(centre / 1023.0 * (curve.size - 1),
                              0, curve.size - 1))
            amplitude = float(curve[idx]) / (1 << shift)
            if sigma > 0 and amplitude > 0:
                xs.append(sigma)
                ys.append(amplitude)
        if len(xs) < 4:
            print(f"skip {title}: only {len(xs)} usable bins", file=sys.stderr)
            continue
        b, r, t = fit_loglog(xs, ys)
        fits.append(b)
        report[title] = {"b": b, "r": r, "t": t, "bins": len(xs),
                         "sigma": xs, "amplitude": ys}
        print(f"{title:17} {len(xs):5} {b:8.3f} {r:7.3f} {t:7.2f}")

    if len(fits) < 3:
        print("too few within-title fits", file=sys.stderr)
        return 1

    med = statistics.median(fits)
    mean_b = statistics.mean(fits)
    sd = statistics.stdev(fits)
    se = sd / math.sqrt(len(fits))
    print(f"\n=== within-title exponent, pooled over {len(fits)} titles ===")
    print(f"median b = {med:.3f}   mean b = {mean_b:.3f} +/- {se:.3f} (se)")
    print(f"95% interval on the mean: "
          f"[{mean_b - 1.96 * se:.3f}, {mean_b + 1.96 * se:.3f}]")
    print(f"implied ratio slope (b-1) = {mean_b - 1:.3f}"
          f"   [one-defect measured -0.414]")
    print()
    for label, value in (("correct tracking", 1.0), ("sd-for-variance", 0.5),
                         ("pure floor", 0.0)):
        z = (mean_b - value) / se if se else float("inf")
        verdict = "excluded" if abs(z) > 1.96 else "NOT excluded"
        print(f"  b = {value:<4} {label:18} z = {z:+6.2f}  {verdict}")

    (OUT / "emission-exponent-bins.json").write_text(
        json.dumps({"per_title": report, "mean_b": mean_b, "se": se,
                    "median_b": med}, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
