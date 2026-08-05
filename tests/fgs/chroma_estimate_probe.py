#!/usr/bin/env python3
"""Does the spatial source-minus-base estimate inflate where grain is weak?

`FINDINGS-2026-08-05-CHROMA-DIAGNOSIS.md` found chroma over-signal tracks plane
grain strength (corr -0.543) rather than plane identity, and proposed a
mechanism: luma moved to a temporal source/base strength estimate while chroma
still uses the spatial one, and a spatial estimate on a faint-grain plane is
dominated by surviving picture structure rather than grain.

That mechanism was asserted, not measured.  This measures it.

For each plane, on the same luma-derived flat/static mask the analyser uses:

    spatial estimate   sqrt(max(0, var_detrended(source) - var_detrended(base)))
    temporal estimate  sqrt(max(0, var(source_temporal) - var(base_temporal)))

The temporal pair is the (n - n+1)/sqrt(2) field, which cancels the picture
exactly; the spatial pair only removes a per-block mean-plus-plane, so
structure above that survives in both terms.  If the mechanism is right, the
spatial estimate should exceed the temporal one most on the weak-grain planes,
and that excess should track the measured over-signal.

Offline only: reads existing encodes, changes nothing.
"""
import argparse
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from source_fit import (  # noqa: E402
    blockwise, detrend_blocks, production_flat_blocks, static_flat_blocks,
)
from temporal_grain_report import (  # noqa: E402
    decode_selected, plane_geometry, probe_size,
)

FRAMES = (10, 58, 106, 154, 202, 250)


def detrended_variance(frame, blocks, bs):
    """Mean per-block variance after removing each block's mean-plus-plane."""
    grid = blockwise(frame, bs)
    values = []
    for by, bx in blocks:
        block = grid[by, bx]
        values.append(float(np.var(detrend_blocks(block[None, None])[0, 0])))
    return float(np.mean(values)) if values else 0.0


def measure(source, base, plane, bits=10, frames=FRAMES):
    width, height = probe_size(source)
    pw, ph, pbs = plane_geometry(width, height, plane)
    indices = sorted({f for n in frames for f in (n, n + 1)})
    luma = decode_selected(source, width, height, indices, bits=bits)
    src = decode_selected(source, pw, ph, indices, plane=plane, bits=bits)
    bas = decode_selected(base, pw, ph, indices, filmgrain=0, plane=plane,
                          bits=bits)
    rows = []
    for n in frames:
        candidates, _, _ = production_flat_blocks(luma[n], bits)
        static = static_flat_blocks(luma[n], luma[n + 1], candidates)
        if len(static) < 8:
            continue
        vs_sp = detrended_variance(src[n], static, pbs)
        vb_sp = detrended_variance(bas[n], static, pbs)
        tsrc = (src[n] - src[n + 1]) / math.sqrt(2.0)
        tbas = (bas[n] - bas[n + 1]) / math.sqrt(2.0)
        vs_t = detrended_variance(tsrc, static, pbs)
        vb_t = detrended_variance(tbas, static, pbs)
        rows.append({
            "frame": n,
            "spatial_estimate": math.sqrt(max(0.0, vs_sp - vb_sp)),
            "temporal_estimate": math.sqrt(max(0.0, vs_t - vb_t)),
            "temporal_source_sigma": math.sqrt(max(0.0, vs_t)),
        })
    if not rows:
        return None
    mean = lambda k: sum(r[k] for r in rows) / len(rows)  # noqa: E731
    sp, tp, ts = (mean("spatial_estimate"), mean("temporal_estimate"),
                  mean("temporal_source_sigma"))
    return {"frames": len(rows), "spatial_estimate": sp,
            "temporal_estimate": tp, "temporal_source_sigma": ts,
            "spatial_over_temporal": sp / tp if tp > 1e-9 else None,
            "spatial_over_source": sp / ts if ts > 1e-9 else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", default="/media/merged-storage/media/"
                        "test-encodes/sourcefit-texture-final-sixfilm-20260804")
    parser.add_argument("--sources", default="/media/merged-storage/media/"
                        "test-encodes/keep-original")
    parser.add_argument("--titles", default="Taxi_Driver,The_Shining,Casino,"
                        "Scarface,The_Deer_Hunter,Interstellar")
    parser.add_argument("--out", default="/tmp/downloads/"
                        "chroma-estimate-probe-20260805.json")
    args = parser.parse_args()
    out = []
    for title in args.titles.split(","):
        src = os.path.join(args.sources, f"clip_{title}-ref288.mkv")
        if not os.path.isfile(src):
            src = os.path.join(args.sources, f"clip_{title}.mkv")
        base = os.path.join(args.candidates, title, "candidate.mkv")
        if not (os.path.isfile(src) and os.path.isfile(base)):
            print(f"MISSING {title}", flush=True)
            continue
        for plane in ("u", "v"):
            row = measure(src, base, plane)
            if row is None:
                continue
            row.update(title=title, plane=plane)
            out.append(row)
            print(json.dumps(row), flush=True)
            with open(args.out, "w", encoding="utf-8") as handle:
                json.dump(out, handle, indent=1)


if __name__ == "__main__":
    main()
