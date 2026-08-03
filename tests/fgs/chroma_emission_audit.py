#!/usr/bin/env python3
"""Audit exact AV1 chroma-grain emission on source-selected flat blocks.

The source-fit analyzer estimates U/V strength in source-luma bins, then AV1
combines a chroma AR template, an optional luma-grain predictor, an integer
scaling curve, overlap, rounding and output clipping. This audit reproduces
that decoder path on the exact bitstream parameters and verifies it against
dav1d pixel-for-pixel before using counterfactual templates diagnostically.

The counterfactuals change only the offline normative model:

* ``no_luma`` zeros the final cross-plane AR coefficient;
* ``no_spatial`` zeros the 24 chroma spatial AR coefficients; and
* ``white`` zeros every chroma AR coefficient.

They are not alternate encodes and are never candidates for production. They
separate the realised template response from the emitted strength curve.

Usage:
  python3 tests/fgs/chroma_emission_audit.py \
      --source clip_Taxi_Driver.mkv --encoded bilateral-source.mkv \
      --table bilateral-source.tbl --plane v --json-out Taxi-v.json
"""
import argparse
import copy
import hashlib
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import av1_grain  # noqa: E402
import emission_audit  # noqa: E402
import filmgrn  # noqa: E402
from source_fit import (  # noqa: E402
    blockwise, production_flat_blocks, static_flat_blocks,
)
from strength_selection_report import decode_selected, probe_size  # noqa: E402


VARIANCE_FIELDS = (
    "truth", "base", "target", "actual", "predicted", "played",
    "no_luma", "no_spatial", "white", "template",
)


def selected_blocks(frame, blocks, block_size):
    grid = blockwise(np.asarray(frame), block_size)
    rows = np.asarray([row for row, _col in blocks])
    cols = np.asarray([col for _row, col in blocks])
    return np.asarray(grid[rows, cols], dtype=np.float64)


def counterfactual_entry(entry, plane, mode):
    """Copy a decoded entry and remove selected chroma predictor classes."""
    if plane not in ("cb", "cr"):
        raise ValueError(f"chroma plane must be cb or cr, got {plane}")
    if mode not in ("no_luma", "no_spatial", "white"):
        raise ValueError(f"unknown counterfactual mode {mode}")
    changed = copy.deepcopy(entry)
    coefficients = changed["ar_coeffs"][plane]
    spatial_count = len(coefficients) - (
        1 if changed["scaling_points"]["y"] else 0)
    if mode in ("no_spatial", "white"):
        coefficients[:spatial_count] = [0] * spatial_count
    if mode in ("no_luma", "white") and len(coefficients) > spatial_count:
        coefficients[spatial_count] = 0
    return changed


def block_variances(blocks):
    return emission_audit.selected_variances(np.asarray(blocks, dtype=np.float64))


def frame_fields(
        source, next_source, base, next_base, on, next_on,
        source_luma, next_source_luma, base_luma, next_base_luma,
        blocks, entry, next_entry,
        gaussian, bits, plane):
    """Return one value per selected block plus exact mismatch diagnostics."""
    source_blocks = selected_blocks(source, blocks, 16)
    next_source_blocks = selected_blocks(next_source, blocks, 16)
    base_blocks = selected_blocks(base, blocks, 16)
    next_base_blocks = selected_blocks(next_base, blocks, 16)
    on_blocks = selected_blocks(on, blocks, 16)
    next_on_blocks = selected_blocks(next_on, blocks, 16)

    actual = on_blocks - base_blocks
    next_actual = next_on_blocks - next_base_blocks
    response = av1_grain.selected_chroma_response(
        base_luma, base, blocks, entry, gaussian, bits, plane)
    next_response = av1_grain.selected_chroma_response(
        next_base_luma, next_base, blocks, next_entry, gaussian, bits, plane)
    predicted = np.asarray(response["delta"], dtype=np.float64)
    next_predicted = np.asarray(next_response["delta"], dtype=np.float64)

    truth = block_variances((source_blocks - next_source_blocks) / math.sqrt(2.0))
    base_variance = block_variances((base_blocks - next_base_blocks) / math.sqrt(2.0))
    target = np.maximum(0.0, truth - base_variance)
    actual_variance = 0.5 * (
        block_variances(actual) + block_variances(next_actual))
    predicted_variance = 0.5 * (
        block_variances(predicted) + block_variances(next_predicted))
    played = block_variances((on_blocks - next_on_blocks) / math.sqrt(2.0))
    template = 0.5 * (
        block_variances(response["grain"])
        + block_variances(next_response["grain"]))

    fields = {
        "truth": truth,
        "base": base_variance,
        "target": target,
        "actual": actual_variance,
        "predicted": predicted_variance,
        "played": played,
        "template": template,
    }
    for mode in ("no_luma", "no_spatial", "white"):
        changed = counterfactual_entry(entry, plane, mode)
        next_changed = counterfactual_entry(next_entry, plane, mode)
        changed_delta = av1_grain.synthesize_selected_chroma(
            base_luma, base, blocks, changed, gaussian, bits, plane)
        next_changed_delta = av1_grain.synthesize_selected_chroma(
            next_base_luma, next_base, blocks, next_changed, gaussian, bits, plane)
        fields[mode] = 0.5 * (
            block_variances(changed_delta)
            + block_variances(next_changed_delta))

    difference = np.concatenate((
        (predicted - actual).reshape(len(blocks), -1),
        (next_predicted - next_actual).reshape(len(blocks), -1)), axis=1)
    scales = np.concatenate((
        response["scales"].reshape(len(blocks), -1),
        next_response["scales"].reshape(len(blocks), -1)), axis=1)
    indices = np.concatenate((
        response["indices"].reshape(len(blocks), -1),
        next_response["indices"].reshape(len(blocks), -1)), axis=1)
    source_luma_blocks = selected_blocks(source_luma, blocks, 32)
    next_source_luma_blocks = selected_blocks(next_source_luma, blocks, 32)
    curve_plane = ("y" if entry["params"].get("chroma_scaling_from_luma", 0)
                   else plane)
    next_curve_plane = (
        "y" if next_entry["params"].get("chroma_scaling_from_luma", 0)
        else plane)
    block_mean_scale = av1_grain.scale_values(
        av1_grain.scaling_lut(entry["scaling_points"][curve_plane]),
        np.rint(source_luma_blocks.mean(axis=(-2, -1))).astype(np.int64), bits)
    next_block_mean_scale = av1_grain.scale_values(
        av1_grain.scaling_lut(next_entry["scaling_points"][next_curve_plane]),
        np.rint(next_source_luma_blocks.mean(axis=(-2, -1))).astype(np.int64), bits)
    actual_delta = np.concatenate((
        actual.reshape(len(blocks), -1),
        next_actual.reshape(len(blocks), -1)), axis=1)
    return {
        "variance": fields,
        "scale_sq": np.mean(scales.astype(np.float64) ** 2, axis=1),
        "block_mean_scale_sq": 0.5 * (
            block_mean_scale.astype(np.float64) ** 2
            + next_block_mean_scale.astype(np.float64) ** 2),
        "index_sum": indices.sum(axis=1, dtype=np.int64),
        "index_count": indices.shape[1],
        "index_min": indices.min(axis=1),
        "index_max": indices.max(axis=1),
        "nonzero": np.count_nonzero(actual_delta, axis=1),
        "pixel_count": actual_delta.shape[1],
        "mismatches": np.count_nonzero(difference, axis=1),
        "max_abs_error": np.max(np.abs(difference), axis=1),
    }


def accumulate(fields, positions=None):
    count = len(fields["variance"]["truth"])
    selected = (np.arange(count, dtype=np.int64) if positions is None
                else np.asarray(positions, dtype=np.int64))
    record = {
        "blocks": int(len(selected)),
        "variance_sums": {
            name: float(fields["variance"][name][selected].sum())
            for name in VARIANCE_FIELDS
        },
        "scale_sq_sum": float(fields["scale_sq"][selected].sum()),
        "block_mean_scale_sq_sum": float(
            fields["block_mean_scale_sq"][selected].sum()),
        "index_sum": int(fields["index_sum"][selected].sum()),
        "index_count": int(len(selected) * fields["index_count"]),
        "index_min": int(fields["index_min"][selected].min()) if len(selected) else None,
        "index_max": int(fields["index_max"][selected].max()) if len(selected) else None,
        "nonzero": int(fields["nonzero"][selected].sum()),
        "pixel_count": int(len(selected) * fields["pixel_count"]),
        "mismatches": int(fields["mismatches"][selected].sum()),
        "max_abs_error": int(fields["max_abs_error"][selected].max()) if len(selected) else 0,
    }
    return record


def combine(records):
    present = [record for record in records if record["blocks"]]
    combined = {
        "blocks": sum(record["blocks"] for record in present),
        "variance_sums": {
            name: sum(record["variance_sums"][name] for record in present)
            for name in VARIANCE_FIELDS
        },
        "scale_sq_sum": sum(record["scale_sq_sum"] for record in present),
        "block_mean_scale_sq_sum": sum(
            record["block_mean_scale_sq_sum"] for record in present),
        "index_sum": sum(record["index_sum"] for record in present),
        "index_count": sum(record["index_count"] for record in present),
        "index_min": min(
            record["index_min"] for record in present
            if record["index_min"] is not None) if present else None,
        "index_max": max(
            record["index_max"] for record in present
            if record["index_max"] is not None) if present else None,
        "nonzero": sum(record["nonzero"] for record in present),
        "pixel_count": sum(record["pixel_count"] for record in present),
        "mismatches": sum(record["mismatches"] for record in present),
        "max_abs_error": max(
            (record["max_abs_error"] for record in present), default=0),
    }
    return combined


def finalize(record, bits):
    blocks = record["blocks"]
    sigmas = {
        name: math.sqrt(max(0.0, total / blocks)) if blocks else None
        for name, total in record["variance_sums"].items()
    }
    truth = sigmas["truth"]
    target = sigmas["target"]

    def ratio(numerator, denominator):
        return numerator / denominator if denominator and denominator > 0.0 else None

    curve_scale_rms = (
        math.sqrt(record["scale_sq_sum"] / blocks) if blocks else None)
    block_mean_curve_scale_rms = (
        math.sqrt(record["block_mean_scale_sq_sum"] / blocks)
        if blocks else None)
    return {
        "blocks": blocks,
        "sigma": sigmas,
        "ratio_to_truth": {
            name: ratio(sigmas[name], truth)
            for name in ("base", "target", "actual", "predicted", "played")
        },
        "synth_over_target": {
            name: ratio(sigmas[name], target)
            for name in ("actual", "predicted", "no_luma", "no_spatial", "white")
        },
        "counterfactual_over_actual": {
            name: ratio(sigmas[name], sigmas["actual"])
            for name in ("no_luma", "no_spatial", "white")
        },
        "curve_scale_rms": curve_scale_rms,
        "block_mean_curve_scale_rms": block_mean_curve_scale_rms,
        "pixel_over_block_curve_rms": ratio(
            curve_scale_rms, block_mean_curve_scale_rms),
        "lookup_index_mean": (
            record["index_sum"] / record["index_count"]
            if record["index_count"] else None),
        "lookup_index_mean_8bit": (
            record["index_sum"] / record["index_count"]
            / (1 << (bits - 8)) if record["index_count"] else None),
        "lookup_index_range": [record["index_min"], record["index_max"]],
        "nonzero_delta_fraction": (
            record["nonzero"] / record["pixel_count"]
            if record["pixel_count"] else None),
        "pixel_mismatches": record["mismatches"],
        "pixel_count": record["pixel_count"],
        "max_abs_pixel_error": record["max_abs_error"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--encoded", required=True)
    parser.add_argument("--table", default="")
    parser.add_argument("--plane", choices=("u", "v"), required=True)
    parser.add_argument("--frames", default="10,58,106,154,202,250,275")
    parser.add_argument("--bits", type=int, default=10, choices=(8, 10, 12))
    parser.add_argument("--luma-bins", type=int, default=8)
    parser.add_argument("--static-lo", type=float, default=0.8)
    parser.add_argument("--static-hi", type=float, default=1.3)
    parser.add_argument(
        "--aom-grain-source",
        default=os.environ.get(
            "AOM_GRAIN_SOURCE", "/tmp/aomref/src/av1/decoder/grain_synthesis.c"))
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    frames = [int(value) for value in args.frames.split(",")]
    indices = sorted(set(frames + [frame + 1 for frame in frames]))
    width, height = probe_size(args.source)
    if probe_size(args.encoded) != (width, height):
        raise SystemExit("source and encoded dimensions differ")
    source_luma = decode_selected(
        args.source, width, height, indices, args.bits)
    source_chroma = decode_selected(
        args.source, width, height, indices, args.bits, plane=args.plane)
    base_luma = decode_selected(
        args.encoded, width, height, indices, args.bits, filmgrain=0)
    base_chroma = decode_selected(
        args.encoded, width, height, indices, args.bits,
        filmgrain=0, plane=args.plane)
    on_chroma = decode_selected(
        args.encoded, width, height, indices, args.bits,
        filmgrain=1, plane=args.plane)
    stream_entries = emission_audit.probe_grain_entries(
        args.encoded, max(indices) + 1)
    fps_num, fps_den = emission_audit.probe_rate(args.source)
    table_entries = filmgrn.load(args.table) if args.table else []
    table_updating = [
        entry for entry in table_entries
        if entry["apply_grain"] and entry["update_parameters"]
    ]
    gaussian = av1_grain.load_gaussian_sequence(args.aom_grain_source)
    with open(args.aom_grain_source, "rb") as handle:
        grain_source_sha256 = hashlib.sha256(handle.read()).hexdigest()

    plane = "cb" if args.plane == "u" else "cr"
    ranges = [
        [index / args.luma_bins, (index + 1) / args.luma_bins]
        for index in range(args.luma_bins)
    ]
    all_records = []
    band_records = [[] for _range in ranges]
    frame_reports = []
    table_matches = []
    max_value = float(1 << args.bits)
    for frame_number in frames:
        luma = source_luma[frame_number].astype(np.float64)
        next_luma = source_luma[frame_number + 1].astype(np.float64)
        production, _score, _sigma = production_flat_blocks(luma, args.bits)
        blocks = static_flat_blocks(
            luma, next_luma, production,
            lo=args.static_lo, hi=args.static_hi)
        if not blocks:
            continue
        entry = stream_entries[frame_number]
        next_entry = stream_entries[frame_number + 1]
        fields = frame_fields(
            source_chroma[frame_number], source_chroma[frame_number + 1],
            base_chroma[frame_number], base_chroma[frame_number + 1],
            on_chroma[frame_number], on_chroma[frame_number + 1],
            source_luma[frame_number], source_luma[frame_number + 1],
            base_luma[frame_number], base_luma[frame_number + 1],
            blocks, entry, next_entry, gaussian, args.bits, plane)
        overall = accumulate(fields)
        all_records.append(overall)
        positions = emission_audit.selected_luma_band_positions(
            luma, blocks, args.bits, ranges)
        frame_bands = []
        for band, selected in enumerate(positions):
            record = accumulate(fields, selected)
            band_records[band].append(record)
            frame_bands.append({
                "range": ranges[band],
                **finalize(record, args.bits),
            })
        model_matches = None
        if table_updating:
            table_entry = emission_audit.entry_for_frame(
                table_updating, frame_number, fps_num, fps_den)
            next_table_entry = emission_audit.entry_for_frame(
                table_updating, frame_number + 1, fps_num, fps_den)
            model_matches = (
                emission_audit.table_matches_stream(table_entry, entry)
                and emission_audit.table_matches_stream(
                    next_table_entry, next_entry))
            table_matches.append(model_matches)
        frame_reports.append({
            "frame": frame_number,
            "table_model_matches_stream": model_matches,
            "aggregate": finalize(overall, args.bits),
            "luma_bins": frame_bands,
        })

    aggregate = finalize(combine(all_records), args.bits)
    luma_bins = [
        {"range": ranges[index], **finalize(combine(records), args.bits)}
        for index, records in enumerate(band_records)
        if sum(record["blocks"] for record in records) > 0
    ]
    report = {
        "source": os.path.abspath(args.source),
        "encoded": os.path.abspath(args.encoded),
        "table": os.path.abspath(args.table) if args.table else None,
        "plane": args.plane,
        "bits": args.bits,
        "frames": frames,
        "static_ratio": [args.static_lo, args.static_hi],
        "aom_grain_source": os.path.abspath(args.aom_grain_source),
        "aom_grain_source_sha256": grain_source_sha256,
        "table_models_match_stream": all(table_matches) if table_matches else None,
        "aggregate": aggregate,
        "luma_bins": luma_bins,
        "rows": frame_reports,
    }

    print(f"{os.path.basename(args.source)} plane={args.plane} "
          f"blocks={aggregate['blocks']} mismatches="
          f"{aggregate['pixel_mismatches']}/{aggregate['pixel_count']}")
    print(f"{'range':<15}{'blocks':>8}{'truth':>9}{'target':>9}"
          f"{'synth':>9}{'played':>9}{'s/tgt':>9}{'noY/act':>10}"
          f"{'white/act':>11}{'curve':>9}{'nz':>8}")
    def number(value, width):
        return f"{value:>{width}.3f}" if value is not None else f"{'n/a':>{width}}"

    for row in luma_bins:
        low, high = row["range"]
        sigma = row["sigma"]
        print(f"{low:.3f}-{high:.3f} {row['blocks']:>7}"
              f"{number(sigma['truth'], 9)}{number(sigma['target'], 9)}"
              f"{number(sigma['actual'], 9)}{number(sigma['played'], 9)}"
              f"{number(row['synth_over_target']['actual'], 9)}"
              f"{number(row['counterfactual_over_actual']['no_luma'], 10)}"
              f"{number(row['counterfactual_over_actual']['white'], 11)}"
              f"{number(row['curve_scale_rms'], 9)}"
              f"{number(row['nonzero_delta_fraction'], 8)}")
    print("aggregate "
          f"truth={aggregate['sigma']['truth']:.3f} "
          f"target={aggregate['sigma']['target']:.3f} "
          f"synth={aggregate['sigma']['actual']:.3f} "
          f"played={aggregate['sigma']['played']:.3f} "
          f"pred/actual={aggregate['sigma']['predicted'] / aggregate['sigma']['actual']:.4f}")
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")
        print(f"wrote {args.json_out}")


if __name__ == "__main__":
    main()
