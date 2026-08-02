#!/usr/bin/env python3
"""Strict scoring helpers and the motion-review scorer.

The original review was scored with a scratchpad script.  This checked-in
version makes the run reproducible and treats frame count/alignment as a gate:
paired inputs must expose the same ordered timestamps, every decoder must exit
successfully, and cached JSON is reused only when its input manifest matches.
"""
import argparse
import json
import os
import shlex
import statistics
import subprocess
from pathlib import Path


FFMPEG = os.environ.get("FFMPEG_BIN", "ffmpeg")
FFPROBE = os.environ.get("FFPROBE_BIN", "ffprobe")
VMAF = os.environ.get(
    "VMAF_BIN",
    os.path.expanduser("~/git-repos/vmaf/libvmaf/build/tools/vmaf"))
FFVSHIP_IMG = os.environ.get(
    "FFVSHIP_IMAGE", "docker-apps/video-metrics:cuda13.3.0")
WORK = "/media/merged-storage/media/test-encodes/review-vmaf-20260802"
BLIND = "/media/merged-storage/media/test-encodes/sourcefit-review-20260802/blind"
CORPUS = "/media/merged-storage/media/test-encodes/sourcefit-corpus-20260801"
MAX_FRAMES = 288
# Compatibility for the first metric-sensitivity script.  New code should use
# aligned_frame_count() and score the returned count, not assume this many exist.
FRAMES = MAX_FRAMES
_PROBE_CACHE = {}


def run(argv, timeout=1800):
    result = subprocess.run(
        argv, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        command = shlex.join(str(value) for value in argv)
        raise RuntimeError(
            f"command failed ({result.returncode}): {command}\n"
            f"{result.stderr[-4000:]}")
    return result


def shell(command, timeout=1800):
    """Compatibility wrapper for older experiment scripts."""
    return run(["bash", "-c", command], timeout=timeout)


def pct(sorted_values, percentile):
    if not sorted_values:
        raise ValueError("cannot take a percentile of an empty sequence")
    index = int(len(sorted_values) * percentile / 100.0)
    return sorted_values[min(len(sorted_values) - 1, max(0, index))]


def _decoder_args(codec, filmgrain=0):
    return (["-c:v", "libdav1d", "-filmgrain", str(filmgrain)]
            if codec == "av1" else [])


def probe_video(path):
    """Return dimensions, codec and every packet presentation timestamp.

    The scoring decode itself is checked separately.  Packet timestamps make
    the alignment preflight fast enough to run before every metric while still
    catching the dropped/repeated-frame class that invalidated earlier runs.
    """
    path = os.path.abspath(path)
    stat = os.stat(path)
    key = (path, stat.st_size, stat.st_mtime_ns)
    if key in _PROBE_CACHE:
        return _PROBE_CACHE[key]
    document = json.loads(run([
        FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_packets",
        "-show_entries",
        "stream=codec_name,width,height,avg_frame_rate,pix_fmt,color_range,"
        "color_space,color_transfer,color_primaries:packet=pts_time",
        "-of", "json", path], timeout=300).stdout)
    streams = document.get("streams", [])
    if len(streams) != 1:
        raise RuntimeError(f"{path}: expected one selected video stream")
    stream = streams[0]
    timestamps = []
    for index, packet in enumerate(document.get("packets", [])):
        value = packet.get("pts_time")
        if value is None:
            raise RuntimeError(f"{path}: packet {index} has no presentation timestamp")
        timestamps.append(float(value))
    if not timestamps:
        raise RuntimeError(f"{path}: decoder returned no video frames")
    if any(right <= left for left, right in zip(timestamps, timestamps[1:])):
        raise RuntimeError(f"{path}: timestamps are not strictly increasing")
    result = {
        "path": path,
        "codec": stream.get("codec_name"),
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "avg_frame_rate": stream.get("avg_frame_rate"),
        "pix_fmt": stream.get("pix_fmt"),
        "color_range": stream.get("color_range"),
        "color_space": stream.get("color_space"),
        "color_transfer": stream.get("color_transfer"),
        "color_primaries": stream.get("color_primaries"),
        "timestamps": timestamps,
    }
    _PROBE_CACHE[key] = result
    return result


def aligned_frame_count(reference, distorted, limit=MAX_FRAMES,
                        allow_dimension_mismatch=False):
    """Require a one-to-one timeline over the interval that will be scored."""
    ref = probe_video(reference)
    dist = probe_video(distorted)
    if not allow_dimension_mismatch and (
            ref["width"], ref["height"]) != (dist["width"], dist["height"]):
        raise RuntimeError(
            f"dimension mismatch: {ref['width']}x{ref['height']} vs "
            f"{dist['width']}x{dist['height']}")
    ref_count = min(len(ref["timestamps"]), limit)
    dist_count = min(len(dist["timestamps"]), limit)
    if ref_count != dist_count:
        raise RuntimeError(
            f"frame-count mismatch in scored interval: {ref_count} vs {dist_count} "
            f"({reference} vs {distorted})")
    if ref_count < 2:
        raise RuntimeError("at least two aligned frames are required")
    ref_times = [value - ref["timestamps"][0]
                 for value in ref["timestamps"][:ref_count]]
    dist_times = [value - dist["timestamps"][0]
                  for value in dist["timestamps"][:dist_count]]
    ref_steps = [right - left for left, right in zip(ref_times, ref_times[1:])]
    period = statistics.median(ref_steps)
    tolerance = max(0.002, period * 0.05)
    worst = max(abs(left - right) for left, right in zip(ref_times, dist_times))
    if worst > tolerance:
        raise RuntimeError(
            f"timeline mismatch: maximum relative PTS error {worst:.6f}s "
            f"exceeds {tolerance:.6f}s")
    return ref_count, ref, dist


COLOR_FIELDS = (
    "color_range", "color_space", "color_transfer", "color_primaries")


def color_signature(probe):
    return {field: probe.get(field) for field in COLOR_FIELDS}


def require_matching_color(reference_probe, distorted_probe):
    """Reject metadata mismatches that invalidate display-referred metrics."""
    reference = color_signature(reference_probe)
    distorted = color_signature(distorted_probe)
    if reference != distorted:
        raise RuntimeError(
            "color metadata mismatch: "
            f"reference={reference}, distorted={distorted}")
    return reference


def _file_identity(path):
    stat = os.stat(path)
    return {
        "path": os.path.abspath(path),
        "bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _cache_matches(path, expected):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle) == expected
    except (FileNotFoundError, json.JSONDecodeError):
        return False


def _write_json(path, value):
    temporary = f"{path}.tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, path)


def _validate_vmaf(path, frames, model_names):
    with open(path, encoding="utf-8") as handle:
        document = json.load(handle)
    rows = document.get("frames", [])
    if len(rows) != frames:
        raise RuntimeError(f"{path}: scored {len(rows)} frames, expected {frames}")
    for name in model_names:
        missing = sum(row.get("metrics", {}).get(name) is None for row in rows)
        if missing:
            raise RuntimeError(f"{path}: {missing} null frames for {name}")
    return document


def vmaf_run(reference, distorted, tag, work=WORK, models=None,
             distorted_filter="", allow_dimension_mismatch=False, timeout=3600):
    """Score a pair through FIFO-fed libvmaf after strict alignment checks."""
    models = models or {
        "vmaf": "version=vmaf_v0.6.1",
        "vmaf_neg": "version=vmaf_v0.6.1neg",
    }
    os.makedirs(work, exist_ok=True)
    frames, ref_probe, dist_probe = aligned_frame_count(
        reference, distorted, allow_dimension_mismatch=allow_dimension_mismatch)
    output = os.path.join(work, f"vmaf-{tag}.json")
    manifest_path = f"{output}.manifest.json"
    manifest = {
        "reference": _file_identity(reference),
        "distorted": _file_identity(distorted),
        "frames": frames,
        "reference_codec": ref_probe["codec"],
        "distorted_codec": dist_probe["codec"],
        "distorted_filter": distorted_filter,
        "models": models,
    }
    if os.path.isfile(output) and _cache_matches(manifest_path, manifest):
        return _validate_vmaf(output, frames, models), frames

    ref_pipe = os.path.join(work, f"ref-{tag}.fifo")
    dist_pipe = os.path.join(work, f"dist-{tag}.fifo")
    ref_log = os.path.join(work, f"decode-ref-{tag}.log")
    dist_log = os.path.join(work, f"decode-dist-{tag}.log")
    ref_command = [FFMPEG, "-v", "error", "-nostdin"]
    ref_command += _decoder_args(ref_probe["codec"], filmgrain=1)
    ref_command += ["-i", reference, "-frames:v", str(frames),
                    "-pix_fmt", "yuv420p10le", "-strict", "-1",
                    "-f", "yuv4mpegpipe", "-y", ref_pipe]
    dist_command = [FFMPEG, "-v", "error", "-nostdin"]
    dist_command += _decoder_args(dist_probe["codec"], filmgrain=1)
    dist_command += ["-i", distorted, "-frames:v", str(frames)]
    if distorted_filter:
        dist_command += ["-vf", distorted_filter]
    dist_command += ["-pix_fmt", "yuv420p10le", "-strict", "-1",
                     "-f", "yuv4mpegpipe", "-y", dist_pipe]
    model_args = []
    for name, description in models.items():
        model_args += ["--model", f"{description}:name={name}"]
    vmaf_command = [
        VMAF, "--reference", ref_pipe, "--distorted", dist_pipe,
        "--gpumask", "0", *model_args,
        "--feature", "psnr_cuda", "--feature", "ssim_cuda",
        "--feature", "ciede_cuda", "--json", "--output", output]
    script = f"""
set -u
rm -f {shlex.quote(ref_pipe)} {shlex.quote(dist_pipe)}
mkfifo {shlex.quote(ref_pipe)} {shlex.quote(dist_pipe)} || exit 1
cleanup() {{
    kill "${{ref_pid:-}}" "${{dist_pid:-}}" 2>/dev/null || true
    rm -f {shlex.quote(ref_pipe)} {shlex.quote(dist_pipe)}
}}
trap cleanup EXIT INT TERM
{shlex.join(ref_command)} > /dev/null 2> {shlex.quote(ref_log)} & ref_pid=$!
{shlex.join(dist_command)} > /dev/null 2> {shlex.quote(dist_log)} & dist_pid=$!
{shlex.join(vmaf_command)}
metric_status=$?
if [ "$metric_status" -ne 0 ]; then
    kill "$ref_pid" "$dist_pid" 2>/dev/null || true
fi
wait "$ref_pid"; ref_status=$?
wait "$dist_pid"; dist_status=$?
if [ "$metric_status" -ne 0 ] || [ "$ref_status" -ne 0 ] || [ "$dist_status" -ne 0 ]; then
    echo "statuses metric=$metric_status ref=$ref_status dist=$dist_status" >&2
    exit 1
fi
"""
    shell(script, timeout=timeout)
    document = _validate_vmaf(output, frames, models)
    _write_json(manifest_path, manifest)
    return document, frames


def ffvship(reference, distorted, tag, metric, output_name, frames,
            work=WORK, display_model=None):
    """Run FFVship and reject short or stale output."""
    available, reference_probe, distorted_probe = aligned_frame_count(
        reference, distorted, limit=frames)
    if available != frames:
        raise RuntimeError(
            f"FFVship requested {frames} frames but pair has {available}")
    colors = require_matching_color(reference_probe, distorted_probe)
    output = os.path.join(work, output_name)
    manifest_path = f"{output}.manifest.json"
    manifest = {
        "reference": _file_identity(reference),
        "distorted": _file_identity(distorted),
        "frames": frames,
        "metric": metric,
        "image": FFVSHIP_IMG,
        "display_model": display_model,
        "color": colors,
    }
    if not (os.path.isfile(output) and _cache_matches(manifest_path, manifest)):
        Path(output).unlink(missing_ok=True)
        reference = os.path.abspath(reference)
        distorted = os.path.abspath(distorted)
        command = [
            "docker", "run", "--rm", "--gpus", "all",
            "-v", f"{work}:/data",
            "-v", f"{os.path.dirname(reference)}:/reference:ro",
            "-v", f"{os.path.dirname(distorted)}:/distorted:ro",
            "--entrypoint", "FFVship", FFVSHIP_IMG,
            "-s", f"/reference/{os.path.basename(reference)}",
            "-e", f"/distorted/{os.path.basename(distorted)}",
            "--end", str(frames), "-m", metric,
            "--json", f"/data/{output_name}"]
        if display_model:
            command += ["--displayModel", display_model]
        run(command, timeout=3600)
        _write_json(manifest_path, manifest)
    with open(output, encoding="utf-8") as handle:
        rows = json.load(handle)
    if len(rows) != frames:
        raise RuntimeError(f"{output}: scored {len(rows)} frames, expected {frames}")
    if any(not isinstance(row, list) or not row or row[0] is None for row in rows):
        raise RuntimeError(f"{output}: malformed or null {metric} score")
    return rows


ARM = {
    ("The_Shining", "A"): "motion",
    ("The_Shining", "B"): "bilateral",
    ("The_Deer_Hunter", "A"): "bilateral",
    ("The_Deer_Hunter", "B"): "motion",
    ("Scarface", "A"): "motion",
    ("Scarface", "B"): "bilateral",
}


def score_review(include_plain=False):
    rows = []
    for title in ("The_Shining", "The_Deer_Hunter", "Scarface"):
        reference = os.path.join(WORK, f"{title}-ref.mkv")
        for letter in ("A", "B"):
            for kind in ("base", "finished"):
                distorted = os.path.join(BLIND, f"{title}-{letter}-{kind}.mkv")
                tag = f"{title}-{letter}-{kind}"
                document, frames = vmaf_run(reference, distorted, tag)
                pooled = document["pooled_metrics"]
                ssimu2 = sorted(value[0] for value in ffvship(
                    reference, distorted, tag, "SSIMULACRA2",
                    f"ssimu2-{tag}.json", frames))
                butter = ffvship(reference, distorted, tag, "Butteraugli",
                                 f"butter-{tag}.json", frames)
                vmaf_frames = sorted(
                    frame["metrics"]["vmaf"] for frame in document["frames"])
                row = {
                    "title": title,
                    "letter": letter,
                    "arm": ARM[(title, letter)],
                    "kind": kind,
                    "frames": frames,
                    "vmaf": round(pooled["vmaf"]["mean"], 3),
                    "vmaf_p1": round(pct(vmaf_frames, 1), 2),
                    "vmaf_neg": round(pooled["vmaf_neg"]["mean"], 3),
                    "psnr_y": round(pooled["psnr_y"]["mean"], 3),
                    "ssim": round(pooled["float_ssim"]["mean"], 5),
                    "ciede": round(pooled["ciede2000"]["mean"], 3),
                    "ssimu2": round(statistics.mean(ssimu2), 3),
                    "ssimu2_p5": round(pct(ssimu2, 5), 3),
                    "butter_2norm": round(statistics.mean(x[0] for x in butter), 4),
                    "butter_max_p95": round(
                        pct(sorted(x[2] for x in butter), 95), 3),
                }
                rows.append(row)
                print(json.dumps(row), flush=True)
    _write_json(os.path.join(WORK, "scores.json"), rows)

    if include_plain:
        plain_rows = []
        for title in ("The_Shining", "The_Deer_Hunter", "Scarface"):
            reference = os.path.join(WORK, f"{title}-ref.mkv")
            distorted = os.path.join(CORPUS, f"{title}-plain.mkv")
            document, frames = vmaf_run(
                reference, distorted, f"{title}-plain",
                distorted_filter="crop=1920:1080:960:540",
                allow_dimension_mismatch=True)
            pooled = document["pooled_metrics"]
            row = {
                "title": title,
                "arm": "plain",
                "kind": "control",
                "frames": frames,
                "vmaf": round(pooled["vmaf"]["mean"], 3),
                "vmaf_neg": round(pooled["vmaf_neg"]["mean"], 3),
                "psnr_y": round(pooled["psnr_y"]["mean"], 3),
                "ssim": round(pooled["float_ssim"]["mean"], 5),
                "ciede": round(pooled["ciede2000"]["mean"], 3),
                "bytes": os.path.getsize(distorted),
            }
            plain_rows.append(row)
            print(json.dumps(row), flush=True)
        _write_json(os.path.join(WORK, "plain-control.json"), plain_rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--include-plain", action="store_true",
        help="also score the same-QVBR plain 4K encodes after the centre crop")
    args = parser.parse_args()
    score_review(include_plain=args.include_plain)


if __name__ == "__main__":
    main()
