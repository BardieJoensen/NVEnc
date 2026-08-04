#!/usr/bin/env python3
"""Compare exact chroma-emission audits across two encoder arms.

``chroma_emission_audit.py`` measures source truth, grain-disabled base,
normative synthesis and played output on adjacent-frame static blocks.  This
tool aggregates those reports without mixing them with the spatial texture
statistics used by ``temporal_texture_report.py``.

Ratios remain useful for closure, but can become very large when chroma grain
is nearly absent.  Every ratio is therefore accompanied by its absolute error
in 8-bit code-value sigma.  A report whose normative replay differs from
dav1d is rejected instead of being silently included.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


DEFAULT_TITLES = (
    "Casino", "Interstellar", "Scarface", "Taxi_Driver",
    "The_Deer_Hunter", "The_Shining",
)


def _ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0.0:
        raise ValueError("amplitude denominator must be positive")
    return numerator / denominator


def _row(title: str, plane: str, record: dict, bits: int,
         luma_range: list[float] | None = None) -> dict:
    sigma = record["sigma"]
    depth_scale = float(1 << (bits - 8))
    row = {
        "title": title,
        "plane": plane,
        "blocks": int(record["blocks"]),
        "synth_ratio": _ratio(float(sigma["actual"]), float(sigma["target"])),
        "played_ratio": _ratio(float(sigma["played"]), float(sigma["truth"])),
        "synth_sigma_error_8bit": (
            float(sigma["actual"]) - float(sigma["target"])) / depth_scale,
        "played_sigma_error_8bit": (
            float(sigma["played"]) - float(sigma["truth"])) / depth_scale,
    }
    if luma_range is not None:
        row["luma_range"] = list(luma_range)
    return row


def _summary(rows: list[dict], field: str, centre: float = 0.0) -> dict:
    errors = [float(row[field]) - centre for row in rows]
    weights = [int(row["blocks"]) for row in rows]
    if not errors or sum(weights) <= 0:
        raise ValueError(f"no usable rows for {field}")
    return {
        "count": len(errors),
        "bias": sum(errors) / len(errors),
        "mae": sum(abs(error) for error in errors) / len(errors),
        "max_abs": max(abs(error) for error in errors),
        "block_weighted_rmse": math.sqrt(
            sum(weight * error * error for weight, error in zip(weights, errors))
            / sum(weights)),
    }


def summarize(rows: list[dict]) -> dict:
    return {
        "synth_ratio_error": _summary(rows, "synth_ratio", 1.0),
        "played_ratio_error": _summary(rows, "played_ratio", 1.0),
        "synth_sigma_error_8bit": _summary(
            rows, "synth_sigma_error_8bit"),
        "played_sigma_error_8bit": _summary(
            rows, "played_sigma_error_8bit"),
    }


def load_arm(root: Path, titles: tuple[str, ...], plane: str,
             filename: str) -> dict:
    title_rows = []
    band_rows = []
    reports = []
    for title in titles:
        path = root / title / filename.format(plane=plane)
        with path.open(encoding="utf-8") as handle:
            report = json.load(handle)
        if report.get("plane") != plane:
            raise ValueError(
                f"{path}: expected plane {plane}, got {report.get('plane')}")
        aggregate = report["aggregate"]
        if int(aggregate["pixel_mismatches"]) != 0:
            raise ValueError(
                f"{path}: normative replay has "
                f"{aggregate['pixel_mismatches']} dav1d pixel mismatches")
        if report.get("table_models_match_stream") is False:
            raise ValueError(f"{path}: table model does not match stream")
        bits = int(report["bits"])
        title_rows.append(_row(title, plane, aggregate, bits))
        for band in report["luma_bins"]:
            if int(band["blocks"]) <= 0:
                continue
            band_rows.append(_row(
                title, plane, band, bits, luma_range=band["range"]))
        reports.append(str(path.resolve()))
    return {
        "reports": reports,
        "titles": title_rows,
        "luma_bands": band_rows,
        "title_summary": summarize(title_rows),
        "band_summary": summarize(band_rows),
    }


def compare(control: dict, candidate: dict) -> dict:
    result = {}
    for level in ("title_summary", "band_summary"):
        result[level] = {}
        for metric in control[level]:
            result[level][metric] = {
                field: candidate[level][metric][field]
                - control[level][metric][field]
                for field in ("bias", "mae", "max_abs", "block_weighted_rmse")
            }
    return result


def print_plane(plane: str, control: dict, candidate: dict) -> None:
    print(f"\nplane {plane.upper()}")
    print(f"{'level / metric':<34}{'control':>11}{'candidate':>12}{'delta':>11}")
    for level, label in (("title_summary", "title"),
                         ("band_summary", "luma-band")):
        for metric in ("played_ratio_error", "played_sigma_error_8bit"):
            old = control[level][metric]["mae"]
            new = candidate[level][metric]["mae"]
            print(f"{label + ' ' + metric:<34}{old:>11.5f}{new:>12.5f}"
                  f"{new - old:>+11.5f}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-dir", required=True)
    parser.add_argument("--candidate-dir", required=True)
    parser.add_argument(
        "--titles", default=",".join(DEFAULT_TITLES),
        help="comma-separated title directory names")
    parser.add_argument("--planes", default="u,v")
    parser.add_argument(
        "--filename", default="emission-{plane}.json",
        help="per-title filename template; {plane} is replaced with u or v")
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    titles = tuple(value.strip() for value in args.titles.split(",")
                   if value.strip())
    planes = tuple(value.strip().lower() for value in args.planes.split(",")
                   if value.strip())
    if not titles:
        parser.error("at least one title is required")
    if not planes or any(plane not in ("u", "v") for plane in planes):
        parser.error("--planes must contain u and/or v")
    if "{plane}" not in args.filename:
        parser.error("--filename must contain {plane}")

    control_root = Path(args.control_dir).resolve()
    candidate_root = Path(args.candidate_dir).resolve()
    output = {
        "control_dir": str(control_root),
        "candidate_dir": str(candidate_root),
        "titles": list(titles),
        "filename": args.filename,
        "planes": {},
    }
    for plane in planes:
        control = load_arm(control_root, titles, plane, args.filename)
        candidate = load_arm(candidate_root, titles, plane, args.filename)
        output["planes"][plane] = {
            "control": control,
            "candidate": candidate,
            "candidate_minus_control": compare(control, candidate),
        }
        print_plane(plane, control, candidate)

    if args.json_out:
        path = Path(args.json_out)
        path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
