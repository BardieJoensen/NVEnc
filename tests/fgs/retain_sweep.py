#!/usr/bin/env python3
"""Fast synthetic quality/bitrate sweep for AV1 film-grain retain=.

Runs the constant-luma KAT fixture at several retain levels, decodes with
film-grain synthesis both enabled and disabled, and reports:

  * encoded byte size;
  * retained base-layer grain amplitude and source-position correlation;
  * synthesized grain amplitude versus sqrt(1-retain^2);
  * total played-out grain amplitude versus the injected source grain.

Usage:
  python3 tests/fgs/retain_sweep.py [--bits 8|10|both]

Environment:
  NVENCC, FGS_KAT_DENOISER, FGS_RETAIN_SWEEP_DIR
"""
import argparse
import csv
import os
import sys

import fgs_kat as kat
import numpy as np


WORK = os.environ.get("FGS_RETAIN_SWEEP_DIR", "/tmp/nvenc-fgs-tests/retain-sweep")
DEFAULT_RETAINS = "0,0.25,0.5,0.75,0.9"


def decode_source(src, raw, bits):
    pix = "yuv420p" if bits == 8 else "yuv420p10le"
    kat.run(["ffmpeg", "-v", "error", "-y", "-i", src,
             "-pix_fmt", pix, "-f", "rawvideo", raw])


def mean_ratio(values, expected):
    return float((values / expected).mean())


def validate(row):
    retain = row["retain"]
    synth_target = row["synth_target"]
    retained_ok = row["retained_ratio"] < 0.25 if retain == 0.0 else (
        retain * 0.60 < row["retained_ratio"] < retain * 1.40)
    # Low retain values approach one 8-bit code value and naturally compete
    # with base-layer quantization, so require correlation to scale with the
    # amount of original residual that was requested.
    position_ok = retain == 0.0 or row["position_corr"] > retain
    synth_ok = (synth_target * 0.55 < row["synth_ratio"] < synth_target * 1.40)
    total_ok = 0.70 < row["total_ratio"] < 1.35
    return retained_ok and position_ok and synth_ok and total_ok


def run_depth(bits, retains, keep):
    depth_dir = os.path.join(WORK, f"{bits}bit")
    os.makedirs(depth_dir, exist_ok=True)
    spec_base = {"sigma_y_mode": "const", "sigma_y": 6.0, "bits": bits}
    kat.apply_spec(spec_base)
    src = os.path.join(depth_dir, "src.y4m")
    src_raw = os.path.join(depth_dir, "src.yuv")
    expected, _ = kat.generate("retain_sweep", spec_base, src)
    decode_source(src, src_raw, bits)
    expected_y = np.maximum(expected[0], 1e-9)
    frames = range(kat.SKIP, kat.FRAMES)
    rows = []
    for retain in retains:
        tag = f"r{int(round(retain * 100)):02d}"
        out = os.path.join(depth_dir, f"{tag}.mkv")
        on = os.path.join(depth_dir, f"{tag}-on.yuv")
        off = os.path.join(depth_dir, f"{tag}-off.yuv")
        spec = dict(spec_base, retain=retain)
        kat.encode(src, out, spec)
        kat.decode(out, 1, on)
        kat.decode(out, 0, off)
        synth_sigma, _ = kat.measure(on, off, frames)
        retained_sigma = kat.luma_band_sigmas(off, frames)
        total_sigma = kat.luma_band_sigmas(on, frames)
        row = {
            "bits": bits,
            "retain": retain,
            "bytes": os.path.getsize(out),
            "retained_ratio": mean_ratio(retained_sigma, expected_y),
            "position_corr": kat.retained_grain_corr(src_raw, off, frames),
            "synth_ratio": mean_ratio(synth_sigma[0], expected_y),
            "synth_target": (1.0 - retain * retain) ** 0.5,
            "total_ratio": mean_ratio(total_sigma, expected_y),
        }
        row["pass"] = validate(row)
        rows.append(row)
        print(f"{bits:>2}-bit retain={retain:>4.2f} bytes={row['bytes']:>9} "
              f"base={row['retained_ratio']:.3f} corr={row['position_corr']:.3f} "
              f"synth={row['synth_ratio']:.3f}/{row['synth_target']:.3f} "
              f"total={row['total_ratio']:.3f} {'PASS' if row['pass'] else 'FAIL'}")
        if not keep:
            for path in (out, on, off):
                if os.path.exists(path):
                    os.remove(path)
    if not keep:
        for path in (src, src_raw):
            if os.path.exists(path):
                os.remove(path)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bits", choices=("8", "10", "both"), default="both")
    parser.add_argument("--retains", default=DEFAULT_RETAINS)
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()
    retains = [float(value) for value in args.retains.split(",")]
    if not retains or any(value < 0.0 or value > 0.9 for value in retains):
        parser.error("--retains values must be in the range 0.0..0.9")
    depths = (8, 10) if args.bits == "both" else (int(args.bits),)
    os.makedirs(WORK, exist_ok=True)
    rows = []
    for bits in depths:
        rows.extend(run_depth(bits, retains, args.keep))
    report = os.path.join(WORK, "results.csv")
    fields = ["bits", "retain", "bytes", "retained_ratio", "position_corr",
              "synth_ratio", "synth_target", "total_ratio", "pass"]
    with open(report, "w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"results: {report}")
    sys.exit(0 if all(row["pass"] for row in rows) else 1)


if __name__ == "__main__":
    main()
