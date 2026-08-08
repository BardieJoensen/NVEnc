#!/usr/bin/env python3
"""Does anisotropy ranking fix over-synthesis without breaking strong grain?

The compressive measurement was traced to one coefficient: flat blocks are
selected by libaom's flat_block_finder logistic, whose dominant term is
`-6682 * varNorm` -- the block's own variance.  Grainy blocks rank as less
flat, and the top-scoring blocks are then used to *measure* grain.
`NVENC_FGS_TEST_MEASURE_RANK=on` ranks on anisotropy instead.

The test is **selectivity, not level**.  A change that lowered delivered grain
everywhere would "fix" the weak-grain titles and quietly wreck the strong-grain
ones, and a level test cannot tell that from a real fix.  So:

  weak-grain sources   retention should fall toward 1.0
  strong-grain sources retention should NOT move

Retention is delivered grain over source grain, measured the way the library
verifier measures it: high-frequency energy in the decoded output against the
same in the source, on flat regions.  Both arms encode from one lossless cut of
the original, so they and the reference are aligned by construction, and
alignment is verified per encode rather than assumed -- three runs in this
project produced confident nonsense from misalignment.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

from animation_bucket_calibration import cut, resolve as _resolve
from deployed_verification import aligned

BASE = Path("/opt/docker-apps/build/tdarr-node/nvencc")
OUT = Path("/tmp/downloads/measure-rank-20260808")
MOV = Path("/tmp/downloads/movies")
DL_TV = Path("/tmp/downloads/tv-shows")
SEED_MOV = Path("/media/merged-storage/media/downloads/long-term-seeding/movies")
SEED_TV = Path("/media/merged-storage/media/downloads/long-term-seeding/tv-shows")


def resolve(raw: Path):
    """Sources age out of /tmp/downloads into long-term-seeding after ~36h, so
    a path that worked yesterday is gone today.  Fall back by basename."""
    got = _resolve(raw)
    if got is not None:
        return got
    for root in (SEED_MOV, SEED_TV):
        for cand in root.rglob(raw.name):
            got = _resolve(cand)
            if got is not None:
                return got
        stem = raw.name.split(".")[0].split(" ")[0]
        if len(stem) >= 4:
            for cand in root.glob(f"*{stem}*"):
                got = _resolve(cand)
                if got is not None:
                    return got
    return None
KEEP = Path("/media/merged-storage/media/test-encodes/keep-original")

FGS = "denoise=auto,chroma=auto,denoiser=bilateral"
ARGS = ("--codec av1 --output-depth 10 --max-bitrate 50000 "
        f"--av1-film-grain {FGS} --preset quality --tune hq "
        "--lookahead 32 --lookahead-level 3 --aq --aq-temporal "
        "--colormatrix auto --colorprim auto --transfer auto --colorrange auto")

# grain class -> titles.  Weak-grain is where over-synthesis was reported;
# strong-grain is the control that must not move.
CASES = [
    ("weak", "Elemental", MOV / ("Elemental 2023 BluRay 1080p TrueHD Atmos 7 1 AVC HYBRID "
        "REMUX-FraMeSToR/Elemental.2023.BluRay.1080p.TrueHD.Atmos.7.1.AVC.HYBRID."
        "REMUX-FraMeSToR/Elemental.2023.BluRay.1080p.TrueHD.Atmos.7.1.AVC.HYBRID."
        "REMUX-FraMeSToR.mkv"), 34),
    ("weak", "LongHalloween", SEED_MOV / ("Batman The Long Halloween 2021 Deluxe Edition "
        "BluRay 1080p DTS-HD MA 5 1 AVC REMUX-FraMeSToR"), 34),
    ("weak", "Silo_S03E06", DL_TV / ("Silo.S03E06.The.Drive.1080p.ATVP.WEB-DL.DDP5.1."
        "Atmos.H.264-playWEB.mkv"), 30),
    ("weak", "Sugar_S02E08", DL_TV / ("Sugar.2024.S02E08.Like.Sugar.1080p.ATVP.WEB-DL."
        "DDP5.1.Atmos.H.264-playWEB.mkv"), 30),
    ("strong", "Alien_1979", MOV / ("Alien.1979.Directors.Cut.UHD.BluRay.2160p.DTS-HD.MA."
        "5.1.HEVC.REMUX-FraMeSToR/Alien.1979.Directors.Cut.UHD.BluRay.2160p.DTS-HD.MA."
        "5.1.HEVC.REMUX-FraMeSToR.mkv"), 27),
    ("strong", "Taxi_Driver", KEEP / "clip_Taxi_Driver-ref288.mkv", 27),
    ("strong", "The_Shining", KEEP / "clip_The_Shining-ref288.mkv", 27),
    ("strong", "Casino", KEEP / "clip_Casino-ref288.mkv", 27),
]


def encode(binary: Path, ref: Path, out: Path, qvbr: int, rank: bool) -> int:
    if out.is_file():
        return out.stat().st_size
    env = dict(os.environ)
    env.pop("NVENC_FGS_TEST_MEASURE_RANK", None)
    if rank:
        env["NVENC_FGS_TEST_MEASURE_RANK"] = "on"
    r = subprocess.run([str(binary), "--avsw", "-i", str(ref)] + ARGS.split()
                       + ["--qvbr", str(qvbr), "-o", str(out)],
                       capture_output=True, text=True, env=env)
    if r.returncode != 0:
        raise RuntimeError(f"{out.name}:\n{r.stderr[-1200:]}")
    blob = r.stderr + r.stdout
    if rank and "anisotropy" not in blob:
        raise RuntimeError(f"{out.name}: MEASURE_RANK did not take effect")
    if not rank and "anisotropy" in blob:
        raise RuntimeError(f"{out.name}: control arm applied the override")
    return out.stat().st_size


def hf_energy(path: Path, decoder: str | None, frames: int) -> float:
    """High-frequency energy on flat regions -- the retention numerator/denominator."""
    st = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height", "-of", "json", str(path)],
        capture_output=True, text=True).stdout)["streams"][0]
    w, h = st["width"], st["height"]
    cmd = ["ffmpeg", "-v", "error", "-nostdin"]
    if decoder:
        cmd += ["-c:v", decoder]
    cmd += ["-i", str(path), "-frames:v", str(frames), "-pix_fmt", "gray10le",
            "-f", "rawvideo", "-"]
    a = np.frombuffer(subprocess.run(cmd, capture_output=True).stdout,
                      np.uint16).astype(np.float64)
    n = a.size // (w * h)
    a = a[:n * w * h].reshape(n, h, w)
    block = 32
    by, bx = h // block, w // block
    t = (a[:, :by * block, :bx * block].reshape(n, by, block, bx, block)
         .transpose(0, 1, 3, 2, 4).reshape(n, by * bx, block, block))
    pool = block // 8
    coarse = t.reshape(n, by * bx, 8, pool, 8, pool).mean(axis=(3, 5))
    up = np.repeat(np.repeat(coarse, pool, axis=2), pool, axis=3)
    noise = (t - up).reshape(n, by * bx, block * block).std(axis=2)
    structure = coarse.reshape(n, by * bx, 64).std(axis=2)
    keep = max(1, int(structure.shape[1] * 0.25))
    order = np.argsort(structure, axis=1)[:, :keep]
    sel = np.take_along_axis(noise, order, axis=1).ravel()
    sel = sel[sel > 0]
    return float(np.median(sel)) if sel.size else 0.0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--binary", required=True)
    p.add_argument("--seek", type=float, default=1500.0)
    p.add_argument("--frames", type=int, default=192)
    args = p.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for cls, name, raw, qvbr in CASES:
        source = resolve(raw)
        if source is None:
            print(f"skip {name}: no source", file=sys.stderr)
            continue
        ref = OUT / f"{name}-ref.mkv"
        cut(source, ref, args.seek, args.frames)
        src_hf = hf_energy(ref, None, args.frames)
        if src_hf <= 0:
            print(f"skip {name}: no measurable source grain", file=sys.stderr)
            continue
        print(f"\n### [{cls}] {name}  qvbr{qvbr}  source HF {src_hf:.3f}", flush=True)
        row = {"class": cls, "qvbr": qvbr, "source_hf": src_hf}
        ok = True
        for tag, rank in (("off", False), ("on", True)):
            enc = OUT / f"{name}-{tag}.mkv"
            size = encode(Path(args.binary), ref, enc, qvbr, rank)
            good, lag0, lag1 = aligned(ref, enc)
            if not good:
                print(f"  {tag}: MISALIGNED ({lag0:.3f}/{lag1:.3f}) -- not scoring")
                ok = False
                continue
            hf = hf_energy(enc, "libdav1d", args.frames)
            row[tag] = {"bytes": size, "hf": hf, "retention": hf / src_hf}
            print(f"  rank={tag:3} {size/1e6:8.2f}MB  HF {hf:.3f}  "
                  f"retention {hf/src_hf:.3f}", flush=True)
        if ok and "off" in row and "on" in row:
            rows.append((name, row))

    (OUT / "measure-rank.json").write_text(
        json.dumps({n: r for n, r in rows}, indent=2) + "\n")

    print("\n=== retention: 1.0 is correct, >1 is over-synthesis ===")
    print(f"{'title':16} {'class':7} {'off':>8} {'on':>8} {'change':>9} {'size':>9}")
    for name, r in rows:
        o, n2 = r["off"], r["on"]
        print(f"{name:16} {r['class']:7} {o['retention']:8.3f} {n2['retention']:8.3f} "
              f"{n2['retention']-o['retention']:+9.3f} "
              f"{1-n2['bytes']/o['bytes']:+8.1%}")
    weak = [r for _, r in rows if r["class"] == "weak"]
    strong = [r for _, r in rows if r["class"] == "strong"]
    if weak and strong:
        dw = sum(r["on"]["retention"] - r["off"]["retention"] for r in weak) / len(weak)
        ds = sum(r["on"]["retention"] - r["off"]["retention"] for r in strong) / len(strong)
        print(f"\n  mean change  weak {dw:+.3f}   strong {ds:+.3f}")
        print("  a fix moves weak toward 1.0 and leaves strong alone;"
              "\n  both moving down together is a global gain change, not a fix.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
