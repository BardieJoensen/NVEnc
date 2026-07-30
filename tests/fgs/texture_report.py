#!/usr/bin/env python3
"""Generate a grain-texture report from aligned raw YUV420 inputs."""

import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import texture_metrics  # noqa: E402


def parse_arm(spec):
    label, separator, paths = spec.partition("=")
    grain_on, comma, grain_off = paths.partition(",")
    if not separator or not comma or not label or not grain_on or not grain_off:
        raise argparse.ArgumentTypeError(
            "arm must be LABEL=GRAIN_ON.yuv,GRAIN_OFF.yuv")
    return label, (grain_on, grain_off)


def parse_bands(spec):
    try:
        return tuple(int(value) for value in spec.split(","))
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "luma bands must be comma-separated integers") from error


def print_summary(report):
    print("== amplitude-independent grain texture ==")
    selection = report["flat_selection"]
    for name, mask in selection["masks"].items():
        print(
            f"{name:<9} {mask['selected_blocks']:>7} blocks "
            f"(score <= {mask['structure_score_threshold']:.4f})")
    for comparison_name, masks in report["comparisons"].items():
        print(f"\n{comparison_name}")
        for mask_name, result in masks.items():
            aggregate = result["occupancy_weighted"]
            print(
                f"  {mask_name:<9} coverage={result['occupancy_coverage']:.3f} "
                f"spectrum-TV={aggregate['spectrum_total_variation']:.4f} "
                f"ACF-RMSE={aggregate['acf_rmse']:.4f} "
                f"anisotropy={aggregate['anisotropy_abs_delta']:.4f} "
                f"flicker={aggregate['temporal_spread_abs_delta']:.4f}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-raw", required=True)
    parser.add_argument("--clean-raw", required=True)
    parser.add_argument(
        "--arm", action="append", type=parse_arm, required=True,
        help="LABEL=grain-on.yuv,grain-off.yuv; repeatable")
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument("--bits", type=int, choices=(8, 10), required=True)
    parser.add_argument("--first-frame", type=int, default=0)
    parser.add_argument("--frames", type=int)
    parser.add_argument(
        "--luma-bands", type=parse_bands,
        default=texture_metrics.DEFAULT_LUMA_BANDS)
    parser.add_argument("--minimum-blocks", type=int, default=32)
    parser.add_argument("--title", default=None)
    parser.add_argument("--build", default=None)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    arms = dict(args.arm)
    if len(arms) != len(args.arm):
        parser.error("arm labels must be unique")
    report = texture_metrics.analyze_raw_texture(
        args.source_raw, args.clean_raw, arms,
        args.width, args.height, args.bits,
        first_frame=args.first_frame, frame_count=args.frames,
        luma_bands=args.luma_bands, minimum_blocks=args.minimum_blocks)
    report["created_utc"] = datetime.datetime.now(
        datetime.timezone.utc).isoformat()
    report["identity"] = {
        key: value for key, value in (
            ("title", args.title), ("build", args.build))
        if value is not None
    }
    output = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w") as destination:
        json.dump(report, destination, indent=2, sort_keys=True)
        destination.write("\n")
    print_summary(report)
    print(f"\nreport: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
