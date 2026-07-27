#!/usr/bin/env python3
"""Matched-bitrate routing comparison on a real grainy title.

`retain_sweep.py` verifies the retention *mechanism* on synthetic grain
(retained + synthesized variance stays on target).  This script answers a
different question: at an equal byte budget on real content, is film-grain
synthesis a better use of the bits than simply encoding the grain?

Every NVENC variant is encoded at the same VBR target so the comparison is
like-for-like against a plain NVENC control and an SVT-AV1 file of the same
size.  Alongside the full-reference battery it reports two grain descriptors,
because neither alone is sufficient:

- HF sigma: how much high-frequency (grain) energy survives.
- Residual autocorrelation at lags 1..3: how *coarse* that energy is.

Full-reference metrics reward pixel-aligned grain, and synthesized grain is a
new random realization by design, so they are structurally biased against
synthesis (see the position-correlation column of the synthetic sweep).  The
grain descriptors are the counterweight: read them together.

Usage:
  python3 tests/fgs/matched_rate_sweep.py --clip <clip.mkv> --ref <ref.mkv> \
      [--rate 31700] [--svt <file.mkv>] [--denoiser fft3d]
"""
import argparse
import json
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from campaign import NVENCC, COLOR, TUNED, run, score, hf_sigma

ALPHAS = (0.0, 0.15, 0.30, 0.45, 0.60)


def encode(clip, out, rate, fg):
    if os.path.exists(out):
        return out
    cmd = [NVENCC, "--avhw", "--codec", "av1", "--output-depth", "10",
           "--vbr", str(rate), "--max-bitrate", str(rate * 2), *TUNED, *COLOR]
    if fg:
        cmd += ["--av1-film-grain", fg]
    cmd += ["-i", clip, "-o", out]
    print(f"[encode] {os.path.basename(out)}", flush=True)
    run(cmd, timeout=1800)
    return out


def high_pass(a):
    b = (a[0:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, 0:-2] + a[1:-1, 2:] + a[1:-1, 1:-1] * 4) / 8
    return a[1:-1, 1:-1] - b


def autocorr(r, lag):
    r = r - r.mean()
    v = (r * r).mean()
    h = (r[:, :-lag] * r[:, lag:]).mean()
    w = (r[:-lag, :] * r[lag:, :]).mean()
    return (h + w) / (2 * v)


def grain_structure(path, w, h, frames=(6, 10, 14), decoder=None):
    """Normalized residual autocorrelation at lags 1..3.

    Coarse film grain keeps neighbouring residual samples correlated; grain
    that is reproduced too finely decorrelates after one sample even when its
    amplitude is correct.
    """
    tmp = "/tmp/grainstruct.yuv"
    cmd = ["ffmpeg", "-v", "error", "-y"]
    if decoder:
        cmd += ["-c:v", decoder]
    cmd += ["-i", path, "-vframes", str(max(frames) + 2), "-pix_fmt", "yuv420p10le",
            "-vf", f"scale={w}:{h}", "-f", "rawvideo", tmp]
    subprocess.run(cmd, check=True)
    fp = w * h * 3 // 2
    mm = np.memmap(tmp, dtype=np.uint16, mode="r")
    lags = {1: [], 2: [], 3: []}
    for f in frames:
        r = high_pass(mm[f * fp:f * fp + w * h].reshape(h, w).astype(np.float64))
        for lag in lags:
            lags[lag].append(autocorr(r, lag))
    del mm
    os.remove(tmp)
    return {f"acf{lag}": round(float(np.mean(v)), 3) for lag, v in lags.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", required=True, help="source clip")
    ap.add_argument("--ref", required=True, help="lossless reference for scoring (ffvhuff preferred; FFMS2 decodes ffv1 slowly)")
    ap.add_argument("--svt", default="", help="same-size SVT-AV1 file to include")
    ap.add_argument("--rate", type=int, default=31700, help="VBR kbps for every NVENC variant")
    ap.add_argument("--denoiser", default="fft3d")
    ap.add_argument("--frames", type=int, default=600)
    ap.add_argument("--output", default="")
    args = ap.parse_args()

    d = os.path.dirname(os.path.abspath(args.clip))
    stem = os.path.join(d, "mrs-" + os.path.splitext(os.path.basename(args.clip))[0])
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height", "-of", "csv=p=0", args.clip],
                       capture_output=True, text=True, check=True)
    w, h = (int(x) for x in r.stdout.strip().split(",")[:2])

    variants = [("plain", encode(args.clip, f"{stem}-plain.mkv", args.rate, None))]
    for a in ALPHAS:
        fg = f"denoise=auto,chroma=auto,denoiser={args.denoiser}"
        if a > 0:
            fg += f",retain={a:.2f}"
        tag = f"retain{int(round(a * 100)):02d}"
        variants.append((tag, encode(args.clip, f"{stem}-{tag}.mkv", args.rate, fg)))
    variants.append(("retain-auto", encode(args.clip, f"{stem}-auto.mkv", args.rate,
                                           f"denoise=auto,chroma=auto,denoiser={args.denoiser},retain=auto")))
    if args.svt:
        variants.append(("svt", args.svt))

    src = {"hf": hf_sigma(args.clip, w, h), **grain_structure(args.clip, w, h)}
    print(f"source: HF {src['hf']}  acf {src['acf1']}/{src['acf2']}/{src['acf3']}", flush=True)

    results = {"_source": src}
    for tag, enc in variants:
        row = {"mb": round(os.path.getsize(enc) / 1e6, 1)}
        print(f"[score] {tag} ({row['mb']}MB)", flush=True)
        row.update(score(args.ref, enc, f"mrs-{tag}", d, h, args.frames, clip=args.clip))
        row["hf"] = hf_sigma(enc, w, h, decoder="libdav1d")
        row.update(grain_structure(enc, w, h, decoder="libdav1d"))
        results[tag] = row

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=1)

    hdr = (f"{'variant':<13}{'MB':>7}{'VMAF':>8}{'min':>7}{'SSIMU2':>8}{'p5':>7}"
           f"{'PSNR-Y':>8}{'SSIM':>8}{'HF':>6}{'acf1':>7}")
    print("\n" + hdr)
    print("-" * len(hdr))
    for tag, _ in variants:
        r = results[tag]
        print(f"{tag:<13}{r['mb']:>7}{r['vmaf']:>8}{r['vmaf_min']:>7}{r['ssimu2']:>8}"
              f"{r['ssimu2_p5']:>7}{r['psnr_y']:>8}{r['ssim']:>8}{r['hf']:>6}{r['acf1']:>7}")
    print(f"{'source':<13}{'-':>7}{'-':>8}{'-':>7}{'-':>8}{'-':>7}{'-':>8}{'-':>8}"
          f"{src['hf']:>6}{src['acf1']:>7}   <- match both to match the grain")


if __name__ == "__main__":
    main()
