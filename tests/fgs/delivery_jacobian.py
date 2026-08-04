#!/usr/bin/env python3
"""Offline sparse finite-difference solver for AV1 luma grain delivery.

The simple delivery normalizer assumes that multiplying a scaling curve
multiplies decoded grain amplitude by the same factor. Restricted-range
clipping makes that false near black. This prototype measures the local,
cross-band response of the *quantized* proposed table on a bounded set of
actual clean pixels, solves a damped Jacobian update, and re-evaluates it.

It is deliberately an offline implementation gate, not an encoder option.
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
from delivery_normalize import (  # noqa: E402
    interpolate_factor, scale_entry_luma, target_from_pre_leak,
)
from delivery_response import (  # noqa: E402
    analyzer_bin_from_native, deterministic_sample_positions,
    representative_sample_positions, response_population_features,
)
from emission_audit import (  # noqa: E402
    entry_for_frame, evaluation_seed, probe_grain_entries,
    selected_luma_band_positions, selected_variances,
)
from source_fit import (  # noqa: E402
    blockwise, production_flat_blocks, static_flat_blocks,
)
from strength_selection_report import decode_selected, probe_size  # noqa: E402


def solve_damped_step(jacobian, residual, regularization, max_log_step):
    """Solve a regularized response update and clamp each log-factor."""
    jacobian = np.asarray(jacobian, dtype=np.float64)
    residual = np.asarray(residual, dtype=np.float64)
    if jacobian.ndim != 2 or residual.shape != (jacobian.shape[0],):
        raise ValueError("Jacobian and residual dimensions differ")
    if regularization < 0.0 or max_log_step <= 0.0:
        raise ValueError("invalid solver regularization or step bound")
    if regularization:
        root = math.sqrt(regularization)
        system = np.vstack((jacobian, root * np.eye(jacobian.shape[1])))
        target = np.concatenate((residual, np.zeros(jacobian.shape[1])))
    else:
        system = jacobian
        target = residual
    raw, _residuals, _rank, _singular = np.linalg.lstsq(
        system, target, rcond=None)
    bounded = np.clip(raw, -max_log_step, max_log_step)
    return raw, bounded


def scale_entries(entries, factor_points):
    factor_at = lambda x: interpolate_factor(factor_points, x)
    adjusted = []
    shifted = 0
    for entry in entries:
        candidate, shift_down = scale_entry_luma(entry, factor_at)
        adjusted.append(candidate)
        shifted += shift_down > 0
    return adjusted, shifted


def build_contexts(source, clean, frames, bits, luma_ranges,
                   blocks_per_bin, selection_salt, sampling,
                   limited_range):
    contexts = []
    for frame in frames:
        current = np.asarray(source[frame], dtype=np.float64)
        following = np.asarray(source[frame + 1], dtype=np.float64)
        blocks, _score, _sigma = production_flat_blocks(current, bits)
        blocks = static_flat_blocks(
            current, following, blocks, lo=0.8, hi=1.3)
        if not blocks:
            continue
        source_grid = blockwise(current)
        block_bins = np.asarray([
            analyzer_bin_from_native(source_grid[row, col].mean(), bits)
            for row, col in blocks
        ], dtype=np.int64)
        features = (response_population_features(
            (clean[frame], clean[frame + 1]), blocks, bits, limited_range)
            if sampling == "response-representative" else None)
        selected_by_bin = {}
        weights_by_bin = {}
        for bin_index in sorted(set(block_bins.tolist())):
            positions = np.flatnonzero(block_bins == bin_index)
            if sampling == "response-representative":
                selected, weights = representative_sample_positions(
                    positions, features, blocks, frame,
                    blocks_per_bin, selection_salt)
            else:
                selected = deterministic_sample_positions(
                    positions, blocks, frame,
                    blocks_per_bin, selection_salt)
                weights = np.ones(len(selected), dtype=np.int64)
            selected_by_bin[bin_index] = selected
            weights_by_bin[bin_index] = weights
        selected_positions = sorted(set(
            int(position) for positions in selected_by_bin.values()
            for position in positions))
        selected_blocks = [blocks[position] for position in selected_positions]
        selected_lookup = {
            position: index for index, position in enumerate(selected_positions)
        }
        contexts.append({
            "frame": frame,
            "blocks": blocks,
            "block_bins": block_bins,
            "band_positions": selected_luma_band_positions(
                current, blocks, bits, luma_ranges),
            "selected_by_bin": selected_by_bin,
            "weights_by_bin": weights_by_bin,
            "selected_blocks": selected_blocks,
            "selected_lookup": selected_lookup,
            "clean": (clean[frame], clean[frame + 1]),
        })
    return contexts


def evaluate_entries(entries, contexts, gaussian, bits, fps_num, fps_den,
                     limited_range, band_count, response_seeds,
                     seed_mode="oracle", stream_entries=None):
    variance_sums = np.zeros(band_count, dtype=np.float64)
    counts = np.zeros(band_count, dtype=np.int64)
    sampled_blocks = 0
    for context in contexts:
        frame = context["frame"]
        selected_blocks = context["selected_blocks"]
        pair_variances = np.zeros(len(selected_blocks), dtype=np.float64)
        for sample in range(response_seeds):
            frame_variances = []
            for frame_number, clean in zip((frame, frame + 1), context["clean"]):
                entry = entry_for_frame(entries, frame_number, fps_num, fps_den)
                seeded = {
                    **entry,
                    "random_seed": evaluation_seed(
                        frame_number, sample, seed_mode, stream_entries),
                    "limit_output_range": limited_range,
                }
                frame_variances.append(selected_variances(
                    av1_grain.synthesize_selected_luma(
                        clean, selected_blocks, seeded, gaussian, bits)))
            pair_variances += 0.5 * (
                frame_variances[0] + frame_variances[1])
        pair_variances /= response_seeds
        responses = {}
        for bin_index, positions in context["selected_by_bin"].items():
            local = [context["selected_lookup"][int(position)]
                     for position in positions]
            responses[bin_index] = float(np.average(
                pair_variances[local],
                weights=context["weights_by_bin"][bin_index]))
            sampled_blocks += len(local)
        for band, positions in enumerate(context["band_positions"]):
            for position in positions:
                variance_sums[band] += responses[
                    int(context["block_bins"][position])]
                counts[band] += 1
    return variance_sums, counts, sampled_blocks


def ratios_from_variance(variance_sums, counts, truth_sigmas):
    if np.any(counts <= 0):
        raise ValueError("one or more luma bands have no blocks")
    sigmas = np.sqrt(variance_sums / counts)
    return sigmas / np.asarray(truth_sigmas, dtype=np.float64)


def postencode_target_ratios(source, encoded_base, contexts, band_count):
    """Measure exact missing synthesis variance on the response population."""
    source_sums = np.zeros(band_count, dtype=np.float64)
    base_sums = np.zeros(band_count, dtype=np.float64)
    counts = np.zeros(band_count, dtype=np.int64)
    for context in contexts:
        frame = context["frame"]
        source_field = (
            np.asarray(source[frame], dtype=np.float64)
            - np.asarray(source[frame + 1], dtype=np.float64)) / math.sqrt(2.0)
        base_field = (
            np.asarray(encoded_base[frame], dtype=np.float64)
            - np.asarray(encoded_base[frame + 1], dtype=np.float64)) / math.sqrt(2.0)
        source_grid = blockwise(source_field)
        base_grid = blockwise(base_field)
        blocks = context["blocks"]
        for band, positions in enumerate(context["band_positions"]):
            if not positions:
                continue
            rows = np.asarray(
                [blocks[position][0] for position in positions], dtype=np.int64)
            cols = np.asarray(
                [blocks[position][1] for position in positions], dtype=np.int64)
            source_sums[band] += float(
                selected_variances(source_grid[rows, cols]).sum())
            base_sums[band] += float(
                selected_variances(base_grid[rows, cols]).sum())
            counts[band] += len(positions)
    if np.any(counts <= 0) or np.any(source_sums <= 0.0):
        raise ValueError("post-encode target has an empty or zero-energy band")
    source_variance = source_sums / counts
    base_variance = base_sums / counts
    leak_squared = np.clip(base_variance / source_variance, 0.0, 1.0)
    return {
        "ratios": np.sqrt(1.0 - leak_squared),
        "counts": counts,
        "source_sigma": np.sqrt(source_variance),
        "base_sigma": np.sqrt(base_variance),
        "post_leak_ratio": np.sqrt(leak_squared),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="candidate filmgrn1 table")
    parser.add_argument("--emission", required=True,
                        help="emission report defining source, base and targets")
    parser.add_argument("--qvbr", type=float, required=True)
    parser.add_argument("--blocks-per-bin", type=int, default=16)
    parser.add_argument("--response-seeds", type=int, default=1,
                        help="deterministic synthesis seeds per response evaluation")
    parser.add_argument(
        "--response-seed-mode", choices=("oracle", "stream"),
        default="oracle",
        help="seed source for response evaluation (default: synthetic oracle)")
    parser.add_argument("--selection-salt", type=int, default=0)
    parser.add_argument(
        "--sampling", choices=("spatial", "response-representative"),
        default="spatial",
        help="bounded response population (default preserves historical spatial sample)")
    parser.add_argument(
        "--response-base", choices=("clean", "encoded"), default="clean",
        help="pixels used to model AV1 synthesis response (default: pre-encode clean base)")
    parser.add_argument(
        "--target", choices=("qvbr", "postencode"), default="qvbr",
        help="strength target (postencode requires --response-base encoded)")
    parser.add_argument("--perturbation", type=float, default=0.08,
                        help="finite-difference log-factor (default 0.08)")
    parser.add_argument("--regularization", type=float, default=0.01)
    parser.add_argument("--max-log-step", type=float, default=0.40)
    parser.add_argument("--iterations", type=int, default=1, choices=(1, 2))
    parser.add_argument("--full-range", action="store_true")
    parser.add_argument(
        "--aom-grain-source",
        default=os.environ.get(
            "AOM_GRAIN_SOURCE", "/tmp/aomref/src/av1/decoder/grain_synthesis.c"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()
    if (args.blocks_per_bin <= 0 or args.response_seeds <= 0
            or args.perturbation <= 0.0):
        parser.error("sample count and perturbation must be positive")
    if args.target == "postencode" and args.response_base != "encoded":
        parser.error("--target postencode requires --response-base encoded")
    if args.response_seed_mode == "stream" and args.response_base != "encoded":
        parser.error("--response-seed-mode stream requires --response-base encoded")
    if args.response_seed_mode == "stream" and args.response_seeds != 1:
        parser.error("--response-seed-mode stream requires --response-seeds 1")

    with open(args.emission, encoding="utf-8") as handle:
        emission = json.load(handle)
    with open(emission["closure"], encoding="utf-8") as handle:
        closure = json.load(handle)
    source_path = emission["source"]
    clean_path = closure["clean_base"]
    encoded_path = emission.get("encoded")
    response_path = clean_path
    response_filmgrain = None
    if args.response_base == "encoded":
        if not encoded_path:
            raise SystemExit("emission report has no encoded response base")
        response_path = encoded_path
        response_filmgrain = 0
    bits = emission["bits"]
    frames = closure["frames"]
    indices = sorted(set(frames + [frame + 1 for frame in frames]))
    width, height = probe_size(source_path)
    if probe_size(response_path) != (width, height):
        raise SystemExit("source and response-base dimensions differ")
    source = decode_selected(source_path, width, height, indices, bits)
    clean = decode_selected(
        response_path, width, height, indices, bits,
        filmgrain=response_filmgrain)
    response_stream_entries = None
    if args.response_seed_mode == "stream":
        response_stream_entries = probe_grain_entries(
            encoded_path, max(indices) + 1, required_frames=indices)
    gaussian = av1_grain.load_gaussian_sequence(args.aom_grain_source)
    fps_num, fps_den = emission["fps"]
    bands = emission["luma_bins"]
    luma_ranges = [band["range"] for band in bands]
    truth_sigmas = [band["truth_sigma"] for band in bands]
    centers = [128.0 * (lower + upper) for lower, upper in luma_ranges]
    contexts = build_contexts(
        source, clean, frames, bits, luma_ranges,
        args.blocks_per_bin, args.selection_salt, args.sampling,
        not args.full_range)
    expected_counts = np.asarray([band["blocks"] for band in bands])
    postencode_target = None
    if args.target == "postencode":
        postencode_target = postencode_target_ratios(
            source, clean, contexts, len(bands))
        if not np.array_equal(postencode_target["counts"], expected_counts):
            raise RuntimeError("post-encode target population differs")
        targets = postencode_target["ratios"]
    else:
        targets = np.asarray([
            target_from_pre_leak(band["pre_encode_leak"], args.qvbr)[2]
            for band in bands
        ], dtype=np.float64)
    entries = filmgrn.load(args.input)
    iteration_rows = []
    total_evaluations = 0
    for iteration in range(args.iterations):
        baseline_variance, counts, sampled_blocks = evaluate_entries(
            entries, contexts, gaussian, bits, fps_num, fps_den,
            not args.full_range, len(bands), args.response_seeds,
            args.response_seed_mode, response_stream_entries)
        total_evaluations += 1
        if not np.array_equal(counts, expected_counts):
            raise RuntimeError("reconstructed luma-band populations differ")
        baseline = ratios_from_variance(
            baseline_variance, counts, truth_sigmas)
        jacobian = np.empty((len(bands), len(centers)), dtype=np.float64)
        for column in range(len(centers)):
            points = [
                (center, math.exp(args.perturbation) if index == column else 1.0)
                for index, center in enumerate(centers)
            ]
            perturbed, _shifted = scale_entries(entries, points)
            variance, perturbed_counts, _samples = evaluate_entries(
                perturbed, contexts, gaussian, bits, fps_num, fps_den,
                not args.full_range, len(bands), args.response_seeds,
                args.response_seed_mode, response_stream_entries)
            total_evaluations += 1
            if not np.array_equal(perturbed_counts, counts):
                raise RuntimeError("perturbation changed luma-band populations")
            response = ratios_from_variance(variance, counts, truth_sigmas)
            jacobian[:, column] = (
                response - baseline) / args.perturbation
        residual = targets - baseline
        raw_step, step = solve_damped_step(
            jacobian, residual, args.regularization, args.max_log_step)
        factors = np.exp(step)
        factor_points = list(zip(centers, factors.tolist()))
        proposed, shifted = scale_entries(entries, factor_points)
        proposed_variance, proposed_counts, _samples = evaluate_entries(
            proposed, contexts, gaussian, bits, fps_num, fps_den,
            not args.full_range, len(bands), args.response_seeds,
            args.response_seed_mode, response_stream_entries)
        total_evaluations += 1
        proposed_response = ratios_from_variance(
            proposed_variance, proposed_counts, truth_sigmas)
        singular = np.linalg.svd(jacobian, compute_uv=False)
        iteration_rows.append({
            "iteration": iteration + 1,
            "baseline_response": baseline.tolist(),
            "target": targets.tolist(),
            "baseline_error": (baseline - targets).tolist(),
            "jacobian": jacobian.tolist(),
            "singular_values": singular.tolist(),
            "condition_number": (
                float(singular[0] / singular[-1])
                if singular[-1] > 0.0 else None),
            "raw_log_step": raw_step.tolist(),
            "bounded_log_step": step.tolist(),
            "factor_points": factor_points,
            "entries_requiring_shared_shift": shifted,
            "proposed_response": proposed_response.tolist(),
            "proposed_error": (proposed_response - targets).tolist(),
            "proposed_max_abs_error": float(np.max(np.abs(
                proposed_response - targets))),
        })
        entries = proposed

    filmgrn.write(args.output, entries)
    filmgrn.load(args.output)
    report = {
        "scope": "offline sparse quantized response-Jacobian gate",
        "input": os.path.abspath(args.input),
        "output": os.path.abspath(args.output),
        "emission": os.path.abspath(args.emission),
        "qvbr": args.qvbr,
        "blocks_per_frame_bin": args.blocks_per_bin,
        "response_seeds": args.response_seeds,
        "response_seed_mode": args.response_seed_mode,
        "selection_salt": args.selection_salt,
        "sampling": args.sampling,
        "response_base": args.response_base,
        "response_base_path": os.path.abspath(response_path),
        "target_mode": args.target,
        "postencode_target": (None if postencode_target is None else {
            key: value.tolist() for key, value in postencode_target.items()
        }),
        "perturbation_log_factor": args.perturbation,
        "regularization": args.regularization,
        "max_log_step": args.max_log_step,
        "iterations": iteration_rows,
        "sampled_block_pairs_per_evaluation": sampled_blocks,
        "evaluated_clean_pixels_per_evaluation": (
            sampled_blocks * args.response_seeds * 2 * 32 * 32),
        "response_evaluations": total_evaluations,
    }
    print(json.dumps(report, indent=2))
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")


if __name__ == "__main__":
    main()
