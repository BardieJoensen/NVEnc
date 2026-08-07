#!/usr/bin/env python3
"""Re-run the smoke-test titles from their ORIGINALS under the deployed flow.

The first attempt at these three tested nothing: Tdarr runs its flow from the
database (`flowsjsondb`), not from the exported JSON under
`configs/tdarr-flow/flows/`, so the edits sat on disk while every job used the
old settings.  The job reports show `--qvbr 29` and no lookahead.  Routing was
correct on all three -- 4K override, no-match, and animation NFO all fired --
so only the encode settings went untested.

The flow has since been written into the database and verified across a Tdarr
restart.  This re-runs the three titles at the settings that are now live.

**From the originals, not the library copies.**  All three library files were
replaced in place by the first run, so re-encoding those would measure a second
generation -- the exact fault that invalidated the animation gate result
(`FINDINGS-2026-08-07-LIBRARY-AUDIT.md`).  The originals are in
`/tmp/downloads`, and scoring uses them as reference too.

Arguments are the deployed template verbatim, with the flow's own bucket logic
applied to pick qvbr:

    4K (4KUHD/DCI4K/8KUHD)      -> cq29 -> qvbr 28
    animation genre in the NFO  -> cq34 -> qvbr 33
    otherwise                   -> cq29 -> qvbr 28

A segment rather than a whole feature: a full 4K remux is hours of encoding and
the question here is whether the settings are right per content class, which a
representative segment answers.  These outputs are test artifacts and are not
written into the library.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import campaign

BIN = Path("/opt/docker-apps/build/tdarr-node/nvencc")
OUT = Path("/tmp/downloads/flow-rerun-20260807")

# (label, original source, bucket, qvbr as the deployed flow resolves it)
CASES = [
    ("Alien_1979_4K", Path("/tmp/downloads/movies/"
      "Alien.1979.Directors.Cut.UHD.BluRay.2160p.DTS-HD.MA.5.1.HEVC.REMUX-FraMeSToR/"
      "Alien.1979.Directors.Cut.UHD.BluRay.2160p.DTS-HD.MA.5.1.HEVC.REMUX-FraMeSToR.mkv"),
     "cq29 (4K override)", 28),
    ("Elemental_anim", Path("/tmp/downloads/movies/"
      "Elemental 2023 BluRay 1080p TrueHD Atmos 7 1 AVC HYBRID REMUX-FraMeSToR/"
      "Elemental.2023.BluRay.1080p.TrueHD.Atmos.7.1.AVC.HYBRID.REMUX-FraMeSToR/"
      "Elemental.2023.BluRay.1080p.TrueHD.Atmos.7.1.AVC.HYBRID.REMUX-FraMeSToR.mkv"),
     "cq34 (animation NFO)", 33),
    ("Sugar_S02E08", Path("/tmp/downloads/tv-shows/"
      "Sugar.2024.S02E08.Like.Sugar.1080p.ATVP.WEB-DL.DDP5.1.Atmos.H.264-playWEB.mkv"),
     "cq29 (no match)", 28),
]

# The deployed encode arguments, minus qvbr and the per-file variables.
DEPLOYED = ("--codec av1 --output-depth 10 --max-bitrate 50000 "
            "--av1-film-grain denoise=auto,chroma=auto,denoiser=bilateral "
            "--preset quality --tune hq --lookahead 32 --lookahead-level 3 "
            "--aq --aq-temporal --colormatrix auto --colorprim auto "
            "--transfer auto --colorrange auto --master-display copy --max-cll copy")

# The old settings, for the comparison the first run should have produced.
BASELINE_QVBR = {28: 29, 33: 34}


def encode(source: Path, out: Path, qvbr: int, lookahead: bool) -> float:
    """Encode the pre-cut segment.

    `source` here is the lossless intermediate, not the original.  nvencc's
    `--seek` and ffmpeg's `-ss` do not land on the same frame, so seeking
    independently in the encoder and in the reference scored different content
    against each other -- vmaf_neg 0.15 and ssimu2 -411, which read as a broken
    encode rather than as the misalignment they were.  Cutting once and
    encoding from that cut makes alignment structural instead of assumed.
    """
    if out.is_file():
        return out.stat().st_size
    args = DEPLOYED if lookahead else DEPLOYED.replace(
        "--lookahead 32 --lookahead-level 3 ", "")
    command = ([str(BIN), "--avsw", "-i", str(source)]
               + args.split() + ["--qvbr", str(qvbr), "-o", str(out)])
    r = subprocess.run(command, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{out.name}:\n{r.stderr[-1500:]}")
    blob = r.stderr + r.stdout
    if lookahead and "lookahead" not in blob.lower():
        print(f"  warning: cannot confirm lookahead for {out.name}", file=sys.stderr)
    return out.stat().st_size


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--seek", type=float, default=1500.0)
    p.add_argument("--frames", type=int, default=288)
    p.add_argument("--cases", nargs="*", default=[c[0] for c in CASES])
    args = p.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    for label, source, bucket, qvbr in CASES:
        if label not in args.cases:
            continue
        if not source.is_file():
            print(f"skip {label}: missing {source}", file=sys.stderr)
            continue
        print(f"\n### {label}  [{bucket}]  qvbr {qvbr} (was {BASELINE_QVBR[qvbr]})",
              flush=True)

        info = json.loads(subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height", "-of", "json", str(source)],
            capture_output=True, text=True).stdout)["streams"][0]
        height = info["height"]

        # Lossless reference for the same segment, inside the working directory
        # so the FFVship container can see it.
        ref = OUT / f"{label}-ref.mkv"
        if not ref.is_file():
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-ss", str(args.seek), "-i", str(source),
                 "-frames:v", str(args.frames), "-an", "-c:v", "ffvhuff",
                 "-pix_fmt", "yuv420p10le", str(ref)], check=True)

        row = {"bucket": bucket, "height": height}
        for tag, q, la in (("new", qvbr, True), ("old", BASELINE_QVBR[qvbr], False)):
            enc = OUT / f"{label}-{tag}.mkv"
            size = encode(ref, enc, q, la)
            s = campaign.score(str(ref), str(enc), f"{label}-{tag}", str(OUT),
                               height, args.frames)
            s["bytes"] = size
            s["qvbr"] = q
            row[tag] = s
            print(f"  {tag:3} qvbr{q:<3} {size/1e6:8.2f}MB  "
                  f"vmaf_neg {s['vmaf_neg']:6.2f}  ssimu2 {s['ssimu2']:6.2f}  "
                  f"butter_p95 {s['butter_max_p95']:6.2f}", flush=True)
        report[label] = row

    (OUT / "flow-rerun.json").write_text(json.dumps(report, indent=2) + "\n")

    print("\n=== deployed vs previous settings, scored against the ORIGINAL ===")
    print(f"{'case':16} {'bucket':22} {'size':>18} {'vmaf_neg':>16} {'butter p95':>14}")
    for label, r in report.items():
        o, n = r["old"], r["new"]
        print(f"{label:16} {r['bucket']:22} "
              f"{o['bytes']/1e6:7.1f}->{n['bytes']/1e6:6.1f}MB "
              f"{1-n['bytes']/o['bytes']:+6.1%} "
              f"{o['vmaf_neg']:7.2f}->{n['vmaf_neg']:6.2f} "
              f"{o['butter_max_p95']:6.2f}->{n['butter_max_p95']:5.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
