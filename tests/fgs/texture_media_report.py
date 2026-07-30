#!/usr/bin/env python3
"""Decode aligned media and generate an amplitude-independent texture report."""

import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import texture_metrics  # noqa: E402
import texture_report  # noqa: E402


def run(argv):
    result = subprocess.run(argv, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(argv)}\n"
            f"{result.stdout[-2000:]}\n{result.stderr[-2000:]}")
    return {
        "argv": argv,
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-2000:],
    }


def parse_arm(spec):
    label, separator, path = spec.partition("=")
    if not separator or not label or not path:
        raise argparse.ArgumentTypeError("arm must be LABEL=encoded-media")
    return label, path


def parse_pair(spec):
    bad, separator, good = spec.partition(",")
    if not separator or not bad or not good:
        raise argparse.ArgumentTypeError(
            "labelled negative must be BAD_LABEL,GOOD_LABEL")
    return bad, good


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def probe(path):
    result = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,pix_fmt",
        "-of", "json", path,
    ], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"cannot probe {path}: {result.stderr.strip()}")
    streams = json.loads(result.stdout).get("streams", [])
    if not streams:
        raise RuntimeError(f"no video stream in {path}")
    return streams[0]


def decode(path, output, pixel_format, frames, filmgrain=None):
    argv = ["ffmpeg", "-v", "error", "-y"]
    if filmgrain is not None:
        argv.extend(["-c:v", "libdav1d", "-filmgrain", str(filmgrain)])
    argv.extend(["-i", path, "-map", "0:v:0", "-frames:v", str(frames),
                 "-pix_fmt", pixel_format, "-f", "rawvideo", output])
    return run(argv)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument(
        "--clean", required=True,
        help="aligned, identically denoised source used as the reference guide")
    parser.add_argument(
        "--arm", action="append", type=parse_arm, required=True,
        help="LABEL=encoded AV1 media; repeatable")
    parser.add_argument("--frames", type=int, default=24)
    parser.add_argument("--first-frame", type=int, default=0)
    parser.add_argument("--minimum-blocks", type=int, default=32)
    parser.add_argument("--title", default=None)
    parser.add_argument("--build", default=None)
    parser.add_argument("--output", required=True)
    parser.add_argument("--work", default=None)
    parser.add_argument("--keep-work", action="store_true")
    parser.add_argument(
        "--labelled-negative", type=parse_pair,
        help="BAD_LABEL,GOOD_LABEL; require the known texture change to separate")
    parser.add_argument("--minimum-spectrum-tv", type=float, default=0.01)
    parser.add_argument("--minimum-acf-rmse", type=float, default=0.01)
    parser.add_argument("--minimum-occupancy-coverage", type=float, default=0.50)
    parser.add_argument(
        "--require-common-base", action="store_true",
        help="fail unless every arm's grain-off decode is byte-identical")
    args = parser.parse_args()

    arms = dict(args.arm)
    if len(arms) != len(args.arm):
        parser.error("arm labels must be unique")
    if args.labelled_negative:
        missing = [
            label for label in args.labelled_negative if label not in arms]
        if missing:
            parser.error(
                f"labelled-negative arm not supplied: {','.join(missing)}")
    stream = probe(args.source)
    width, height = int(stream["width"]), int(stream["height"])
    pixel_format = stream.get("pix_fmt", "")
    bits = 10 if ("10" in pixel_format or "p010" in pixel_format) else 8
    target_pixel_format = "yuv420p10le" if bits == 10 else "yuv420p"
    for label, path in (("clean", args.clean), *arms.items()):
        candidate = probe(path)
        if (int(candidate["width"]), int(candidate["height"])) != (width, height):
            parser.error(f"{label} geometry differs from the source")

    total_frames = args.first_frame + args.frames
    work = args.work or tempfile.mkdtemp(prefix="fgs-texture-media-")
    os.makedirs(work, exist_ok=True)
    source_raw = os.path.join(work, "source.yuv")
    clean_raw = os.path.join(work, "clean.yuv")
    commands = {
        "decode_source": decode(
            args.source, source_raw, target_pixel_format, total_frames),
        "decode_clean": decode(
            args.clean, clean_raw, target_pixel_format, total_frames),
    }
    raw_arms = {}
    try:
        for label, path in arms.items():
            grain_on = os.path.join(work, f"{label}-on.yuv")
            grain_off = os.path.join(work, f"{label}-off.yuv")
            commands[f"decode_{label}_on"] = decode(
                path, grain_on, target_pixel_format, total_frames, 1)
            commands[f"decode_{label}_off"] = decode(
                path, grain_off, target_pixel_format, total_frames, 0)
            raw_arms[label] = (grain_on, grain_off)
        report = texture_metrics.analyze_raw_texture(
            source_raw, clean_raw, raw_arms, width, height, bits,
            first_frame=args.first_frame, frame_count=args.frames,
            minimum_blocks=args.minimum_blocks)
        report["created_utc"] = datetime.datetime.now(
            datetime.timezone.utc).isoformat()
        report["identity"] = {
            "title": args.title,
            "build": args.build,
            "source": args.source,
            "clean_reference": args.clean,
            "arms": arms,
        }
        report["commands"] = commands
        base_hashes = {
            label: sha256(grain_off)
            for label, (_, grain_off) in raw_arms.items()
        }
        common_base = len(set(base_hashes.values())) == 1
        report["common_synthesis_base"] = {
            "identical": common_base,
            "grain_off_sha256": base_hashes,
            "required": args.require_common_base,
        }
        exit_code = 0
        if args.labelled_negative:
            bad, good = args.labelled_negative
            gate = texture_metrics.labelled_negative_gate(
                report, bad, good,
                args.minimum_spectrum_tv, args.minimum_acf_rmse,
                args.minimum_occupancy_coverage)
            report["labelled_negative_gate"] = gate
            exit_code = 0 if gate["status"] == "PASS" else 1
        if args.require_common_base and not common_base:
            exit_code = 1
        output = os.path.abspath(args.output)
        os.makedirs(os.path.dirname(output), exist_ok=True)
        with open(output, "w") as destination:
            json.dump(report, destination, indent=2, sort_keys=True)
            destination.write("\n")
        texture_report.print_summary(report)
        if args.labelled_negative:
            print(
                f"\nlabelled negative: "
                f"{report['labelled_negative_gate']['status']}")
        print(f"common synthesis base: {common_base}")
        print(f"\nreport: {output}")
        if args.keep_work:
            print(f"work: {work}")
        return exit_code
    finally:
        if not args.keep_work and args.work is None:
            shutil.rmtree(work)


if __name__ == "__main__":
    sys.exit(main())
