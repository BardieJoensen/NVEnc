#!/usr/bin/env python3
"""Separate AV1 texture limits from unmodelled base-texture leakage.

Source fitting currently treats the source's temporal grain covariance as the
synthesis target, while its strength path correctly subtracts grain left in
the encoded base.  Independent decoder synthesis adds covariance as well as
variance.  The matching texture target is therefore:

    C_synthesis = C_source_temporal - C_base_temporal

This offline oracle measures that target on the same source-selected static
blocks used by :mod:`temporal_grain_report`, fits an AR(3) model to the
covariance difference, quantises it at every AV1 coefficient shift, and
compares it with both the emitted table and decoded output.  It changes no
encode, emits no routing verdict, and is not a production threshold.

Example:
  python3 tests/fgs/texture_leak_oracle.py \
      --source clip.mkv --encoded candidate.mkv --table candidate.tbl \
      --frames 10,58,106,154,202,250 --json-out oracle.json
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

import ar_acf  # noqa: E402
import av1_grain  # noqa: E402
from emission_audit import (  # noqa: E402
    entry_for_frame, oracle_seed, probe_grain_entries, probe_rate,
    table_matches_stream,
)
import filmgrn  # noqa: E402
from source_fit import (  # noqa: E402
    blockwise, detrend_blocks, production_flat_blocks, static_flat_blocks,
)
from temporal_grain_report import decode_selected, probe_size  # noqa: E402


AXES = ("h1", "v1", "h2", "v2")
LAG = 3
BLOCK_SIZE = 32


def empty_axis_moments():
    return {
        "variance_sum": 0.0,
        "variance_count": 0,
        "covariance_sum": {axis: 0.0 for axis in AXES},
        "covariance_count": {axis: 0 for axis in AXES},
    }


def accumulate_patch_moments(moment, patches, detrend=True):
    """Pool patch variance/covariance without averaging correlations."""
    patches = np.asarray(patches, dtype=np.float64)
    if not len(patches):
        return
    if detrend:
        patches = detrend_blocks(patches[None])[0]
    moment["variance_sum"] += float(np.sum(patches * patches))
    moment["variance_count"] += int(patches.size)
    pairs = {
        "h1": (patches[:, :, 1:], patches[:, :, :-1]),
        "v1": (patches[:, 1:, :], patches[:, :-1, :]),
        "h2": (patches[:, :, 2:], patches[:, :, :-2]),
        "v2": (patches[:, 2:, :], patches[:, :-2, :]),
    }
    for axis, (left, right) in pairs.items():
        moment["covariance_sum"][axis] += float(np.sum(left * right))
        moment["covariance_count"][axis] += int(left.size)


def accumulate_axis_moments(moment, field, blocks, detrend=True):
    """Select aligned blocks from a field and pool their axis moments."""
    if not blocks:
        return
    grid = blockwise(np.asarray(field, dtype=np.float64), BLOCK_SIZE)
    patches = np.stack([grid[row, col] for row, col in blocks])
    accumulate_patch_moments(moment, patches, detrend)


def finish_axis_moments(moment):
    count = moment["variance_count"]
    if count <= 0:
        return None
    variance = moment["variance_sum"] / count
    if variance <= 0.0:
        return None
    result = {
        "samples": count,
        "variance": variance,
        "sigma": math.sqrt(variance),
        "covariance": {},
    }
    for axis in AXES:
        axis_count = moment["covariance_count"][axis]
        covariance = moment["covariance_sum"][axis] / axis_count
        result["covariance"][axis] = covariance
        result[axis] = covariance / variance
    result["lag1"] = 0.5 * (result["h1"] + result["v1"])
    result["lag2"] = 0.5 * (result["h2"] + result["v2"])
    return result


def subtract_axis_moments(source, base):
    """Return the independent synthesis covariance needed above ``base``."""
    if source is None or base is None:
        return None
    variance = source["variance"] - base["variance"]
    if variance <= 0.0:
        return {
            "valid": False,
            "reason": "base temporal variance is not below source truth",
            "variance": variance,
        }
    result = {
        "valid": True,
        "variance": variance,
        "sigma": math.sqrt(variance),
        "amplitude_over_source": math.sqrt(variance / source["variance"]),
        "covariance": {},
    }
    for axis in AXES:
        covariance = source["covariance"][axis] - base["covariance"][axis]
        result["covariance"][axis] = covariance
        result[axis] = covariance / variance
    result["lag1"] = 0.5 * (result["h1"] + result["v1"])
    result["lag2"] = 0.5 * (result["h2"] + result["v2"])
    return result


def empty_ar_system():
    count = len(ar_acf.ar_taps(LAG))
    return {
        "ata": np.zeros((count, count), dtype=np.float64),
        "atb": np.zeros(count, dtype=np.float64),
        "btb": 0.0,
        "observations": 0,
    }


def accumulate_ar_system(system, field, blocks, detrend=True):
    """Accumulate dense lag-3 normal equations and target energy per block."""
    grid = blockwise(np.asarray(field, dtype=np.float64), BLOCK_SIZE)
    taps = ar_acf.ar_taps(LAG)
    for row, col in blocks:
        patch = grid[row, col]
        if detrend:
            patch = detrend_blocks(patch[None, None])[0, 0]
        target = patch[LAG:, LAG:BLOCK_SIZE - LAG].ravel()
        predictors = np.stack([
            patch[LAG + drow:BLOCK_SIZE + drow,
                  LAG + dcol:BLOCK_SIZE - LAG + dcol].ravel()
            for drow, dcol in taps
        ], axis=1)
        system["ata"] += predictors.T @ predictors
        system["atb"] += predictors.T @ target
        system["btb"] += float(target @ target)
        system["observations"] += int(target.size)


def fgs_sample_hash(value):
    """Bit-exact Python form of ``fgs_sample_hash`` in the hot path."""
    value = int(value) & 0xffffffff
    value ^= value >> 16
    value = (value * 0x7feb352d) & 0xffffffff
    value ^= value >> 15
    value = (value * 0x846ca68b) & 0xffffffff
    value ^= value >> 16
    return value & 0xffffffff


def fgs_stratified_sample_offset(extent, leading, trailing, stratum, random):
    """Bit-exact Python form of the analyzer's eight-stratum selector."""
    usable = extent - leading - trailing
    if usable <= 0:
        return leading
    begin = leading + usable * stratum // 8
    end = leading + usable * (stratum + 1) // 8
    span = end - begin
    return begin + (int(random) % span if span > 0 else 0)


def temporal_detrended_block(current, previous):
    """Mirror the integer values accumulated by the temporal CUDA kernel.

    CUDA fits a mean-plus-plane to the unscaled frame difference and rounds
    each detrended predictor with ``__float2int_rn``. NumPy uses the same
    nearest-even rounding; CUDA's float reduction order can still move a value
    on an exact half-integer boundary. The common factor of two
    in temporal covariance cancels from the AR solve, but this integer rounding
    does not, so a sparse-vs-dense comparison has to preserve it.
    """
    difference = (
        np.asarray(current, dtype=np.float64)
        - np.asarray(previous, dtype=np.float64)
    )
    return np.rint(detrend_blocks(difference[None, None])[0, 0]).astype(np.int64)


def accumulate_ar_system_cuda64(system, current, previous, blocks):
    """Accumulate the analyzer's 64 stratified observations per 32x32 block.

    This deliberately reproduces only the estimator population.  Rolling
    history and model hold/update policy remain separate variables, so this
    mode can say whether the response calibrated with the dense pooled oracle
    transfers to the CUDA sampling scheme before another encode is built.
    """
    current = np.asarray(current)
    previous = np.asarray(previous)
    if current.shape != previous.shape or current.ndim != 2:
        raise ValueError("temporal CUDA64 inputs must be equal-sized planes")
    height, width = current.shape
    blocks_x = (width + BLOCK_SIZE - 1) // BLOCK_SIZE
    taps = ar_acf.ar_taps(LAG)
    for row, col in blocks:
        y0 = row * BLOCK_SIZE
        x0 = col * BLOCK_SIZE
        block_h = min(BLOCK_SIZE, height - y0)
        block_w = min(BLOCK_SIZE, width - x0)
        if block_w <= LAG * 2 or block_h <= LAG:
            continue
        patch = temporal_detrended_block(
            current[y0:y0 + block_h, x0:x0 + block_w],
            previous[y0:y0 + block_h, x0:x0 + block_w])
        predictors = []
        targets = []
        block_index = row * blocks_x + col
        for tid in range(64):
            tx = tid & 7
            ty = tid >> 3
            sample_hash = fgs_sample_hash(block_index * 64 + tid)
            x = fgs_stratified_sample_offset(
                block_w, LAG, LAG, tx, sample_hash)
            y = fgs_stratified_sample_offset(
                block_h, LAG, 0, ty, sample_hash >> 8)
            predictors.append([patch[y + drow, x + dcol]
                               for drow, dcol in taps])
            targets.append(patch[y, x])
        predictors = np.asarray(predictors, dtype=np.int64)
        targets = np.asarray(targets, dtype=np.int64)
        system["ata"] += predictors.T @ predictors
        system["atb"] += predictors.T @ targets
        system["btb"] += float(targets @ targets)
        system["observations"] += int(targets.size)


def subtract_ar_system(source, base):
    return covariance_difference_system(source, base, 1.0)


def covariance_difference_system(source, base, base_weight):
    """Subtract a controlled share of base covariance from source statistics."""
    if source["observations"] != base["observations"]:
        raise ValueError("source and base AR systems use different observations")
    if not 0.0 <= base_weight <= 1.0:
        raise ValueError("base covariance weight must be in [0, 1]")
    return {
        "ata": source["ata"] - base_weight * base["ata"],
        "atb": source["atb"] - base_weight * base["atb"],
        "btb": source["btb"] - base_weight * base["btb"],
        "observations": source["observations"],
    }


def solve_covariance_system(system):
    """Solve the covariance difference while exposing any PSD repair."""
    ata = 0.5 * (system["ata"] + system["ata"].T)
    diagonal_mean = float(np.mean(np.diag(ata)))
    if system["observations"] <= 0 or diagonal_mean <= 0.0 or system["btb"] <= 0.0:
        return {
            "valid": False,
            "reason": "covariance difference has non-positive energy",
            "observations": system["observations"],
            "diagonal_mean": diagonal_mean,
        }
    eigenvalues = np.linalg.eigvalsh(ata)
    minimum = float(eigenvalues[0])
    ridge = max(diagonal_mean * 1e-6,
                -minimum + diagonal_mean * 1e-6)
    coefficients = np.linalg.solve(
        ata + ridge * np.eye(ata.shape[0]), system["atb"])
    residual = (
        system["btb"]
        - 2.0 * float(coefficients @ system["atb"])
        + float(coefficients @ ata @ coefficients)
    ) / system["observations"]
    return {
        "valid": residual > 0.0,
        "reason": None if residual > 0.0 else "AR innovation variance is non-positive",
        "observations": system["observations"],
        "diagonal_mean": diagonal_mean,
        "minimum_eigenvalue": minimum,
        "minimum_eigenvalue_over_diagonal": minimum / diagonal_mean,
        "ridge": ridge,
        "ridge_over_diagonal": ridge / diagonal_mean,
        "innovation_variance": residual,
        "coefficients": coefficients.tolist(),
    }


def axis_error(left, right):
    if left is None or right is None:
        return None
    return float(np.mean([abs(left[axis] - right[axis]) for axis in AXES]))


def quantized_oracles(coefficients, target, bit_depth, seeds, sigma):
    rows = []
    coefficients = np.asarray(coefficients, dtype=np.float64)
    for shift in range(6, 10):
        quantized = np.rint(coefficients * (1 << shift)).astype(np.int64)
        feasible = bool(np.all(quantized >= -128) and np.all(quantized <= 127))
        row = {
            "shift": shift,
            "feasible": feasible,
            "coefficients": quantized.tolist(),
        }
        if feasible:
            entry = {
                "params": {"ar_coeff_lag": LAG, "ar_coeff_shift": shift},
                "ar_coeffs": {"y": quantized.tolist()},
            }
            implied = ar_acf.implied(
                entry, "y", seeds=seeds, sigma=sigma, bit_depth=bit_depth)
            implied["lag2"] = 0.5 * (implied["h2"] + implied["v2"])
            row["implied"] = implied
            row["axis_mae_to_target"] = axis_error(implied, target)
        rows.append(row)
    feasible_rows = [row for row in rows if row["feasible"]]
    best = (min(feasible_rows,
                key=lambda row: (row["axis_mae_to_target"], -row["shift"]))
            if feasible_rows else None)
    return rows, best


def average_table_model(entries, frames, weights, fps_num, fps_den,
                        bit_depth, seeds, sigma):
    cache = {}
    totals = {axis: 0.0 for axis in AXES}
    total_weight = 0.0
    starts = []
    for frame, weight in zip(frames, weights):
        for current in (frame, frame + 1):
            entry = entry_for_frame(entries, current, fps_num, fps_den)
            key = (
                entry["params"]["ar_coeff_shift"],
                tuple(entry["ar_coeffs"]["y"]),
            )
            if key not in cache:
                cache[key] = ar_acf.implied(
                    entry, "y", seeds=seeds, sigma=sigma,
                    bit_depth=bit_depth)
            implied = cache[key]
            for axis in AXES:
                totals[axis] += implied[axis] * weight
            total_weight += weight
            starts.append(entry["start"])
    if total_weight <= 0.0:
        return None
    result = {axis: totals[axis] / total_weight for axis in AXES}
    result["lag1"] = 0.5 * (result["h1"] + result["v1"])
    result["lag2"] = 0.5 * (result["h2"] + result["v2"])
    result["unique_models"] = len(cache)
    result["entry_starts"] = sorted(set(starts))
    return result


def mix_with_base(base, synthesis, desired, source):
    """Predict played covariance with exact target synthesis variance."""
    if not desired.get("valid"):
        return None
    total_variance = base["variance"] + desired["variance"]
    result = {
        "variance": total_variance,
        "sigma": math.sqrt(total_variance),
        "covariance": {},
    }
    for axis in AXES:
        covariance = (
            base["covariance"][axis]
            + synthesis[axis] * desired["variance"]
        )
        result["covariance"][axis] = covariance
        result[axis] = covariance / total_variance
    result["lag1"] = 0.5 * (result["h1"] + result["v1"])
    result["lag2"] = 0.5 * (result["h2"] + result["v2"])
    result["sigma_over_source"] = result["sigma"] / source["sigma"]
    return result


def replace_luma_model(entry, quantized):
    """Copy an entry while replacing only its luma AR model."""
    return {
        **entry,
        "params": {
            **entry["params"],
            "ar_coeff_lag": LAG,
            "ar_coeff_shift": quantized["shift"],
        },
        "ar_coeffs": {
            **entry["ar_coeffs"],
            "y": list(quantized["coefficients"]),
        },
    }


def exact_model_replay(base_frames, frames, selected_blocks, table_entries,
                       stream_entries, fps_num, fps_den, quantized, gaussian,
                       bit_depth, seed_samples, include_current=True):
    """Replay current/oracle tables through exact normative selected pixels."""
    moments = {"oracle": empty_axis_moments()}
    if include_current:
        moments["current"] = empty_axis_moments()
    for frame, blocks in zip(frames, selected_blocks):
        for current in (frame, frame + 1):
            table_entry = entry_for_frame(
                table_entries, current, fps_num, fps_den)
            # filmgrn1 cannot store the range-clipping flag; inherit the exact
            # bitstream value before replaying either model.
            current_entry = {
                **table_entry,
                "limit_output_range": stream_entries[current]["limit_output_range"],
            }
            oracle_entry = replace_luma_model(current_entry, quantized)
            for sample in range(seed_samples):
                seed = oracle_seed(current, sample)
                seeded_current = {**current_entry, "random_seed": seed}
                seeded_oracle = {**oracle_entry, "random_seed": seed}
                oracle_patches = av1_grain.synthesize_selected_luma(
                    base_frames[current], blocks, seeded_oracle,
                    gaussian, bit_depth)
                accumulate_patch_moments(
                    moments["oracle"], oracle_patches)
                if include_current:
                    current_patches = av1_grain.synthesize_selected_luma(
                        base_frames[current], blocks, seeded_current,
                        gaussian, bit_depth)
                    accumulate_patch_moments(
                        moments["current"], current_patches)
    return {name: finish_axis_moments(value)
            for name, value in moments.items()}


def run(args):
    width, height = probe_size(args.source)
    if probe_size(args.encoded) != (width, height):
        raise ValueError("source and encoded dimensions differ")
    frames = sorted({int(value) for value in args.frames.split(",")})
    if not frames or min(frames) < 0:
        raise ValueError("frames must contain non-negative indices")
    indices = sorted(set(frames + [frame + 1 for frame in frames]))
    source_frames = decode_selected(
        args.source, width, height, indices, bits=args.bits)
    base_frames = decode_selected(
        args.encoded, width, height, indices, bits=args.bits, filmgrain=0)
    played_frames = decode_selected(
        args.encoded, width, height, indices, bits=args.bits, filmgrain=1)

    moments = {
        name: empty_axis_moments()
        for name in ("source", "base", "decoded_synthesis", "decoded_total")
    }
    systems = {name: empty_ar_system() for name in ("source", "base")}
    selected_counts = []
    selected_blocks = []
    for frame in frames:
        source = source_frames[frame].astype(np.float64)
        next_source = source_frames[frame + 1].astype(np.float64)
        candidates, _score, _sigma = production_flat_blocks(source, args.bits)
        blocks = static_flat_blocks(
            source, next_source, candidates,
            lo=args.static_lo, hi=args.static_hi)
        if len(blocks) < args.minimum_blocks:
            raise ValueError(
                f"frame {frame}: only {len(blocks)} static flat blocks")
        selected_counts.append(len(blocks))
        selected_blocks.append(blocks)
        current_base = base_frames[frame].astype(np.float64)
        next_base = base_frames[frame + 1].astype(np.float64)
        source_temporal = (source - next_source) / math.sqrt(2.0)
        base_temporal = (current_base - next_base) / math.sqrt(2.0)
        played_temporal = (
            played_frames[frame].astype(np.float64)
            - played_frames[frame + 1].astype(np.float64)
        ) / math.sqrt(2.0)
        accumulate_axis_moments(moments["source"], source_temporal, blocks)
        accumulate_axis_moments(moments["base"], base_temporal, blocks)
        accumulate_axis_moments(moments["decoded_total"], played_temporal, blocks)
        if args.ar_sampling == "cuda64":
            accumulate_ar_system_cuda64(
                systems["source"], source, next_source, blocks)
            accumulate_ar_system_cuda64(
                systems["base"], current_base, next_base, blocks)
        else:
            accumulate_ar_system(systems["source"], source_temporal, blocks)
            accumulate_ar_system(systems["base"], base_temporal, blocks)
        for index in (frame, frame + 1):
            synthesis = (
                played_frames[index].astype(np.float64)
                - base_frames[index].astype(np.float64)
            )
            accumulate_axis_moments(
                moments["decoded_synthesis"], synthesis, blocks)

    axes = {name: finish_axis_moments(value)
            for name, value in moments.items()}
    desired = subtract_axis_moments(axes["source"], axes["base"])
    target_system = subtract_ar_system(systems["source"], systems["base"])
    solution = solve_covariance_system(target_system)
    candidates = []
    best = None
    if solution.get("valid") and desired.get("valid"):
        candidates, best = quantized_oracles(
            solution["coefficients"], desired, args.bits,
            args.ar_seeds, args.ar_sigma)

    table_entries = filmgrn.load(args.table)
    fps_num, fps_den = probe_rate(args.source)
    table_model = average_table_model(
        table_entries, frames, selected_counts, fps_num, fps_den,
        args.bits, args.ar_seeds, args.ar_sigma)
    stream_entries = probe_grain_entries(args.encoded, max(indices) + 1)
    table_matches = []
    for frame in indices:
        table_entry = entry_for_frame(
            table_entries, frame, fps_num, fps_den)
        table_matches.append(table_matches_stream(table_entry, stream_entries[frame]))

    oracle_total = (mix_with_base(
        axes["base"], best["implied"], desired, axes["source"])
        if best is not None else None)
    exact_replay = None
    exact_oracle_total = None
    grain_source_sha256 = None
    if args.exact_seeds > 0 and best is not None:
        gaussian = av1_grain.load_gaussian_sequence(args.aom_grain_source)
        import hashlib
        with open(args.aom_grain_source, "rb") as handle:
            grain_source_sha256 = hashlib.sha256(handle.read()).hexdigest()
        exact_replay = exact_model_replay(
            base_frames, frames, selected_blocks, table_entries,
            stream_entries, fps_num, fps_den, best, gaussian, args.bits,
            args.exact_seeds)
        exact_oracle_total = mix_with_base(
            axes["base"], exact_replay["oracle"], desired, axes["source"])
    response_grid = []
    if args.response_alphas:
        if args.response_seeds <= 0:
            raise ValueError("response alpha grid requires positive response seeds")
        if not os.path.isfile(args.aom_grain_source):
            raise ValueError(f"missing AV1 grain source: {args.aom_grain_source}")
        if grain_source_sha256 is None:
            gaussian = av1_grain.load_gaussian_sequence(args.aom_grain_source)
            import hashlib
            with open(args.aom_grain_source, "rb") as handle:
                grain_source_sha256 = hashlib.sha256(handle.read()).hexdigest()
        for alpha in args.response_alphas:
            alpha_system = covariance_difference_system(
                systems["source"], systems["base"], alpha)
            alpha_solution = solve_covariance_system(alpha_system)
            alpha_candidates = []
            alpha_best = None
            alpha_exact = None
            alpha_total = None
            if alpha_solution.get("valid") and desired.get("valid"):
                alpha_candidates, alpha_best = quantized_oracles(
                    alpha_solution["coefficients"], desired, args.bits,
                    args.response_ar_seeds, args.ar_sigma)
            if alpha_best is not None:
                alpha_exact = exact_model_replay(
                    base_frames, frames, selected_blocks, table_entries,
                    stream_entries, fps_num, fps_den, alpha_best, gaussian,
                    args.bits, args.response_seeds,
                    include_current=False)["oracle"]
                alpha_total = mix_with_base(
                    axes["base"], alpha_exact, desired, axes["source"])
            response_grid.append({
                "base_covariance_weight": alpha,
                "covariance_system": alpha_solution,
                "quantized_candidates": alpha_candidates,
                "best_quantized_model": alpha_best,
                "exact_synthesis": alpha_exact,
                "predicted_total": alpha_total,
                "synthesis_axis_mae_to_target": axis_error(
                    alpha_exact, desired),
                "total_axis_mae_to_source": axis_error(
                    alpha_total, axes["source"]),
            })
    errors = {
        "table_to_decoded_synthesis_axis_mae": axis_error(
            table_model, axes["decoded_synthesis"]),
        "decoded_synthesis_to_desired_axis_mae": axis_error(
            axes["decoded_synthesis"], desired),
        "decoded_total_to_source_axis_mae": axis_error(
            axes["decoded_total"], axes["source"]),
        "oracle_synthesis_to_desired_axis_mae": (
            best["axis_mae_to_target"] if best is not None else None),
        "oracle_total_to_source_axis_mae": axis_error(
            oracle_total, axes["source"]),
        "exact_current_to_decoded_synthesis_axis_mae": (
            axis_error(exact_replay["current"], axes["decoded_synthesis"])
            if exact_replay is not None else None),
        "exact_oracle_synthesis_to_desired_axis_mae": (
            axis_error(exact_replay["oracle"], desired)
            if exact_replay is not None else None),
        "exact_oracle_total_to_source_axis_mae": axis_error(
            exact_oracle_total, axes["source"]),
    }
    return {
        "purpose": "offline texture-leak representability oracle",
        "warning": "diagnostic only; not a routing or production verdict",
        "changes_output": False,
        "routing_verdict": None,
        "source": os.path.abspath(args.source),
        "encoded": os.path.abspath(args.encoded),
        "table": os.path.abspath(args.table),
        "dimensions": [width, height],
        "bits": args.bits,
        "settings": {
            "frames": frames,
            "flat_selector": "production",
            "static_ratio": [args.static_lo, args.static_hi],
            "minimum_blocks": args.minimum_blocks,
            "ar_seeds": args.ar_seeds,
            "ar_sigma": args.ar_sigma,
            "exact_seeds": args.exact_seeds,
            "response_alphas": args.response_alphas,
            "response_seeds": args.response_seeds,
            "response_ar_seeds": args.response_ar_seeds,
            "ar_sampling": args.ar_sampling,
        },
        "static_blocks": selected_counts,
        "source_truth": axes["source"],
        "base_leak": axes["base"],
        "desired_synthesis": desired,
        "decoded_synthesis": axes["decoded_synthesis"],
        "decoded_total": axes["decoded_total"],
        "current_table_implied": table_model,
        "table_models_match_bitstream": all(table_matches),
        "covariance_system": solution,
        "quantized_oracles": candidates,
        "best_quantized_oracle": best,
        "predicted_oracle_total": oracle_total,
        "exact_replay": exact_replay,
        "predicted_exact_oracle_total": exact_oracle_total,
        "aom_grain_source": (
            os.path.abspath(args.aom_grain_source)
            if args.exact_seeds > 0 else None),
        "aom_grain_source_sha256": grain_source_sha256,
        "response_grid": response_grid,
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--encoded", required=True)
    parser.add_argument("--table", required=True)
    parser.add_argument("--frames", default="10,58,106,154,202,250")
    parser.add_argument("--bits", type=int, default=10, choices=(8, 10, 12))
    parser.add_argument("--static-lo", type=float, default=0.8)
    parser.add_argument("--static-hi", type=float, default=1.3)
    parser.add_argument("--minimum-blocks", type=int, default=8)
    parser.add_argument("--ar-seeds", type=int, default=64)
    parser.add_argument("--ar-sigma", type=float, default=4.0)
    parser.add_argument(
        "--ar-sampling", choices=("dense", "cuda64"), default="dense",
        help="AR normal-equation population; cuda64 mirrors the GPU hot path")
    parser.add_argument(
        "--exact-seeds", type=int, default=0,
        help="exact normative current/oracle replays per selected frame")
    parser.add_argument(
        "--response-alphas", default="",
        help="comma-separated base-covariance weights for exact response grid")
    parser.add_argument(
        "--response-seeds", type=int, default=4,
        help="exact normative seeds per response-grid weight")
    parser.add_argument(
        "--response-ar-seeds", type=int, default=16,
        help="raw AR seeds used to select a legal shift in the response grid")
    parser.add_argument(
        "--aom-grain-source",
        default=os.environ.get(
            "AOM_GRAIN_SOURCE", "/tmp/aomref/src/av1/decoder/grain_synthesis.c"),
        help="pinned libaom grain_synthesis.c containing gaussian_sequence")
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()
    args.response_alphas = (
        [float(value) for value in args.response_alphas.split(",") if value]
        if args.response_alphas else [])
    for path in (args.source, args.encoded, args.table):
        if not os.path.isfile(path):
            parser.error(f"missing input: {path}")
    if args.exact_seeds < 0:
        parser.error("exact seeds must be non-negative")
    if (args.response_seeds < 0 or args.response_ar_seeds < 1
            or (args.response_alphas and args.response_seeds < 1)
            or any(value < 0.0 or value > 1.0
                   for value in args.response_alphas)):
        parser.error("response settings require alphas in [0,1] and positive seeds")
    if args.exact_seeds > 0 and not os.path.isfile(args.aom_grain_source):
        parser.error(f"missing AV1 grain source: {args.aom_grain_source}")
    report = run(args)
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.json_out:
        temporary = args.json_out + ".partial"
        with open(temporary, "w", encoding="utf-8") as handle:
            handle.write(encoded)
        os.replace(temporary, args.json_out)
    else:
        print(encoded, end="")
    desired = report["desired_synthesis"]
    best = report["best_quantized_oracle"]
    if desired.get("valid") and best is not None:
        print(
            "truth={:.4f}/{:.4f} base={:.4f}/{:.4f} "
            "target={:.4f}/{:.4f} oracle={:.4f}/{:.4f}".format(
                report["source_truth"]["lag1"], report["source_truth"]["lag2"],
                report["base_leak"]["lag1"], report["base_leak"]["lag2"],
                desired["lag1"], desired["lag2"],
                best["implied"]["lag1"], best["implied"]["lag2"]),
            file=sys.stderr)
    else:
        print(
            "no feasible covariance-subtracted AV1 model: "
            + str(desired.get("reason") or report["covariance_system"].get("reason")),
            file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
