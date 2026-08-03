#!/usr/bin/env python3
"""Reproduce the rolling source-fit chroma strength population offline.

The exact emission audit can prove what dav1d synthesizes, but it cannot say
which observations produced the curve.  This tool reproduces the other side
of that boundary: production's spatial flat-block selection, dense detrended
U/V source-minus-base variance, hard luma bins, eight-frame rolling window,
empty-bin fill and unconditional 1-2-1 smoothing.  It then compares that shape
with the scaling curve stored in each active ``filmgrn1`` table entry.

Only a global least-squares scale is fitted.  AR/template gain, grain-scale
shift and scaling-shift are global for a plane, so a shape mismatch after that
fit cannot be explained by any of them.

Usage:
  python3 tests/fgs/chroma_population_trace.py \
      --source clip_Taxi_Driver.mkv \
      --clean-base production-clean.y4m \
      --table bilateral-source.tbl --plane v --json-out Taxi-v-population.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import emission_audit  # noqa: E402
import filmgrn  # noqa: E402
from source_fit import (  # noqa: E402
    blockwise, detrend_blocks, production_flat_blocks,
)
from strength_selection_report import decode_selected, probe_size  # noqa: E402


STRENGTH_BINS = 20
MODEL_WINDOW = 8
TABLE_TIMEBASE = 10_000_000


def update_frame(entry, fps_num, fps_den):
    return int(round(entry["start"] * fps_num / (TABLE_TIMEBASE * fps_den)))


def history_frames(frame, window=MODEL_WINDOW):
    return list(range(max(0, frame - window + 1), frame + 1))


def fill_strength(strength, counts):
    """Match ``solve_plane``'s nearest/linear fill for empty hard bins."""
    result = np.asarray(strength, dtype=np.float64).copy()
    populated = np.asarray(counts) > 0
    if not np.any(populated):
        return result
    indices = np.flatnonzero(populated)
    for index in np.flatnonzero(~populated):
        left = indices[indices < index]
        right = indices[indices > index]
        if not len(left):
            result[index] = result[right[0]]
        elif not len(right):
            result[index] = result[left[-1]]
        else:
            low, high = left[-1], right[0]
            mix = (index - low) / (high - low)
            result[index] = result[low] * (1.0 - mix) + result[high] * mix
    return result


def smooth_strength(strength):
    """Match the analyser's unconditional interior 1-2-1 filter."""
    source = np.asarray(strength, dtype=np.float64)
    result = source.copy()
    result[1:-1] = (source[:-2] + 2.0 * source[1:-1] + source[2:]) * 0.25
    return result


def evaluate_points(points, position):
    if not points:
        return 0.0
    if position <= points[0][0]:
        return float(points[0][1])
    for left, right in zip(points, points[1:]):
        if position <= right[0]:
            mix = (position - left[0]) / max(1e-9, right[0] - left[0])
            return left[1] * (1.0 - mix) + right[1] * mix
    return float(points[-1][1])


def fit_shape(expected, observed, weights):
    expected = np.asarray(expected, dtype=np.float64)
    observed = np.asarray(observed, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)
    usable = weights > 0
    if not np.any(usable):
        return {"scale": None, "weighted_relative_rmse": None, "cosine": None,
                "predicted": [None] * len(expected)}
    expected = expected[usable]
    observed = observed[usable]
    weights = weights[usable]
    denominator = float(np.sum(weights * expected * expected))
    scale = (float(np.sum(weights * expected * observed)) / denominator
             if denominator > 1e-12 else 0.0)
    predicted = np.asarray(expected) * scale
    observed_energy = float(np.sum(weights * observed * observed))
    rmse = (math.sqrt(float(np.sum(weights * (predicted - observed) ** 2))
                      / observed_energy) if observed_energy > 1e-12 else None)
    cosine_denominator = math.sqrt(
        float(np.sum(weights * predicted * predicted)) * observed_energy)
    cosine = (float(np.sum(weights * predicted * observed)) / cosine_denominator
              if cosine_denominator > 1e-12 else None)
    full_predicted = np.full(len(usable), np.nan, dtype=np.float64)
    full_predicted[usable] = predicted
    return {
        "scale": scale,
        "weighted_relative_rmse": rmse,
        "cosine": cosine,
        "predicted": [None if not np.isfinite(value) else float(value)
                      for value in full_predicted],
    }


def selected_variances(frame, rows, cols, block_size):
    residual = detrend_blocks(blockwise(frame.astype(np.float64), block_size))
    variance = np.mean(residual * residual, axis=(-2, -1))
    return variance[rows, cols]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--clean-base", required=True)
    parser.add_argument("--table", required=True)
    parser.add_argument("--plane", choices=("u", "v"), required=True)
    parser.add_argument("--bits", type=int, default=10, choices=(8, 10, 12))
    parser.add_argument("--window", type=int, default=MODEL_WINDOW)
    parser.add_argument(
        "--updates", default="",
        help="comma-separated table update frame numbers; default is every entry")
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    width, height = probe_size(args.source)
    entries = [entry for entry in filmgrn.load(args.table)
               if entry["apply_grain"] and entry["update_parameters"]]
    fps_num, fps_den = emission_audit.probe_rate(args.source)
    by_frame = {update_frame(entry, fps_num, fps_den): entry for entry in entries}
    if args.updates:
        requested = [int(value) for value in args.updates.split(",")]
        missing = sorted(set(requested) - set(by_frame))
        if missing:
            raise SystemExit(f"table has no entries starting at frames {missing}")
        by_frame = {frame: by_frame[frame] for frame in requested}
    updates = sorted(by_frame)
    frames = sorted({frame for update in updates
                     for frame in history_frames(update, args.window)})

    source_luma = decode_selected(
        args.source, width, height, frames, args.bits, plane="y")
    selection = {}
    for frame in frames:
        luma = source_luma[frame].astype(np.float64)
        blocks, _score, _sigma = production_flat_blocks(luma, args.bits)
        rows = np.asarray([row for row, _col in blocks], dtype=np.int64)
        cols = np.asarray([col for _row, col in blocks], dtype=np.int64)
        means = blockwise(luma, 32).mean(axis=(-2, -1))[rows, cols]
        bins = np.minimum(
            STRENGTH_BINS - 1,
            np.maximum(0, (means * STRENGTH_BINS // (1 << args.bits)).astype(np.int64)))
        selection[frame] = {"rows": rows, "cols": cols, "bins": bins}
    del source_luma

    source_chroma = decode_selected(
        args.source, width, height, frames, args.bits, plane=args.plane)
    source_variance = {
        frame: selected_variances(
            source_chroma[frame], selection[frame]["rows"],
            selection[frame]["cols"], 16)
        for frame in frames
    }
    del source_chroma

    base_chroma = decode_selected(
        args.clean_base, width, height, frames, args.bits, plane=args.plane)
    base_variance = {
        frame: selected_variances(
            base_chroma[frame], selection[frame]["rows"],
            selection[frame]["cols"], 16)
        for frame in frames
    }
    del base_chroma

    curve_plane = "cb" if args.plane == "u" else "cr"
    rows = []
    for update in updates:
        variance_sum = np.zeros(STRENGTH_BINS, dtype=np.float64)
        signed_variance_sum = np.zeros(STRENGTH_BINS, dtype=np.float64)
        counts = np.zeros(STRENGTH_BINS, dtype=np.int64)
        rectified = np.zeros(STRENGTH_BINS, dtype=np.int64)
        for frame in history_frames(update, args.window):
            bins = selection[frame]["bins"]
            difference = source_variance[frame] - base_variance[frame]
            signed_variance_sum += np.bincount(
                bins, weights=difference, minlength=STRENGTH_BINS)
            variance_sum += np.bincount(
                bins, weights=np.maximum(0.0, difference), minlength=STRENGTH_BINS)
            counts += np.bincount(bins, minlength=STRENGTH_BINS)
            rectified += np.bincount(
                bins[difference <= 0.0], minlength=STRENGTH_BINS)
        raw = np.zeros(STRENGTH_BINS, dtype=np.float64)
        signed = np.zeros(STRENGTH_BINS, dtype=np.float64)
        populated = counts > 0
        raw[populated] = np.sqrt(variance_sum[populated] / counts[populated])
        signed[populated] = np.sqrt(np.maximum(
            0.0, signed_variance_sum[populated] / counts[populated]))
        filled = fill_strength(raw, counts)
        smoothed = smooth_strength(filled)
        positions = np.linspace(0.0, 255.0, STRENGTH_BINS)
        table_curve = np.asarray([
            evaluate_points(by_frame[update]["scaling_points"][curve_plane], position)
            for position in positions
        ])
        shape = fit_shape(smoothed, table_curve, counts)
        predicted = shape.pop("predicted")
        bins = []
        for index in range(STRENGTH_BINS):
            bins.append({
                "bin": index,
                "range": [index / STRENGTH_BINS, (index + 1) / STRENGTH_BINS],
                "blocks": int(counts[index]),
                "rectified_blocks": int(rectified[index]),
                "rectified_fraction": (
                    float(rectified[index] / counts[index]) if counts[index] else None),
                "raw_sigma": float(raw[index]) if counts[index] else None,
                "signed_sigma": float(signed[index]) if counts[index] else None,
                "clamp_sigma_gain": (
                    float(raw[index] / signed[index])
                    if counts[index] and signed[index] > 0.0 else None),
                "filled_sigma": float(filled[index]),
                "smoothed_sigma": float(smoothed[index]),
                "table_scaling": float(table_curve[index]),
                "predicted_scaling": predicted[index],
            })
        rows.append({
            "update_frame": update,
            "history_frames": history_frames(update, args.window),
            "blocks": int(counts.sum()),
            "rectified_blocks": int(rectified.sum()),
            "rectified_fraction": float(rectified.sum() / counts.sum()),
            "shape_fit": shape,
            "bins": bins,
        })

    report = {
        "source": os.path.abspath(args.source),
        "clean_base": os.path.abspath(args.clean_base),
        "table": os.path.abspath(args.table),
        "plane": args.plane,
        "bits": args.bits,
        "model_window": args.window,
        "updates": rows,
    }
    for row in rows:
        shape = row["shape_fit"]
        print(f"update={row['update_frame']:>3} blocks={row['blocks']:>6} "
              f"rectified={row['rectified_fraction']:.3f} "
              f"cos={shape['cosine']:.4f} relrmse={shape['weighted_relative_rmse']:.4f}")
        for item in row["bins"]:
            if item["blocks"]:
                print(f"  bin={item['bin']:>2} n={item['blocks']:>5} "
                      f"raw={item['raw_sigma']:.3f} smooth={item['smoothed_sigma']:.3f} "
                      f"signed={item['signed_sigma']:.3f} "
                      f"table={item['table_scaling']:.1f} "
                      f"pred={item['predicted_scaling']:.1f} "
                      f"zero={item['rectified_fraction']:.3f}")
    if args.json_out:
        destination = os.path.abspath(args.json_out)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        with open(destination, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print(f"wrote {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
