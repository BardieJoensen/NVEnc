#!/usr/bin/env python3
"""Offline aggregate luma expected-delivery normalisation for a filmgrn1 table.

This is an experiment, not an encoder option.  It closes the analyser's
rate-dependent temporal target against the expected AV1 synthesis amplitude
measured by ``emission_audit.py --seed-samples``.  The multiplier is therefore
calculated from two analyser-available quantities; it is not fitted to the
post-encode result of an individual title.

The luma curve alone is changed.  If it would overflow, the shared
``scaling_shift`` is reduced and chroma integer curves are requantised so their
physical amplitude remains unchanged.

This deliberately applies one factor to the whole curve.  It is useful for
testing whether delivery is correctable, but it is not a production proposal:
the output must pass fixed luma-band closure, not only a whole-title aggregate.
"""
import argparse
import copy
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import filmgrn  # noqa: E402


THETA_INTERCEPT = 0.01579030304339795
THETA_QVBR_SLOPE = 0.004870139420489915
MASK = "production_static"


def target_from_pre_leak(pre_leak, qvbr):
    theta = THETA_INTERCEPT + THETA_QVBR_SLOPE * qvbr
    post_leak = max(0.0, pre_leak - theta)
    return theta, post_leak, math.sqrt(max(0.0, 1.0 - post_leak * post_leak))


def interpolate_factor(points, x):
    if not points:
        raise ValueError("no luma factors")
    if x <= points[0][0]:
        return points[0][1]
    for left, right in zip(points, points[1:]):
        if x <= right[0]:
            mix = (x - left[0]) / max(right[0] - left[0], 1e-9)
            return left[1] * (1.0 - mix) + right[1] * mix
    return points[-1][1]


def scale_entry_luma(entry, factor):
    """Scale effective luma amplitude while preserving effective chroma."""
    candidate = copy.deepcopy(entry)
    if not (entry["apply_grain"] and entry["update_parameters"]):
        return candidate, 0
    factor_at = factor if callable(factor) else lambda _x: factor
    desired = [
        [x, y * factor_at(x)] for x, y in entry["scaling_points"]["y"]
    ]
    shift_down = 0
    while desired and max(y for _x, y in desired) > 255.0:
        if candidate["params"]["scaling_shift"] <= 8:
            raise ValueError("luma curve cannot be represented without overflow")
        candidate["params"]["scaling_shift"] -= 1
        desired = [[x, y * 0.5] for x, y in desired]
        shift_down += 1
    candidate["scaling_points"]["y"] = [
        [x, min(255, max(0, int(round(y))))] for x, y in desired
    ]
    if shift_down:
        divisor = 1 << shift_down
        for plane in ("cb", "cr"):
            candidate["scaling_points"][plane] = [
                [x, min(255, max(0, int(round(y / divisor))))]
                for x, y in entry["scaling_points"][plane]
            ]
    return candidate, shift_down


def sparse_expected_by_range(response, emission, blocks_per_bin, repeat):
    """Return synthesis/truth ratios from one realizable sparse selection."""
    models = response.get("sparse_clean_pixels", {}).get("models", [])
    matches = [
        model for model in models
        if model["blocks_per_frame_bin"] == blocks_per_bin
    ]
    if len(matches) != 1:
        raise ValueError(
            f"sparse response has no unique {blocks_per_bin}-block model")
    model = matches[0]
    if repeat < 0 or repeat >= model["selection_repeats"]:
        raise ValueError(
            f"sparse repeat {repeat} outside 0..{model['selection_repeats'] - 1}")
    reference = emission.get("luma_bins", [])
    bands = model.get("bands", [])
    if len(bands) != len(reference):
        raise ValueError("sparse response and emission luma-band counts differ")
    expected = {}
    for response_band, reference_band in zip(bands, reference):
        if response_band["range"] != reference_band["range"]:
            raise ValueError("sparse response and emission luma ranges differ")
        values = response_band.get("predicted_sigma", {}).get("values", [])
        if repeat >= len(values):
            raise ValueError("sparse response does not retain per-repeat values")
        truth = reference_band["truth_sigma"]
        if truth <= 0.0:
            raise ValueError("emission luma band has non-positive truth sigma")
        expected[tuple(reference_band["range"])] = values[repeat] / truth
    return expected, model


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="candidate filmgrn1 table")
    parser.add_argument("--closure", required=True,
                        help="pre-encode closure report for the candidate")
    parser.add_argument("--emission", required=True,
                        help="expected-seed emission audit for the candidate")
    parser.add_argument("--qvbr", type=float, required=True)
    parser.add_argument(
        "--per-luma", action="store_true",
        help="derive an interpolated factor from every populated fixed luma band")
    parser.add_argument(
        "--sparse-response", default="",
        help="delivery_response.py JSON used instead of the exact multi-seed "
             "expectation to derive per-luma factors")
    parser.add_argument(
        "--sparse-blocks-per-bin", type=int, default=0,
        help="sample limit to select from --sparse-response")
    parser.add_argument(
        "--sparse-repeat", type=int, default=0,
        help="deterministic selection index from --sparse-response")
    parser.add_argument("--output", required=True)
    parser.add_argument("--json-out", default="")
    parser.add_argument("--min-factor", type=float, default=0.75)
    parser.add_argument("--max-factor", type=float, default=1.25)
    args = parser.parse_args()

    with open(args.closure, encoding="utf-8") as handle:
        closure = json.load(handle)
    with open(args.emission, encoding="utf-8") as handle:
        emission = json.load(handle)
    sparse_expected = None
    sparse_model = None
    if args.sparse_response:
        if not args.per_luma:
            parser.error("--sparse-response requires --per-luma")
        if args.sparse_blocks_per_bin <= 0:
            parser.error(
                "--sparse-response requires positive --sparse-blocks-per-bin")
        with open(args.sparse_response, encoding="utf-8") as handle:
            response = json.load(handle)
        if os.path.realpath(response.get("emission", "")) != os.path.realpath(
                args.emission):
            parser.error("sparse response was not derived from --emission")
        try:
            sparse_expected, sparse_model = sparse_expected_by_range(
                response, emission, args.sparse_blocks_per_bin,
                args.sparse_repeat)
        except ValueError as error:
            parser.error(str(error))
    pre_leak = closure["aggregate"][MASK]["temporal_leak_ratio"]
    expected = emission["aggregate"]["seed_mean_ratio"]
    samples = emission["aggregate"]["seed_samples"]
    if samples <= 0 or expected is None or expected <= 0.0:
        raise SystemExit("emission report has no positive expected-seed amplitude")
    theta, predicted_post_leak, target = target_from_pre_leak(pre_leak, args.qvbr)
    factor = target / expected
    band_report = []
    factor_points = []
    if args.per_luma:
        for band in emission.get("luma_bins", []):
            band_expected = (
                sparse_expected[tuple(band["range"])]
                if sparse_expected is not None else band["seed_mean_ratio"])
            if not band_expected or band["blocks"] <= 0:
                continue
            band_theta, band_post, band_target = target_from_pre_leak(
                band["pre_encode_leak"], args.qvbr)
            band_factor = band_target / band_expected
            center = 128.0 * (band["range"][0] + band["range"][1])
            factor_points.append((center, band_factor))
            band_report.append({
                "range": band["range"],
                "blocks": band["blocks"],
                "center": center,
                "pre_encode_leak": band["pre_encode_leak"],
                "theta": band_theta,
                "predicted_post_encode_leak": band_post,
                "predicted_synthesis_target": band_target,
                "expected_synthesis_before": band_expected,
                "requested_luma_factor": band_factor,
            })
        if not factor_points:
            raise SystemExit("emission report has no populated fixed luma bands")
        factors = [point[1] for point in factor_points]
    else:
        factors = [factor]
    if min(factors) < args.min_factor or max(factors) > args.max_factor:
        raise SystemExit(
            f"required factor range {min(factors):.4f}..{max(factors):.4f} "
            f"outside conservative [{args.min_factor:.3f}, "
            f"{args.max_factor:.3f}] gate")
    factor_at = (
        (lambda x: interpolate_factor(factor_points, x))
        if args.per_luma else factor)

    entries = filmgrn.load(args.input)
    adjusted = []
    shifted = 0
    updated = 0
    for entry in entries:
        candidate, shift_down = scale_entry_luma(entry, factor_at)
        adjusted.append(candidate)
        if entry["apply_grain"] and entry["update_parameters"]:
            updated += 1
            shifted += shift_down > 0
    filmgrn.write(args.output, adjusted)
    # Validate the exact integer representation handed to the replay encoder.
    filmgrn.load(args.output)

    report = {
        "scope": (
            "per-luma sparse actual-clean-pixel prototype"
            if sparse_expected is not None else
            "per-luma interpolated prototype" if args.per_luma else
            "whole-curve aggregate prototype; requires luma-band validation"),
        "input": os.path.abspath(args.input),
        "output": os.path.abspath(args.output),
        "closure": os.path.abspath(args.closure),
        "emission": os.path.abspath(args.emission),
        "qvbr": args.qvbr,
        "mask": MASK,
        "pre_encode_leak": pre_leak,
        "theta": theta,
        "predicted_post_encode_leak": predicted_post_leak,
        "predicted_synthesis_target": target,
        "expected_synthesis_before": expected,
        "requested_luma_factor": factor if not args.per_luma else None,
        "luma_factor_points": factor_points,
        "luma_bins": band_report,
        "seed_samples": samples,
        "sparse_response": (
            os.path.abspath(args.sparse_response)
            if args.sparse_response else None),
        "sparse_blocks_per_frame_bin": (
            args.sparse_blocks_per_bin if sparse_model is not None else None),
        "sparse_selection_repeat": (
            args.sparse_repeat if sparse_model is not None else None),
        "sparse_sampled_fraction": (
            sparse_model["sampled_fraction"] if sparse_model is not None else None),
        "updated_entries": updated,
        "entries_requiring_shared_shift": shifted,
    }
    print(json.dumps(report, indent=2))
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")


if __name__ == "__main__":
    main()
