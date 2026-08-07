#!/usr/bin/env python3
"""Verify the deployed buckets against originals, per routing branch.

Covers every branch the router can now take, including the three titles run
before the flow was actually live (Alien, Sugar, Elemental -- those jobs used
qvbr 29/29/34 with no lookahead because Tdarr reads its flow from the database
and the edits were sitting in the exported JSON).

    bucket 29  4K override only    -> qvbr 27
    bucket 30  fall-through        -> qvbr 30
    bucket 34  animation NFO       -> qvbr 34

Each title is encoded twice from a single lossless cut of its original: once at
the pre-lookahead settings for that branch, once at the deployed settings.  Both
read the same cut, so the two arms and the reference are aligned by
construction.

**Alignment is verified rather than assumed.**  Three separate runs today
produced impossible scores from misaligned comparisons -- independent seeking in
encoder and reference, and a one-frame encoder offset on Elemental that made it
read as 39 VMAF-neg.  Comparing per-frame luma means at lag 0 against lag 1
catches both, and a title that fails is reported rather than scored.

Scoring goes through the vmaf binary directly.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from animation_bucket_calibration import cut, encode, resolve, vmaf_neg

OUT = Path("/tmp/downloads/deployed-verify-20260807")
MOV = Path("/tmp/downloads/movies")
DL_TV = Path("/tmp/downloads/tv-shows")
SEED_TV = Path("/media/merged-storage/media/downloads/long-term-seeding/tv-shows")
SEED_MOV = Path("/media/merged-storage/media/downloads/long-term-seeding/movies")

# (title, source, branch, old qvbr, deployed qvbr)
CASES = [
    ("Alien_1979", MOV / ("Alien.1979.Directors.Cut.UHD.BluRay.2160p.DTS-HD.MA.5.1."
        "HEVC.REMUX-FraMeSToR/Alien.1979.Directors.Cut.UHD.BluRay.2160p.DTS-HD.MA.5.1."
        "HEVC.REMUX-FraMeSToR.mkv"), "cq29 4K", 29, 27),
    ("HotD_S03E07", SEED_TV / ("House.of.the.Dragon.S03E07.2160p.HMAX.WEB-DL.DDP5.1."
        "Atmos.H.265-N1H4L.mkv"), "cq29 4K", 29, 27),
    ("Sugar_S02E08", DL_TV / ("Sugar.2024.S02E08.Like.Sugar.1080p.ATVP.WEB-DL.DDP5.1."
        "Atmos.H.264-playWEB.mkv"), "cq30 other", 29, 30),
    ("Silo_S03E06", DL_TV / ("Silo.S03E06.The.Drive.1080p.ATVP.WEB-DL.DDP5.1.Atmos."
        "H.264-playWEB.mkv"), "cq30 other", 29, 30),
    ("Elemental", MOV / ("Elemental 2023 BluRay 1080p TrueHD Atmos 7 1 AVC HYBRID "
        "REMUX-FraMeSToR/Elemental.2023.BluRay.1080p.TrueHD.Atmos.7.1.AVC.HYBRID."
        "REMUX-FraMeSToR/Elemental.2023.BluRay.1080p.TrueHD.Atmos.7.1.AVC.HYBRID."
        "REMUX-FraMeSToR.mkv"), "cq34 anim", 34, 34),
    ("LongHalloween", SEED_MOV / ("Batman The Long Halloween 2021 Deluxe Edition "
        "BluRay 1080p DTS-HD MA 5 1 AVC REMUX-FraMeSToR"), "cq34 anim", 34, 34),
]


def frame_means(path: Path, decoder: str | None, n: int = 16) -> np.ndarray:
    st = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height", "-of", "json", str(path)],
        capture_output=True, text=True).stdout)["streams"][0]
    w, h = st["width"], st["height"]
    cmd = ["ffmpeg", "-v", "error", "-nostdin"]
    if decoder:
        cmd += ["-c:v", decoder]
    cmd += ["-i", str(path), "-frames:v", str(n), "-pix_fmt", "gray10le",
            "-f", "rawvideo", "-"]
    a = np.frombuffer(subprocess.run(cmd, capture_output=True).stdout,
                      np.uint16).astype(np.float64)
    k = a.size // (w * h)
    return a[:k * w * h].reshape(k, h * w).mean(axis=1)


def aligned(ref: Path, enc: Path) -> tuple[bool, float, float]:
    """True when the encode matches the reference frame-for-frame."""
    r, e = frame_means(ref, None), frame_means(enc, "libdav1d")
    n = min(len(r), len(e)) - 1
    if n < 4:
        return False, float("nan"), float("nan")
    lag0 = float(np.abs(r[:n] - e[:n]).mean())
    lag1 = float(np.abs(r[1:n + 1] - e[:n]).mean())
    return lag1 >= lag0 * 0.6, lag0, lag1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--seek", type=float, default=1500.0)
    p.add_argument("--frames", type=int, default=192)
    args = p.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    work = OUT / "work"; work.mkdir(exist_ok=True)
    rows = []
    for name, raw, branch, oldq, newq in CASES:
        source = resolve(raw)
        if source is None:
            print(f"skip {name}: no source", file=sys.stderr)
            continue
        height = json.loads(subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=height", "-of", "json", str(source)],
            capture_output=True, text=True).stdout)["streams"][0]["height"]
        ref = OUT / f"{name}-ref.mkv"
        cut(source, ref, args.seek, args.frames)
        print(f"\n### {name}  [{branch}]  {oldq} -> {newq}", flush=True)

        row = {"branch": branch, "height": height}
        bad = False
        for tag, q, la in (("old", oldq, False), ("new", newq, True)):
            enc = OUT / f"{name}-{tag}.mkv"
            size = encode(ref, enc, q, lookahead=la)
            ok, lag0, lag1 = aligned(ref, enc)
            if not ok:
                print(f"  {tag}: MISALIGNED (lag0 {lag0:.3f} lag1 {lag1:.3f}) "
                      f"-- not scoring", flush=True)
                bad = True
                continue
            v = vmaf_neg(ref, enc, height, work)
            row[tag] = {"qvbr": q, "bytes": size, "vmaf_neg": v}
            print(f"  {tag} qvbr{q:<3} {size/1e6:8.2f}MB  neg {v:6.2f}", flush=True)
        if not bad and "old" in row and "new" in row:
            rows.append((name, row))

    (OUT / "deployed-verify.json").write_text(
        json.dumps({n: r for n, r in rows}, indent=2) + "\n")

    print("\n=== deployed vs pre-lookahead, scored against the original ===")
    print(f"{'title':16} {'branch':12} {'size':>20} {'vmaf_neg':>16}")
    for name, r in rows:
        o, n2 = r["old"], r["new"]
        print(f"{name:16} {r['branch']:12} "
              f"{o['bytes']/1e6:7.2f}->{n2['bytes']/1e6:6.2f}MB {1-n2['bytes']/o['bytes']:+7.1%} "
              f"{o['vmaf_neg']:7.2f}->{n2['vmaf_neg']:6.2f} {n2['vmaf_neg']-o['vmaf_neg']:+5.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
