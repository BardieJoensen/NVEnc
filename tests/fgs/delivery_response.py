#!/usr/bin/env python3
"""Test cheap AV1 luma-delivery estimators against the exact seed oracle.

The exact oracle in :mod:`emission_audit` can close a luma scaling curve, but
it has the decoded base pixels and runs normative synthesis over several seeds.
Those are not reasonable inputs to the analyzer hot path.  This experiment
tests progressively richer substitutes:

* ``uniform_20bin`` uses only the analyzer's 20 source-luma block counts;
* ``clean_block_mean`` additionally uses one clean-base mean per block;
* ``clean_pixel_histogram`` uses the clean pixels' 8-bit luma histogram;
* ``fixed_seed_clean_pixels`` (optional and deliberately expensive) runs one
  normative seed over the actual clean blocks as an upper-bound diagnostic.

All response curves use the quantized table model and one deterministic seed
per measured frame.  The reference values come from an existing
``emission_audit.py --seed-samples`` JSON report.
"""
import argparse
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import av1_grain  # noqa: E402
import filmgrn  # noqa: E402
from delivery_normalize import target_from_pre_leak  # noqa: E402
from emission_audit import (  # noqa: E402
    entry_for_frame, oracle_seed, selected_luma_band_positions,
    selected_variances,
)
from source_fit import (  # noqa: E402
    blockwise, production_flat_blocks, static_flat_blocks,
)
from strength_selection_report import decode_selected, probe_size  # noqa: E402

FGS_STRENGTH_BINS = 20


def parse_positive_ints(value):
    if not value:
        return []
    values = sorted(set(int(item) for item in value.split(",")))
    if any(item <= 0 for item in values):
        raise ValueError("sample counts must be positive")
    return values


def analyzer_bin_from_native(value, bits):
    return min(FGS_STRENGTH_BINS - 1, max(
        0, int(value * FGS_STRENGTH_BINS / (1 << bits))))


def native_to_8bit(value, bits, minimum, maximum):
    scale = 1 << (bits - 8)
    return min(maximum, max(minimum, int(round(value / scale))))


def response_fixture(bits, minimum, maximum):
    """One constant 32x32 block for every legal 8-bit luma code."""
    codes = np.arange(minimum, maximum + 1, dtype=np.int64)
    columns = 16
    rows = math.ceil(len(codes) / columns)
    depth_scale = 1 << (bits - 8)
    midpoint = depth_scale // 2
    native_maximum = min((1 << bits) - 1, maximum * depth_scale)
    base = np.zeros((rows * 32, columns * 32), dtype=np.int64)
    blocks = []
    for index, code in enumerate(codes):
        block_row, block_col = divmod(index, columns)
        base[block_row * 32:(block_row + 1) * 32,
             block_col * 32:(block_col + 1) * 32] = (
                 min(native_maximum, int(code) * depth_scale + midpoint))
        blocks.append((block_row, block_col))
    return codes, base, blocks


def response_map(entry, frame, gaussian, bits, limited_range,
                 fixture_codes, fixture_base, fixture_blocks):
    """Single-seed constant-luma response for one quantized table entry."""
    seeded = {
        **entry,
        "random_seed": oracle_seed(frame, 0),
        "limit_output_range": limited_range,
    }
    variances = selected_variances(av1_grain.synthesize_selected_luma(
        fixture_base, fixture_blocks, seeded, gaussian, bits))
    response = np.empty(256, dtype=np.float64)
    response[:fixture_codes[0]] = variances[0]
    response[fixture_codes] = variances
    response[fixture_codes[-1] + 1:] = variances[-1]
    return response, seeded


def uniform_bin_response(response, legal_codes):
    result = np.zeros(FGS_STRENGTH_BINS, dtype=np.float64)
    bins = np.asarray([
        analyzer_bin_from_native(code + 0.5, 8) for code in legal_codes
    ])
    for index in range(FGS_STRENGTH_BINS):
        selected = legal_codes[bins == index]
        if len(selected):
            result[index] = float(response[selected].mean())
    return result


def correction_residual(target_ratio, exact_sigma, predicted_sigma):
    """Residual target-ratio error after scaling by target/prediction."""
    if predicted_sigma <= 0.0:
        return None
    return target_ratio * (exact_sigma / predicted_sigma - 1.0)


def deterministic_sample_positions(positions, blocks, frame, limit, salt):
    """Choose a repeatable spatially mixed subset without Python hash state."""
    positions = [int(position) for position in positions]
    if len(positions) <= limit:
        return np.asarray(positions, dtype=np.int64)

    def rank(position):
        row, col = blocks[position]
        value = ((frame + 1) * 0x9E3779B1
                 ^ (row + 1) * 0x85EBCA6B
                 ^ (col + 1) * 0xC2B2AE35
                 ^ (salt + 1) * 0x27D4EB2F) & 0xffffffff
        value ^= value >> 16
        value = (value * 0x7FEB352D) & 0xffffffff
        value ^= value >> 15
        return value, position

    return np.asarray(sorted(positions, key=rank)[:limit], dtype=np.int64)


def sampled_bin_responses(pair_variances, block_bins, blocks,
                          frame, limit, salt):
    """Estimate each populated analyser-bin response from selected blocks."""
    responses = np.full(FGS_STRENGTH_BINS, np.nan, dtype=np.float64)
    samples = 0
    for bin_index in range(FGS_STRENGTH_BINS):
        positions = np.flatnonzero(block_bins == bin_index)
        if not len(positions):
            continue
        selected = deterministic_sample_positions(
            positions, blocks, frame, limit, salt)
        responses[bin_index] = float(np.mean(pair_variances[selected]))
        samples += len(selected)
    return responses, samples


def summarize_band(band, sums, count, qvbr):
    _theta, _post_leak, target = target_from_pre_leak(
        band["pre_encode_leak"], qvbr)
    exact = band["seed_mean_sigma"]
    methods = {}
    for name, variance_sum in sums.items():
        predicted = math.sqrt(variance_sum / count) if count else None
        methods[name] = {
            "predicted_sigma": predicted,
            "predicted_over_exact": (
                predicted / exact if predicted is not None and exact else None),
            "post_correction_target_error": (
                correction_residual(target, exact, predicted)
                if predicted is not None else None),
        }
    return {
        "range": band["range"],
        "blocks": count,
        "reference_blocks": band["blocks"],
        "truth_sigma": band["truth_sigma"],
        "exact_seed_mean_sigma": exact,
        "predicted_synthesis_target": target,
        "methods": methods,
    }


def summarize_sparse(reference_bands, variance_sums, counts, qvbr,
                     sample_limit, sampled_blocks):
    """Summarize deterministic selection sensitivity for one sample limit."""
    repeats = variance_sums.shape[0]
    band_rows = []
    all_errors = []
    for band_index, band in enumerate(reference_bands):
        exact = band["seed_mean_sigma"]
        _theta, _post_leak, target = target_from_pre_leak(
            band["pre_encode_leak"], qvbr)
        predicted = np.sqrt(variance_sums[:, band_index] / counts[band_index])
        errors = np.asarray([
            correction_residual(target, exact, value) for value in predicted
        ], dtype=np.float64)
        all_errors.extend(np.abs(errors).tolist())
        band_rows.append({
            "range": band["range"],
            "blocks": int(counts[band_index]),
            "predicted_sigma": {
                "mean": float(np.mean(predicted)),
                "minimum": float(np.min(predicted)),
                "maximum": float(np.max(predicted)),
            },
            "post_correction_target_error": {
                "mean": float(np.mean(errors)),
                "minimum": float(np.min(errors)),
                "maximum": float(np.max(errors)),
                "max_abs": float(np.max(np.abs(errors))),
            },
        })
    absolute = np.asarray(all_errors, dtype=np.float64)
    total_blocks = int(np.sum(counts))
    return {
        "blocks_per_frame_bin": sample_limit,
        "selection_repeats": repeats,
        "sampled_block_pairs_per_repeat": sampled_blocks,
        "selected_block_pairs": total_blocks,
        "sampled_fraction": sampled_blocks / total_blocks,
        "evaluated_clean_pixels_per_repeat": sampled_blocks * 2 * 32 * 32,
        "error_summary": {
            "mean_abs": float(np.mean(absolute)),
            "p95_abs": float(np.percentile(absolute, 95)),
            "max_abs": float(np.max(absolute)),
        },
        "bands": band_rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--emission", required=True,
        help="existing emission_audit.py --seed-samples JSON report")
    parser.add_argument("--qvbr", type=float, default=29.0)
    parser.add_argument("--full-range", action="store_true",
                        help="model full-range rather than limited-range output")
    parser.add_argument(
        "--fixed-seed-clean-pixels", action="store_true",
        help="also run the expensive one-seed actual-clean-pixel upper bound")
    parser.add_argument(
        "--sparse-blocks-per-bin", default="",
        help="comma-separated actual-clean block limits per frame/luma bin")
    parser.add_argument(
        "--sparse-repeats", type=int, default=8,
        help="deterministic spatial selections per sparse limit (default 8)")
    parser.add_argument(
        "--aom-grain-source",
        default=os.environ.get(
            "AOM_GRAIN_SOURCE", "/tmp/aomref/src/av1/decoder/grain_synthesis.c"))
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()
    try:
        sparse_limits = parse_positive_ints(args.sparse_blocks_per_bin)
    except ValueError as error:
        parser.error(str(error))
    if args.sparse_repeats <= 0:
        parser.error("--sparse-repeats must be positive")

    with open(args.emission, encoding="utf-8") as handle:
        emission = json.load(handle)
    with open(emission["closure"], encoding="utf-8") as handle:
        closure = json.load(handle)
    if emission["aggregate"].get("seed_samples", 0) <= 0:
        raise SystemExit("emission report has no multi-seed reference")

    source_path = emission["source"]
    clean_path = closure["clean_base"]
    bits = emission["bits"]
    frames = closure["frames"]
    indices = sorted(set(frames + [frame + 1 for frame in frames]))
    width, height = probe_size(source_path)
    source = decode_selected(source_path, width, height, indices, bits)
    clean = decode_selected(clean_path, width, height, indices, bits)
    entries = filmgrn.load(emission.get("expected_table") or emission["table"])
    fps_num, fps_den = emission["fps"]
    gaussian = av1_grain.load_gaussian_sequence(args.aom_grain_source)
    limited_range = not args.full_range
    legal_minimum, legal_maximum = ((16, 235) if limited_range else (0, 255))
    fixture_codes, fixture_base, fixture_blocks = response_fixture(
        bits, legal_minimum, legal_maximum)
    luma_ranges = [band["range"] for band in emission["luma_bins"]]
    method_names = [
        "uniform_20bin", "clean_block_mean", "clean_pixel_histogram"]
    if args.fixed_seed_clean_pixels:
        method_names.append("fixed_seed_clean_pixels")
    sums = {
        name: np.zeros(len(luma_ranges), dtype=np.float64)
        for name in method_names
    }
    counts = np.zeros(len(luma_ranges), dtype=np.int64)
    sparse_sums = {
        limit: np.zeros(
            (args.sparse_repeats, len(luma_ranges)), dtype=np.float64)
        for limit in sparse_limits
    }
    sparse_sampled_blocks = {limit: 0 for limit in sparse_limits}

    for frame in frames:
        current_source = np.asarray(source[frame], dtype=np.float64)
        next_source = np.asarray(source[frame + 1], dtype=np.float64)
        production, _score, _sigma = production_flat_blocks(
            current_source, bits)
        blocks = static_flat_blocks(
            current_source, next_source, production, lo=0.8, hi=1.3)
        if not blocks:
            continue
        positions = selected_luma_band_positions(
            current_source, blocks, bits, luma_ranges)
        source_grid = blockwise(current_source)
        clean_grids = [blockwise(clean[frame]), blockwise(clean[frame + 1])]
        block_bins = np.asarray([
            analyzer_bin_from_native(source_grid[row, col].mean(), bits)
            for row, col in blocks
        ])

        responses = []
        uniform = []
        exact_clean = []
        for frame_number in (frame, frame + 1):
            table_entry = entry_for_frame(
                entries, frame_number, fps_num, fps_den)
            response, seeded = response_map(
                table_entry, frame_number, gaussian, bits, limited_range,
                fixture_codes, fixture_base, fixture_blocks)
            responses.append(response)
            uniform.append(uniform_bin_response(response, fixture_codes))
            if args.fixed_seed_clean_pixels or sparse_limits:
                exact_clean.append(selected_variances(
                    av1_grain.synthesize_selected_luma(
                        clean[frame_number], blocks, seeded, gaussian, bits)))

        sparse_responses = {}
        if sparse_limits:
            pair_variances = 0.5 * (exact_clean[0] + exact_clean[1])
            for limit in sparse_limits:
                sparse_responses[limit] = []
                for repeat in range(args.sparse_repeats):
                    responses_by_bin, sample_count = sampled_bin_responses(
                        pair_variances, block_bins, blocks,
                        frame, limit, repeat)
                    sparse_responses[limit].append(responses_by_bin)
                    if repeat == 0:
                        sparse_sampled_blocks[limit] += sample_count

        for band, selected_positions in enumerate(positions):
            for position in selected_positions:
                row, col = blocks[position]
                source_bin = block_bins[position]
                sums["uniform_20bin"][band] += 0.5 * (
                    uniform[0][source_bin] + uniform[1][source_bin])
                means = [native_to_8bit(
                    grid[row, col].mean(), bits,
                    legal_minimum, legal_maximum) for grid in clean_grids]
                sums["clean_block_mean"][band] += 0.5 * (
                    responses[0][means[0]] + responses[1][means[1]])
                hist_variances = []
                for response, grid in zip(responses, clean_grids):
                    depth_scale = 1 << (bits - 8)
                    codes = np.clip(
                        (grid[row, col].astype(np.int64) + depth_scale // 2)
                        // depth_scale,
                        legal_minimum, legal_maximum)
                    hist_variances.append(float(response[codes].mean()))
                sums["clean_pixel_histogram"][band] += 0.5 * sum(
                    hist_variances)
                if args.fixed_seed_clean_pixels:
                    sums["fixed_seed_clean_pixels"][band] += 0.5 * (
                        exact_clean[0][position] + exact_clean[1][position])
                for limit, repeated in sparse_responses.items():
                    for repeat, responses_by_bin in enumerate(repeated):
                        sparse_sums[limit][repeat, band] += responses_by_bin[
                            source_bin]
                counts[band] += 1

    bands = []
    for index, reference in enumerate(emission["luma_bins"]):
        band_sums = {name: float(values[index]) for name, values in sums.items()}
        bands.append(summarize_band(
            reference, band_sums, int(counts[index]), args.qvbr))
    if any(row["blocks"] != row["reference_blocks"] for row in bands):
        raise RuntimeError("reconstructed luma-band populations do not match oracle")
    report = {
        "scope": "offline response-model gate; no encoder or production change",
        "emission": os.path.abspath(args.emission),
        "source": source_path,
        "clean_base": clean_path,
        "table": emission.get("expected_table") or emission["table"],
        "qvbr": args.qvbr,
        "bits": bits,
        "limited_range": limited_range,
        "reference_seed_samples": emission["aggregate"]["seed_samples"],
        "fixed_response_seed_samples_per_frame": 1,
        "bands": bands,
    }
    if sparse_limits:
        report["sparse_clean_pixels"] = {
            "sampling": (
                "bounded deterministic blocks per frame pair and analyser "
                "source-luma bin; one normative seed on actual clean pixels"),
            "models": [
                summarize_sparse(
                    emission["luma_bins"], sparse_sums[limit], counts,
                    args.qvbr, limit, sparse_sampled_blocks[limit])
                for limit in sparse_limits
            ],
        }
    print(json.dumps(report, indent=2))
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")


if __name__ == "__main__":
    main()
