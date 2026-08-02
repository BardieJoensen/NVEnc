#!/usr/bin/env python3
"""Audit decoded luma grain amplitude against the exact AV1 emission path.

The strength estimator and the AV1 emission path are separate error sources.
This audit freezes production's source-selected static blocks, weights every
frame's luma scaling curve by the grain-disabled AV1 pixels on those blocks,
then reproduces the normative template, offsets, overlap, rounding and output
clipping.  The prediction is checked pixel-for-pixel against dav1d and against
the synthesis variance already measured by strength_selection_report.py.

The frame side data is deliberate.  NVENC's public API does not accept the
``filmgrn1`` random seed, so the seed in a table written by the analyser is not
the seed NVENC puts in the AV1 bitstream.  Table-only amplitude predictions can
therefore vary with title merely because they simulated the wrong template.

Usage:
  python3 tests/fgs/emission_audit.py \
      --source clip.mkv --table arm.tbl --closure closure-qvbr.json \
      --arm q29 --json-out emission.json
"""
import argparse
import hashlib
import json
import math
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import av1_grain  # noqa: E402
import filmgrn  # noqa: E402
from source_fit import (  # noqa: E402
    blockwise, detrend_blocks, production_flat_blocks, static_flat_blocks,
)
from strength_selection_report import (  # noqa: E402
    decode_selected, probe_size,
)

FFPROBE = os.environ.get("FGS_FFPROBE", "/usr/local/bin/ffprobe")
TABLE_TIMEBASE = 10_000_000


def probe_rate(path):
    result = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", path],
        check=True, capture_output=True, text=True)
    # Some ffprobe builds append an empty CSV side-data column ("24000/1001,").
    rate = result.stdout.strip().splitlines()[0].split(",", 1)[0]
    numerator, denominator = rate.split("/")
    return int(numerator), int(denominator)


def entry_for_frame(entries, frame, fps_num, fps_den):
    timestamp = int(round(frame * TABLE_TIMEBASE * fps_den / fps_num))
    for entry in entries:
        if entry["start"] <= timestamp < entry["end"]:
            return entry
    raise ValueError(f"no grain-table entry covers frame {frame} ({timestamp})")


def _integers(value):
    return [int(item) for item in value.split()] if value else []


def entry_from_side_data(side_data):
    """Convert ffprobe's AV1 film-grain side data to the local table shape."""
    components = side_data.get("components", [])
    if not components:
        raise ValueError("AV1 film-grain side data has no luma component")
    luma = components[0]
    values = _integers(luma.get("y_points_value", ""))
    scales = _integers(luma.get("y_points_scaling", ""))
    if len(values) != len(scales):
        raise ValueError("AV1 luma scaling-point arrays differ in length")
    parameter_names = (
        "ar_coeff_lag", "ar_coeff_shift", "grain_scale_shift",
        "scaling_shift", "overlap_flag",
    )
    return {
        "random_seed": int(side_data["seed"]),
        "params": {name: int(side_data[name]) for name in parameter_names},
        "scaling_points": {"y": [[value, scale] for value, scale in zip(values, scales)]},
        "ar_coeffs": {"y": _integers(luma.get("ar_coeffs_y", ""))},
        "limit_output_range": bool(int(side_data.get("limit_output_range", 0))),
    }


def probe_grain_entries(path, frame_count):
    """Read the actual per-frame grain parameters, including NVENC's seeds."""
    result = subprocess.run(
        [FFPROBE, "-v", "error", "-c:v", "libdav1d", "-filmgrain", "0",
         "-export_side_data", "film_grain", "-select_streams", "v:0",
         "-show_frames", "-read_intervals", f"%+#{frame_count}", "-of", "json", path],
        check=True, capture_output=True, text=True)
    frames = json.loads(result.stdout).get("frames", [])
    entries = {}
    for frame_number, frame in enumerate(frames):
        candidates = [
            item for item in frame.get("side_data_list", [])
            if item.get("side_data_type") == "Film grain parameters"
        ]
        if len(candidates) != 1:
            raise ValueError(
                f"frame {frame_number}: expected one film-grain side-data item, "
                f"found {len(candidates)}")
        entries[frame_number] = entry_from_side_data(candidates[0])
    if len(entries) != frame_count:
        raise ValueError(f"ffprobe returned {len(entries)} frames, expected {frame_count}")
    return entries


def table_matches_stream(table_entry, stream_entry):
    """The seed is expected to differ; every signalled model field must match."""
    names = stream_entry["params"].keys()
    return (
        all(table_entry["params"][name] == stream_entry["params"][name]
            for name in names)
        and table_entry["scaling_points"]["y"] == stream_entry["scaling_points"]["y"]
        and table_entry["ar_coeffs"]["y"] == stream_entry["ar_coeffs"]["y"]
    )


def selected_variances(blocks):
    residual = detrend_blocks(np.asarray(blocks, dtype=np.float64))
    return (residual * residual).mean(axis=(-2, -1))


def selected_axis_stats(blocks):
    """Lag statistics of selected synthesis blocks, matching texture reports."""
    values = np.asarray(blocks, dtype=np.float64)
    values -= values.mean(axis=(-2, -1), keepdims=True)
    variance = float((values * values).mean())
    if variance <= 0.0:
        return None
    return {
        "h1": float((values[:, :, 1:] * values[:, :, :-1]).mean() / variance),
        "v1": float((values[:, 1:, :] * values[:, :-1, :]).mean() / variance),
        "h2": float((values[:, :, 2:] * values[:, :, :-2]).mean() / variance),
        "v2": float((values[:, 2:, :] * values[:, :-2, :]).mean() / variance),
    }


def average_axis(rows):
    present = [row for row in rows if row is not None]
    if not present:
        return None
    return {key: float(np.mean([row[key] for row in present])) for key in present[0]}


def actual_synth_blocks(encoded_on, encoded_off, blocks):
    rows = np.asarray([row for row, _col in blocks])
    cols = np.asarray([col for _row, col in blocks])
    difference = blockwise(
        encoded_on.astype(np.int64) - encoded_off.astype(np.int64))
    return difference[rows, cols]


def oracle_seed(frame_number, sample_number):
    """Deterministic, well-spread non-zero seed for pre-encode expectation."""
    value = (((frame_number + 1) * 0x9E3779B1)
             ^ ((sample_number + 1) * 0x85EBCA6B)) & 0xffffffff
    value ^= value >> 16
    value = (value * 0x7FEB352D) & 0xffffffff
    value ^= value >> 15
    seed = value & 0xffff
    return seed if seed else 1


def synth_variance_for_seed(base, blocks, entry, gaussian, bits, seed):
    seeded = {**entry, "random_seed": seed}
    predicted = av1_grain.synthesize_selected_luma(
        base, blocks, seeded, gaussian, bits)
    return float(selected_variances(predicted).mean()), selected_axis_stats(predicted)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--table", required=True)
    parser.add_argument(
        "--expected-table", default="",
        help="alternate table used only by the expected-seed oracle")
    parser.add_argument("--closure", required=True)
    parser.add_argument("--arm", default="q29")
    parser.add_argument("--bits", type=int, default=10, choices=(8, 10, 12))
    parser.add_argument(
        "--aom-grain-source",
        default=os.environ.get(
            "AOM_GRAIN_SOURCE", "/tmp/aomref/src/av1/decoder/grain_synthesis.c"),
        help="grain_synthesis.c from the pinned build_aom_reference.sh checkout")
    parser.add_argument("--static-lo", type=float, default=0.8)
    parser.add_argument("--static-hi", type=float, default=1.3)
    parser.add_argument(
        "--seed-samples", type=int, default=0,
        help="also estimate pre-encode expected variance over this many "
             "deterministic AV1 seeds (default 0)")
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    with open(args.closure, encoding="utf-8") as handle:
        closure = json.load(handle)
    encoded_paths = closure.get("encoded_arms", {})
    if args.arm not in encoded_paths:
        raise SystemExit(f"closure report has no encoded arm {args.arm}")
    encoded = encoded_paths[args.arm]
    frames = closure["frames"]
    indices = sorted(set(frames + [frame + 1 for frame in frames]))
    width, height = probe_size(args.source)
    if probe_size(encoded) != (width, height):
        raise SystemExit("source and encoded dimensions differ")
    fps_num, fps_den = probe_rate(args.source)

    source_decoded = decode_selected(
        args.source, width, height, indices, args.bits)
    base_decoded = decode_selected(
        encoded, width, height, indices, args.bits, filmgrain=0)
    on_decoded = decode_selected(
        encoded, width, height, indices, args.bits, filmgrain=1)
    entries = filmgrn.load(args.table)
    updating = [entry for entry in entries
                if entry["apply_grain"] and entry["update_parameters"]]
    if not updating:
        raise SystemExit("grain table has no updating entry")
    expected_entries = filmgrn.load(args.expected_table) if args.expected_table else entries
    expected_updating = [entry for entry in expected_entries
                         if entry["apply_grain"] and entry["update_parameters"]]
    if not expected_updating:
        raise SystemExit("expected table has no updating entry")
    gaussian = av1_grain.load_gaussian_sequence(args.aom_grain_source)
    with open(args.aom_grain_source, "rb") as handle:
        grain_source_sha256 = hashlib.sha256(handle.read()).hexdigest()
    stream_entries = probe_grain_entries(encoded, max(indices) + 1)
    closure_rows = {row["frame"]: row for row in closure["rows"]}

    report_rows = []
    predicted_sum = 0.0
    direct_sum = 0.0
    delivered_sum = 0.0
    truth_sum = 0.0
    seed_mean_sum = 0.0
    reference_seed_mean_sum = 0.0
    seed_axis_sum = {key: 0.0 for key in ("h1", "v1", "h2", "v2")}
    reference_axis_sum = {key: 0.0 for key in seed_axis_sum}
    total_blocks = 0
    for frame_number in frames:
        source = source_decoded[frame_number].astype(np.float64)
        next_source = source_decoded[frame_number + 1].astype(np.float64)
        production, _score, _sigma = production_flat_blocks(source, args.bits)
        blocks = static_flat_blocks(
            source, next_source, production,
            lo=args.static_lo, hi=args.static_hi)
        if not blocks:
            continue
        table_entry = entry_for_frame(updating, frame_number, fps_num, fps_den)
        next_table_entry = entry_for_frame(
            updating, frame_number + 1, fps_num, fps_den)
        expected_entry = entry_for_frame(
            expected_updating, frame_number, fps_num, fps_den)
        next_expected_entry = entry_for_frame(
            expected_updating, frame_number + 1, fps_num, fps_den)
        entry = stream_entries[frame_number]
        next_entry = stream_entries[frame_number + 1]
        # filmgrn1 has no clip_to_restricted_range field.  A replay table
        # inherits that property from the encode, so an alternate-table oracle
        # must do the same.  Defaulting to full range changes measured variance
        # near black/white and can make curve scaling appear non-linear.
        expected_entry = {
            **expected_entry,
            "limit_output_range": entry["limit_output_range"],
        }
        next_expected_entry = {
            **next_expected_entry,
            "limit_output_range": next_entry["limit_output_range"],
        }
        predicted_blocks = av1_grain.synthesize_selected_luma(
            base_decoded[frame_number], blocks, entry, gaussian, args.bits)
        next_predicted_blocks = av1_grain.synthesize_selected_luma(
            base_decoded[frame_number + 1], blocks, next_entry, gaussian, args.bits)
        actual_blocks = actual_synth_blocks(
            on_decoded[frame_number], base_decoded[frame_number], blocks)
        next_actual_blocks = actual_synth_blocks(
            on_decoded[frame_number + 1], base_decoded[frame_number + 1], blocks)
        predicted = 0.5 * (
            float(selected_variances(predicted_blocks).mean())
            + float(selected_variances(next_predicted_blocks).mean()))
        actual = 0.5 * (
            float(selected_variances(actual_blocks).mean())
            + float(selected_variances(next_actual_blocks).mean()))
        seed_mean = None
        reference_seed_mean = None
        seed_axis = None
        reference_seed_axis = None
        if args.seed_samples > 0:
            seed_variance_sum = 0.0
            reference_variance_sum = 0.0
            seed_axes = []
            reference_axes = []
            for sample_number in range(args.seed_samples):
                frame_seed = oracle_seed(frame_number, sample_number)
                next_frame_seed = oracle_seed(frame_number + 1, sample_number)
                first_variance, first_axis = synth_variance_for_seed(
                    base_decoded[frame_number], blocks, expected_entry, gaussian,
                    args.bits, frame_seed)
                next_variance, next_axis = synth_variance_for_seed(
                    base_decoded[frame_number + 1], blocks, next_expected_entry,
                    gaussian, args.bits, next_frame_seed)
                seed_variance_sum += 0.5 * (first_variance + next_variance)
                seed_axes.extend((first_axis, next_axis))
                if args.expected_table:
                    first_reference_variance, first_reference_axis = synth_variance_for_seed(
                        base_decoded[frame_number], blocks, entry, gaussian,
                        args.bits, frame_seed)
                    next_reference_variance, next_reference_axis = synth_variance_for_seed(
                        base_decoded[frame_number + 1], blocks, next_entry,
                        gaussian, args.bits, next_frame_seed)
                    reference_variance_sum += 0.5 * (
                        first_reference_variance + next_reference_variance)
                    reference_axes.extend((first_reference_axis, next_reference_axis))
                else:
                    reference_variance_sum += 0.5 * (first_variance + next_variance)
                    reference_axes.extend((first_axis, next_axis))
            seed_mean = seed_variance_sum / args.seed_samples
            reference_seed_mean = reference_variance_sum / args.seed_samples
            seed_axis = average_axis(seed_axes)
            reference_seed_axis = average_axis(reference_axes)
        difference = np.concatenate((
            (predicted_blocks - actual_blocks).reshape(-1),
            (next_predicted_blocks - next_actual_blocks).reshape(-1)))
        measured = closure_rows[frame_number]["masks"]["production_static"]
        delivered = measured["encoded_arms"][args.arm]
        delivered_variance = delivered["synth_variance_sum"] / delivered["blocks"]
        truth_variance = delivered["truth_variance_sum"] / delivered["blocks"]
        count = delivered["blocks"]
        predicted_sum += predicted * count
        direct_sum += actual * count
        delivered_sum += delivered_variance * count
        truth_sum += truth_variance * count
        if seed_mean is not None:
            seed_mean_sum += seed_mean * count
            reference_seed_mean_sum += reference_seed_mean * count
            for key in seed_axis_sum:
                seed_axis_sum[key] += seed_axis[key] * count
                reference_axis_sum[key] += reference_seed_axis[key] * count
        total_blocks += count
        report_rows.append({
            "frame": frame_number,
            "blocks": count,
            "entry_start": table_entry["start"],
            "grain_scale_shift": entry["params"]["grain_scale_shift"],
            "scaling_shift": entry["params"]["scaling_shift"],
            "table_seed": table_entry["random_seed"],
            "bitstream_seed": entry["random_seed"],
            "next_table_seed": next_table_entry["random_seed"],
            "next_bitstream_seed": next_entry["random_seed"],
            "table_model_matches_stream": (
                table_matches_stream(table_entry, entry)
                and table_matches_stream(next_table_entry, next_entry)),
            "predicted_sigma": math.sqrt(predicted),
            "direct_sigma": math.sqrt(actual),
            "delivered_sigma": math.sqrt(delivered_variance),
            "predicted_over_delivered": (
                math.sqrt(predicted / delivered_variance)
                if delivered_variance > 0 else None),
            "direct_over_delivered": (
                math.sqrt(actual / delivered_variance)
                if delivered_variance > 0 else None),
            "seed_mean_sigma": math.sqrt(seed_mean) if seed_mean is not None else None,
            "seed_mean_axis": seed_axis,
            "reference_seed_mean_sigma": (
                math.sqrt(reference_seed_mean)
                if reference_seed_mean is not None else None),
            "reference_seed_mean_axis": reference_seed_axis,
            "seed_mean_over_delivered": (
                math.sqrt(seed_mean / delivered_variance)
                if seed_mean is not None and delivered_variance > 0 else None),
            "pixel_mismatches": int(np.count_nonzero(difference)),
            "pixel_count": int(difference.size),
            "max_abs_pixel_error": int(np.max(np.abs(difference))),
        })

    predicted_sigma = math.sqrt(predicted_sum / total_blocks)
    direct_sigma = math.sqrt(direct_sum / total_blocks)
    delivered_sigma = math.sqrt(delivered_sum / total_blocks)
    truth_sigma = math.sqrt(truth_sum / total_blocks)
    aggregate = {
        "blocks": total_blocks,
        "predicted_sigma": predicted_sigma,
        "direct_sigma": direct_sigma,
        "delivered_sigma": delivered_sigma,
        "truth_sigma": truth_sigma,
        "predicted_ratio": predicted_sigma / truth_sigma,
        "delivered_ratio": delivered_sigma / truth_sigma,
        "predicted_over_delivered": predicted_sigma / delivered_sigma,
        "direct_over_delivered": direct_sigma / delivered_sigma,
        "seed_samples": args.seed_samples,
        "seed_mean_sigma": (
            math.sqrt(seed_mean_sum / total_blocks)
            if args.seed_samples > 0 else None),
        "seed_mean_ratio": (
            math.sqrt(seed_mean_sum / truth_sum)
            if args.seed_samples > 0 else None),
        "seed_mean_over_delivered": (
            math.sqrt(seed_mean_sum / delivered_sum)
            if args.seed_samples > 0 else None),
        "seed_mean_axis": (
            {key: value / total_blocks for key, value in seed_axis_sum.items()}
            if args.seed_samples > 0 else None),
        "reference_seed_mean_sigma": (
            math.sqrt(reference_seed_mean_sum / total_blocks)
            if args.seed_samples > 0 else None),
        "reference_seed_mean_ratio": (
            math.sqrt(reference_seed_mean_sum / truth_sum)
            if args.seed_samples > 0 else None),
        "reference_seed_mean_axis": (
            {key: value / total_blocks for key, value in reference_axis_sum.items()}
            if args.seed_samples > 0 else None),
        "pixel_mismatches": sum(row["pixel_mismatches"] for row in report_rows),
        "pixel_count": sum(row["pixel_count"] for row in report_rows),
        "max_abs_pixel_error": max(
            row["max_abs_pixel_error"] for row in report_rows),
        "table_models_match_stream": all(
            row["table_model_matches_stream"] for row in report_rows),
        "table_seed_matches": sum(
            row["table_seed"] == row["bitstream_seed"]
            for row in report_rows),
        "table_seed_comparisons": len(report_rows),
    }
    report = {
        "source": os.path.abspath(args.source),
        "encoded": os.path.abspath(encoded),
        "table": os.path.abspath(args.table),
        "expected_table": os.path.abspath(
            args.expected_table if args.expected_table else args.table),
        "closure": os.path.abspath(args.closure),
        "arm": args.arm,
        "bits": args.bits,
        "fps": [fps_num, fps_den],
        "aom_grain_source": os.path.abspath(args.aom_grain_source),
        "aom_grain_source_sha256": grain_source_sha256,
        "mask": "production_static",
        "aggregate": aggregate,
        "rows": report_rows,
    }
    print(f"{'frame':>6}{'blocks':>9}{'tblseed':>9}{'seed':>9}"
          f"{'predicted':>11}{'direct':>11}{'delivered':>11}"
          + (f"{'seed mean':>11}" if args.seed_samples > 0 else "")
          + f"{'pred/del':>11}{'bad px':>10}")
    for row in report_rows:
        seed_column = (f"{row['seed_mean_sigma']:>11.3f}"
                       if args.seed_samples > 0 else "")
        print(f"{row['frame']:>6}{row['blocks']:>9}"
              f"{row['table_seed']:>9}{row['bitstream_seed']:>9}"
              f"{row['predicted_sigma']:>11.3f}"
              f"{row['direct_sigma']:>11.3f}"
              f"{row['delivered_sigma']:>11.3f}"
              f"{seed_column}"
              f"{row['predicted_over_delivered']:>11.3f}"
              f"{row['pixel_mismatches']:>10}")
    print("\naggregate "
          f"predicted={aggregate['predicted_ratio']:.4f} "
          f"delivered={aggregate['delivered_ratio']:.4f} "
          f"pred/del={aggregate['predicted_over_delivered']:.4f}"
          + (f" seed-mean={aggregate['seed_mean_ratio']:.4f} "
             f"seed/del={aggregate['seed_mean_over_delivered']:.4f}"
             if args.seed_samples > 0 else ""))
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")
        print(f"wrote {args.json_out}")


if __name__ == "__main__":
    main()
