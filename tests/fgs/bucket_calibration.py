#!/usr/bin/env python3
"""Recalibrate the Tdarr qvbr buckets after enabling lookahead.

Measured on Casino 2026-08-06: adding `--lookahead 32 --lookahead-level 3` to
the production flow cuts bytes 53% at the same qvbr for -0.74 VMAF, and at
matched size beats the no-lookahead arm on VMAF, VMAF-neg, VMAF-min and the
Butteraugli artifact tail.  `--lookahead-level` is the whole effect: lookahead
without it reproduces the old flow to within 0.3%.  Multipass was dropped --
3.9% smaller for marginally *worse* quality and an extra pass.

The consequence is that qvbr no longer means what it used to.  The flow's
buckets (29 / 34 / 38) were chosen against the old rate-quality curve, so this
finds the qvbr that reproduces each bucket's *old quality* under the new
settings.  Without that, enabling lookahead silently moves the whole library to
a lower quality point that nobody chose.

Method: encode each title at each bucket with the OLD settings to get the
target scores, then sweep the NEW settings across a qvbr range and interpolate
where each target is met.  VMAF-neg is the primary target -- the default model
hands out an enhancement bonus for synthesized grain, and every arm here has
FGS enabled, so neg is the honest comparison.  Butteraugli's max p95 is
reported alongside because mean-pooled metrics average away exactly the starved
frames a rate-control change would cause.

Film titles only.  The buckets also serve animation and clean digital content,
whose rate-quality curves differ and which FGS additionally over-synthesizes
(~1.9x on grain-free material in the production analyser) -- those need their
own pass before any bucket is changed for them.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import campaign

BIN = Path("/opt/docker-apps/build/tdarr-node/nvencc")
FILM = Path("/media/merged-storage/media/test-encodes/keep-original")
OUT = Path("/tmp/downloads/bucket-calibration-20260807")

TITLES = {
    "Casino": FILM / "clip_Casino-ref288.mkv",
    "Scarface": FILM / "clip_Scarface-ref288.mkv",
    "Taxi_Driver": FILM / "clip_Taxi_Driver-ref288.mkv",
}

BUCKETS = (29, 34, 38)
SWEEP = (24, 26, 28, 30, 32, 34, 36)

# Exactly the production flow's encode arguments, minus the qvbr and the
# lookahead pair under test.  Kept as one string so it stays diffable against
# the flow template.
BASE = ("--codec av1 --output-depth 10 --max-bitrate 50000 "
        "--av1-film-grain denoise=auto,chroma=auto,denoiser=bilateral "
        "--preset quality --tune hq --aq --aq-temporal "
        "--colormatrix auto --colorprim auto --transfer auto --colorrange auto")
LOOKAHEAD = "--lookahead 32 --lookahead-level 3"


def encode(source: Path, output: Path, qvbr: int, lookahead: bool) -> None:
    if output.is_file():
        return
    command = ([str(BIN), "--avsw", "-i", str(source)] + BASE.split()
               + (LOOKAHEAD.split() if lookahead else [])
               + ["--qvbr", str(qvbr), "-o", str(output)])
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"{output.name}: {result.stderr[-1200:]}")
    blob = result.stderr + result.stdout
    if lookahead and "lookahead" not in blob.lower():
        # A silently dropped flag would make the new arm identical to the old
        # one and the calibration would report "no change needed".
        print(f"  warning: cannot confirm lookahead applied for {output.name}",
              file=sys.stderr)


def interpolate(sweep: list[tuple[int, float]], target: float) -> float | None:
    """qvbr at which the swept metric crosses `target` (metric falls with qvbr)."""
    ordered = sorted(sweep)
    for (q0, v0), (q1, v1) in zip(ordered, ordered[1:]):
        if (v0 - target) * (v1 - target) <= 0 and v0 != v1:
            return q0 + (v0 - target) * (q1 - q0) / (v0 - v1)
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=288)
    parser.add_argument("--metric", default="vmaf_neg")
    parser.add_argument("--titles", nargs="*", default=list(TITLES))
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    report: dict[str, dict] = {}

    for title in args.titles:
        source = TITLES[title]
        if not source.is_file():
            print(f"skip {title}: no source", file=sys.stderr)
            continue
        # campaign.score mounts the working directory as /data, so the lossless
        # reference has to live inside it; make_ref short-circuits to the clip's
        # own path when it is already ffvhuff, which the container cannot see.
        ref = OUT / f"{title}-ref.mkv"
        if not ref.is_file():
            built = campaign.make_ref(str(source), str(ref), args.frames)
            if Path(built) != ref:
                subprocess.run(["cp", str(built), str(ref)], check=True)
        report[title] = {"old": {}, "new": {}}

        for qvbr in BUCKETS:
            path = OUT / f"{title}-old-q{qvbr}.mkv"
            encode(source, path, qvbr, lookahead=False)
            r = campaign.score(str(ref), str(path), f"{title}-old-q{qvbr}",
                               str(OUT), 2160, args.frames)
            r["bytes"] = path.stat().st_size
            report[title]["old"][qvbr] = r
            print(f"{title:12} old q{qvbr:<3} {args.metric}={r[args.metric]:6.2f} "
                  f"bytes={r['bytes']/1e6:7.2f}MB", flush=True)

        for qvbr in SWEEP:
            path = OUT / f"{title}-new-q{qvbr}.mkv"
            encode(source, path, qvbr, lookahead=True)
            r = campaign.score(str(ref), str(path), f"{title}-new-q{qvbr}",
                               str(OUT), 2160, args.frames)
            r["bytes"] = path.stat().st_size
            report[title]["new"][qvbr] = r
            print(f"{title:12} new q{qvbr:<3} {args.metric}={r[args.metric]:6.2f} "
                  f"bytes={r['bytes']/1e6:7.2f}MB", flush=True)

    (OUT / "bucket-calibration.json").write_text(json.dumps(report, indent=2) + "\n")

    print(f"\n=== qvbr that reproduces each bucket's old {args.metric} ===")
    print(f"{'title':12} {'bucket':>7} {'old':>8} {'new qvbr':>9} "
          f"{'old MB':>8} {'new MB':>8} {'saving':>8}")
    recommend: dict[int, list[float]] = {b: [] for b in BUCKETS}
    for title, data in report.items():
        sweep = [(q, r[args.metric]) for q, r in data["new"].items()]
        for bucket in BUCKETS:
            if bucket not in data["old"]:
                continue
            target = data["old"][bucket][args.metric]
            matched = interpolate(sweep, target)
            old_mb = data["old"][bucket]["bytes"] / 1e6
            if matched is None:
                print(f"{title:12} {bucket:7} {target:8.2f} "
                      f"{'off-range':>9} {old_mb:8.2f}")
                continue
            recommend[bucket].append(matched)
            lo = max(q for q, _ in sweep if q <= matched)
            hi = min(q for q, _ in sweep if q >= matched)
            new_mb = ((data["new"][lo]["bytes"] + data["new"][hi]["bytes"]) / 2
                      if lo != hi else data["new"][lo]["bytes"]) / 1e6
            print(f"{title:12} {bucket:7} {target:8.2f} {matched:9.1f} "
                  f"{old_mb:8.2f} {new_mb:8.2f} {1 - new_mb / old_mb:7.1%}")

    print("\n=== recommended buckets ===")
    for bucket, values in recommend.items():
        if not values:
            print(f"  {bucket} -> (no crossing found)")
            continue
        mean = sum(values) / len(values)
        print(f"  {bucket} -> {mean:.1f}   (per-title {', '.join(f'{v:.1f}' for v in values)})")
    print("\nFilm titles only; animation and clean digital need their own pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
