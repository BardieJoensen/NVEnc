#!/usr/bin/env python3
"""Offline luma expected-delivery normalisation for a filmgrn1 table.

This is an experiment, not an encoder option.  It closes the analyser's
rate-dependent temporal target against the expected AV1 synthesis amplitude
measured by ``emission_audit.py --seed-samples``.  The multiplier is therefore
calculated from two analyser-available quantities; it is not fitted to the
post-encode result of an individual title.

The luma curve alone is changed.  If it would overflow, the shared
``scaling_shift`` is reduced and chroma integer curves are requantised so their
physical amplitude remains unchanged.
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


def scale_entry_luma(entry, factor):
    """Scale effective luma amplitude while preserving effective chroma."""
    candidate = copy.deepcopy(entry)
    if not (entry["apply_grain"] and entry["update_parameters"]):
        return candidate, 0
    desired = [[x, y * factor] for x, y in entry["scaling_points"]["y"]]
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="candidate filmgrn1 table")
    parser.add_argument("--closure", required=True,
                        help="pre-encode closure report for the candidate")
    parser.add_argument("--emission", required=True,
                        help="expected-seed emission audit for the candidate")
    parser.add_argument("--qvbr", type=float, required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--json-out", default="")
    parser.add_argument("--min-factor", type=float, default=0.75)
    parser.add_argument("--max-factor", type=float, default=1.25)
    args = parser.parse_args()

    with open(args.closure, encoding="utf-8") as handle:
        closure = json.load(handle)
    with open(args.emission, encoding="utf-8") as handle:
        emission = json.load(handle)
    pre_leak = closure["aggregate"][MASK]["temporal_leak_ratio"]
    expected = emission["aggregate"]["seed_mean_ratio"]
    samples = emission["aggregate"]["seed_samples"]
    if samples <= 0 or expected is None or expected <= 0.0:
        raise SystemExit("emission report has no positive expected-seed amplitude")
    theta, predicted_post_leak, target = target_from_pre_leak(pre_leak, args.qvbr)
    factor = target / expected
    if not args.min_factor <= factor <= args.max_factor:
        raise SystemExit(
            f"required factor {factor:.4f} outside conservative "
            f"[{args.min_factor:.3f}, {args.max_factor:.3f}] gate")

    entries = filmgrn.load(args.input)
    adjusted = []
    shifted = 0
    updated = 0
    for entry in entries:
        candidate, shift_down = scale_entry_luma(entry, factor)
        adjusted.append(candidate)
        if entry["apply_grain"] and entry["update_parameters"]:
            updated += 1
            shifted += shift_down > 0
    filmgrn.write(args.output, adjusted)
    # Validate the exact integer representation handed to the replay encoder.
    filmgrn.load(args.output)

    report = {
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
        "requested_luma_factor": factor,
        "seed_samples": samples,
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
