#!/usr/bin/env python3
"""Localise source-fit strength error across flat-block selection boundaries.

This compares the dense source-minus-base variance with a temporal ground truth
and a temporal clean-base leakage estimate on the same blocks.  It deliberately
reports three masks:

* the old top-decile temporal oracle used during source-fit development;
* production's exact spatial selector before motion-confidence filtering; and
* that production selector restricted to temporal-static blocks.

The last comparison answers whether a weak strength curve comes from the dense
estimator itself or from the block population supplied to it.  On temporal-static
blocks, consecutive-frame differencing also removes picture structure from the
clean base.  This separates actual time-varying base residue from static picture
or denoiser error that the spatial subtraction incorrectly calls retained grain.
The unfiltered production row is diagnostic only: motion contaminates temporal
truth there.

Usage:
  python3 tests/fgs/strength_selection_report.py \
      --source clip.mkv --clean-base clean.y4m \
      --frames 10,58,106,154,202,250,275 --json-out report.json
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from source_fit import (  # noqa: E402
    blockwise, detrend_blocks, production_flat_blocks, select_flat,
    static_flat_blocks,
)

FFMPEG = os.environ.get("FGS_FFMPEG", "/usr/local/bin/ffmpeg")
FFPROBE = os.environ.get("FGS_FFPROBE", "/usr/local/bin/ffprobe")


def probe_size(path):
    result = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", path],
        check=True, capture_output=True, text=True)
    return tuple(int(value) for value in result.stdout.strip().split(",")[:2])


def decode_y4m_selected(path, width, height, indices, bits):
    """Read selected Y4M luma planes without streaming every skipped payload.

    The clean-base corpus uses multi-gigabyte uncompressed Y4M files. FFmpeg's
    select filter still reads all intervening pixels; Y4M is seekable at the
    frame-payload level once each small, potentially variable-length `FRAME`
    header has been consumed.
    """
    wanted = set(indices)
    selected = {}
    dtype = np.uint8 if bits == 8 else np.dtype("<u2")
    itemsize = np.dtype(dtype).itemsize
    with open(path, "rb") as handle:
        header = handle.readline().decode("ascii", errors="strict").strip()
        if not header.startswith("YUV4MPEG2 "):
            raise RuntimeError(f"{path}: invalid Y4M header")
        width_match = re.search(r"(?:^| )W(\d+)(?: |$)", header)
        height_match = re.search(r"(?:^| )H(\d+)(?: |$)", header)
        chroma_match = re.search(r"(?:^| )C([^ ]+)(?: |$)", header)
        if not width_match or not height_match or not chroma_match:
            raise RuntimeError(f"{path}: incomplete Y4M header")
        file_size = (int(width_match.group(1)), int(height_match.group(1)))
        if file_size != (width, height):
            raise RuntimeError(f"{path}: Y4M dimensions {file_size} do not match probe")
        chroma = chroma_match.group(1).lower()
        if not chroma.startswith("420"):
            raise RuntimeError(f"{path}: only 4:2:0 Y4M is supported, got C{chroma}")
        header_bits_match = re.search(r"p(\d+)", chroma)
        header_bits = int(header_bits_match.group(1)) if header_bits_match else 8
        if header_bits != bits:
            raise RuntimeError(
                f"{path}: Y4M is {header_bits}-bit, requested {bits}-bit")

        luma_bytes = width * height * itemsize
        frame_bytes = width * height * 3 // 2 * itemsize
        for frame_number in range(max(indices) + 1):
            frame_header = handle.readline()
            if not frame_header.startswith(b"FRAME"):
                raise RuntimeError(
                    f"{path}: missing FRAME header at index {frame_number}")
            if frame_number in wanted:
                raw = handle.read(luma_bytes)
                if len(raw) != luma_bytes:
                    raise RuntimeError(f"{path}: truncated frame {frame_number}")
                selected[frame_number] = np.frombuffer(
                    raw, dtype, count=width * height).reshape(height, width)
                handle.seek(frame_bytes - luma_bytes, os.SEEK_CUR)
            else:
                handle.seek(frame_bytes, os.SEEK_CUR)
    if selected.keys() != wanted:
        missing = sorted(wanted.difference(selected))
        raise RuntimeError(f"{path}: selected frames missing: {missing}")
    return {index: selected[index] for index in indices}


def decode_selected(path, width, height, indices, bits, filmgrain=None):
    if filmgrain is None and os.path.splitext(path)[1].lower() == ".y4m":
        return decode_y4m_selected(path, width, height, indices, bits)
    terms = "+".join(f"eq(n\\,{index})" for index in indices)
    pix_fmt = "gray" if bits == 8 else f"gray{bits}le"
    cmd = [FFMPEG, "-v", "error"]
    if filmgrain is not None:
        cmd += ["-c:v", "libdav1d", "-filmgrain", str(filmgrain)]
    cmd += ["-i", path, "-map", "0:v:0",
            # extractplanes keeps the stored luma code values exact. Asking the
            # scaler for gray10le directly expands limited-range luma, which would
            # no longer match the direct Y4M reader.
            "-vf", f"select='{terms}',extractplanes=y", "-fps_mode", "passthrough",
            "-pix_fmt", pix_fmt, "-f", "rawvideo", "-"]
    result = subprocess.run(
        cmd,
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    dtype = np.uint8 if bits == 8 else np.uint16
    frame_bytes = width * height * np.dtype(dtype).itemsize
    if len(result.stdout) != len(indices) * frame_bytes:
        raise RuntimeError(
            f"{path}: decoded {len(result.stdout) // frame_bytes} frames, "
            f"expected {len(indices)}")
    return {
        index: np.frombuffer(result.stdout, dtype, count=width * height,
                             offset=position * frame_bytes).reshape(height, width)
        for position, index in enumerate(indices)
    }


def block_variances(frame):
    residual = detrend_blocks(blockwise(frame))
    return (residual * residual).mean(axis=(-2, -1))


def strength_variance_fields(source, next_source, clean, next_clean):
    """Calculate each full-frame block statistic once for all masks/bands."""
    return {
        "source": block_variances(source),
        "base": block_variances(clean),
        "truth": block_variances((source - next_source) / math.sqrt(2.0)),
        "leak": block_variances((clean - next_clean) / math.sqrt(2.0)),
    }


def measure_strength_fields(fields, blocks):
    if not blocks:
        return None
    rows = np.asarray([row for row, _col in blocks])
    cols = np.asarray([col for _row, col in blocks])
    source_var = fields["source"]
    base_var = fields["base"]
    temporal_var = fields["truth"]
    base_temporal_var = fields["leak"]
    missing = np.maximum(0.0, source_var[rows, cols] - base_var[rows, cols])
    truth = temporal_var[rows, cols]
    leak = base_temporal_var[rows, cols]
    missing_var = float(missing.mean())
    truth_var = float(truth.mean())
    leak_var = float(leak.mean())
    temporal_target_var = max(0.0, truth_var - leak_var)
    return {
        "blocks": len(blocks),
        "source_sigma": float(np.sqrt(source_var[rows, cols].mean())),
        "base_sigma": float(np.sqrt(base_var[rows, cols].mean())),
        "truth_sigma": float(np.sqrt(truth_var)),
        "missing_sigma": float(np.sqrt(missing_var)),
        "amplitude_ratio": float(np.sqrt(missing_var / truth_var)) if truth_var > 0 else None,
        "base_temporal_sigma": float(np.sqrt(leak_var)),
        "temporal_leak_ratio": float(np.sqrt(leak_var / truth_var)) if truth_var > 0 else None,
        "temporal_target_sigma": float(np.sqrt(temporal_target_var)),
        "temporal_target_ratio": (
            float(np.sqrt(temporal_target_var / truth_var)) if truth_var > 0 else None
        ),
        "missing_variance_sum": missing_var * len(blocks),
        "truth_variance_sum": truth_var * len(blocks),
        "base_temporal_variance_sum": leak_var * len(blocks),
    }


def measure(source, next_source, clean, next_clean, blocks):
    return measure_strength_fields(
        strength_variance_fields(source, next_source, clean, next_clean), blocks)


def aggregate(rows):
    present = [row for row in rows if row]
    missing = sum(row["missing_variance_sum"] for row in present)
    truth = sum(row["truth_variance_sum"] for row in present)
    leak = sum(row["base_temporal_variance_sum"] for row in present)
    blocks = sum(row["blocks"] for row in present)
    target = max(0.0, truth - leak)
    return {
        "blocks": blocks,
        "missing_sigma": float(np.sqrt(missing / blocks)) if blocks else None,
        "truth_sigma": float(np.sqrt(truth / blocks)) if blocks else None,
        "amplitude_ratio": float(np.sqrt(missing / truth)) if truth > 0 else None,
        "base_temporal_sigma": float(np.sqrt(leak / blocks)) if blocks else None,
        "temporal_leak_ratio": float(np.sqrt(leak / truth)) if truth > 0 else None,
        "temporal_target_sigma": float(np.sqrt(target / blocks)) if blocks else None,
        "temporal_target_ratio": float(np.sqrt(target / truth)) if truth > 0 else None,
    }


def encoded_variance_fields(source, next_source, encoded_on, next_encoded_on,
                            encoded_off, next_encoded_off):
    """Calculate decoded block fields once for all source-selected masks."""
    # Decoder buffers are uint16 for every >8-bit format. Differences must be
    # signed: grain-on minus grain-off legitimately crosses zero, and uint16
    # wrap turns a one-code negative delta into an apparent 65535-code grain.
    source = np.asarray(source, dtype=np.float64)
    next_source = np.asarray(next_source, dtype=np.float64)
    encoded_on = np.asarray(encoded_on, dtype=np.float64)
    next_encoded_on = np.asarray(next_encoded_on, dtype=np.float64)
    encoded_off = np.asarray(encoded_off, dtype=np.float64)
    next_encoded_off = np.asarray(next_encoded_off, dtype=np.float64)
    return {
        "truth": block_variances((source - next_source) / math.sqrt(2.0)),
        "base": block_variances(
            (encoded_off - next_encoded_off) / math.sqrt(2.0)),
        "synth": 0.5 * (
            block_variances(encoded_on - encoded_off)
            + block_variances(next_encoded_on - next_encoded_off)),
        "total": block_variances(
            (encoded_on - next_encoded_on) / math.sqrt(2.0)),
    }


def measure_encoded_fields(fields, blocks):
    if not blocks:
        return None
    rows = np.asarray([row for row, _col in blocks])
    cols = np.asarray([col for _row, col in blocks])

    def selected_mean(name):
        return float(fields[name][rows, cols].mean())

    truth_var = selected_mean("truth")
    base_var = selected_mean("base")
    synth_var = selected_mean("synth")
    total_var = selected_mean("total")
    target_var = max(0.0, truth_var - base_var)
    predicted_total_var = base_var + synth_var
    ratio = lambda value: float(np.sqrt(value / truth_var)) if truth_var > 0 else None
    return {
        "blocks": len(blocks),
        "post_base_sigma": float(np.sqrt(base_var)),
        "post_leak_ratio": ratio(base_var),
        "post_target_sigma": float(np.sqrt(target_var)),
        "post_target_ratio": ratio(target_var),
        "synth_sigma": float(np.sqrt(synth_var)),
        "synth_ratio": ratio(synth_var),
        "total_sigma": float(np.sqrt(total_var)),
        "total_ratio": ratio(total_var),
        "predicted_total_ratio": ratio(predicted_total_var),
        "closure_error": ratio(total_var) - ratio(predicted_total_var),
        "truth_variance_sum": truth_var * len(blocks),
        "post_base_variance_sum": base_var * len(blocks),
        "synth_variance_sum": synth_var * len(blocks),
        "total_variance_sum": total_var * len(blocks),
    }


def measure_encoded(source, next_source, encoded_on, next_encoded_on,
                    encoded_off, next_encoded_off, blocks):
    """Measure the post-encode variance closure on the same source mask."""
    return measure_encoded_fields(
        encoded_variance_fields(
            source, next_source, encoded_on, next_encoded_on,
            encoded_off, next_encoded_off),
        blocks)


def aggregate_encoded(rows):
    present = [row for row in rows if row]
    blocks = sum(row["blocks"] for row in present)
    truth = sum(row["truth_variance_sum"] for row in present)
    base = sum(row["post_base_variance_sum"] for row in present)
    synth = sum(row["synth_variance_sum"] for row in present)
    total = sum(row["total_variance_sum"] for row in present)
    target = max(0.0, truth - base)
    ratio = lambda value: float(np.sqrt(value / truth)) if truth > 0 else None
    predicted = ratio(base + synth)
    actual = ratio(total)
    return {
        "blocks": blocks,
        "post_leak_ratio": ratio(base),
        "post_target_ratio": ratio(target),
        "synth_ratio": ratio(synth),
        "total_ratio": actual,
        "predicted_total_ratio": predicted,
        "closure_error": actual - predicted,
    }


def luma_bands(frame, blocks, count, max_value):
    grid = blockwise(frame)
    out = [[] for _ in range(count)]
    for row, col in blocks:
        index = min(count - 1, max(0, int(grid[row, col].mean() / (max_value + 1) * count)))
        out[index].append((row, col))
    return out


def parse_encoded_arms(specs):
    """Parse repeatable LABEL=PATH encoded-arm arguments."""
    arms = {}
    for spec in specs:
        if "=" not in spec:
            raise ValueError(f"encoded arm must be LABEL=PATH, got: {spec}")
        label, path = spec.split("=", 1)
        label = label.strip()
        path = path.strip()
        if not label or not path:
            raise ValueError(f"encoded arm must be LABEL=PATH, got: {spec}")
        if label in arms:
            raise ValueError(f"duplicate encoded-arm label: {label}")
        arms[label] = path
    return arms


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--clean-base", required=True)
    parser.add_argument("--encoded", default="",
                        help="optional AV1 arm; adds exact libdav1d grain-on/off "
                             "post-encode closure on the same masks")
    parser.add_argument(
        "--encoded-arm", action="append", default=[], metavar="LABEL=PATH",
        help="repeatable labelled AV1 arms measured against one source/base "
             "analysis; cannot be combined with --encoded")
    parser.add_argument("--frames", default="10,58,106,154,202,250,275")
    parser.add_argument("--bits", type=int, default=10, choices=(8, 10, 12, 16))
    parser.add_argument("--flat-fraction", type=float, default=0.10)
    parser.add_argument("--static-lo", type=float, default=0.8)
    parser.add_argument("--static-hi", type=float, default=1.3)
    parser.add_argument("--luma-bins", type=int, default=8)
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    if args.encoded and args.encoded_arm:
        parser.error("--encoded and --encoded-arm cannot be combined")
    try:
        encoded_paths = (
            {"encoded": args.encoded} if args.encoded
            else parse_encoded_arms(args.encoded_arm)
        )
    except ValueError as error:
        parser.error(str(error))
    legacy_encoded = bool(args.encoded)

    size = probe_size(args.source)
    if probe_size(args.clean_base) != size:
        raise SystemExit("source and clean-base dimensions differ")
    for label, path in encoded_paths.items():
        if probe_size(path) != size:
            raise SystemExit(f"source and encoded arm {label} dimensions differ")
    width, height = size
    frames = [int(value) for value in args.frames.split(",")]
    source_indices = sorted(set(frames + [frame + 1 for frame in frames]))
    source_decoded = decode_selected(args.source, width, height, source_indices, args.bits)
    clean_decoded = decode_selected(
        args.clean_base, width, height, source_indices, args.bits)
    encoded_decoded = {
        label: {
            "on": decode_selected(
                path, width, height, source_indices, args.bits, filmgrain=1),
            "off": decode_selected(
                path, width, height, source_indices, args.bits, filmgrain=0),
        }
        for label, path in encoded_paths.items()
    }

    report = {
        "source": os.path.abspath(args.source),
        "clean_base": os.path.abspath(args.clean_base),
        "encoded": os.path.abspath(args.encoded) if args.encoded else None,
        "dimensions": [width, height],
        "bits": args.bits,
        "frames": frames,
        "static_ratio": [args.static_lo, args.static_hi],
        "rows": [],
        "luma_bins": [],
    }
    if args.encoded_arm:
        report["encoded_arms"] = {
            label: os.path.abspath(path) for label, path in encoded_paths.items()
        }
    by_mask = {name: [] for name in ("top10_static", "production_spatial", "production_static")}
    encoded_by_arm = {
        label: {name: [] for name in by_mask} for label in encoded_decoded
    }
    per_frame_masks = {name: [] for name in ("top10_static", "production_static")}
    per_frame_strength_fields = {}
    per_frame_encoded_fields = {}

    print(f"{os.path.basename(args.source)}: {width}x{height} {args.bits}-bit")
    print(f"{'frame':>6} {'mask':<20}{'blocks':>8}{'src s':>9}{'base s':>9}"
          f"{'truth s':>9}{'spatial':>10}{'leak':>9}{'target':>9}")
    for frame_number in frames:
        source = source_decoded[frame_number].astype(np.float64)
        next_source = source_decoded[frame_number + 1].astype(np.float64)
        clean = clean_decoded[frame_number].astype(np.float64)
        next_clean = clean_decoded[frame_number + 1].astype(np.float64)
        strength_fields = strength_variance_fields(
            source, next_source, clean, next_clean)
        per_frame_strength_fields[frame_number] = strength_fields
        encoded_fields = {
            label: encoded_variance_fields(
                source, next_source,
                decoded["on"][frame_number], decoded["on"][frame_number + 1],
                decoded["off"][frame_number], decoded["off"][frame_number + 1])
            for label, decoded in encoded_decoded.items()
        }
        per_frame_encoded_fields[frame_number] = encoded_fields
        top, _score, _sigma = select_flat(source, args.bits, args.flat_fraction)
        production, _score, _sigma = production_flat_blocks(source, args.bits)
        masks = {
            "top10_static": static_flat_blocks(
                source, next_source, top, lo=args.static_lo, hi=args.static_hi),
            "production_spatial": production,
            "production_static": static_flat_blocks(
                source, next_source, production, lo=args.static_lo, hi=args.static_hi),
        }
        for name in per_frame_masks:
            per_frame_masks[name].append(masks[name])
        frame_record = {"frame": frame_number, "masks": {}}
        for name, blocks in masks.items():
            row = measure_strength_fields(strength_fields, blocks)
            encoded_rows = {}
            for label, fields in encoded_fields.items():
                encoded_rows[label] = measure_encoded_fields(fields, blocks)
                encoded_by_arm[label][name].append(encoded_rows[label])
            if legacy_encoded:
                row["encoded"] = encoded_rows["encoded"]
            elif encoded_rows:
                row["encoded_arms"] = encoded_rows
            by_mask[name].append(row)
            frame_record["masks"][name] = row
            print(f"{frame_number:>6} {name:<20}{row['blocks']:>8}"
                  f"{row['source_sigma']:>9.2f}{row['base_sigma']:>9.2f}"
                  f"{row['truth_sigma']:>9.2f}{row['amplitude_ratio']:>10.3f}"
                  f"{row['temporal_leak_ratio']:>9.3f}"
                  f"{row['temporal_target_ratio']:>9.3f}")
        report["rows"].append(frame_record)

    report["aggregate"] = {name: aggregate(rows) for name, rows in by_mask.items()}
    if legacy_encoded:
        report["encoded_aggregate"] = {
            name: aggregate_encoded(rows)
            for name, rows in encoded_by_arm["encoded"].items()
        }
    elif encoded_by_arm:
        report["encoded_aggregates"] = {
            label: {name: aggregate_encoded(rows) for name, rows in by_mask_rows.items()}
            for label, by_mask_rows in encoded_by_arm.items()
        }
    print("\nvariance-weighted aggregate")
    for name, row in report["aggregate"].items():
        print(f"{name:<20}{row['blocks']:>8} blocks  "
              f"spatial {row['amplitude_ratio']:.3f}  "
              f"temporal leak {row['temporal_leak_ratio']:.3f}  "
              f"target {row['temporal_target_ratio']:.3f}")
    encoded_aggregates = (
        {"encoded": report["encoded_aggregate"]} if legacy_encoded
        else report.get("encoded_aggregates", {})
    )
    for label, aggregates in encoded_aggregates.items():
        heading = "post-encode variance closure"
        print(f"\n{heading}" if legacy_encoded else f"\n{heading}: {label}")
        print(f"{'mask':<20}{'blocks':>8}{'leak':>9}{'target':>9}"
              f"{'synth':>9}{'total':>9}{'closure':>10}")
        for name, row in aggregates.items():
            print(f"{name:<20}{row['blocks']:>8}{row['post_leak_ratio']:>9.3f}"
                  f"{row['post_target_ratio']:>9.3f}{row['synth_ratio']:>9.3f}"
                  f"{row['total_ratio']:>9.3f}{row['closure_error']:>+10.3f}")

    max_value = (1 << args.bits) - 1
    report["luma_bins"] = {name: [] for name in per_frame_masks}
    print("\nwithin-luma mask comparison")
    print(f"{'range':<15}{'mask':<20}{'blocks':>8}{'truth s':>10}"
          f"{'spatial':>10}{'leak':>10}{'target':>10}")
    for bin_index in range(args.luma_bins):
        for name, frame_masks in per_frame_masks.items():
            rows = []
            for frame_number, blocks in zip(frames, frame_masks):
                source = source_decoded[frame_number].astype(np.float64)
                next_source = source_decoded[frame_number + 1].astype(np.float64)
                band = luma_bands(source, blocks, args.luma_bins, max_value)[bin_index]
                if len(band) >= 8:
                    measured = measure_strength_fields(
                        per_frame_strength_fields[frame_number], band)
                    encoded_rows = {}
                    for label, fields in per_frame_encoded_fields[frame_number].items():
                        encoded_rows[label] = measure_encoded_fields(fields, band)
                    if legacy_encoded:
                        measured["encoded"] = encoded_rows["encoded"]
                    elif encoded_rows:
                        measured["encoded_arms"] = encoded_rows
                    rows.append(measured)
            if not rows:
                continue
            row = aggregate(rows)
            limits = [bin_index / args.luma_bins, (bin_index + 1) / args.luma_bins]
            record = {"range": limits, **row}
            if legacy_encoded:
                record["encoded"] = aggregate_encoded(
                    [measured["encoded"] for measured in rows])
            elif encoded_decoded:
                record["encoded_arms"] = {
                    label: aggregate_encoded(
                        [measured["encoded_arms"][label] for measured in rows])
                    for label in encoded_decoded
                }
            report["luma_bins"][name].append(record)
            print(f"{limits[0]:.3f}-{limits[1]:.3f} {name:<20}{row['blocks']:>8}"
                  f"{row['truth_sigma']:>10.2f}{row['amplitude_ratio']:>10.3f}"
                  f"{row['temporal_leak_ratio']:>10.3f}"
                  f"{row['temporal_target_ratio']:>10.3f}")

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")
        print(f"\nwrote {args.json_out}")


if __name__ == "__main__":
    main()
