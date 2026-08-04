#!/usr/bin/env python3
"""Compare pre-encode luma/chroma strength estimators with played truth.

The input reports come from :mod:`strength_selection_report`.  They contain
three deliberately separate quantities on one fixed block population:

* temporal source/base variance available before encoding;
* the post-encode grain-disabled base residue; and
* the synthesis delivered by dav1d.

This gate asks whether applying the existing QVBR deadzone per luma bin is a
better strength target than applying one title-wide fraction.  For U/V it also
compares the legacy luma-temporal selector with a plane-specific temporal
selector and fits a *single per-plane deadzone* under leave-one-title-out
validation.  It never fits a title multiplier and it does not rewrite a grain
table.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from delivery_normalize import target_from_pre_leak


PLANES = ("y", "u", "v")


def synthesis_target(pre_leak: float, theta: float) -> float:
    post_leak = max(0.0, min(1.0, pre_leak) - theta)
    return math.sqrt(max(0.0, 1.0 - post_leak * post_leak))


def fit_deadzone(records: list[dict]) -> float:
    """Fit one physical post=max(0, pre-theta) transfer.

    Source-variance weight keeps a nearly grain-free chroma band from deciding
    the transfer for the whole plane.  Reporting remains equal-band as well,
    so the weighting cannot hide a sparse luma-range failure.
    """
    if not records:
        raise ValueError("at least one record is required")
    pre = np.asarray([row["pre_leak"] for row in records], dtype=np.float64)
    post = np.asarray([row["post_leak"] for row in records], dtype=np.float64)
    weight = np.asarray([row["weight"] for row in records], dtype=np.float64)
    if not np.all(np.isfinite(pre)) or not np.all(np.isfinite(post)):
        raise ValueError("leak observations must be finite")
    if not np.any(weight > 0.0):
        weight = np.ones_like(weight)
    # A dense deterministic grid is adequate for a one-parameter diagnostic
    # and makes the result independent of an optional scipy installation.
    candidates = np.linspace(0.0, 0.75, 7501)
    predicted = np.maximum(0.0, pre[None, :] - candidates[:, None])
    error = np.average((predicted - post[None, :]) ** 2, axis=1, weights=weight)
    return float(candidates[int(np.argmin(error))])


def error_summary(records: list[dict], field: str) -> dict:
    errors = np.asarray(
        [row[field] - row["true_target"] for row in records], dtype=np.float64)
    weights = np.asarray([row["weight"] for row in records], dtype=np.float64)
    if not len(errors):
        return {"bands": 0, "bias": None, "mae": None, "max": None,
                "weighted_rmse": None}
    if not np.any(weights > 0.0):
        weights = np.ones_like(weights)
    return {
        "bands": int(len(errors)),
        "bias": float(np.mean(errors)),
        "mae": float(np.mean(np.abs(errors))),
        "max": float(np.max(np.abs(errors))),
        "weighted_rmse": float(np.sqrt(np.average(errors * errors, weights=weights))),
    }


def read_records(path: Path, title: str, plane: str, mask: str,
                 arm: str, qvbr: float, min_blocks: int) -> list[dict]:
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("plane") != plane:
        raise ValueError(f"{path}: expected plane {plane}, got {report.get('plane')}")
    aggregate = report.get("aggregate", {}).get(mask)
    bins = report.get("luma_bins", {}).get(mask)
    if aggregate is None or bins is None:
        return []
    _theta, _post, global_fraction = target_from_pre_leak(
        float(aggregate["temporal_leak_ratio"]), qvbr)
    global_target = float(global_fraction)
    theta = target_from_pre_leak(0.0, qvbr)[0]
    rows = []
    for band in bins:
        if int(band["blocks"]) < min_blocks:
            continue
        encoded = band.get("encoded_arms", {}).get(arm)
        if encoded is None:
            continue
        pre_leak = float(band["temporal_leak_ratio"])
        post_leak = float(encoded["post_leak_ratio"])
        truth_sigma = float(band["truth_sigma"])
        rows.append({
            "title": title,
            "plane": plane,
            "mask": mask,
            "range": band["range"],
            "blocks": int(band["blocks"]),
            "weight": float(band["blocks"]) * truth_sigma * truth_sigma,
            "pre_leak": pre_leak,
            "post_leak": post_leak,
            "true_target": float(encoded["post_target_ratio"]),
            "current_synth": float(encoded["synth_ratio"]),
            "global_qvbr": global_target,
            "local_qvbr": synthesis_target(pre_leak, theta),
        })
    return rows


def leave_one_title_out(records: list[dict]) -> dict:
    predictions = []
    theta_by_holdout = {}
    for title in sorted({row["title"] for row in records}):
        train = [row for row in records if row["title"] != title]
        held = [row for row in records if row["title"] == title]
        if not train or not held:
            continue
        theta = fit_deadzone(train)
        theta_by_holdout[title] = theta
        for row in held:
            copied = dict(row)
            copied["loo_plane"] = synthesis_target(row["pre_leak"], theta)
            predictions.append(copied)
    return {
        "theta_by_holdout": theta_by_holdout,
        "summary": error_summary(predictions, "loo_plane"),
        "records": predictions,
    }


def analyse_group(records: list[dict], qvbr: float, allow_plane_fit: bool) -> dict:
    result = {
        "records": records,
        "models": {
            name: error_summary(records, name)
            for name in ("current_synth", "global_qvbr", "local_qvbr")
        },
    }
    if allow_plane_fit and records:
        theta = fit_deadzone(records)
        fitted = []
        for row in records:
            copied = dict(row)
            copied["pooled_plane"] = synthesis_target(row["pre_leak"], theta)
            fitted.append(copied)
        result["pooled_plane_deadzone"] = {
            "theta": theta,
            "summary": error_summary(fitted, "pooled_plane"),
        }
        result["leave_one_title_out"] = leave_one_title_out(records)
    return result


def print_group(label: str, result: dict) -> None:
    print(f"\n{label}")
    print(f"{'model':<24}{'bands':>7}{'bias':>10}{'MAE':>10}"
          f"{'max':>10}{'wRMSE':>10}")
    for name, row in result["models"].items():
        print(f"{name:<24}{row['bands']:>7}{row['bias']:>10.4f}"
              f"{row['mae']:>10.4f}{row['max']:>10.4f}"
              f"{row['weighted_rmse']:>10.4f}")
    if "pooled_plane_deadzone" in result:
        pooled = result["pooled_plane_deadzone"]
        row = pooled["summary"]
        print(f"{'pooled_plane':<24}{row['bands']:>7}{row['bias']:>10.4f}"
              f"{row['mae']:>10.4f}{row['max']:>10.4f}"
              f"{row['weighted_rmse']:>10.4f}  theta={pooled['theta']:.4f}")
        loo = result["leave_one_title_out"]["summary"]
        print(f"{'LOO_plane':<24}{loo['bands']:>7}{loo['bias']:>10.4f}"
              f"{loo['mae']:>10.4f}{loo['max']:>10.4f}"
              f"{loo['weighted_rmse']:>10.4f}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-dir", required=True)
    parser.add_argument(
        "--titles", default=(
            "Casino,Interstellar,Scarface,Taxi_Driver,The_Deer_Hunter,The_Shining"))
    parser.add_argument("--arm", default="hybrid")
    parser.add_argument("--qvbr", type=float, default=29.0)
    parser.add_argument("--min-blocks", type=int, default=100)
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    report_dir = Path(args.report_dir).resolve()
    titles = [value.strip() for value in args.titles.split(",") if value.strip()]
    groups = {}
    for plane in PLANES:
        masks = ["production_static"]
        if plane != "y":
            masks.append("production_plane_static")
        for mask in masks:
            rows = []
            missing = []
            for title in titles:
                path = report_dir / f"{title}-{plane}.json"
                if not path.is_file():
                    missing.append(str(path))
                    continue
                rows.extend(read_records(
                    path, title, plane, mask, args.arm, args.qvbr,
                    args.min_blocks))
            if missing:
                raise SystemExit("missing reports: " + ", ".join(missing))
            key = f"{plane}:{mask}"
            groups[key] = analyse_group(rows, args.qvbr, plane != "y")
            print_group(key, groups[key])

    output = {
        "report_dir": str(report_dir),
        "titles": titles,
        "arm": args.arm,
        "qvbr": args.qvbr,
        "min_blocks": args.min_blocks,
        "groups": groups,
    }
    if args.json_out:
        path = Path(args.json_out)
        path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
