#!/usr/bin/env python3
"""Summarise the provenance-correct tail architecture gate reproducibly.

The gate's raw reports deliberately retain per-scene and per-plane detail.
This script produces decision tables without hiding occupancy or coverage:

* only titles with at least three gradable scenes enter corpus grain means;
* luma-band results include both unweighted and block-occupancy-weighted means;
* chroma U and V remain separate;
* bytes are summed, not averaged as percentages; and
* base safety is scored directly between grain-disabled arms as well as against
  the source reel.  The latter contains grain and must not be mistaken for a
  clean-base oracle.

VMAF work is cached by ``review_score.py`` using input manifests.  The summary
itself contains no media and is safe to regenerate.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import sys


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import general_content_gate as common  # noqa: E402
import review_score  # noqa: E402
from integrated_architecture import write_json  # noqa: E402
from tail_architecture_gate import ARMS, MEASUREMENT_VERSION  # noqa: E402


PLANES = ("y", "u", "v")
FGS_ARMS = ("production", "candidate-control", "source", "response")
DELTA_PAIRS = (
    ("production", "candidate-control", "build-drift"),
    ("candidate-control", "source", "source-fit"),
    ("source", "response", "response-closure"),
)


def mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def absolute_error(value: float, target: float = 1.0) -> float:
    return abs(value - target)


def arm_stats(records: list[dict], arm: str) -> dict:
    present = [record["summary"]["arms"].get(arm) for record in records]
    present = [record for record in present if record is not None]
    return {
        "scenes": len(present),
        "amplitude_mean": mean([record["total_amplitude"] for record in present]),
        "amplitude_mae": mean([
            absolute_error(record["total_amplitude"]) for record in present]),
        "texture_mae": mean([record["texture_mae"] for record in present]),
        "base_amplitude_mean": mean([
            record["base_amplitude"] for record in present]),
        "synth_amplitude_mean": mean([
            record["synth_amplitude"] for record in present]),
    }


def gradable_records(title: dict, plane: str) -> list[dict]:
    return [
        record for record in title.get("grain_reports", {}).get(plane, [])
        if record["summary"]["gradable"]
    ]


def aggregate_bands(rows: list[dict]) -> list[dict]:
    grouped: dict[tuple[float, float, str], list[dict]] = {}
    for row in rows:
        grouped.setdefault(
            (row["range"][0], row["range"][1], row["arm"]), []).append(row)
    result = []
    for (lo, hi, arm), values in sorted(grouped.items()):
        blocks = sum(value["blocks"] for value in values)
        amplitudes = [value["amplitude"] for value in values]
        result.append({
            "range": [lo, hi],
            "arm": arm,
            "scene_bands": len(values),
            "blocks": blocks,
            "amplitude_mean": statistics.mean(amplitudes),
            "amplitude_mae": statistics.mean(map(absolute_error, amplitudes)),
            "occupancy_weighted_amplitude": sum(
                value["amplitude"] * value["blocks"] for value in values) / blocks,
            "occupancy_weighted_mae": sum(
                absolute_error(value["amplitude"]) * value["blocks"]
                for value in values) / blocks,
        })
    return result


def load_band_rows(manifest: dict) -> list[dict]:
    rows = []
    for title in manifest["titles"].values():
        if not title["temporal_coverage"]["y"]["title_gradable"]:
            continue
        for record in title["grain_reports"]["y"]:
            if not record["summary"]["gradable"]:
                continue
            document = json.loads(Path(
                record["identity"]["path"]).read_text(encoding="utf-8"))
            for band in document["luma_bins"]:
                for arm in ("production", "source", "response"):
                    rows.append({
                        "range": band["range"],
                        "arm": arm,
                        "blocks": band["blocks"],
                        "amplitude": band["arms"][arm]["total"][
                            "amplitude_ratio"]["ratio_of_means"],
                    })
    return rows


def source_reference_scores(rows: list[dict]) -> dict:
    result = {}
    for arm in ARMS:
        selected = [row for row in rows if row["arm"] == arm]
        result[arm] = {
            "titles": len(selected),
            "vmaf_mean": mean([row["vmaf"] for row in selected]),
            "vmaf_p1_mean": mean([row["vmaf_p1"] for row in selected]),
            "psnr_y_mean": mean([row["psnr_y"] for row in selected]),
            "ssim_mean": mean([row["ssim"] for row in selected]),
        }
    return result


def score_base_deltas(
    manifest: dict, metric_dir: Path, ffmpeg: Path, ffprobe: Path,
) -> list[dict]:
    review_score.FFMPEG = str(ffmpeg)
    review_score.FFPROBE = str(ffprobe)
    rows = []
    for title_name, title in manifest["titles"].items():
        for left, right, kind in DELTA_PAIRS:
            left_record, right_record = title["arms"][left], title["arms"][right]
            if left_record["base_pixel_sha256"] == right_record["base_pixel_sha256"]:
                rows.append({
                    "title": title_name,
                    "left": left,
                    "right": right,
                    "kind": kind,
                    "pixel_identical": True,
                    "frames": 600,
                })
                continue
            left_path = Path(left_record["base"]["outputs"][0]["path"])
            right_path = Path(right_record["base"]["outputs"][0]["path"])
            row = common.score_pair(
                left_path, right_path, title_name, f"{left}-vs-{right}",
                kind, metric_dir, full=False)
            row.update({
                "left": left,
                "right": right,
                "pixel_identical": False,
            })
            rows.append(row)
    return rows


def summarize(manifest: dict, base_scores: list[dict], base_deltas: list[dict]) -> dict:
    if manifest.get("measurement_version") != MEASUREMENT_VERSION:
        raise RuntimeError(
            f"measurement version is {manifest.get('measurement_version')!r}, "
            f"expected {MEASUREMENT_VERSION!r}")
    coverage = {}
    plane_corpus: dict[str, dict[str, list[dict]]] = {
        plane: {arm: [] for arm in ARMS} for plane in PLANES
    }
    per_title = {}
    for title_name, title in manifest["titles"].items():
        coverage[title_name] = title["temporal_coverage"]
        per_title[title_name] = {
            "tail": title["tail"],
            "production_selector": title["production_selector"],
            "planes": {},
        }
        for plane in PLANES:
            records = gradable_records(title, plane)
            eligible = title["temporal_coverage"][plane]["title_gradable"]
            per_title[title_name]["planes"][plane] = {
                "decision_eligible": eligible,
                "arms": {arm: arm_stats(records, arm) for arm in ARMS},
            }
            if eligible:
                for arm in ARMS:
                    plane_corpus[plane][arm].extend(records)

    corpus = {
        plane: {
            arm: arm_stats(records, arm)
            for arm, records in arms.items()
        }
        for plane, arms in plane_corpus.items()
    }

    byte_totals = {
        arm: sum(title["arms"][arm]["encoded"]["size"]
                 for title in manifest["titles"].values())
        for arm in ARMS
    }
    plain_bytes = byte_totals["plain"]
    production_bytes = byte_totals["production"]
    byte_summary = {
        "titles": len(manifest["titles"]),
        "totals": byte_totals,
        "percent_of_plain": {
            arm: 100.0 * value / plain_bytes for arm, value in byte_totals.items()},
        "percent_delta_from_production": {
            arm: 100.0 * (value - production_bytes) / production_bytes
            for arm, value in byte_totals.items()},
    }

    delta_groups = {}
    for _, _, kind in DELTA_PAIRS:
        selected = [row for row in base_deltas if row["kind"] == kind]
        scored = [row for row in selected if not row["pixel_identical"]]
        delta_groups[kind] = {
            "titles": len(selected),
            "pixel_identical": sum(row["pixel_identical"] for row in selected),
            "vmaf_mean": mean([row["vmaf"] for row in scored]),
            "vmaf_p1_mean": mean([row["vmaf_p1"] for row in scored]),
            "psnr_y_mean": mean([row["psnr_y"] for row in scored]),
            "ssim_mean": mean([row["ssim"] for row in scored]),
        }

    return {
        "measurement_version": MEASUREMENT_VERSION,
        "coverage": coverage,
        "per_title": per_title,
        "corpus": corpus,
        "luma_bands": aggregate_bands(load_band_rows(manifest)),
        "bytes": byte_summary,
        "base_quality": {
            "warning": (
                "source-reference scores include source grain; use direct base "
                "deltas to judge architecture-induced base changes"),
            "source_reference": source_reference_scores(base_scores),
            "direct_delta_summary": delta_groups,
            "direct_delta_rows": base_deltas,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--work", default="/media/merged-storage/media/test-encodes/"
        "sourcefit-tail-gate-20260809")
    parser.add_argument("--ffmpeg", default="/usr/local/bin/ffmpeg")
    parser.add_argument("--ffprobe", default="/usr/local/bin/ffprobe")
    args = parser.parse_args()

    work = Path(args.work).resolve()
    manifest_path = work / "manifest.json"
    base_scores_path = work / "metrics" / "base-scores.json"
    for path in (manifest_path, base_scores_path):
        if not path.is_file():
            parser.error(f"missing gate output: {path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    base_scores = json.loads(base_scores_path.read_text(encoding="utf-8"))
    expected_scores = len(manifest["titles"]) * len(ARMS)
    if len(base_scores) != expected_scores:
        raise RuntimeError(
            f"base score table has {len(base_scores)} rows; expected {expected_scores}")

    base_deltas = score_base_deltas(
        manifest, work / "metrics" / "base-deltas",
        Path(args.ffmpeg).resolve(), Path(args.ffprobe).resolve())
    write_json(work / "metrics" / "base-deltas.json", base_deltas)
    summary = summarize(manifest, base_scores, base_deltas)
    output = work / "summary.json"
    write_json(output, summary)
    print(f"summary: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
