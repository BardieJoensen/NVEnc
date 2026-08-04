#!/usr/bin/env python3
"""Compare source-fit and residual-fit admission reports without routing.

Both reports describe a grain table against temporal source evidence.  This
tool keeps two questions separate:

* does the source look film-like; and
* which table follows the measured source texture more closely?

The second question cannot answer the first.  Source fitting can reproduce
temporally persistent animation or compression structure more accurately than
residual fitting while still being the wrong thing to synthesize as film
grain.  Consequently this report always emits ``routing_verdict: null``.

Table intervals need not be identical.  Each table is compared against source
evidence gathered over its own intervals, then reduced with the report's
block-weighted title aggregate.  This is a title-level counterfactual, not a
paired-frame significance test.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import sourcefit_admission_report as admission


def load_report(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document.get("entries"), list):
        raise ValueError(f"{path}: missing admission-report entries")
    settings = document.get("settings", {})
    luma_bins = int(settings.get("luma_bins", 8))
    document["summary"] = admission.aggregate_entries(
        document["entries"], luma_bins)
    return document


def texture_errors(summary: dict) -> dict:
    model = summary.get("model_fidelity")
    if model is None:
        return {
            "lag1_abs": None,
            "lag2_abs": None,
            "lag_mean_abs": None,
            "acf_rmse": None,
            "spectrum_total_variation": None,
            "anisotropy_abs": None,
            "diagonal_acf_lag1_abs": None,
        }
    lag1 = abs(model["lag1_delta"])
    lag2 = abs(model["lag2_delta"])
    return {
        "lag1_abs": lag1,
        "lag2_abs": lag2,
        "lag_mean_abs": 0.5 * (lag1 + lag2),
        "acf_rmse": model["acf_rmse"],
        "spectrum_total_variation": model["spectrum_total_variation"],
        "anisotropy_abs": model["anisotropy_abs"],
        "diagonal_acf_lag1_abs": model["diagonal_acf_lag1_abs"],
    }


def improvements(source_errors: dict, residual_errors: dict) -> dict:
    result = {}
    for key in source_errors:
        source_value = source_errors[key]
        residual_value = residual_errors[key]
        result[key] = (
            None if source_value is None or residual_value is None
            else residual_value - source_value
        )
    return result


def compare_reports(source_fit: dict, residual_fit: dict) -> dict:
    if os.path.realpath(source_fit.get("source", "")) != os.path.realpath(
            residual_fit.get("source", "")):
        raise ValueError("reports do not describe the same source")
    for key in ("bits", "dimensions"):
        if source_fit.get(key) != residual_fit.get(key):
            raise ValueError(f"report {key} does not match")
    source_settings = source_fit.get("settings", {})
    residual_settings = residual_fit.get("settings", {})
    for key in (
            "flat_selector", "flat_fraction", "static_ratio",
            "minimum_pair_blocks", "minimum_band_blocks", "luma_bins",
            "texture_blocks_per_pair", "texture_blocks_per_pair_band"):
        if source_settings.get(key) != residual_settings.get(key):
            raise ValueError(f"report setting {key} does not match")

    source_summary = source_fit["summary"]
    residual_summary = residual_fit["summary"]
    source_errors = texture_errors(source_summary)
    residual_errors = texture_errors(residual_summary)
    return {
        "purpose": (
            "separate film-like evidence from source-vs-residual model "
            "fidelity; never a routing verdict"
        ),
        "source": os.path.realpath(source_fit["source"]),
        "pairing": "independent table intervals; block-weighted title aggregate",
        "coverage": {
            "source_fit": source_summary["coverage"],
            "residual_fit": residual_summary["coverage"],
        },
        "film_like_evidence": source_summary.get("film_like_evidence"),
        "source_fit": {
            "table": os.path.realpath(source_fit["table"]),
            "model_fidelity": source_summary.get("model_fidelity"),
            "texture_errors": source_errors,
        },
        "residual_fit": {
            "table": os.path.realpath(residual_fit["table"]),
            "model_fidelity": residual_summary.get("model_fidelity"),
            "texture_errors": residual_errors,
        },
        "residual_minus_source_error": improvements(
            source_errors, residual_errors),
        "routing_verdict": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-fit-report", required=True)
    parser.add_argument("--residual-fit-report", required=True)
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    source_path = Path(args.source_fit_report).resolve()
    residual_path = Path(args.residual_fit_report).resolve()
    for path in (source_path, residual_path):
        if not path.is_file():
            parser.error(f"missing report: {path}")
    try:
        report = compare_reports(
            load_report(source_path), load_report(residual_path))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))

    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.json_out:
        output = Path(args.json_out).resolve()
        temporary = output.with_suffix(output.suffix + ".partial")
        temporary.write_text(encoded, encoding="utf-8")
        os.replace(temporary, output)
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
