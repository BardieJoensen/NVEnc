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


def parse_planes(value: str) -> tuple[str, ...]:
    planes = tuple(item.strip().lower() for item in value.split(",") if item.strip())
    if not planes:
        raise ValueError("at least one plane is required")
    invalid = [plane for plane in planes if plane not in PLANES]
    if invalid:
        raise ValueError("invalid plane(s): " + ", ".join(invalid))
    if len(set(planes)) != len(planes):
        raise ValueError("planes must not be repeated")
    return planes


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


def fit_rate_deadzone(records: list[dict]) -> dict:
    """Fit one plane-specific deadzone at each rate, then a linear transfer."""
    if not records:
        raise ValueError("at least one record is required")
    rates = sorted({float(row["qvbr"]) for row in records})
    theta_by_rate = {
        rate: fit_deadzone([row for row in records if row["qvbr"] == rate])
        for rate in rates
    }
    if len(rates) == 1:
        slope = 0.0
        intercept = theta_by_rate[rates[0]]
    else:
        slope, intercept = np.polyfit(
            np.asarray(rates),
            np.asarray([theta_by_rate[rate] for rate in rates]), 1)
    return {
        "intercept": float(intercept),
        "slope": float(slope),
        "theta_by_rate": {str(rate): theta_by_rate[rate] for rate in rates},
    }


def rate_theta(model: dict, qvbr: float) -> float:
    return max(0.0, float(model["intercept"]) + float(model["slope"]) * qvbr)


def error_summary(records: list[dict], field: str) -> dict:
    errors = np.asarray(
        [row[field] - row["true_target"] for row in records], dtype=np.float64)
    weights = np.asarray([row["weight"] for row in records], dtype=np.float64)
    if not len(errors):
        return {"bands": 0, "bias": None, "mae": None, "max": None,
                "weighted_rmse": None, "sigma8_mae": None,
                "sigma8_max": None}
    if not np.any(weights > 0.0):
        weights = np.ones_like(weights)
    result = {
        "bands": int(len(errors)),
        "bias": float(np.mean(errors)),
        "mae": float(np.mean(np.abs(errors))),
        "max": float(np.max(np.abs(errors))),
        "weighted_rmse": float(np.sqrt(np.average(errors * errors, weights=weights))),
    }
    if all("truth_sigma_8bit" in row for row in records):
        sigma_error = np.abs(errors) * np.asarray(
            [row["truth_sigma_8bit"] for row in records], dtype=np.float64)
        result["sigma8_mae"] = float(np.mean(sigma_error))
        result["sigma8_max"] = float(np.max(sigma_error))
    else:
        result["sigma8_mae"] = None
        result["sigma8_max"] = None
    return result


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
    depth_scale = float(1 << (int(report.get("bits", 8)) - 8))
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
            "arm": arm,
            "qvbr": float(qvbr),
            "range": band["range"],
            "blocks": int(band["blocks"]),
            "weight": float(band["blocks"]) * truth_sigma * truth_sigma,
            "truth_sigma_8bit": truth_sigma / depth_scale,
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
        model = fit_rate_deadzone(train)
        theta_by_holdout[title] = model
        for row in held:
            copied = dict(row)
            copied["loo_plane"] = synthesis_target(
                row["pre_leak"], rate_theta(model, row["qvbr"]))
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
        model = fit_rate_deadzone(records)
        fitted = []
        for row in records:
            copied = dict(row)
            copied["pooled_plane"] = synthesis_target(
                row["pre_leak"], rate_theta(model, row["qvbr"]))
            fitted.append(copied)
        result["pooled_plane_deadzone"] = {
            "rate_model": model,
            "summary": error_summary(fitted, "pooled_plane"),
        }
        result["leave_one_title_out"] = leave_one_title_out(records)
    return result


def print_group(label: str, result: dict) -> None:
    print(f"\n{label}")
    print(f"{'model':<24}{'bands':>7}{'bias':>10}{'MAE':>10}"
          f"{'max':>10}{'wRMSE':>10}{'sigma8':>10}")
    for name, row in result["models"].items():
        print(f"{name:<24}{row['bands']:>7}{row['bias']:>10.4f}"
              f"{row['mae']:>10.4f}{row['max']:>10.4f}"
              f"{row['weighted_rmse']:>10.4f}{row['sigma8_max']:>10.4f}")
    if "pooled_plane_deadzone" in result:
        pooled = result["pooled_plane_deadzone"]
        row = pooled["summary"]
        print(f"{'pooled_plane':<24}{row['bands']:>7}{row['bias']:>10.4f}"
              f"{row['mae']:>10.4f}{row['max']:>10.4f}"
              f"{row['weighted_rmse']:>10.4f}{row['sigma8_max']:>10.4f}  "
              f"theta={pooled['rate_model']['intercept']:.4f}"
              f"+{pooled['rate_model']['slope']:.6f}q")
        loo = result["leave_one_title_out"]["summary"]
        print(f"{'LOO_plane':<24}{loo['bands']:>7}{loo['bias']:>10.4f}"
              f"{loo['mae']:>10.4f}{loo['max']:>10.4f}"
              f"{loo['weighted_rmse']:>10.4f}{loo['sigma8_max']:>10.4f}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-dir", required=True)
    parser.add_argument(
        "--titles", default=(
            "Casino,Interstellar,Scarface,Taxi_Driver,The_Deer_Hunter,The_Shining"))
    parser.add_argument("--arm", default="hybrid")
    parser.add_argument("--qvbr", type=float, default=29.0)
    parser.add_argument(
        "--arms", default="",
        help="optional comma-separated ARM=QVBR map for a multi-rate report")
    parser.add_argument("--min-blocks", type=int, default=100)
    parser.add_argument(
        "--planes", default=",".join(PLANES),
        help="comma-separated planes to analyse (default y,u,v)")
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    try:
        planes = parse_planes(args.planes)
    except ValueError as error:
        parser.error(str(error))

    report_dir = Path(args.report_dir).resolve()
    titles = [value.strip() for value in args.titles.split(",") if value.strip()]
    arms = {args.arm: args.qvbr}
    if args.arms:
        arms = {}
        for value in args.arms.split(","):
            arm, separator, rate = value.partition("=")
            if not separator or not arm or not rate:
                parser.error(f"invalid --arms item {value!r}; expected ARM=QVBR")
            if arm in arms:
                parser.error(f"duplicate --arms label {arm!r}")
            try:
                arms[arm] = float(rate)
            except ValueError:
                parser.error(f"invalid QVBR in --arms item {value!r}")
    groups = {}
    for plane in planes:
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
                for arm, qvbr in arms.items():
                    rows.extend(read_records(
                        path, title, plane, mask, arm, qvbr,
                        args.min_blocks))
            if missing:
                raise SystemExit("missing reports: " + ", ".join(missing))
            key = f"{plane}:{mask}"
            if not rows:
                raise SystemExit(
                    f"{key}: no bands found; regenerate reports with the "
                    "current strength_selection_report.py")
            groups[key] = analyse_group(rows, args.qvbr, plane != "y")
            print_group(key, groups[key])

    output = {
        "report_dir": str(report_dir),
        "titles": titles,
        "planes": list(planes),
        "arms": arms,
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
