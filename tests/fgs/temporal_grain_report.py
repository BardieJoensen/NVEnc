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

Use ``--plane u`` or ``--plane v`` to measure real-film chroma.  Flat/static
selection and intensity bands always come from source luma; the selected
32x32 luma blocks map exactly to 16x16 blocks in 4:2:0 chroma.  This keeps the
population fixed across planes instead of letting chroma noise select itself.
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
from source_fit import (  # noqa: E402
    blockwise, field_acf, production_flat_blocks, select_flat,
    static_flat_blocks,
)

FFMPEG = os.environ.get("FGS_FFMPEG", "/usr/local/bin/ffmpeg")
TEXTURE_AXES = ("h1", "h2", "v1", "v2")


def probe_size(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", path],
        check=True, capture_output=True, text=True)
    return tuple(int(value) for value in result.stdout.strip().split(",")[:2])


def decode_selected(path, width, height, indices, filmgrain=None, plane="y",
                    bits=10):
    """Decode exact display-order plane frames in the requested code domain."""
    pixel_formats = {
        8: ("gray", np.uint8),
        10: ("gray10le", np.uint16),
        12: ("gray12le", np.uint16),
        16: ("gray16le", np.uint16),
    }
    if bits not in pixel_formats:
        raise ValueError(f"unsupported decode depth {bits}")
    pixel_format, dtype = pixel_formats[bits]
    terms = "+".join(f"eq(n\\,{index})" for index in indices)
    # Reports are often driven by a shell loop whose stdin carries the next
    # corpus record.  FFmpeg's interactive command reader must not consume it.
    cmd = [FFMPEG, "-nostdin", "-v", "error"]
    if filmgrain is not None:
        cmd += ["-c:v", "libdav1d", "-filmgrain", str(filmgrain)]
    # Always extract the stored plane before selecting a gray output format.
    # Direct yuv->gray conversion expands limited-range samples; that changes
    # the flat-block population even when the requested nominal depth matches.
    filters = f"select='{terms}',extractplanes={plane}"
    cmd += ["-i", path, "-map", "0:v:0", "-vf", filters,
            "-fps_mode", "passthrough", "-pix_fmt", pixel_format,
            "-f", "rawvideo", "-"]
    result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    frame_bytes = width * height * np.dtype(dtype).itemsize
    expected = len(indices) * frame_bytes
    if len(result.stdout) != expected:
        raise RuntimeError(
            f"{path}: decoded {len(result.stdout) // frame_bytes} selected frames, "
            f"expected {len(indices)}")
    return {
        index: np.frombuffer(result.stdout, dtype, count=width * height,
                             offset=position * frame_bytes)
        .reshape(height, width).astype(np.float64)
        for position, index in enumerate(indices)
    }


def mean_sd(values):
    if not values:
        return {"mean": None, "sd": None}
    return {"mean": float(np.mean(values)), "sd": float(np.std(values))}


def distribution(values):
    finite = np.asarray([
        value for value in values if value is not None and np.isfinite(value)
    ], dtype=np.float64)
    if not finite.size:
        return {"mean": None, "sd": None, "p50": None,
                "p95": None, "max": None}
    return {
        "mean": float(np.mean(finite)),
        "sd": float(np.std(finite)),
        "p50": float(np.percentile(finite, 50)),
        "p95": float(np.percentile(finite, 95)),
        "max": float(np.max(finite)),
    }


def axis_mae(left, right):
    if left is None or right is None:
        return None
    return float(np.mean([
        abs(float(left[axis]) - float(right[axis]))
        for axis in TEXTURE_AXES
    ]))


def average_acf(rows):
    present = [row for row in rows if row is not None]
    if not present:
        return None
    return {
        key: float(np.mean([row[key] for row in present]))
        for key in present[0]
    }


def ratio_rows(rows, truth_rows):
    return mean_sd([
        (row["sigma"] if row is not None else 0.0) / truth["sigma"]
        for row, truth in zip(rows, truth_rows)
        if truth is not None and truth["sigma"] > 1e-9
    ])


def format_axis(row):
    if not row:
        return "       -       -       -"
    lag1 = 0.5 * (row["h1"] + row["v1"])
    lag2 = 0.5 * (row["h2"] + row["v2"])
    return f"{row['sigma']:>8.2f}{lag1:>8.3f}{lag2:>8.3f}"


def lag1(row):
    if not row:
        return float("nan")
    return 0.5 * (row["h1"] + row["v1"])


def masks_by_luma(frame, static, count, bits=16):
    """Split one source-derived mask into fixed normalised luma ranges."""
    grid = blockwise(frame)
    out = [[] for _ in range(count)]
    for by, bx in static:
        normalised = float(grid[by, bx].mean()) / float(1 << bits)
        index = min(count - 1, max(0, int(normalised * count)))
        out[index].append((by, bx))
    return out


def plane_geometry(width, height, plane):
    """Return decoded dimensions and block size for a 4:2:0 plane."""
    if plane == "y":
        return width, height, 32
    return (width + 1) // 2, (height + 1) // 2, 16


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--arm", action="append", default=[], required=True,
                        help="LABEL=encoded.mkv; repeatable")
    parser.add_argument("--plane", choices=("y", "u", "v"), default="y",
                        help="grain plane to measure; masks always come from luma")
    parser.add_argument(
        "--bits", type=int, choices=(8, 10, 12, 16), default=10,
        help="common decode/sample domain (default 10; match the analyzer input)")
    parser.add_argument("--frames", default="10,58,106,154,202,250",
                        help="comma-separated frame indices; n+1 is also decoded")
    parser.add_argument("--flat-fraction", type=float, default=0.10)
    parser.add_argument("--flat-selector", choices=("top10", "production"),
                        default="top10",
                        help="source spatial mask before temporal-static filtering; "
                             "top10 preserves historical reports")
    parser.add_argument("--static-lo", type=float, default=0.8)
    parser.add_argument("--static-hi", type=float, default=1.3)
    parser.add_argument("--luma-bins", type=int, default=8,
                        help="fixed normalised-luma bands in the JSON report (default 8)")
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
    plane_width, plane_height, plane_block_size = plane_geometry(
        width, height, args.plane)

    frames = [int(value) for value in args.frames.split(",")]
    indices = sorted(set(frames + [frame + 1 for frame in frames]))
    source_luma = decode_selected(
        args.source, width, height, indices, bits=args.bits)
    source = (source_luma if args.plane == "y" else decode_selected(
        args.source, plane_width, plane_height, indices, plane=args.plane,
        bits=args.bits))
    decoded = {
        label: {
            "on": decode_selected(path, plane_width, plane_height, indices,
                                  filmgrain=1, plane=args.plane, bits=args.bits),
            "off": decode_selected(path, plane_width, plane_height, indices,
                                   filmgrain=0, plane=args.plane, bits=args.bits),
        }
        for label, path in arms.items()
    }

    truth_rows = []
    masks = []
    luma_masks = []
    selected_counts = []
    for frame in frames:
        if args.flat_selector == "production":
            candidates, _, _ = production_flat_blocks(
                source_luma[frame], args.bits)
        else:
            candidates, _, _ = select_flat(
                source_luma[frame], args.bits, args.flat_fraction)
        static = static_flat_blocks(
            source_luma[frame], source_luma[frame + 1], candidates,
            lo=args.static_lo, hi=args.static_hi)
        if len(static) < 8:
            raise SystemExit(
                f"frame {frame}: only {len(static)} static flat blocks; choose a quieter frame")
        masks.append(static)
        luma_masks.append(masks_by_luma(
            source_luma[frame], static, args.luma_bins, args.bits))
        selected_counts.append(len(static))
        truth_rows.append(field_acf(
            (source[frame] - source[frame + 1]) / math.sqrt(2.0),
            static, detrend=False, bs=plane_block_size))

    report = {
        "source": os.path.abspath(args.source),
        "source_dimensions": [width, height],
        "dimensions": [plane_width, plane_height],
        "plane": args.plane,
        "bits": args.bits,
        "frames": frames,
        "flat_fraction": args.flat_fraction,
        "flat_selector": args.flat_selector,
        "static_ratio": [args.static_lo, args.static_hi],
        "static_blocks": selected_counts,
        "truth": average_acf(truth_rows),
        "arms": {},
        "luma_bins": [],
    }

    print(f"{os.path.basename(args.source)}: plane {args.plane} "
          f"{plane_width}x{plane_height}, frames {frames}")
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
                layer_rows[name].append(field_acf(
                    field, static, detrend=False, bs=plane_block_size))
            # Include both independent synthesis draws without changing the
            # mask or treating a temporal difference as a single-frame field.
            layer_rows["synth"].append(average_acf([
                field_acf(on[frame] - off[frame], static, detrend=False,
                          bs=plane_block_size),
                field_acf(on[frame + 1] - off[frame + 1], static,
                          detrend=False, bs=plane_block_size),
            ]))

        arm_report = {}
        for name, rows in layer_rows.items():
            axis = average_acf(rows)
            amplitude = ratio_rows(rows, truth_rows)
            arm_report[name] = {"axis": axis, "amplitude_ratio": amplitude}
            print(f"{(label + ' ' + name):<28}{format_axis(axis)}"
                  f"{amplitude['mean']:>9.3f}±{amplitude['sd']:<.3f}")
        frame_samples = []
        for index, frame in enumerate(frames):
            truth = truth_rows[index]
            layers = {}
            for name, rows in layer_rows.items():
                row = rows[index]
                layers[name] = {
                    "axis": row,
                    "amplitude_ratio": (
                        row["sigma"] / truth["sigma"]
                        if row is not None and truth is not None
                        and truth["sigma"] > 1e-9 else None),
                }
            frame_samples.append({
                "frame": frame,
                "static_blocks": selected_counts[index],
                "truth": truth,
                "layers": layers,
                "total_axis_mae_to_truth": axis_mae(
                    layers["total"]["axis"], truth),
            })
        arm_report["frame_samples"] = frame_samples
        arm_report["total_axis_error_to_truth"] = distribution([
            row["total_axis_mae_to_truth"] for row in frame_samples
        ])
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
        texture_error = arm_report["total_axis_error_to_truth"]
        print(f"{label + ' per-frame texture':<28}{'':>8}"
              f"mean={texture_error['mean']:.4f} "
              f"sd={texture_error['sd']:.4f} "
              f"p95={texture_error['p95']:.4f} "
              f"max={texture_error['max']:.4f}")

    # A whole-title aggregate can repeat the dark-film occupancy trap in a new
    # metric.  Report fixed luma ranges as a requirement, not an optional
    # diagnostic.  A bin needs at least eight blocks in at least two sampled
    # frames; anything thinner is recorded as absent rather than thresholded.
    print("\nfixed luma-band decomposition")
    print(f"{'range':<15}{'blocks':>8}{'truth s':>10}{'truth L1':>10}  "
          f"{'arm':<18}{'synth amp':>11}{'synth L1':>10}{'total amp':>11}{'total L1':>10}")
    for bin_index in range(args.luma_bins):
        eligible = [
            (frame, band)
            for frame, per_frame in zip(frames, luma_masks)
            if len((band := per_frame[bin_index])) >= 8
        ]
        if len(eligible) < 2:
            continue
        bin_truth = [
            field_acf((source[frame] - source[frame + 1]) / math.sqrt(2.0),
                      band, detrend=False, bs=plane_block_size)
            for frame, band in eligible
        ]
        truth_axis = average_acf(bin_truth)
        bin_record = {
            "range": [bin_index / args.luma_bins, (bin_index + 1) / args.luma_bins],
            "blocks": sum(len(band) for _, band in eligible),
            "frames": [frame for frame, _ in eligible],
            "truth": truth_axis,
            "arms": {},
        }
        range_label = (f"{bin_index / args.luma_bins:.3f}-"
                       f"{(bin_index + 1) / args.luma_bins:.3f}")
        first = True
        for label, layers in decoded.items():
            layer_rows = {"base": [], "synth": [], "total": []}
            for frame, band in eligible:
                on, off = layers["on"], layers["off"]
                layer_rows["base"].append(field_acf(
                    (off[frame] - off[frame + 1]) / math.sqrt(2.0),
                    band, detrend=False, bs=plane_block_size))
                layer_rows["synth"].append(average_acf([
                    field_acf(on[frame] - off[frame], band, detrend=False,
                              bs=plane_block_size),
                    field_acf(on[frame + 1] - off[frame + 1], band,
                              detrend=False, bs=plane_block_size),
                ]))
                layer_rows["total"].append(field_acf(
                    (on[frame] - on[frame + 1]) / math.sqrt(2.0),
                    band, detrend=False, bs=plane_block_size))
            measured = {}
            for name, rows in layer_rows.items():
                measured[name] = {
                    "axis": average_acf(rows),
                    "amplitude_ratio": ratio_rows(rows, bin_truth),
                }
            bin_record["arms"][label] = measured
            synth, total = measured["synth"], measured["total"]
            block_label = str(bin_record["blocks"]) if first else ""
            truth_sigma_label = f"{truth_axis['sigma']:.1f}" if first else ""
            truth_lag1_label = f"{lag1(truth_axis):.3f}" if first else ""
            print(f"{(range_label if first else ''):<15}"
                  f"{block_label:>8}"
                  f"{truth_sigma_label:>10}"
                  f"{truth_lag1_label:>10}  "
                  f"{label:<18}{synth['amplitude_ratio']['mean']:>11.3f}"
                  f"{lag1(synth['axis']):>10.3f}"
                  f"{total['amplitude_ratio']['mean']:>11.3f}"
                  f"{lag1(total['axis']):>10.3f}")
            first = False
        report["luma_bins"].append(bin_record)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")
        print(f"\nwrote {args.json_out}")


if __name__ == "__main__":
    main()
