#!/usr/bin/env python3
"""Reposition an NVEnc luma strength curve onto its measured bin centres.

This is an offline isolation tool, not an encoder option.  NVEnc currently
assigns each block to one of 20 equal-width intensity intervals, but
``fit_strength_points`` emits those 20 estimates at endpoint-spaced positions
0..255.  libaom's endpoint grid is paired with fractional observations; a
hard-interval observation belongs at the interval centre instead.

Only luma point coordinates move.  Point amplitudes, AR coefficients, chroma,
timing and every other parameter remain byte-for-byte equivalent in the parsed
model.  Re-encoding one saved clean base with the original and remapped tables
therefore isolates the coordinate mapping from the separator and analyser.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import filmgrn


STRENGTH_BINS = 20
CODE_VALUES = 256


def interval_center_from_endpoint(value: int, bins: int = STRENGTH_BINS) -> int:
    """Map an endpoint-grid coordinate to the matching hard-bin centre."""
    if bins < 2:
        raise ValueError("at least two strength bins are required")
    if value < 0 or value >= CODE_VALUES:
        raise ValueError(f"8-bit scaling coordinate outside 0..255: {value}")
    # Existing points lie on i*255/(bins-1), possibly rounded to an integer.
    # The hard collector instead covers [i*256/bins, (i+1)*256/bins), whose
    # centre is (i+0.5)*256/bins.  Applying the affine map avoids guessing the
    # original integer bin after point reduction has removed intermediate
    # controls.
    endpoint_fraction = value / (CODE_VALUES - 1)
    center = CODE_VALUES / (2.0 * bins) + endpoint_fraction * (
        CODE_VALUES * (bins - 1) / bins)
    return min(CODE_VALUES - 1, max(0, int(round(center))))


def remap_luma(entries: list[dict], bins: int = STRENGTH_BINS) -> tuple[list[dict], dict]:
    """Return a deep-copied table with only luma x coordinates remapped."""
    adjusted = copy.deepcopy(entries)
    updated_entries = 0
    moved_points = 0
    total_points = 0
    for entry in adjusted:
        if not (entry["apply_grain"] and entry["update_parameters"]):
            continue
        points = entry["scaling_points"]["y"]
        remapped = []
        for value, scaling in points:
            mapped = interval_center_from_endpoint(value, bins)
            total_points += 1
            moved_points += mapped != value
            remapped.append([mapped, scaling])
        if any(left[0] >= right[0] for left, right in zip(remapped, remapped[1:])):
            raise ValueError("remapped luma coordinates are not strictly increasing")
        entry["scaling_points"]["y"] = remapped
        updated_entries += 1
    return adjusted, {
        "strength_bins": bins,
        "updated_entries": updated_entries,
        "luma_points": total_points,
        "moved_luma_points": moved_points,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--bins", type=int, default=STRENGTH_BINS)
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    source = Path(args.input).resolve()
    output = Path(args.output).resolve()
    entries = filmgrn.load(source)
    adjusted, report = remap_luma(entries, args.bins)
    output.parent.mkdir(parents=True, exist_ok=True)
    filmgrn.write(output, adjusted)
    # Parse the exact representation handed to NVEncC rather than trusting the
    # in-memory form.
    filmgrn.load(output)
    report.update({"input": str(source), "output": str(output)})
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.json_out:
        destination = Path(args.json_out).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
