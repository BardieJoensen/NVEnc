#!/usr/bin/env python3
"""Audit the source-correlation ceiling against temporal grain truth.

The source-fit regularizer currently limits the AV1 model to the median
``FilmGrainBlockMetric::spatialCorrelation`` plus a fixed margin.  That median
weights every selected 32x32 block equally, while the AR normal equations pool
pixel observations and therefore weight energetic blocks more strongly.  A
single margin cannot repair an estimator mismatch: it may improve one title
and suppress correct texture in another.

This report reproduces the CUDA block statistic exactly, then compares:

* the shipping mean-of-frame-medians;
* an unweighted mean of block correlations; and
* a pooled numerator/energy correlation.

Adjacent-frame differencing on static source-selected blocks supplies the
picture-free target.  Fixed luma bands are mandatory because film grain scale
can vary with exposure and an AV1 interval still has only one luma AR model.
The output is diagnostic evidence only and deliberately contains no routing or
shipping verdict.

Example:
  python3 tests/fgs/correlation_target_report.py \
      --source clip_Taxi_Driver.mkv \
      --frames 10,58,106,154,202,250 --json-out taxi-correlation.json
"""

import argparse
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from source_fit import (  # noqa: E402
    accumulate_ar, blockwise, detrend_blocks, implied_acf,
    production_flat_blocks, solve_ar, static_flat_blocks,
)
import ar_acf  # noqa: E402
from sourcefit_admission_report import decode_pair_stream  # noqa: E402
from strength_selection_report import probe_size  # noqa: E402


def correlation_terms(patches):
    """Return CUDA-equivalent lag-one numerator, energy and block values.

    ``patches`` must already have its per-block mean-plus-plane removed.  The
    interior and symmetric energy denominator match
    ``kernel_fgs_flat_metrics`` rather than using NumPy's conventional ACF
    normalization.
    """
    patches = np.asarray(patches, dtype=np.float64)
    if patches.ndim != 3 or patches.shape[1:] != (32, 32):
        raise ValueError("patches must have shape (count, 32, 32)")
    centre = patches[:, 1:-1, 1:-1]
    right = patches[:, 1:-1, 2:]
    down = patches[:, 2:, 1:-1]
    numerator = np.sum(centre * (right + down), axis=(1, 2))
    energy = 0.5 * np.sum(
        2.0 * centre * centre + right * right + down * down,
        axis=(1, 2))
    values = np.divide(
        numerator, energy, out=np.zeros_like(numerator), where=energy > 1e-12)
    return numerator, energy, np.clip(values, -1.0, 1.0)


def upper_median(values):
    """Match C++ ``nth_element(begin + size / 2)`` for even populations."""
    values = np.asarray(values, dtype=np.float64)
    if not len(values):
        return None
    return float(np.partition(values, len(values) // 2)[len(values) // 2])


def term_summary(numerator, energy, values):
    numerator = np.asarray(numerator, dtype=np.float64)
    energy = np.asarray(energy, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)
    if not len(values):
        return {
            "blocks": 0,
            "upper_median": None,
            "mean": None,
            "sd": None,
            "pooled": None,
            "energy_sum": 0.0,
            "numerator_sum": 0.0,
        }
    energy_sum = float(energy.sum())
    return {
        "blocks": int(len(values)),
        "upper_median": upper_median(values),
        "mean": float(values.mean()),
        "sd": float(values.std()),
        "pooled": (float(numerator.sum()) / energy_sum
                   if energy_sum > 1e-12 else 0.0),
        "energy_sum": energy_sum,
        "numerator_sum": float(numerator.sum()),
    }


def patches_at(grid, blocks):
    if not blocks:
        return np.empty((0, 32, 32), dtype=np.float64)
    return np.stack([grid[row, col] for row, col in blocks]).astype(np.float64)


def summarize_patches(patches, detrend=True):
    patches = np.asarray(patches, dtype=np.float64)
    if detrend and len(patches):
        patches = detrend_blocks(patches[None])[0]
    return term_summary(*correlation_terms(patches))


def make_ar_accumulators():
    count = len(ar_acf.ar_taps(3))
    return {
        key: {
            "ata": np.zeros((count, count), dtype=np.float64),
            "atb": np.zeros(count, dtype=np.float64),
            "observations": 0,
        }
        for key in ("spatial_all", "spatial_static", "temporal_truth")
    }


def accumulate_pair_ar(source, next_source, candidates, static, accumulators):
    fields = {
        "spatial_all": (source, candidates),
        "spatial_static": (source, static),
        "temporal_truth": ((source - next_source) / math.sqrt(2.0), static),
    }
    for key, (field, blocks) in fields.items():
        accumulator = accumulators[key]
        accumulator["observations"] += accumulate_ar(
            field, blocks, True, accumulator["ata"], accumulator["atb"])


def ar_fit_summary(accumulators, bits, shift, seeds, sigma):
    result = {}
    for key, accumulator in accumulators.items():
        coeffs = solve_ar(accumulator["ata"], accumulator["atb"])
        implied = implied_acf(coeffs, shift, seeds, bits, sigma)
        result[key] = {
            "observations": accumulator["observations"],
            "ar_shift": shift,
            "coefficients": coeffs.tolist(),
            "implied_lag1": implied["lag1"],
            "implied_lag2": 0.5 * (implied["h2"] + implied["v2"]),
            "implied_gain": implied["gain"],
            "clip_fraction": implied["clip_fraction"],
        }
    static = result["spatial_static"]
    truth = result["temporal_truth"]
    result["static_minus_temporal_fit"] = {
        "lag1": static["implied_lag1"] - truth["implied_lag1"],
        "lag2": static["implied_lag2"] - truth["implied_lag2"],
    }
    result["purpose"] = (
        "dense offline fit; temporal fit is the same AV1-model upper control, "
        "not direct field truth")
    return result


def measure_pair(frame, source, next_source, bits, static_lo, static_hi,
                 luma_bins, ar_accumulators=None):
    source = np.asarray(source, dtype=np.float64)
    next_source = np.asarray(next_source, dtype=np.float64)
    candidates, _score, _sigma = production_flat_blocks(source, bits)
    static = static_flat_blocks(
        source, next_source, candidates, lo=static_lo, hi=static_hi)
    if ar_accumulators is not None:
        accumulate_pair_ar(
            source, next_source, candidates, static, ar_accumulators)

    source_grid = blockwise(source)
    next_grid = blockwise(next_source)
    source_patches = patches_at(source_grid, candidates)
    static_source = patches_at(source_grid, static)
    static_next = patches_at(next_grid, static)
    source_detrended = (detrend_blocks(source_patches[None])[0]
                        if len(source_patches) else source_patches)
    static_source_detrended = (detrend_blocks(static_source[None])[0]
                               if len(static_source) else static_source)
    static_next_detrended = (detrend_blocks(static_next[None])[0]
                             if len(static_next) else static_next)
    temporal = ((static_source_detrended - static_next_detrended)
                / math.sqrt(2.0))

    result = {
        "frame": frame,
        "candidate_blocks": len(candidates),
        "static_blocks": len(static),
        "spatial_all": term_summary(*correlation_terms(source_detrended)),
        "spatial_static": term_summary(
            *correlation_terms(static_source_detrended)),
        "temporal_truth": term_summary(*correlation_terms(temporal)),
        "luma_bands": {},
    }
    maximum = float((1 << bits) - 1)
    static_bands = np.asarray([
        min(luma_bins - 1, max(0, int(source_grid[row, col].mean()
                                     / maximum * luma_bins)))
        for row, col in static
    ], dtype=np.int16)
    for band in range(luma_bins):
        keep = static_bands == band
        result["luma_bands"][str(band)] = {
            "range": [band / luma_bins, (band + 1) / luma_bins],
            "spatial_static": term_summary(
                *correlation_terms(static_source_detrended[keep])),
            "temporal_truth": term_summary(
                *correlation_terms(temporal[keep])),
        }
    return result


def aggregate_summaries(rows, key):
    present = [row[key] for row in rows if row[key]["blocks"]]
    if not present:
        return term_summary([], [], [])
    numerator_sum = sum(row["numerator_sum"] for row in present)
    energy_sum = sum(row["energy_sum"] for row in present)
    block_count = sum(row["blocks"] for row in present)
    return {
        "blocks": block_count,
        "mean_of_frame_upper_medians": float(np.mean([
            row["upper_median"] for row in present])),
        "mean_of_frame_means": float(np.mean([
            row["mean"] for row in present])),
        "mean_of_frame_pooled": float(np.mean([
            row["pooled"] for row in present])),
        "all_frame_pooled": (numerator_sum / energy_sum
                             if energy_sum > 1e-12 else 0.0),
    }


def aggregate_report(rows, luma_bins):
    spatial_all = aggregate_summaries(rows, "spatial_all")
    spatial_static = aggregate_summaries(rows, "spatial_static")
    temporal = aggregate_summaries(rows, "temporal_truth")
    target = temporal.get("mean_of_frame_pooled")
    estimators = {
        "shipping_frame_median": spatial_all.get(
            "mean_of_frame_upper_medians"),
        "frame_mean": spatial_all.get("mean_of_frame_means"),
        "frame_pooled": spatial_all.get("mean_of_frame_pooled"),
        "all_frame_pooled": spatial_all.get("all_frame_pooled"),
        "static_frame_median": spatial_static.get(
            "mean_of_frame_upper_medians"),
        "static_frame_pooled": spatial_static.get("mean_of_frame_pooled"),
    }
    errors = {
        key: (value - target if value is not None and target is not None
              else None)
        for key, value in estimators.items()
    }
    bands = {}
    for band in range(luma_bins):
        spatial_rows = []
        temporal_rows = []
        for row in rows:
            record = row["luma_bands"][str(band)]
            spatial_rows.append({"value": record["spatial_static"]})
            temporal_rows.append({"value": record["temporal_truth"]})
        spatial = aggregate_summaries(spatial_rows, "value")
        truth = aggregate_summaries(temporal_rows, "value")
        bands[str(band)] = {
            "range": [band / luma_bins, (band + 1) / luma_bins],
            "blocks": truth["blocks"],
            "spatial_static_pooled": spatial.get("mean_of_frame_pooled"),
            "temporal_truth_pooled": truth.get("mean_of_frame_pooled"),
        }
    return {
        "spatial_all": spatial_all,
        "spatial_static": spatial_static,
        "temporal_truth": temporal,
        "estimator_error_vs_temporal_truth": errors,
        "luma_bands": bands,
        "routing_verdict": None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--frames", default="10,58,106,154,202,250")
    parser.add_argument("--bits", type=int, default=10)
    parser.add_argument("--static-lo", type=float, default=0.8)
    parser.add_argument("--static-hi", type=float, default=1.3)
    parser.add_argument("--luma-bins", type=int, default=8)
    parser.add_argument("--ar-shift", type=int, default=9)
    parser.add_argument("--ar-seeds", type=int, default=64)
    parser.add_argument("--ar-sim-sigma", type=float, default=4.0)
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()
    if not os.path.isfile(args.source):
        parser.error(f"missing source: {args.source}")
    frames = sorted({int(value) for value in args.frames.split(",")})
    if not frames or min(frames) < 0 or args.luma_bins < 1:
        parser.error("frames must be non-negative and luma bins positive")

    width, height = probe_size(args.source)
    rows = []
    ar_accumulators = make_ar_accumulators()
    for frame, source, next_source in decode_pair_stream(
            args.source, width, height, frames, args.bits):
        row = measure_pair(
            frame, source, next_source, args.bits,
            args.static_lo, args.static_hi, args.luma_bins, ar_accumulators)
        if row["static_blocks"] < 8:
            raise RuntimeError(
                f"frame {frame}: only {row['static_blocks']} static blocks")
        rows.append(row)
    if [row["frame"] for row in rows] != frames:
        raise RuntimeError("decoder did not return every requested frame pair")

    report = {
        "purpose": "correlation estimator audit; never a routing verdict",
        "source": os.path.abspath(args.source),
        "dimensions": [width, height],
        "bits": args.bits,
        "settings": {
            "frames": frames,
            "flat_selector": "production",
            "static_ratio": [args.static_lo, args.static_hi],
            "luma_bins": args.luma_bins,
        },
        "summary": aggregate_report(rows, args.luma_bins),
        "ar_fit_oracle": ar_fit_summary(
            ar_accumulators, args.bits, args.ar_shift,
            args.ar_seeds, args.ar_sim_sigma),
        "frames": rows,
    }
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.json_out:
        temporary = args.json_out + ".partial"
        with open(temporary, "w", encoding="utf-8") as handle:
            handle.write(encoded)
        os.replace(temporary, args.json_out)
    else:
        print(encoded, end="")
    summary = report["summary"]
    print(
        f"shipping={summary['spatial_all']['mean_of_frame_upper_medians']:.4f} "
        f"pooled={summary['spatial_all']['mean_of_frame_pooled']:.4f} "
        f"truth={summary['temporal_truth']['mean_of_frame_pooled']:.4f}",
        file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
