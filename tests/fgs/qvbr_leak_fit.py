#!/usr/bin/env python3
"""Fit the post-encode base-leak deadzone across a multi-QVBR corpus.

``strength_selection_report.py`` measures the same clean base before and after
AV1 encoding.  This tool tests the one-parameter transfer model

    post_leak = max(0, pre_encode_leak - theta)

at every encoded arm, including leave-one-title-out target-amplitude errors.
When NVEncC logs are available it also relates ``theta`` to the actual mean P
frame qindex and libaom's 10-bit AC quantizer step.

Usage:
  python3 tests/fgs/qvbr_leak_fit.py \
      --report Taxi=Taxi-closure-qvbr.json --report Casino=Casino-closure-qvbr.json \
      --log-root sweep-directory --json-out leak-fit.json
"""
import argparse
import json
import math
import os
import re

import numpy as np


DEFAULT_MASK = "production_static"


def parse_specs(values):
    result = {}
    for value in values:
        label, separator, path = value.partition("=")
        if not separator or not label or not path:
            raise ValueError(f"expected LABEL=PATH, got {value!r}")
        if label in result:
            raise ValueError(f"duplicate label {label!r}")
        result[label] = path
    return result


def fit_deadzone(pre, post):
    """Least-squares theta for max(0, pre - theta)."""
    pre = np.asarray(pre, dtype=np.float64)
    post = np.asarray(post, dtype=np.float64)
    if pre.shape != post.shape or pre.size == 0:
        raise ValueError("pre and post must be non-empty arrays of equal shape")
    theta = max(0.0, float(np.mean(pre - post)))
    for _iteration in range(pre.size + 2):
        active = pre > theta
        if not np.any(active):
            return float(np.max(pre))
        updated = max(0.0, float(np.mean(pre[active] - post[active])))
        if abs(updated - theta) < 1e-15:
            break
        theta = updated
    return theta


def target_from_leak(leak):
    return math.sqrt(max(0.0, 1.0 - leak * leak))


def pearson(left, right):
    left = np.asarray(left, dtype=np.float64)
    right = np.asarray(right, dtype=np.float64)
    if left.size < 2 or np.std(left) == 0 or np.std(right) == 0:
        return None
    return float(np.corrcoef(left, right)[0, 1])


def parse_qlookup(path, bit_depth=10):
    name = "ac_qlookup_QTX" if bit_depth == 8 else f"ac_qlookup_{bit_depth}_QTX"
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    match = re.search(
        rf"{name}\s*\[\s*QINDEX_RANGE\s*\]\s*=\s*\{{(.*?)\}};",
        source, flags=re.DOTALL)
    if not match:
        raise ValueError(f"{path}: {name} not found")
    values = [int(value) for value in re.findall(r"-?\d+", match.group(1))]
    if len(values) != 256:
        raise ValueError(f"{path}: {name} has {len(values)} values, expected 256")
    return np.asarray(values, dtype=np.float64)


def quantizer_step(qindex, lookup, bit_depth=10):
    qindex = min(max(float(qindex), 0.0), 255.0)
    lower = int(math.floor(qindex))
    upper = min(lower + 1, 255)
    value = lookup[lower] + (lookup[upper] - lookup[lower]) * (qindex - lower)
    # QTX values carry three fractional bits, regardless of coded bit depth.
    return float(value / 8.0)


def parse_p_qindex(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        text = handle.read()
    matches = re.findall(r"frame type P\s+\d+,\s+avgQP\s+([0-9]+(?:\.[0-9]+)?)", text)
    if not matches:
        raise ValueError(f"{path}: mean P-frame QP not found")
    return float(matches[-1])


def load_points(specs, mask=DEFAULT_MASK):
    reports = {}
    rates = None
    for title, path in specs.items():
        with open(path, encoding="utf-8") as handle:
            report = json.load(handle)
        available = set(report["encoded_aggregates"])
        rates = available if rates is None else rates.intersection(available)
        reports[title] = report
    if not rates:
        raise ValueError("reports have no common encoded arms")
    points = []
    for title, report in reports.items():
        if mask not in report["aggregate"]:
            raise ValueError(f"{title}: mask {mask!r} is absent from {specs[title]}")
        pre = report["aggregate"][mask]["temporal_leak_ratio"]
        for arm in sorted(rates, key=lambda value: int(re.search(r"\d+", value).group())):
            encoded = report["encoded_aggregates"][arm][mask]
            points.append({
                "title": title,
                "arm": arm,
                "qvbr": int(re.search(r"\d+", arm).group()),
                "pre_leak": pre,
                "post_leak": encoded["post_leak_ratio"],
                "true_target": encoded["post_target_ratio"],
            })
    return points


def analyse(points, log_root="", quant_source="", mask=DEFAULT_MASK):
    titles = sorted({point["title"] for point in points})
    qvbrs = sorted({point["qvbr"] for point in points})
    lookup = parse_qlookup(quant_source) if quant_source else None
    rate_rows = []
    for qvbr in qvbrs:
        rows = [point for point in points if point["qvbr"] == qvbr]
        theta = fit_deadzone(
            [row["pre_leak"] for row in rows], [row["post_leak"] for row in rows])
        observed = [row["pre_leak"] - row["post_leak"] for row in rows]
        raw_errors = [
            abs(target_from_leak(row["pre_leak"]) - row["true_target"])
            for row in rows
        ]
        fitted_errors = [
            abs(target_from_leak(max(0.0, row["pre_leak"] - theta))
                - row["true_target"])
            for row in rows
        ]
        loo_errors = []
        for held in rows:
            training = [row for row in rows if row is not held]
            held_theta = fit_deadzone(
                [row["pre_leak"] for row in training],
                [row["post_leak"] for row in training])
            prediction = target_from_leak(max(0.0, held["pre_leak"] - held_theta))
            loo_errors.append(abs(prediction - held["true_target"]))
        qindices = []
        if log_root:
            for row in rows:
                path = os.path.join(log_root, f"{row['title']}-{row['arm']}.log")
                row["mean_p_qindex"] = parse_p_qindex(path)
                qindices.append(row["mean_p_qindex"])
                if lookup is not None:
                    row["qstep"] = quantizer_step(row["mean_p_qindex"], lookup)
        rate_rows.append({
            "qvbr": qvbr,
            "theta": theta,
            "theta_sd": float(np.std(observed, ddof=1)) if len(observed) > 1 else 0.0,
            "theta_min": min(observed),
            "theta_max": max(observed),
            "pre_post_correlation": pearson(
                [row["pre_leak"] for row in rows],
                [row["post_leak"] for row in rows]),
            "raw_target_mae": float(np.mean(raw_errors)),
            "fitted_target_mae": float(np.mean(fitted_errors)),
            "loo_target_mean": float(np.mean(loo_errors)),
            "loo_target_max": max(loo_errors),
            "mean_p_qindex": float(np.mean(qindices)) if qindices else None,
            "mean_qstep": (
                quantizer_step(float(np.mean(qindices)), lookup)
                if qindices and lookup is not None else None),
        })

    q_values = np.asarray([row["qvbr"] for row in rate_rows], dtype=np.float64)
    theta_values = np.asarray([row["theta"] for row in rate_rows], dtype=np.float64)
    slope, intercept = np.polyfit(q_values, theta_values, 1)
    predictions = intercept + slope * q_values
    loo_rate_errors = []
    for index in range(len(rate_rows)):
        keep = np.arange(len(rate_rows)) != index
        held_slope, held_intercept = np.polyfit(q_values[keep], theta_values[keep], 1)
        loo_rate_errors.append(float(
            held_intercept + held_slope * q_values[index] - theta_values[index]))
    rate_fit = {
        "model": "theta = intercept + slope * qvbr",
        "intercept": float(intercept),
        "slope": float(slope),
        "correlation": pearson(q_values, theta_values),
        "max_abs_residual": float(np.max(np.abs(predictions - theta_values))),
        "loo_errors": loo_rate_errors,
        "loo_max_abs_error": max(abs(value) for value in loo_rate_errors),
    }
    if all(row["mean_qstep"] is not None for row in rate_rows):
        qsteps = np.asarray([row["mean_qstep"] for row in rate_rows])
        rate_fit["qstep_correlation"] = pearson(qsteps, theta_values)
        rate_fit["log2_qstep_correlation"] = pearson(np.log2(qsteps), theta_values)

    title_loo = []
    title_rate_model_loo = []
    for title in titles:
        errors = []
        for qvbr in qvbrs:
            rows = [point for point in points if point["qvbr"] == qvbr]
            held = next(row for row in rows if row["title"] == title)
            training = [row for row in rows if row["title"] != title]
            theta = fit_deadzone(
                [row["pre_leak"] for row in training],
                [row["post_leak"] for row in training])
            predicted = target_from_leak(max(0.0, held["pre_leak"] - theta))
            errors.append(abs(predicted - held["true_target"]))
        title_loo.append({
            "title": title,
            "mean_target_error": float(np.mean(errors)),
            "max_target_error": max(errors),
        })
        training = [point for point in points if point["title"] != title]
        training_thetas = []
        for qvbr in qvbrs:
            rows = [point for point in training if point["qvbr"] == qvbr]
            training_thetas.append(fit_deadzone(
                [row["pre_leak"] for row in rows],
                [row["post_leak"] for row in rows]))
        held_slope, held_intercept = np.polyfit(qvbrs, training_thetas, 1)
        rate_model_errors = []
        for held in [point for point in points if point["title"] == title]:
            theta = held_intercept + held_slope * held["qvbr"]
            predicted = target_from_leak(max(0.0, held["pre_leak"] - theta))
            rate_model_errors.append(abs(predicted - held["true_target"]))
        title_rate_model_loo.append({
            "title": title,
            "mean_target_error": float(np.mean(rate_model_errors)),
            "max_target_error": max(rate_model_errors),
        })
    return {
        "model": "post_leak = max(0, pre_encode_leak - theta)",
        "mask": mask,
        "titles": titles,
        "rates": rate_rows,
        "rate_fit": rate_fit,
        "leave_one_title_out": title_loo,
        "leave_one_title_out_rate_model": title_rate_model_loo,
        "points": points,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", action="append", default=[], metavar="TITLE=PATH")
    parser.add_argument("--log-root", default="")
    parser.add_argument(
        "--mask", default=DEFAULT_MASK,
        help="strength-selection population to fit (default production_static)")
    parser.add_argument(
        "--aom-quant-source",
        default=os.environ.get(
            "AOM_QUANT_SOURCE", "/tmp/aomref/src/av1/common/quant_common.c"))
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()
    if len(args.report) < 3:
        parser.error("at least three --report TITLE=PATH inputs are required")
    quant_source = args.aom_quant_source if args.log_root else ""
    report = analyse(
        load_points(parse_specs(args.report), args.mask),
        args.log_root, quant_source, args.mask)

    print(f"{'qvbr':>5}{'theta':>10}{'SD':>10}{'range':>21}{'r pre/post':>12}"
          f"{'raw MAE':>10}{'fit MAE':>10}{'LOO max':>10}")
    for row in report["rates"]:
        bounds = f"{row['theta_min']:.5f}..{row['theta_max']:.5f}"
        print(f"{row['qvbr']:>5}{row['theta']:>10.5f}{row['theta_sd']:>10.5f}"
              f"{bounds:>21}{row['pre_post_correlation']:>12.4f}"
              f"{row['raw_target_mae']:>10.5f}{row['fitted_target_mae']:>10.5f}"
              f"{row['loo_target_max']:>10.5f}")
    fit = report["rate_fit"]
    print("\nrate fit "
          f"r={fit['correlation']:.5f} residual-max={fit['max_abs_residual']:.5f} "
          f"LOO-max={fit['loo_max_abs_error']:.5f}")
    if "qstep_correlation" in fit:
        print(f"qstep r={fit['qstep_correlation']:.5f} "
              f"log2(qstep) r={fit['log2_qstep_correlation']:.5f}")
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")
        print(f"wrote {args.json_out}")


if __name__ == "__main__":
    main()
