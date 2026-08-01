#!/usr/bin/env python3
"""Measure played-out grain without whole-frame HF-sigma's ringing bias.

The source has no grain-free reference, but time supplies one on static flat
blocks: film grain is independent frame to frame, while the picture is not, so

    (frame[n] - frame[n + 1]) / sqrt(2)

is one grain field with the picture removed.  Apply the same operation to a
grain-on and grain-off decode to split an encoded result into:

    base   temporal residue in the coded grain-off base
    synth  grain-on minus grain-off (decoder synthesis only)
    total  temporal residue in the played grain-on output

All arms use the source's flat/static block mask.  This reports amplitude and
lag-1/lag-2 texture together; it deliberately does not call campaign.hf_sigma.

Usage:
  python3 tests/fgs/temporal_grain_report.py \
      --source clip.mkv \
      --arm bilateral=bilateral.mkv --arm motion=motion.mkv \
      --frames 10,58,106,154,202,250 --json-out report.json
"""
import argparse
import json
import math
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from source_fit import blockwise, field_acf, select_flat, static_flat_blocks  # noqa: E402

FFMPEG = os.environ.get("FGS_FFMPEG", "/usr/local/bin/ffmpeg")


def probe_size(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", path],
        check=True, capture_output=True, text=True)
    return tuple(int(value) for value in result.stdout.strip().split(",")[:2])


def decode_selected(path, width, height, indices, filmgrain=None):
    """Decode exact display-order frames as 16-bit luma, preserving code ratios."""
    terms = "+".join(f"eq(n\\,{index})" for index in indices)
    cmd = [FFMPEG, "-v", "error"]
    if filmgrain is not None:
        cmd += ["-c:v", "libdav1d", "-filmgrain", str(filmgrain)]
    cmd += ["-i", path, "-map", "0:v:0", "-vf", f"select='{terms}'",
            "-fps_mode", "passthrough", "-pix_fmt", "gray16le",
            "-f", "rawvideo", "-"]
    result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    frame_bytes = width * height * 2
    expected = len(indices) * frame_bytes
    if len(result.stdout) != expected:
        raise RuntimeError(
            f"{path}: decoded {len(result.stdout) // frame_bytes} selected frames, "
            f"expected {len(indices)}")
    return {
        index: np.frombuffer(result.stdout, np.uint16, count=width * height,
                             offset=position * frame_bytes)
        .reshape(height, width).astype(np.float64)
        for position, index in enumerate(indices)
    }


def mean_sd(values):
    if not values:
        return {"mean": None, "sd": None}
    return {"mean": float(np.mean(values)), "sd": float(np.std(values))}


def average_acf(rows):
    if not rows:
        return None
    return {key: float(np.mean([row[key] for row in rows])) for key in rows[0]}


def ratio_rows(rows, truth_rows):
    return mean_sd([
        row["sigma"] / truth["sigma"]
        for row, truth in zip(rows, truth_rows) if truth["sigma"] > 1e-9
    ])


def format_axis(row):
    if not row:
        return "       -       -       -"
    lag1 = 0.5 * (row["h1"] + row["v1"])
    lag2 = 0.5 * (row["h2"] + row["v2"])
    return f"{row['sigma']:>8.2f}{lag1:>8.3f}{lag2:>8.3f}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--arm", action="append", default=[], required=True,
                        help="LABEL=encoded.mkv; repeatable")
    parser.add_argument("--frames", default="10,58,106,154,202,250",
                        help="comma-separated frame indices; n+1 is also decoded")
    parser.add_argument("--flat-fraction", type=float, default=0.10)
    parser.add_argument("--static-lo", type=float, default=0.8)
    parser.add_argument("--static-hi", type=float, default=1.3)
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    arms = {}
    for item in args.arm:
        label, separator, path = item.partition("=")
        if not separator or not label or not os.path.exists(path):
            raise SystemExit(f"invalid or missing --arm {item!r}")
        arms[label] = path

    width, height = probe_size(args.source)
    for label, path in arms.items():
        if probe_size(path) != (width, height):
            raise SystemExit(f"{label}: dimensions do not match the source")

    frames = [int(value) for value in args.frames.split(",")]
    indices = sorted(set(frames + [frame + 1 for frame in frames]))
    source = decode_selected(args.source, width, height, indices)
    decoded = {
        label: {
            "on": decode_selected(path, width, height, indices, filmgrain=1),
            "off": decode_selected(path, width, height, indices, filmgrain=0),
        }
        for label, path in arms.items()
    }

    truth_rows = []
    masks = []
    selected_counts = []
    for frame in frames:
        candidates, _, _ = select_flat(source[frame], 16, args.flat_fraction)
        static = static_flat_blocks(
            source[frame], source[frame + 1], candidates,
            lo=args.static_lo, hi=args.static_hi)
        if len(static) < 8:
            raise SystemExit(
                f"frame {frame}: only {len(static)} static flat blocks; choose a quieter frame")
        masks.append(static)
        selected_counts.append(len(static))
        truth_rows.append(field_acf(
            (source[frame] - source[frame + 1]) / math.sqrt(2.0),
            static, detrend=False))

    report = {
        "source": os.path.abspath(args.source),
        "dimensions": [width, height],
        "frames": frames,
        "flat_fraction": args.flat_fraction,
        "static_ratio": [args.static_lo, args.static_hi],
        "static_blocks": selected_counts,
        "truth": average_acf(truth_rows),
        "arms": {},
    }

    print(f"{os.path.basename(args.source)}: {width}x{height}, frames {frames}")
    print(f"static flat blocks per frame: {selected_counts}\n")
    print(f"{'layer':<28}{'sigma':>8}{'lag-1':>8}{'lag-2':>8}{'amp/truth':>12}")
    print(f"{'source temporal truth':<28}{format_axis(report['truth'])}{1.0:>12.3f}")

    for label, layers in decoded.items():
        layer_rows = {"base": [], "synth": [], "total": []}
        for frame, static in zip(frames, masks):
            on = layers["on"]
            off = layers["off"]
            fields = {
                "base": (off[frame] - off[frame + 1]) / math.sqrt(2.0),
                "total": (on[frame] - on[frame + 1]) / math.sqrt(2.0),
            }
            for name, field in fields.items():
                layer_rows[name].append(field_acf(field, static, detrend=False))
            # Include both independent synthesis draws without changing the
            # mask or treating a temporal difference as a single-frame field.
            layer_rows["synth"].append(average_acf([
                field_acf(on[frame] - off[frame], static, detrend=False),
                field_acf(on[frame + 1] - off[frame + 1], static, detrend=False),
            ]))

        arm_report = {}
        for name, rows in layer_rows.items():
            axis = average_acf(rows)
            amplitude = ratio_rows(rows, truth_rows)
            arm_report[name] = {"axis": axis, "amplitude_ratio": amplitude}
            print(f"{(label + ' ' + name):<28}{format_axis(axis)}"
                  f"{amplitude['mean']:>9.3f}±{amplitude['sd']:<.3f}")
        # The independent base and synthesised layers should predict the total
        # amplitude.  Reporting the closure error catches frame/mask mistakes.
        predicted = math.sqrt(
            arm_report["base"]["amplitude_ratio"]["mean"] ** 2
            + arm_report["synth"]["amplitude_ratio"]["mean"] ** 2)
        actual = arm_report["total"]["amplitude_ratio"]["mean"]
        arm_report["variance_closure"] = {
            "predicted_total": predicted,
            "measured_total": actual,
            "error": actual - predicted,
        }
        report["arms"][label] = arm_report
        print(f"{label + ' variance closure':<28}{'':>24}{actual - predicted:>+12.3f}")

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")
        print(f"\nwrote {args.json_out}")


if __name__ == "__main__":
    main()
