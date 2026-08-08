#!/usr/bin/env python3
"""Is the compressive response an artifact of a non-clean base layer?

Eight analyser-side mechanisms have been falsified: selection ranking (twice),
the selection floor, the denoise floor, scaling-point quantisation, AR-gain
accounting, denoiser response shape, mean-of-variances inflation, and emission
cadence.  The arithmetic from measured variance to delivered amplitude checks
out at every step.  So the remaining candidate is that the analyser was never
wrong -- the *accounting between base and synthesis* is.

FGS assumes the base layer it encodes is clean, and that everything the viewer
sees is what synthesis put there.  It is not clean.  It carries

  * whatever grain the denoiser failed to remove, and
  * codec noise introduced by encoding the base at the operating QVBR.

Both are high-frequency energy on flat blocks, so both are counted as "grain" by
the retention metric and by the library verifier.  Delivered is therefore

    played^2  ~  base^2 + synth^2

with synthesis added at full strength on top (retain defaults to 0, so the
sqrt(1 - retain^2) closure never runs).

**The prediction that makes this decisive.**  If the base floor is a roughly
constant *absolute* quantity -- set by the operating point, not by how grainy
the source is -- then

    retention = sqrt(base_abs^2 + (k*src)^2) / src

blows up as src -> 0 and tends to k as src grows.  That is exactly the measured
compressive shape, and it predicts a crossover.  So:

    base_hf         should be roughly flat in absolute terms across the corpus
    synth/src       should be roughly FLAT and near 1.0 across the whole range

If instead synth/src is itself compressive, the base is not the explanation and
the defect really is in the analyser after all.

The base layer is read out of the *same bitstream* as the played frames, by
decoding with dav1d's synthesis disabled (`-filmgrain 0`).  No second encode,
no alignment risk between the arms: they are the same file.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

from animation_bucket_calibration import cut
from deployed_verification import aligned
from measure_rank_gate import KEEP, MOV, DL_TV, SEED_MOV, resolve

BIN = Path("/opt/docker-apps/build/tdarr-node/nvencc")
OUT = Path("/tmp/downloads/base-floor-20260808")

FGS = "denoise=auto,chroma=auto,denoiser=bilateral"
COMMON = ("--codec av1 --output-depth 10 --max-bitrate 50000 "
          "--preset quality --tune hq --lookahead 32 --lookahead-level 3 "
          "--aq --aq-temporal "
          "--colormatrix auto --colorprim auto --transfer auto --colorrange auto")
ARGS_FGS = f"--av1-film-grain {FGS} {COMMON}"
ARGS_PLAIN = COMMON

# The corpus has to span the grain range, because the claim is about how the
# floor behaves ACROSS that range -- a weak-grain-only corpus cannot separate
# "constant floor" from "compressive synthesis".
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
    ("strong", "Taxi_Driver", KEEP / "clip_Taxi_Driver-ref288.mkv", 27),
    ("strong", "The_Shining", KEEP / "clip_The_Shining-ref288.mkv", 27),
    ("strong", "Casino", KEEP / "clip_Casino-ref288.mkv", 27),
    ("strong", "Alien_1979", MOV / ("Alien.1979.Directors.Cut.UHD.BluRay.2160p.DTS-HD.MA."
        "5.1.HEVC.REMUX-FraMeSToR/Alien.1979.Directors.Cut.UHD.BluRay.2160p.DTS-HD.MA."
        "5.1.HEVC.REMUX-FraMeSToR.mkv"), 27),
]


def encode(ref: Path, out: Path, qvbr: int, fgs: bool) -> int:
    if out.is_file():
        return out.stat().st_size
    args = (ARGS_FGS if fgs else ARGS_PLAIN).split()
    r = subprocess.run([str(BIN), "--avsw", "-i", str(ref)] + args
                       + ["--qvbr", str(qvbr), "-o", str(out)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{out.name}:\n{r.stderr[-1200:]}")
    return out.stat().st_size


def hf_energy(path: Path, frames: int, filmgrain: bool | None = None) -> float:
    """HF energy on flat regions -- the same selector the retention metric uses.

    `filmgrain=False` decodes the base layer out of an FGS bitstream with the
    decoder's synthesis switched off, which is what makes this test cheap and
    alignment-free: played and base are literally the same file.
    """
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
                      np.uint16).astype(np.float64)
    n = a.size // (w * h)
    if n == 0:
        raise RuntimeError(f"{path.name}: decoded no frames")
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
    p.add_argument("--seek", type=float, default=1500.0)
    p.add_argument("--frames", type=int, default=192)
    p.add_argument("--plain", action="store_true",
                   help="also encode without FGS, to split codec noise from undenoised grain")
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
        src = hf_energy(ref, args.frames)
        if src <= 0:
            print(f"skip {name}: no measurable source grain", file=sys.stderr)
            continue

        enc = OUT / f"{name}-fgs.mkv"
        size = encode(ref, enc, qvbr, True)
        good, lag0, lag1 = aligned(ref, enc)
        if not good:
            print(f"skip {name}: MISALIGNED ({lag0:.3f}/{lag1:.3f})", file=sys.stderr)
            continue

        played = hf_energy(enc, args.frames, filmgrain=True)
        base = hf_energy(enc, args.frames, filmgrain=False)
        # played^2 ~ base^2 + synth^2, treating the two as independent.
        synth = float(np.sqrt(max(0.0, played ** 2 - base ** 2)))

        row = {"class": cls, "qvbr": qvbr, "src": src, "played": played,
               "base": base, "synth": synth, "bytes": size,
               "retention": played / src, "base_frac": base / src,
               "synth_frac": synth / src}

        if args.plain:
            pl = OUT / f"{name}-plain.mkv"
            encode(ref, pl, qvbr, False)
            row["plain"] = hf_energy(pl, args.frames, filmgrain=True)

        print(f"\n### [{cls}] {name}  qvbr{qvbr}", flush=True)
        print(f"  src {src:6.3f}   played {played:6.3f}   base {base:6.3f}   "
              f"synth {synth:6.3f}", flush=True)
        print(f"  retention {row['retention']:.3f}   base/src {row['base_frac']:.3f}   "
              f"synth/src {row['synth_frac']:.3f}", flush=True)
        if args.plain:
            print(f"  plain-encode HF {row['plain']:.3f}", flush=True)
        rows.append((name, row))

    (OUT / "base-floor.json").write_text(
        json.dumps({n: r for n, r in rows}, indent=2) + "\n")

    print("\n=== does the base floor explain the compressive response? ===")
    print(f"{'title':16} {'cls':7} {'qvbr':>4} {'src':>7} {'base':>7} {'synth':>7} "
          f"{'retention':>10} {'synth/src':>10}")
    for name, r in rows:
        print(f"{name:16} {r['class']:7} {r['qvbr']:4d} {r['src']:7.3f} {r['base']:7.3f} "
              f"{r['synth']:7.3f} {r['retention']:10.3f} {r['synth_frac']:10.3f}")

    if len(rows) >= 4:
        src = np.array([r["src"] for _, r in rows])
        base = np.array([r["base"] for _, r in rows])
        sf = np.array([r["synth_frac"] for _, r in rows])
        ret = np.array([r["retention"] for _, r in rows])
        print(f"\n  base absolute      mean {base.mean():.3f}  sd {base.std():.3f}  "
              f"cv {base.std()/max(base.mean(),1e-9):.3f}")
        print(f"  corr(src, base)         {np.corrcoef(src, base)[0,1]:+.3f}   "
              "(near 0 = a floor, near +1 = it tracks the source)")
        print(f"  corr(src, retention)    {np.corrcoef(src, ret)[0,1]:+.3f}   "
              "(the compressive response, for reference)")
        print(f"  corr(src, synth/src)    {np.corrcoef(src, sf)[0,1]:+.3f}   "
              "(near 0 = synthesis is faithful and the base explains it)")
        print(f"  synth/src          mean {sf.mean():.3f}  sd {sf.std():.3f}")
        # The model the hypothesis predicts, fitted on nothing: k from the
        # strong-grain end, base from the measured mean.
        k = float(np.median(sf))
        pred = np.sqrt(base.mean() ** 2 + (k * src) ** 2) / src
        err = np.abs(pred - ret)
        print(f"\n  predicted retention from  sqrt(base_mean^2 + ({k:.3f}*src)^2)/src :")
        for (name, r), pv in zip(rows, pred):
            print(f"    {name:16} measured {r['retention']:6.3f}   predicted {pv:6.3f}   "
                  f"err {abs(pv-r['retention']):+.3f}")
        print(f"  mean |err| {err.mean():.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
