#!/usr/bin/env python3
"""Summarise the source-texture / strength-provenance experiment."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import sys


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from integrated_architecture import write_json  # noqa: E402
import strength_provenance_gate as gate  # noqa: E402


PLANES = ("y", "u", "v")
ALL_ARMS = (*gate.REFERENCE_ARMS, *gate.EXPERIMENT_ARMS)


def mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def arm_stats(records: list[dict], arm: str) -> dict:
    present = [record["summary"]["arms"].get(arm) for record in records]
    present = [record for record in present if record is not None]
    return {
        "scenes": len(present),
        "amplitude_mean": mean([record["total_amplitude"] for record in present]),
        "amplitude_mae": mean([
            abs(record["total_amplitude"] - 1.0) for record in present]),
        "texture_mae": mean([record["texture_mae"] for record in present]),
        "texture_p95_mean": mean([record["texture_p95"] for record in present]),
        "base_amplitude_mean": mean([
            record["base_amplitude"] for record in present]),
        "synth_amplitude_mean": mean([
            record["synth_amplitude"] for record in present]),
        "legacy_mean_of_ratios": mean([
            record["mean_of_ratios"]["total"] for record in present]),
        "jensen_gap_mean": mean([
            record["jensen_gap"]["total"] for record in present]),
    }


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
            "amplitude_mae": statistics.mean(abs(value - 1.0) for value in amplitudes),
            "occupancy_weighted_amplitude": (
                sum(value["amplitude"] * value["blocks"] for value in values)
                / blocks),
            "occupancy_weighted_mae": (
                sum(abs(value["amplitude"] - 1.0) * value["blocks"]
                    for value in values) / blocks),
        })
    return result


def band_rows(manifest: dict) -> list[dict]:
    rows = []
    for title in manifest["titles"].values():
        if not title["temporal_coverage"]["y"]["title_gradable"]:
            continue
        for record in title["grain_reports"]["y"]:
            if not record["summary"]["gradable"]:
                continue
            document = json.loads(
                Path(record["identity"]["path"]).read_text(encoding="utf-8"))
            for band in document["luma_bins"]:
                if not band["blocks"]:
                    continue
                for arm in ALL_ARMS:
                    measured = band["arms"][arm]["total"]["amplitude_ratio"]
                    rows.append({
                        "range": band["range"],
                        "arm": arm,
                        "blocks": band["blocks"],
                        "amplitude": measured["ratio_of_means"],
                    })
    return rows


def summarize(manifest: dict) -> dict:
    if manifest.get("measurement_version") != gate.MEASUREMENT_VERSION:
        raise RuntimeError(
            f"measurement version is {manifest.get('measurement_version')!r}; "
            f"expected {gate.MEASUREMENT_VERSION!r}")
    corpus_records = {
        plane: {arm: [] for arm in ALL_ARMS} for plane in PLANES}
    per_title = {}
    for name, title in manifest["titles"].items():
        per_title[name] = {"tail": title["tail"], "planes": {}}
        for plane in PLANES:
            coverage = title.get("temporal_coverage", {}).get(plane)
            if coverage is None:
                raise RuntimeError(f"{name}/{plane}: missing temporal coverage")
            records = [
                record for record in title["grain_reports"][plane]
                if record["summary"]["gradable"]
            ]
            eligible = coverage["title_gradable"]
            per_title[name]["planes"][plane] = {
                "decision_eligible": eligible,
                "arms": {arm: arm_stats(records, arm) for arm in ALL_ARMS},
            }
            if eligible:
                for arm in ALL_ARMS:
                    corpus_records[plane][arm].extend(records)

    byte_totals = {}
    for arm in gate.REFERENCE_ARMS:
        byte_totals[arm] = sum(
            title["references"][arm]["encoded"]["size"]
            for title in manifest["titles"].values())
    for arm in gate.NEW_ARMS:
        byte_totals[arm] = sum(
            title["arms"][arm]["encoded"]["size"]
            for title in manifest["titles"].values())
    source_bytes = byte_totals["source"]

    texture_isolation = {}
    for arm in gate.EXPERIMENT_ARMS:
        rows = [title["arms"][arm]["stream_texture_isolation"]
                for title in manifest["titles"].values()]
        jointly = sum(row["jointly_grained_frames"] for row in rows)
        identical = sum(row["all_texture_fields_identical_frames"] for row in rows)
        texture_isolation[arm] = {
            "titles": len(rows),
            "fully_isolated_titles": sum(row["fully_isolated"] for row in rows),
            "grain_presence_mismatch_frames": sum(
                row["grain_presence_mismatch_frames"] for row in rows),
            "jointly_grained_frames": jointly,
            "all_texture_fields_identical_frames": identical,
            "identical_fraction": identical / jointly if jointly else None,
        }

    return {
        "measurement_version": gate.MEASUREMENT_VERSION,
        "titles": len(manifest["titles"]),
        "per_title": per_title,
        "corpus": {
            plane: {
                arm: arm_stats(records, arm)
                for arm, records in arms.items()
            } for plane, arms in corpus_records.items()
        },
        "luma_bands": aggregate_bands(band_rows(manifest)),
        "bytes": {
            "totals": byte_totals,
            "percent_delta_from_source": {
                arm: 100.0 * (value - source_bytes) / source_bytes
                for arm, value in byte_totals.items()
            },
        },
        "isolation": {
            "no_hook_control_passed_titles": sum(
                title["control_isolation"]["passed"]
                for title in manifest["titles"].values()),
            "experiment_base_identical_titles": {
                arm: sum(title["arms"][arm]["base_vs_control_identical"]
                         for title in manifest["titles"].values())
                for arm in gate.EXPERIMENT_ARMS
            },
            "stream_texture": texture_isolation,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--work", default="/media/merged-storage/media/test-encodes/"
        "sourcefit-strength-provenance-20260809")
    args = parser.parse_args()
    work = Path(args.work).resolve()
    manifest_path = work / "manifest.json"
    if not manifest_path.is_file():
        parser.error(f"missing experiment manifest: {manifest_path}")
    summary = summarize(json.loads(manifest_path.read_text(encoding="utf-8")))
    output = work / "summary.json"
    write_json(output, summary)
    print(f"summary: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
