#!/usr/bin/env python3
"""Fit alternate luma curves from continuous temporal observations.

This is an offline isolation tool, not an encoder option.  The current NVEnc
source-fit path accumulates variance in one hard luma bin per block, averages
it, takes the square root and emits the result on an endpoint-spaced grid.
libaom instead contributes each block's standard deviation fractionally to
the two adjacent endpoint controls and solves a regularised least-squares
system.

Two tables are produced from held-out frame pairs:

``fractional-global``
    Uses the current entry-wide leak closure, but changes the population and
    curve estimator to continuous standard-deviation observations.  Its
    source-mean-weighted curve energy is normalised to the input table so the
    experiment tests shape rather than a new global gain.

``fractional-local``
    Uses the same fitted unit conversion, but applies the existing QVBR
    deadzone to each block's temporal base/source ratio before fitting.  This
    tests whether luma-local leakage, rather than curve population alone,
    explains opposite dark/bright errors.

Only luma scaling points change.  AR coefficients, chroma curves, parameter
shifts, random seeds and entry timing remain unchanged.  The resulting tables
must still be replayed on one saved clean base and judged with exact
post-encode luma-band closure.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
from pathlib import Path
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import filmgrn  # noqa: E402
from delivery_normalize import target_from_pre_leak  # noqa: E402
from emission_audit import TABLE_TIMEBASE, probe_rate  # noqa: E402
from source_fit import (  # noqa: E402
    blockwise, production_flat_blocks, static_flat_blocks,
)
from strength_selection_report import (  # noqa: E402
    decode_selected, probe_size, strength_variance_fields,
)


STRENGTH_BINS = 20
MAX_LUMA_POINTS = 14


def parse_frames(value: str) -> list[int]:
    if not value:
        return []
    frames = sorted(set(int(item) for item in value.split(",")))
    if any(frame < 0 for frame in frames):
        raise ValueError("frame indices must be non-negative")
    return frames


def entry_index_for_frame(
    entries: list[dict], frame: int, fps_num: int, fps_den: int,
) -> int:
    timestamp = int(round(frame * TABLE_TIMEBASE * fps_den / fps_num))
    for index, entry in enumerate(entries):
        if entry["start"] <= timestamp < entry["end"]:
            return index
    raise ValueError(f"no grain-table entry covers frame {frame} ({timestamp})")


def evenly_spaced(values: list[int], count: int) -> list[int]:
    """Pick up to ``count`` deterministic interior values without repeats."""
    if count <= 0 or not values:
        return []
    if len(values) <= count:
        return list(values)
    positions = np.linspace(0, len(values) - 1, count + 2)[1:-1]
    chosen = []
    for position in positions:
        value = values[int(round(float(position)))]
        if value not in chosen:
            chosen.append(value)
    if len(chosen) < count:
        for value in values:
            if value not in chosen:
                chosen.append(value)
            if len(chosen) == count:
                break
    return sorted(chosen)


def choose_fit_frames(
    entries: list[dict], fps_num: int, fps_den: int, samples_per_entry: int,
    excluded: set[int],
) -> tuple[dict[int, list[int]], list[int]]:
    """Choose frame pairs wholly inside each updating table entry."""
    final_frame = int(math.ceil(
        max(entry["end"] for entry in entries)
        * fps_num / (TABLE_TIMEBASE * fps_den)))
    chosen: dict[int, list[int]] = {}
    forced_overlap = []
    for index, entry in enumerate(entries):
        if not (entry["apply_grain"] and entry["update_parameters"]):
            continue
        valid = [
            frame for frame in range(max(0, final_frame - 1))
            if entry_index_for_frame(entries, frame, fps_num, fps_den) == index
            and entry_index_for_frame(entries, frame + 1, fps_num, fps_den) == index
        ]
        clean = [
            frame for frame in valid
            if frame not in excluded and frame + 1 not in excluded
        ]
        population = clean
        if not population:
            population = valid
            if population:
                forced_overlap.append(index)
        selected = evenly_spaced(population, samples_per_entry)
        if selected:
            chosen[index] = selected
    return chosen, forced_overlap


def curve_values(points: list[list[int]], x: np.ndarray) -> np.ndarray:
    if not points:
        return np.zeros_like(np.asarray(x, dtype=np.float64))
    ordered = sorted(points)
    xp = np.asarray([point[0] for point in ordered], dtype=np.float64)
    yp = np.asarray([point[1] for point in ordered], dtype=np.float64)
    return np.interp(np.asarray(x, dtype=np.float64), xp, yp,
                     left=yp[0], right=yp[-1])


def fractional_strength_solve(
    means: np.ndarray, strengths: np.ndarray, maximum: int,
    bins: int = STRENGTH_BINS,
) -> np.ndarray:
    """Match libaom's fractional observation and smooth solve."""
    means = np.asarray(means, dtype=np.float64)
    strengths = np.asarray(strengths, dtype=np.float64)
    if means.shape != strengths.shape or means.ndim != 1:
        raise ValueError("means and strengths must be equal-length vectors")
    if not len(means):
        raise ValueError("at least one strength observation is required")
    if bins < 2 or maximum <= 0:
        raise ValueError("invalid strength grid")
    if not np.all(np.isfinite(means)) or not np.all(np.isfinite(strengths)):
        raise ValueError("strength observations must be finite")

    location = (bins - 1) * np.clip(means, 0.0, maximum) / maximum
    left = np.floor(location).astype(np.int64)
    right = np.minimum(bins - 1, left + 1)
    mix = location - left
    weight_left = 1.0 - mix
    weight_right = mix
    matrix = np.zeros((bins, bins), dtype=np.float64)
    rhs = np.zeros(bins, dtype=np.float64)
    np.add.at(matrix, (left, left), weight_left * weight_left)
    np.add.at(matrix, (right, left), weight_right * weight_left)
    np.add.at(matrix, (right, right), weight_right * weight_right)
    np.add.at(matrix, (left, right), weight_left * weight_right)
    np.add.at(rhs, left, weight_left * strengths)
    np.add.at(rhs, right, weight_right * strengths)

    alpha = 2.0 * len(means) / bins
    for index in range(bins):
        lower = max(0, index - 1)
        upper = min(bins - 1, index + 1)
        matrix[index, lower] -= alpha
        matrix[index, index] += 2.0 * alpha
        matrix[index, upper] -= alpha
    mean_strength = float(np.mean(strengths))
    regularizer = 1.0 / 8192.0
    matrix[np.diag_indices(bins)] += regularizer
    rhs += mean_strength * regularizer
    solved = np.linalg.solve(matrix, rhs)
    if not np.all(np.isfinite(solved)):
        raise ValueError("strength solve returned a non-finite curve")
    return solved


def evaluate_controls(
    controls: np.ndarray, means: np.ndarray, maximum: int,
) -> np.ndarray:
    location = ((len(controls) - 1)
                * np.clip(np.asarray(means, dtype=np.float64), 0.0, maximum)
                / maximum)
    left = np.floor(location).astype(np.int64)
    right = np.minimum(len(controls) - 1, left + 1)
    mix = location - left
    return controls[left] * (1.0 - mix) + controls[right] * mix


def reduce_points(points: list[tuple[float, float]], maximum: int) -> list[tuple[float, float]]:
    """Use NVEnc's existing area-weighted greedy point reduction."""
    reduced = list(points)
    while len(reduced) > maximum:
        remove = 1
        least_error = math.inf
        for index in range(1, len(reduced) - 1):
            left, current, right = reduced[index - 1:index + 2]
            mix = (current[0] - left[0]) / max(1e-9, right[0] - left[0])
            estimate = left[1] * (1.0 - mix) + right[1] * mix
            error = abs(current[1] - estimate) * (right[0] - left[0])
            if error < least_error:
                least_error = error
                remove = index
        del reduced[remove]
    return reduced


def quantized_points(
    controls: np.ndarray, bit_depth: int, maximum: int = MAX_LUMA_POINTS,
) -> list[list[int]]:
    native_maximum = (1 << bit_depth) - 1
    depth_scale = 1 << (bit_depth - 8)
    points = [
        (index * native_maximum / (len(controls) - 1) / depth_scale,
         float(value))
        for index, value in enumerate(controls)
    ]
    points = reduce_points(points, maximum)
    if any(value > 255.499 for _x, value in points):
        raise ValueError("alternate luma curve needs a scaling-shift change")
    result = [
        [min(255, max(0, int(round(x)))),
         min(255, max(0, int(round(value))))]
        for x, value in points
    ]
    if any(left[0] >= right[0] for left, right in zip(result, result[1:])):
        raise ValueError("quantized luma coordinates are not strictly increasing")
    return result


def target_strengths(
    source_variance: np.ndarray, base_variance: np.ndarray, qvbr: float,
) -> tuple[np.ndarray, np.ndarray, dict]:
    source_variance = np.asarray(source_variance, dtype=np.float64)
    base_variance = np.asarray(base_variance, dtype=np.float64)
    source_sum = float(np.sum(source_variance))
    base_sum = float(np.sum(base_variance))
    if source_sum <= 0.0:
        raise ValueError("temporal source variance is zero")
    pre_leak = math.sqrt(min(1.0, max(0.0, base_sum / source_sum)))
    theta, post_leak, global_fraction = target_from_pre_leak(pre_leak, qvbr)
    source_sigma = np.sqrt(np.maximum(0.0, source_variance))
    global_target = source_sigma * global_fraction

    block_pre_leak = np.sqrt(np.clip(
        base_variance / np.maximum(source_variance, 1e-12), 0.0, 1.0))
    block_post_leak = np.maximum(0.0, block_pre_leak - theta)
    local_target = source_sigma * np.sqrt(
        np.maximum(0.0, 1.0 - block_post_leak * block_post_leak))
    return global_target, local_target, {
        "pre_encode_leak": pre_leak,
        "post_encode_leak_prediction": post_leak,
        "global_synthesis_fraction": global_fraction,
        "mean_local_synthesis_fraction": float(np.mean(
            np.divide(local_target, source_sigma,
                      out=np.zeros_like(local_target), where=source_sigma > 0))),
    }


def fit_entry(
    entry: dict, means: np.ndarray, source_variance: np.ndarray,
    base_variance: np.ndarray, bit_depth: int, qvbr: float,
) -> tuple[dict[str, list[list[int]]], dict]:
    maximum = (1 << bit_depth) - 1
    global_target, local_target, target_report = target_strengths(
        source_variance, base_variance, qvbr)
    global_controls = fractional_strength_solve(
        means, global_target, maximum)
    local_controls = fractional_strength_solve(
        means, local_target, maximum)

    depth_scale = 1 << (bit_depth - 8)
    old_at_means = curve_values(
        entry["scaling_points"]["y"], means / depth_scale)
    solved_at_means = evaluate_controls(global_controls, means, maximum)
    solved_rms = float(np.sqrt(np.mean(solved_at_means * solved_at_means)))
    old_rms = float(np.sqrt(np.mean(old_at_means * old_at_means)))
    if solved_rms <= 0.0 or old_rms <= 0.0:
        raise ValueError("cannot calibrate an empty luma curve")
    unit_scale = old_rms / solved_rms
    global_scaled = np.maximum(0.0, global_controls * unit_scale)
    local_scaled = np.maximum(0.0, local_controls * unit_scale)
    curves = {
        "fractional_global": quantized_points(global_scaled, bit_depth),
        "fractional_local": quantized_points(local_scaled, bit_depth),
    }
    target_report.update({
        "observations": int(len(means)),
        "old_curve_rms_at_source_means": old_rms,
        "fractional_unit_scale": unit_scale,
        "global_curve_rms_at_source_means_before_quantization": float(
            np.sqrt(np.mean(evaluate_controls(
                global_scaled, means, maximum) ** 2))),
        "local_curve_rms_at_source_means_before_quantization": float(
            np.sqrt(np.mean(evaluate_controls(
                local_scaled, means, maximum) ** 2))),
        "global_control_minmax": [
            float(np.min(global_scaled)), float(np.max(global_scaled))],
        "local_control_minmax": [
            float(np.min(local_scaled)), float(np.max(local_scaled))],
    })
    return curves, target_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--clean-base", required=True)
    parser.add_argument("--table", required=True)
    parser.add_argument("--output-global", required=True)
    parser.add_argument("--output-local", required=True)
    parser.add_argument("--bits", type=int, default=10, choices=(8, 10, 12, 16))
    parser.add_argument("--qvbr", type=float, default=29.0)
    parser.add_argument("--samples-per-entry", type=int, default=1)
    parser.add_argument(
        "--holdout-frames", default="10,58,106,154,202,250,275",
        help="frame pairs excluded from fitting and reserved for replay scoring")
    parser.add_argument("--static-lo", type=float, default=0.8)
    parser.add_argument("--static-hi", type=float, default=1.3)
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()
    if args.samples_per_entry <= 0:
        parser.error("--samples-per-entry must be positive")
    try:
        holdout = parse_frames(args.holdout_frames)
    except ValueError as error:
        parser.error(str(error))

    source_path = str(Path(args.source).resolve())
    clean_path = str(Path(args.clean_base).resolve())
    table_path = str(Path(args.table).resolve())
    width, height = probe_size(source_path)
    if probe_size(clean_path) != (width, height):
        raise SystemExit("source and clean-base dimensions differ")
    fps_num, fps_den = probe_rate(source_path)
    entries = filmgrn.load(table_path)
    excluded = set(holdout)
    excluded.update(frame + 1 for frame in holdout)
    fit_by_entry, forced_overlap = choose_fit_frames(
        entries, fps_num, fps_den, args.samples_per_entry, excluded)
    fit_frames = sorted({
        frame for frames in fit_by_entry.values() for frame in frames
    })
    if not fit_frames:
        raise SystemExit("no fitting frame pairs were available")
    indices = sorted(set(fit_frames + [frame + 1 for frame in fit_frames]))
    source = decode_selected(source_path, width, height, indices, args.bits)
    clean = decode_selected(clean_path, width, height, indices, args.bits)

    observations = {
        index: {"means": [], "source_variance": [], "base_variance": [],
                "selected_blocks": 0}
        for index in fit_by_entry
    }
    for entry_index, frames in fit_by_entry.items():
        for frame in frames:
            current = source[frame].astype(np.float64)
            following = source[frame + 1].astype(np.float64)
            current_clean = clean[frame].astype(np.float64)
            following_clean = clean[frame + 1].astype(np.float64)
            production, _score, _sigma = production_flat_blocks(
                current, args.bits)
            blocks = static_flat_blocks(
                current, following, production,
                lo=args.static_lo, hi=args.static_hi)
            if not blocks:
                continue
            rows = np.asarray([row for row, _col in blocks])
            cols = np.asarray([col for _row, col in blocks])
            fields = strength_variance_fields(
                current, following, current_clean, following_clean)
            source_variance = fields["truth"][rows, cols]
            base_variance = fields["leak"][rows, cols]
            for frame_image in (current, following):
                means = blockwise(frame_image)[rows, cols].mean(axis=(-2, -1))
                observations[entry_index]["means"].extend(means.tolist())
                observations[entry_index]["source_variance"].extend(
                    source_variance.tolist())
                observations[entry_index]["base_variance"].extend(
                    base_variance.tolist())
            observations[entry_index]["selected_blocks"] += len(blocks)

    variants = {
        "fractional_global": copy.deepcopy(entries),
        "fractional_local": copy.deepcopy(entries),
    }
    entry_reports = []
    for entry_index, measured in observations.items():
        means = np.asarray(measured["means"], dtype=np.float64)
        if not len(means):
            entry_reports.append({
                "entry": entry_index,
                "fit_frames": fit_by_entry[entry_index],
                "status": "unchanged-no-static-blocks",
            })
            continue
        curves, fit_report = fit_entry(
            entries[entry_index], means,
            np.asarray(measured["source_variance"], dtype=np.float64),
            np.asarray(measured["base_variance"], dtype=np.float64),
            args.bits, args.qvbr)
        for label, curve in curves.items():
            variants[label][entry_index]["scaling_points"]["y"] = curve
        entry_reports.append({
            "entry": entry_index,
            "start": entries[entry_index]["start"],
            "end": entries[entry_index]["end"],
            "fit_frames": fit_by_entry[entry_index],
            "selected_blocks": measured["selected_blocks"],
            "status": "updated",
            **fit_report,
        })

    outputs = {
        "fractional_global": str(Path(args.output_global).resolve()),
        "fractional_local": str(Path(args.output_local).resolve()),
    }
    for label, destination in outputs.items():
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        filmgrn.write(path, variants[label])
        filmgrn.load(path)

    report = {
        "scope": "offline observation-level strength fitter; no encoder change",
        "source": source_path,
        "clean_base": clean_path,
        "input_table": table_path,
        "outputs": outputs,
        "dimensions": [width, height],
        "bits": args.bits,
        "fps": [fps_num, fps_den],
        "qvbr": args.qvbr,
        "samples_per_entry": args.samples_per_entry,
        "holdout_frames": holdout,
        "fit_frames": fit_frames,
        "forced_holdout_overlap_entries": forced_overlap,
        "entries": entry_reports,
    }
    rendered = json.dumps(report, indent=2)
    print(rendered)
    if args.json_out:
        destination = Path(args.json_out).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
