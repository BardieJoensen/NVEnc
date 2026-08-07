#!/usr/bin/env python3
"""Calibrate bucket cq29 for clean digital content.

The cq29 bucket is reached two ways: the 4K override, and the router's
fall-through for anything without an animation NFO or allowlist match.  Its
qvbr 28 was derived from three grain-heavy 4K films and validated on one more
(Alien 1979, 56% smaller for -0.40 VMAF-neg).

But the fall-through also carries every 1080p WEB-DL and streaming source in
the library, and that class has exactly one measurement behind it -- Sugar
S02E08, 4.3% smaller at +0.04 VMAF-neg.  Fine, and n=1.  Clean digital has far
less high-frequency content than grainy film, and the animation sweep already
showed that lookahead's benefit shrinks as high-frequency content does
(5.6--12.5% on animation against 21--32% on film), so there is a specific
reason to expect 28 not to transfer here either.

Same method as `animation_bucket_calibration.py`, whose helpers this reuses:
cut once and encode from the cut, score with the vmaf binary, target VMAF-neg,
sources are originals rather than library copies.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from animation_bucket_calibration import (
    cut, encode, vmaf_neg, interpolate, resolve)

OUT = Path("/tmp/downloads/clean-digital-20260807")
DL = Path("/tmp/downloads/tv-shows")
SEED = Path("/media/merged-storage/media/downloads/long-term-seeding/tv-shows")

# Streaming/WEB-DL sources: no film grain, heavily pre-denoised by the
# distributor, which is the class the fall-through actually serves.
TITLES = {
    "Silo_S03E06": DL / "Silo.S03E06.The.Drive.1080p.ATVP.WEB-DL.DDP5.1.Atmos.H.264-playWEB.mkv",
    "StarTrek_SNW": DL / ("Star.Trek.Strange.New.Worlds.S04E03.Human.Best.Friend."
                          "1080p.AMZN.WEB-DL.DDP5.1.H.264-FLUX.mkv"),
    "BigBrother_S28E14": DL / "Big.Brother.US.S28E14.1080p.AMZN.WEB-DL.DDP2.0.H.264-NTb.mkv",
}

BASELINE_QVBR = 29          # what cq29 mapped to before lookahead
SWEEP = (26, 28, 30, 32, 34)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--seek", type=float, default=900.0)
    p.add_argument("--frames", type=int, default=288)
    args = p.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    work = OUT / "work"; work.mkdir(exist_ok=True)
    report: dict[str, dict] = {}

    for name, raw in TITLES.items():
        source = resolve(raw)
        if source is None:
            print(f"skip {name}: no source at {raw}", file=sys.stderr)
            continue
        height = json.loads(subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=height", "-of", "json", str(source)],
            capture_output=True, text=True).stdout)["streams"][0]["height"]
        ref = OUT / f"{name}-ref.mkv"
        cut(source, ref, args.seek, args.frames)
        print(f"\n### {name}  ({height}p)", flush=True)

        base = OUT / f"{name}-old-q{BASELINE_QVBR}.mkv"
        bsize = encode(ref, base, BASELINE_QVBR, lookahead=False)
        target = vmaf_neg(ref, base, height, work)
        print(f"  baseline  qvbr{BASELINE_QVBR} (no lookahead)  "
              f"{bsize/1e6:7.2f}MB  vmaf_neg {target:6.2f}", flush=True)

        sweep = []
        report[name] = {"height": height, "baseline_bytes": bsize,
                        "baseline_vmaf_neg": target, "sweep": {}}
        for q in SWEEP:
            enc = OUT / f"{name}-new-q{q}.mkv"
            size = encode(ref, enc, q, lookahead=True)
            v = vmaf_neg(ref, enc, height, work)
            sweep.append((q, v))
            report[name]["sweep"][q] = {"bytes": size, "vmaf_neg": v}
            print(f"  lookahead qvbr{q:<3}                  "
                  f"{size/1e6:7.2f}MB  vmaf_neg {v:6.2f}", flush=True)
        report[name]["match_qvbr"] = interpolate(sweep, target)

    (OUT / "clean-digital.json").write_text(json.dumps(report, indent=2) + "\n")

    print("\n=== qvbr reproducing the old cq29 quality, with lookahead ===")
    matches = []
    for name, r in report.items():
        m = r.get("match_qvbr")
        if m is None:
            print(f"  {name:20} off-range (target {r['baseline_vmaf_neg']:.2f})")
            continue
        matches.append(m)
        lo = max(q for q in SWEEP if q <= m); hi = min(q for q in SWEEP if q >= m)
        s = r["sweep"]
        nb = (s[lo]["bytes"] + s[hi]["bytes"]) / 2 if lo != hi else s[lo]["bytes"]
        print(f"  {name:20} qvbr {m:5.1f}   "
              f"{r['baseline_bytes']/1e6:6.2f} -> {nb/1e6:6.2f} MB   "
              f"{1 - nb/r['baseline_bytes']:+6.1%}")
    if matches:
        print(f"\n  clean digital wants cq29 -> qvbr {sum(matches)/len(matches):.1f}"
              f"   (currently deployed: 28, from grainy film)")
        print("  note: cq29 also serves 4K film via the override, where 28 is"
              "\n  validated. If these disagree materially the bucket is doing two"
              "\n  jobs and the router needs a third branch, not a compromise value.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
