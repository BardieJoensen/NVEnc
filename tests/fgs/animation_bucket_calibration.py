#!/usr/bin/env python3
"""Calibrate the animation bucket (cq34) for the deployed lookahead settings.

`FINDINGS-2026-08-07-LOOKAHEAD-BUCKETS.md` calibrated the qvbr buckets on three
grain-heavy 4K films and applied the result library-wide.  The re-run showed
that was wrong for animation, in the opposite direction from the one feared:

    Elemental  old (qvbr34, no lookahead)  4.95 MB  vmaf_neg 90.36
               new (qvbr33, lookahead)     5.14 MB  vmaf_neg 91.10

3.9% *larger* for +0.74 quality.  Lookahead's efficiency gain is smaller on
animation than on grainy film, so dropping 34 -> 33 more than offset it and the
bucket now buys quality nobody asked for.  Bucket 34 needs to move up.

Method mirrors `bucket_calibration.py` with two corrections learned the hard
way:

* **Cut once, encode from the cut.**  nvencc's `--seek` and ffmpeg's `-ss` do
  not land on the same frame; seeking separately in the encoder and the
  reference silently scores different content and reads as a broken encode
  (vmaf_neg 0.15, ssimu2 -411) rather than as the misalignment it is.
* **Score with the vmaf binary directly.**  `campaign.score` returned garbage
  on this material -- SSIMULACRA2 -411 and Butteraugli 275 on encodes PSNR puts
  at 34.9 dB -- so it is not trusted here.

VMAF-neg is the target: FGS is enabled in every arm and the default model pays
an enhancement bonus for synthesized grain.

Sources are originals from the download tree, never library copies: every one
of these titles exists in the library as AV1 already, and re-encoding that
would measure a second generation.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

BIN = Path("/opt/docker-apps/build/tdarr-node/nvencc")
VMAF = Path.home() / "git-repos/vmaf/libvmaf/build/tools/vmaf"
OUT = Path("/tmp/downloads/animation-bucket-20260807")
SEED = Path("/media/merged-storage/media/downloads/long-term-seeding/movies")

TITLES = {
    "Elemental": Path("/tmp/downloads/movies/"
        "Elemental 2023 BluRay 1080p TrueHD Atmos 7 1 AVC HYBRID REMUX-FraMeSToR/"
        "Elemental.2023.BluRay.1080p.TrueHD.Atmos.7.1.AVC.HYBRID.REMUX-FraMeSToR/"
        "Elemental.2023.BluRay.1080p.TrueHD.Atmos.7.1.AVC.HYBRID.REMUX-FraMeSToR.mkv"),
    "LongHalloween": SEED / ("Batman The Long Halloween 2021 Deluxe Edition BluRay "
        "1080p DTS-HD MA 5 1 AVC REMUX-FraMeSToR"),
    "DarkKnightReturns": SEED / ("Batman The Dark Knight Returns 2013 Deluxe Edition "
        "BluRay 1080p DTS-HD MA 5 1 AVC REMUX-FraMeSToR"),
}

DEPLOYED = ("--codec av1 --output-depth 10 --max-bitrate 50000 "
            "--av1-film-grain denoise=auto,chroma=auto,denoiser=bilateral "
            "--preset quality --tune hq --lookahead 32 --lookahead-level 3 "
            "--aq --aq-temporal --colormatrix auto --colorprim auto "
            "--transfer auto --colorrange auto")
NO_LOOKAHEAD = DEPLOYED.replace("--lookahead 32 --lookahead-level 3 ", "")

BASELINE_QVBR = 34          # what cq34 mapped to before lookahead
SWEEP = (32, 34, 36, 38, 40)


def resolve(p: Path) -> Path | None:
    if p.is_file():
        return p
    if p.is_dir():
        vids = sorted(p.rglob("*.mkv"), key=lambda f: -f.stat().st_size)
        return vids[0] if vids else None
    return None


def cut(source: Path, ref: Path, seek: float, frames: int) -> None:
    if ref.is_file():
        return
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(seek), "-i", str(source),
                    "-frames:v", str(frames), "-an", "-c:v", "ffvhuff",
                    "-pix_fmt", "yuv420p10le", str(ref)], check=True)


def encode(ref: Path, out: Path, qvbr: int, lookahead: bool) -> int:
    if not out.is_file():
        args = (DEPLOYED if lookahead else NO_LOOKAHEAD).split()
        r = subprocess.run([str(BIN), "--avsw", "-i", str(ref)] + args
                           + ["--qvbr", str(qvbr), "-o", str(out)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"{out.name}:\n{r.stderr[-1200:]}")
    return out.stat().st_size


def vmaf_neg(ref: Path, enc: Path, height: int, work: Path) -> float:
    """Score with the vmaf binary; campaign.score is not trusted on this material."""
    model = "vmaf_4k_v0.6.1" if height > 1200 else "vmaf_v0.6.1"
    r_y4m, d_y4m = work / "r.y4m", work / "d.y4m"
    # 4K y4m runs ~7 GB a side, so these live on the roomy filesystem, not /tmp.
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(ref), "-pix_fmt", "yuv420p10le",
                    "-f", "yuv4mpegpipe", "-strict", "-1", "-y", str(r_y4m)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-c:v", "libdav1d", "-i", str(enc),
                    "-pix_fmt", "yuv420p10le", "-f", "yuv4mpegpipe", "-strict", "-1",
                    "-y", str(d_y4m)], check=True)
    out = work / "o.json"
    r = subprocess.run([str(VMAF), "--reference", str(r_y4m), "--distorted", str(d_y4m),
                        "--model", f"version={model}:name=vmaf",
                        "--model", f"version={model}neg:name=vmaf_neg",
                        "--json", "--output", str(out)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"vmaf failed on {enc.name}: {r.stderr[-600:]}")
    d = json.loads(out.read_text())["pooled_metrics"]
    for f in (r_y4m, d_y4m):
        f.unlink(missing_ok=True)
    return d["vmaf_neg"]["mean"]


def interpolate(sweep, target):
    for (q0, v0), (q1, v1) in zip(sorted(sweep), sorted(sweep)[1:]):
        if (v0 - target) * (v1 - target) <= 0 and v0 != v1:
            return q0 + (v0 - target) * (q1 - q0) / (v0 - v1)
    return None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--seek", type=float, default=1500.0)
    p.add_argument("--frames", type=int, default=288)
    args = p.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    work = OUT / "work"; work.mkdir(exist_ok=True)
    report = {}

    for name, raw in TITLES.items():
        source = resolve(raw)
        if source is None:
            print(f"skip {name}: no source at {raw}", file=sys.stderr)
            continue
        info = json.loads(subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=height", "-of", "json", str(source)],
            capture_output=True, text=True).stdout)["streams"][0]
        height = info["height"]
        ref = OUT / f"{name}-ref.mkv"
        cut(source, ref, args.seek, args.frames)
        print(f"\n### {name}  ({height}p)", flush=True)

        base = OUT / f"{name}-old-q{BASELINE_QVBR}.mkv"
        bsize = encode(ref, base, BASELINE_QVBR, lookahead=False)
        btarget = vmaf_neg(ref, base, height, work)
        print(f"  baseline  qvbr{BASELINE_QVBR} (no lookahead)  "
              f"{bsize/1e6:7.2f}MB  vmaf_neg {btarget:6.2f}", flush=True)

        sweep = []
        for q in SWEEP:
            enc = OUT / f"{name}-new-q{q}.mkv"
            size = encode(ref, enc, q, lookahead=True)
            v = vmaf_neg(ref, enc, height, work)
            sweep.append((q, v))
            print(f"  lookahead qvbr{q:<3}                  "
                  f"{size/1e6:7.2f}MB  vmaf_neg {v:6.2f}", flush=True)
            report.setdefault(name, {}).setdefault("sweep", {})[q] = {
                "bytes": size, "vmaf_neg": v}
        report[name].update({"height": height, "baseline_bytes": bsize,
                             "baseline_vmaf_neg": btarget})
        report[name]["match_qvbr"] = interpolate(sweep, btarget)

    (OUT / "animation-bucket.json").write_text(json.dumps(report, indent=2) + "\n")

    print("\n=== qvbr reproducing the old cq34 quality, with lookahead ===")
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
        print(f"\n  recommended cq34 -> qvbr {sum(matches)/len(matches):.1f}"
              f"   (currently deployed: 33)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
