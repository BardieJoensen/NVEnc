#!/usr/bin/env python3
"""Evaluate a response-aware covariance selector without title leakage.

The CUDA texture-closure prototype can form several physically valid
``source - alpha * base`` AR systems.  A raw AV1 template simulation is not a
selection oracle by itself: overlap, scaling, rounding and clipping lower the
correlation delivered at decoded pixels.  The response-grid artifacts contain
both quantities for the same candidate models.

For every held-out title this tool fits one affine raw-to-decoded transfer per
axis using every candidate from the other titles, chooses the held-out alpha
from only its raw template statistics, then reveals the already-recorded exact
result.  It is an offline quality experiment, not a routing or production
decision.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from pathlib import Path

import numpy as np


AXES = ("h1", "h2", "v1", "v2")


def title_of(report: dict) -> str:
    name = Path(report["source"]).stem
    return name.removeprefix("clip_")


def axis_error(left: dict, right: dict) -> float:
    return float(np.mean([abs(left[axis] - right[axis]) for axis in AXES]))


def fit_transfer(reports: list[dict]) -> dict[str, tuple[float, float]]:
    """Fit decoded = slope * raw + intercept independently per axis."""
    result = {}
    for axis in AXES:
        raw = []
        decoded = []
        for report in reports:
            for row in report["response_grid"]:
                raw.append(row["best_quantized_model"]["implied"][axis])
                decoded.append(row["exact_synthesis"][axis])
        design = np.column_stack(
            [np.asarray(raw, dtype=np.float64), np.ones(len(raw))])
        slope, intercept = np.linalg.lstsq(
            design, np.asarray(decoded, dtype=np.float64), rcond=None)[0]
        result[axis] = (float(slope), float(intercept))
    return result


def predict_synthesis(row: dict,
                      transfer: dict[str, tuple[float, float]]) -> dict:
    raw = row["best_quantized_model"]["implied"]
    return {
        axis: transfer[axis][0] * raw[axis] + transfer[axis][1]
        for axis in AXES
    }


def mix_with_base(report: dict, synthesis: dict) -> dict:
    base = report["base_leak"]
    desired = report["desired_synthesis"]
    total_variance = base["variance"] + desired["variance"]
    return {
        axis: (base["covariance"][axis]
               + synthesis[axis] * desired["variance"]) / total_variance
        for axis in AXES
    }


def select_row(report: dict,
               transfer: dict[str, tuple[float, float]]) -> tuple[dict, float]:
    candidates = []
    for row in report["response_grid"]:
        predicted = mix_with_base(report, predict_synthesis(row, transfer))
        candidates.append((axis_error(predicted, report["source_truth"]), row))
    predicted_error, selected = min(
        candidates,
        key=lambda item: (item[0], item[1]["base_covariance_weight"]))
    return selected, predicted_error


def summarize(reports: list[dict]) -> dict:
    if len(reports) < 3:
        raise ValueError("at least three title reports are required")
    titles = [title_of(report) for report in reports]
    if len(titles) != len(set(titles)):
        raise ValueError("response reports must have unique source titles")

    rows = []
    for heldout in reports:
        training = [report for report in reports if report is not heldout]
        transfer = fit_transfer(training)
        selected, predicted_error = select_row(heldout, transfer)
        exact_error = float(selected["total_axis_mae_to_source"])
        best = min(
            heldout["response_grid"],
            key=lambda row: (row["total_axis_mae_to_source"],
                             row["base_covariance_weight"]))
        fixed = next(
            row for row in heldout["response_grid"]
            if abs(row["base_covariance_weight"] - 0.75) < 1e-12)
        rows.append({
            "title": title_of(heldout),
            "selected_weight": selected["base_covariance_weight"],
            "predicted_axis_mae": predicted_error,
            "exact_axis_mae": exact_error,
            "oracle_grid_weight": best["base_covariance_weight"],
            "oracle_grid_axis_mae": best["total_axis_mae_to_source"],
            "fixed_0_75_axis_mae": fixed["total_axis_mae_to_source"],
            "transfer": {
                axis: {"slope": transfer[axis][0],
                       "intercept": transfer[axis][1]}
                for axis in AXES
            },
        })

    selected_errors = [row["exact_axis_mae"] for row in rows]
    fixed_errors = [row["fixed_0_75_axis_mae"] for row in rows]
    oracle_errors = [row["oracle_grid_axis_mae"] for row in rows]
    return {
        "purpose": "leave-one-title-out normative texture response selector",
        "warning": "offline diagnostic only; no routing or production verdict",
        "titles": rows,
        "summary": {
            "selected_mean_axis_mae": float(np.mean(selected_errors)),
            "selected_max_axis_mae": float(np.max(selected_errors)),
            "fixed_0_75_mean_axis_mae": float(np.mean(fixed_errors)),
            "fixed_0_75_max_axis_mae": float(np.max(fixed_errors)),
            "oracle_grid_mean_axis_mae": float(np.mean(oracle_errors)),
            "oracle_grid_max_axis_mae": float(np.max(oracle_errors)),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "reports", nargs="+",
        help="response-grid JSON paths or glob patterns")
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    paths = []
    for pattern in args.reports:
        matches = sorted(glob.glob(pattern))
        paths.extend(matches if matches else [pattern])
    paths = list(dict.fromkeys(os.path.abspath(path) for path in paths))
    missing = [path for path in paths if not os.path.isfile(path)]
    if missing:
        parser.error("missing response reports: " + ", ".join(missing))
    reports = []
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            report = json.load(handle)
        if not report.get("response_grid"):
            parser.error(f"response report has no grid: {path}")
        reports.append(report)

    result = summarize(reports)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.json_out:
        output = Path(args.json_out)
        temporary = output.with_suffix(output.suffix + ".partial")
        temporary.write_text(rendered, encoding="utf-8")
        os.replace(temporary, output)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
