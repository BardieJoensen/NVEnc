#!/usr/bin/env python3
"""Join degrain's exact render signals to the calibrated temporal-lag probe.

This is a mechanism-localisation tool, not a new quality score.  It asks
whether blocks with directional temporal lag are predictable from signals the
motion separator already has before rendering:

* SAD relative to the render threshold;
* the normalised temporal-reference mix;
* nearest-reference motion magnitude;
* disagreement between the one- and two-frame vectors; and
* disagreement with neighbouring motion vectors.

The input trace is opt-in and output-invariant.  Build NVEncC with the trace
support, then run a short raw-output window whose centre is SOURCE_FRAME:

    NVENC_DEGRAIN_BLOCK_TRACE=1 \
    NVENC_DEGRAIN_BLOCK_TRACE_FRAME=SOURCE_FRAME \
      nvencc --avsw --codec raw --trim START:END \
        --av1-film-grain denoise=auto,chroma=auto,denoiser=motion,modelsrc=on \
        --log-level info -i SOURCE -o BASE.y4m > TRACE.log 2>&1

The trace requires an exact frame deliberately: accidentally enabling it on a
whole encode must not produce gigabytes of logs.  START should be at least two
frames before SOURCE_FRAME so both causal references exist.

Pass a JSON manifest:

    {"samples": [{
      "label": "shining-f123", "group": "The Shining",
      "trace": "TRACE.log", "source": "SOURCE.mkv", "source_frame": 123,
      "base": "BASE.y4m", "base_frame": 2
    }]}

The report bins the calibrated previous-minus-next projection by each feature
and reports "safest fraction" curves.  Those curves only localise a predictor;
they do not predict a hybrid output because overlapping motion windows and the
spatial fallback have not yet been rendered.
"""
import argparse
import json
import math
import os
import subprocess

import numpy as np

from review_score import FFMPEG
from temporal_drag import ProjectionAccumulator


TRACE_SUMMARY = '{"type":"degrain_block_trace_summary"'
TRACE_BLOCK = '{"type":"degrain_block_trace"'
RISK_FEATURES = (
    "reference_mix",
    "nearest_sad_ratio",
    "far_sad_ratio",
    "mv_magnitude",
    "temporal_vector_error",
    "spatial_vector_error",
    "neighbor_invalid_fraction",
    "screen_motion",
)


def _json_from_log_line(line, marker):
    start = line.find(marker)
    if start < 0:
        return None
    value, _ = json.JSONDecoder().raw_decode(line[start:])
    return value


def parse_trace(path, expected_frame=None):
    summary = None
    blocks = {}
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            row = _json_from_log_line(line, TRACE_SUMMARY)
            if row is not None:
                if summary is not None:
                    raise RuntimeError(f"{path}: multiple block-trace summaries")
                summary = row
                continue
            row = _json_from_log_line(line, TRACE_BLOCK)
            if row is None:
                continue
            block = int(row["block"])
            if block in blocks:
                raise RuntimeError(f"{path}: duplicate block {block}")
            blocks[block] = row
    if summary is None:
        raise RuntimeError(f"{path}: no degrain block-trace summary")
    if int(summary.get("version", -1)) != 1:
        raise RuntimeError(f"{path}: unsupported trace version")
    frame = int(summary["frame"])
    if expected_frame is not None and frame != expected_frame:
        raise RuntimeError(
            f"{path}: traced frame {frame}, expected {expected_frame}")
    layout = summary["layout"]
    stride = int(summary["stride"])
    expected_blocks = (int(layout["blocks"]) + stride - 1) // stride
    if len(blocks) != expected_blocks:
        raise RuntimeError(
            f"{path}: {len(blocks)} blocks, expected {expected_blocks}")
    for block, row in blocks.items():
        if int(row["frame"]) != frame:
            raise RuntimeError(f"{path}: block {block} has another frame")
        if int(row.get("version", -1)) != 1:
            raise RuntimeError(f"{path}: block {block} has another version")
    return summary, blocks


def _probe_dimensions(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height",
         "-of", "json", path],
        capture_output=True, text=True, check=True)
    streams = json.loads(result.stdout).get("streams", [])
    if len(streams) != 1:
        raise RuntimeError(f"{path}: expected exactly one video stream")
    return int(streams[0]["width"]), int(streams[0]["height"])


def decode_luma(path, indices):
    """Decode exact zero-based frames as 10-bit luma, preserving order."""
    indices = [int(index) for index in indices]
    if not indices or min(indices) < 0 or len(set(indices)) != len(indices):
        raise ValueError("frame indices must be unique non-negative integers")
    width, height = _probe_dimensions(path)
    select = "+".join(f"eq(n\\,{index})" for index in indices)
    result = subprocess.run(
        [FFMPEG, "-v", "error", "-nostdin", "-i", path,
         "-vf", f"select={select}", "-fps_mode", "passthrough",
         "-pix_fmt", "gray10le", "-f", "rawvideo", "-"],
        capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"{path}: decode failed: {result.stderr.decode(errors='replace')[-2000:]}")
    frame_bytes = width * height * 2
    expected = frame_bytes * len(indices)
    if len(result.stdout) != expected:
        raise RuntimeError(
            f"{path}: decoded {len(result.stdout)} bytes, expected {expected}")
    frames = np.frombuffer(result.stdout, np.uint16).reshape(
        len(indices), height, width).astype(np.float32)
    return frames, width, height


def _reference(row, side, delta):
    for reference in row["refs"]:
        if reference["side"] == side and int(reference["delta"]) == delta:
            return reference
    return None


def derive_trace_features(summary, blocks):
    """Return one render-time feature row per traced motion block."""
    layout = summary["layout"]
    blocks_x = int(layout["blocks_x"])
    blocks_y = int(layout["blocks_y"])
    pel = max(1, int(layout["pel"]))
    sad_limit = max(1, int(summary["sad_limit"]))
    grid = {(int(row["block_x"]), int(row["block_y"])): row
            for row in blocks.values()}
    output = {}
    for block, row in blocks.items():
        bx, by = int(row["block_x"]), int(row["block_y"])
        nearest = _reference(row, "prev", 1)
        far = _reference(row, "prev", 2)
        nearest_selected = nearest is not None and bool(nearest["selected"])
        far_selected = far is not None and bool(far["selected"])

        spatial_differences = []
        selected_neighbors = 0
        available_neighbors = 0
        if nearest_selected:
            for nx, ny in ((bx - 1, by), (bx + 1, by),
                           (bx, by - 1), (bx, by + 1)):
                if nx < 0 or ny < 0 or nx >= blocks_x or ny >= blocks_y:
                    continue
                neighbor = grid.get((nx, ny))
                if neighbor is None:
                    continue
                available_neighbors += 1
                neighbor_ref = _reference(neighbor, "prev", 1)
                if neighbor_ref is None or not bool(neighbor_ref["selected"]):
                    continue
                selected_neighbors += 1
                spatial_differences.append(math.hypot(
                    int(nearest["dx"]) - int(neighbor_ref["dx"]),
                    int(nearest["dy"]) - int(neighbor_ref["dy"])) / pel)

        temporal_error = float("nan")
        if nearest_selected and far_selected:
            temporal_error = math.hypot(
                int(far["dx"]) - 2 * int(nearest["dx"]),
                int(far["dy"]) - 2 * int(nearest["dy"])) / pel
        output[block] = {
            "reference_mix": float(row["reference_mix"]),
            "nearest_sad_ratio": (
                float(nearest["sad"]) / sad_limit if nearest is not None
                else float("nan")),
            "far_sad_ratio": (
                float(far["sad"]) / sad_limit if far is not None
                else float("nan")),
            "mv_magnitude": (
                math.hypot(int(nearest["dx"]), int(nearest["dy"])) / pel
                if nearest_selected else float("nan")),
            "temporal_vector_error": temporal_error,
            "spatial_vector_error": (
                float(np.median(spatial_differences))
                if spatial_differences else float("nan")),
            "neighbor_invalid_fraction": (
                1.0 - selected_neighbors / available_neighbors
                if available_neighbors else float("nan")),
        }
    return output


def collect_sample(spec, moving_threshold=64.0):
    source_frame = int(spec["source_frame"])
    base_frame = int(spec.get("base_frame", 2))
    summary, blocks = parse_trace(spec["trace"], source_frame)
    features = derive_trace_features(summary, blocks)
    source, width, height = decode_luma(
        spec["source"], [source_frame - 1, source_frame, source_frame + 1])
    base, base_width, base_height = decode_luma(spec["base"], [base_frame])
    if (base_width, base_height) != (width, height):
        raise RuntimeError(
            f"{spec['label']}: source is {width}x{height}, base is "
            f"{base_width}x{base_height}")

    layout = summary["layout"]
    block_size = int(layout["block_size"])
    step = int(layout["step"])
    overlap = int(layout["overlap"])
    margin = max(0, (block_size - step) // 2)
    arrays = {name: [] for name in (
        "error", "previous", "following", "screen_motion", *RISK_FEATURES[:-1])}
    for block in sorted(blocks):
        row = blocks[block]
        x0 = int(row["block_x"]) * step + margin
        y0 = int(row["block_y"]) * step + margin
        x1 = min(width, x0 + step)
        y1 = min(height, y0 + step)
        if x0 >= x1 or y0 >= y1:
            continue
        current = float(source[1, y0:y1, x0:x1].mean())
        previous = float(source[0, y0:y1, x0:x1].mean()) - current
        following = float(source[2, y0:y1, x0:x1].mean()) - current
        error = float(base[0, y0:y1, x0:x1].mean()) - current
        arrays["error"].append(error)
        arrays["previous"].append(previous)
        arrays["following"].append(following)
        arrays["screen_motion"].append(max(abs(previous), abs(following)))
        for name, value in features[block].items():
            arrays[name].append(value)
    arrays = {name: np.asarray(value, dtype=np.float64)
              for name, value in arrays.items()}
    arrays["moving"] = arrays["screen_motion"] >= moving_threshold
    return {
        "label": spec["label"],
        "group": spec.get("group", spec["label"]),
        "source_frame": source_frame,
        "base_frame": base_frame,
        "width": width,
        "height": height,
        "blocks": len(arrays["error"]),
        "trace_stride": int(summary["stride"]),
        "layout": layout,
        "arrays": arrays,
    }


def _projection(data, mask=None):
    accumulator = ProjectionAccumulator()
    if mask is None:
        mask = np.ones(len(data["error"]), dtype=bool)
    if np.count_nonzero(mask):
        accumulator.add(data["error"], data["previous"],
                        data["following"], mask)
    return accumulator.result()


def _concat(samples):
    names = samples[0]["arrays"].keys()
    return {name: np.concatenate([sample["arrays"][name]
                                  for sample in samples])
            for name in names}


def _feature_report(data, name, base_mask):
    values = data[name]
    finite = base_mask & np.isfinite(values)
    coverage = int(np.count_nonzero(finite))
    report = {
        "coverage": coverage,
        "coverage_fraction": coverage / max(1, int(np.count_nonzero(base_mask))),
        "quantiles": [],
        "safest_fraction": [],
    }
    if coverage < 20:
        return report
    selected_values = values[finite]
    edges = np.unique(np.quantile(selected_values, np.linspace(0.0, 1.0, 6)))
    for index in range(len(edges) - 1):
        low, high = float(edges[index]), float(edges[index + 1])
        mask = finite & (values >= low)
        mask &= values <= high if index == len(edges) - 2 else values < high
        report["quantiles"].append({
            "low": low,
            "high": high,
            **_projection(data, mask),
        })
    finite_indices = np.flatnonzero(finite)
    order = finite_indices[np.argsort(values[finite_indices], kind="stable")]
    for fraction in (0.25, 0.50, 0.75, 0.90):
        count = max(1, min(len(order) - 1, int(round(len(order) * fraction))))
        keep = np.zeros(len(values), dtype=bool)
        keep[order[:count]] = True
        reject = finite & ~keep
        report["safest_fraction"].append({
            "fraction": fraction,
            "maximum_risk": float(values[order[count - 1]]),
            "kept": _projection(data, keep),
            "rejected": _projection(data, reject),
        })
    return report


def analyze_dataset(data):
    moving = data["moving"].astype(bool)
    return {
        "blocks": len(data["error"]),
        "moving_blocks": int(np.count_nonzero(moving)),
        "projection_all": _projection(data),
        "projection_moving": _projection(data, moving),
        "features_on_moving_blocks": {
            name: _feature_report(data, name, moving)
            for name in RISK_FEATURES
        },
    }


def build_report(manifest, moving_threshold=64.0):
    specs = manifest.get("samples", [])
    if not specs:
        raise ValueError("manifest has no samples")
    samples = [collect_sample(spec, moving_threshold) for spec in specs]
    groups = {}
    for sample in samples:
        groups.setdefault(sample["group"], []).append(sample)
    return {
        "question": (
            "Does directional temporal lag concentrate in motion blocks that "
            "the existing render-time signals identify as low confidence?"),
        "falsifiable_prediction": (
            "A usable fallback signal must put materially more lag in its "
            "rejected high-risk blocks than in the kept low-risk blocks, in "
            "the same direction across real titles."),
        "moving_threshold_10bit": moving_threshold,
        "samples": [
            {key: value for key, value in sample.items() if key != "arrays"}
            for sample in samples
        ],
        "overall": analyze_dataset(_concat(samples)),
        "groups": {
            group: analyze_dataset(_concat(group_samples))
            for group, group_samples in groups.items()
        },
        "interpretation_limit": (
            "Safest-fraction rows classify existing motion-base blocks; they "
            "do not predict the pixels or bitrate of an overlap-aware spatial "
            "fallback. A behavior change requires a rendered A/B."),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("--moving-threshold", type=float, default=64.0)
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    with open(args.manifest, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    report = build_report(manifest, args.moving_threshold)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        temporary = f"{args.output}.tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            handle.write(rendered)
            handle.write("\n")
        os.replace(temporary, args.output)
    print(rendered)


if __name__ == "__main__":
    main()
