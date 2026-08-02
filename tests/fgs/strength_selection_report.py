#!/usr/bin/env python3
"""Localise source-fit strength error across flat-block selection boundaries.

This compares the dense source-minus-base variance with a temporal ground truth
and a temporal clean-base leakage estimate on the same blocks.  It deliberately
reports three masks:

* the old top-decile temporal oracle used during source-fit development;
* production's exact spatial selector before motion-confidence filtering; and
* that production selector restricted to temporal-static blocks.

The last comparison answers whether a weak strength curve comes from the dense
estimator itself or from the block population supplied to it.  On temporal-static
blocks, consecutive-frame differencing also removes picture structure from the
clean base.  This separates actual time-varying base residue from static picture
or denoiser error that the spatial subtraction incorrectly calls retained grain.
The unfiltered production row is diagnostic only: motion contaminates temporal
truth there.

Usage:
  python3 tests/fgs/strength_selection_report.py \
      --source clip.mkv --clean-base clean.y4m \
      --frames 10,58,106,154,202,250,275 --json-out report.json
"""
import argparse
import json
import math
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from source_fit import (  # noqa: E402
    blockwise, detrend_blocks, production_flat_blocks, select_flat,
    static_flat_blocks,
)

FFMPEG = os.environ.get("FGS_FFMPEG", "/usr/local/bin/ffmpeg")
FFPROBE = os.environ.get("FGS_FFPROBE", "/usr/local/bin/ffprobe")


def probe_size(path):
    result = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", path],
        check=True, capture_output=True, text=True)
    return tuple(int(value) for value in result.stdout.strip().split(",")[:2])


def decode_selected(path, width, height, indices, bits):
    terms = "+".join(f"eq(n\\,{index})" for index in indices)
    pix_fmt = "gray" if bits == 8 else f"gray{bits}le"
    result = subprocess.run(
        [FFMPEG, "-v", "error", "-i", path, "-map", "0:v:0",
         "-vf", f"select='{terms}'", "-fps_mode", "passthrough",
         "-pix_fmt", pix_fmt, "-f", "rawvideo", "-"],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    dtype = np.uint8 if bits == 8 else np.uint16
    frame_bytes = width * height * np.dtype(dtype).itemsize
    if len(result.stdout) != len(indices) * frame_bytes:
        raise RuntimeError(
            f"{path}: decoded {len(result.stdout) // frame_bytes} frames, "
            f"expected {len(indices)}")
    return {
        index: np.frombuffer(result.stdout, dtype, count=width * height,
                             offset=position * frame_bytes).reshape(height, width)
        for position, index in enumerate(indices)
    }


def block_variances(frame):
    residual = detrend_blocks(blockwise(frame))
    return (residual * residual).mean(axis=(-2, -1))


def measure(source, next_source, clean, next_clean, blocks):
    if not blocks:
        return None
    source_var = block_variances(source)
    base_var = block_variances(clean)
    temporal_var = block_variances((source - next_source) / math.sqrt(2.0))
    base_temporal_var = block_variances((clean - next_clean) / math.sqrt(2.0))
    rows = np.asarray([row for row, _col in blocks])
    cols = np.asarray([col for _row, col in blocks])
    missing = np.maximum(0.0, source_var[rows, cols] - base_var[rows, cols])
    truth = temporal_var[rows, cols]
    leak = base_temporal_var[rows, cols]
    missing_var = float(missing.mean())
    truth_var = float(truth.mean())
    leak_var = float(leak.mean())
    temporal_target_var = max(0.0, truth_var - leak_var)
    return {
        "blocks": len(blocks),
        "source_sigma": float(np.sqrt(source_var[rows, cols].mean())),
        "base_sigma": float(np.sqrt(base_var[rows, cols].mean())),
        "truth_sigma": float(np.sqrt(truth_var)),
        "missing_sigma": float(np.sqrt(missing_var)),
        "amplitude_ratio": float(np.sqrt(missing_var / truth_var)) if truth_var > 0 else None,
        "base_temporal_sigma": float(np.sqrt(leak_var)),
        "temporal_leak_ratio": float(np.sqrt(leak_var / truth_var)) if truth_var > 0 else None,
        "temporal_target_sigma": float(np.sqrt(temporal_target_var)),
        "temporal_target_ratio": (
            float(np.sqrt(temporal_target_var / truth_var)) if truth_var > 0 else None
        ),
        "missing_variance_sum": missing_var * len(blocks),
        "truth_variance_sum": truth_var * len(blocks),
        "base_temporal_variance_sum": leak_var * len(blocks),
    }


def aggregate(rows):
    present = [row for row in rows if row]
    missing = sum(row["missing_variance_sum"] for row in present)
    truth = sum(row["truth_variance_sum"] for row in present)
    leak = sum(row["base_temporal_variance_sum"] for row in present)
    blocks = sum(row["blocks"] for row in present)
    target = max(0.0, truth - leak)
    return {
        "blocks": blocks,
        "missing_sigma": float(np.sqrt(missing / blocks)) if blocks else None,
        "truth_sigma": float(np.sqrt(truth / blocks)) if blocks else None,
        "amplitude_ratio": float(np.sqrt(missing / truth)) if truth > 0 else None,
        "base_temporal_sigma": float(np.sqrt(leak / blocks)) if blocks else None,
        "temporal_leak_ratio": float(np.sqrt(leak / truth)) if truth > 0 else None,
        "temporal_target_sigma": float(np.sqrt(target / blocks)) if blocks else None,
        "temporal_target_ratio": float(np.sqrt(target / truth)) if truth > 0 else None,
    }


def luma_bands(frame, blocks, count, max_value):
    grid = blockwise(frame)
    out = [[] for _ in range(count)]
    for row, col in blocks:
        index = min(count - 1, max(0, int(grid[row, col].mean() / (max_value + 1) * count)))
        out[index].append((row, col))
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--clean-base", required=True)
    parser.add_argument("--frames", default="10,58,106,154,202,250,275")
    parser.add_argument("--bits", type=int, default=10, choices=(8, 10, 12, 16))
    parser.add_argument("--flat-fraction", type=float, default=0.10)
    parser.add_argument("--static-lo", type=float, default=0.8)
    parser.add_argument("--static-hi", type=float, default=1.3)
    parser.add_argument("--luma-bins", type=int, default=8)
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    size = probe_size(args.source)
    if probe_size(args.clean_base) != size:
        raise SystemExit("source and clean-base dimensions differ")
    width, height = size
    frames = [int(value) for value in args.frames.split(",")]
    source_indices = sorted(set(frames + [frame + 1 for frame in frames]))
    source_decoded = decode_selected(args.source, width, height, source_indices, args.bits)
    clean_decoded = decode_selected(
        args.clean_base, width, height, source_indices, args.bits)

    report = {
        "source": os.path.abspath(args.source),
        "clean_base": os.path.abspath(args.clean_base),
        "dimensions": [width, height],
        "bits": args.bits,
        "frames": frames,
        "static_ratio": [args.static_lo, args.static_hi],
        "rows": [],
        "luma_bins": [],
    }
    by_mask = {name: [] for name in ("top10_static", "production_spatial", "production_static")}
    per_frame_masks = {name: [] for name in ("top10_static", "production_static")}

    print(f"{os.path.basename(args.source)}: {width}x{height} {args.bits}-bit")
    print(f"{'frame':>6} {'mask':<20}{'blocks':>8}{'src s':>9}{'base s':>9}"
          f"{'truth s':>9}{'spatial':>10}{'leak':>9}{'target':>9}")
    for frame_number in frames:
        source = source_decoded[frame_number].astype(np.float64)
        next_source = source_decoded[frame_number + 1].astype(np.float64)
        clean = clean_decoded[frame_number].astype(np.float64)
        next_clean = clean_decoded[frame_number + 1].astype(np.float64)
        top, _score, _sigma = select_flat(source, args.bits, args.flat_fraction)
        production, _score, _sigma = production_flat_blocks(source, args.bits)
        masks = {
            "top10_static": static_flat_blocks(
                source, next_source, top, lo=args.static_lo, hi=args.static_hi),
            "production_spatial": production,
            "production_static": static_flat_blocks(
                source, next_source, production, lo=args.static_lo, hi=args.static_hi),
        }
        for name in per_frame_masks:
            per_frame_masks[name].append(masks[name])
        frame_record = {"frame": frame_number, "masks": {}}
        for name, blocks in masks.items():
            row = measure(source, next_source, clean, next_clean, blocks)
            by_mask[name].append(row)
            frame_record["masks"][name] = row
            print(f"{frame_number:>6} {name:<20}{row['blocks']:>8}"
                  f"{row['source_sigma']:>9.2f}{row['base_sigma']:>9.2f}"
                  f"{row['truth_sigma']:>9.2f}{row['amplitude_ratio']:>10.3f}"
                  f"{row['temporal_leak_ratio']:>9.3f}"
                  f"{row['temporal_target_ratio']:>9.3f}")
        report["rows"].append(frame_record)

    report["aggregate"] = {name: aggregate(rows) for name, rows in by_mask.items()}
    print("\nvariance-weighted aggregate")
    for name, row in report["aggregate"].items():
        print(f"{name:<20}{row['blocks']:>8} blocks  "
              f"spatial {row['amplitude_ratio']:.3f}  "
              f"temporal leak {row['temporal_leak_ratio']:.3f}  "
              f"target {row['temporal_target_ratio']:.3f}")

    max_value = (1 << args.bits) - 1
    report["luma_bins"] = {name: [] for name in per_frame_masks}
    print("\nwithin-luma mask comparison")
    print(f"{'range':<15}{'mask':<20}{'blocks':>8}{'truth s':>10}"
          f"{'spatial':>10}{'leak':>10}{'target':>10}")
    for bin_index in range(args.luma_bins):
        for name, frame_masks in per_frame_masks.items():
            rows = []
            for frame_number, blocks in zip(frames, frame_masks):
                source = source_decoded[frame_number].astype(np.float64)
                next_source = source_decoded[frame_number + 1].astype(np.float64)
                clean = clean_decoded[frame_number].astype(np.float64)
                next_clean = clean_decoded[frame_number + 1].astype(np.float64)
                band = luma_bands(source, blocks, args.luma_bins, max_value)[bin_index]
                if len(band) >= 8:
                    rows.append(measure(
                        source, next_source, clean, next_clean, band))
            if not rows:
                continue
            row = aggregate(rows)
            limits = [bin_index / args.luma_bins, (bin_index + 1) / args.luma_bins]
            record = {"range": limits, **row}
            report["luma_bins"][name].append(record)
            print(f"{limits[0]:.3f}-{limits[1]:.3f} {name:<20}{row['blocks']:>8}"
                  f"{row['truth_sigma']:>10.2f}{row['amplitude_ratio']:>10.3f}"
                  f"{row['temporal_leak_ratio']:>10.3f}"
                  f"{row['temporal_target_ratio']:>10.3f}")

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")
        print(f"\nwrote {args.json_out}")


if __name__ == "__main__":
    main()
