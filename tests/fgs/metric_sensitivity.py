#!/usr/bin/env python3
"""Does changing only luma grain strength toward truth improve FR metrics?

The historical candidates below were initially believed to differ only in leak
closure.  The 2026-08-02 audit disproved that: their grain-disabled bases and
some emitted AR entries differ.  This script now checks those invariants before
scoring and deliberately rejects those arms.  Use explicit-pair mode with a
controlled replay before using it for a new result.

  pre-closure   sourcefit-corpus-20260801/<T>-motion_on.mkv   mean synth 0.893
  post-closure  sourcefit-leakclose-20260802/<T>-q29.mkv      mean synth 0.959

For a valid experiment the decoded grain-off pixels, bitstream seed, AR model
and every non-luma-scaling field must be identical on every frame.  At least one
luma scaling curve must differ.

Scored at native 4K against the lossless originals, 4K models, dav1d decode so
film grain is actually applied.  Explicit-pair mode also runs SSIMULACRA2,
Butteraugli and exploratory CVVDP.  Display-referred metrics require identical
colour metadata; ``--copy-reference-color-tags`` repairs replay containers that
were made through Y4M and therefore lost their BT.2020/PQ tags.
"""
import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emission_audit import probe_grain_entries
from review_score import (
    FFMPEG, aligned_frame_count, color_signature, ffvship, pct, probe_video,
    require_matching_color, run, vmaf_run)

WORK = "/media/merged-storage/media/test-encodes/correctness-vmaf-20260802"
SRC = "/media/merged-storage/media/test-encodes/keep-original"
PRE = "/media/merged-storage/media/test-encodes/sourcefit-corpus-20260801"
POST = "/media/merged-storage/media/test-encodes/sourcefit-leakclose-20260802"

SOURCES = {
    "Casino": "clip_Casino-ref288.mkv",
    "Interstellar": "clip_Interstellar.mkv",
    "Scarface": "clip_Scarface-ref288.mkv",
    "Taxi_Driver": "clip_Taxi_Driver-ref288.mkv",
    "The_Deer_Hunter": "clip_The_Deer_Hunter.mkv",
    "The_Shining": "clip_The_Shining-ref288.mkv",
}
# mean synthesis amplitude vs source truth, from FINDINGS-2026-08-02-LEAK-CLOSURE
SYNTH = {"Casino": (0.889, 0.959), "Interstellar": (0.914, 0.993),
         "Scarface": (0.956, 1.001), "Taxi_Driver": (0.874, 0.956),
         "The_Deer_Hunter": (0.835, 0.902), "The_Shining": (0.892, 0.942)}


def grain_off_hash(path, frames, width=None, height=None):
    """Hash decoded base pixels and fail if dav1d does not produce all frames."""
    command = [
        FFMPEG, "-v", "error", "-nostdin", "-c:v", "libdav1d",
        "-filmgrain", "0", "-i", path, "-frames:v", str(frames),
        "-map", "0:v:0", "-pix_fmt", "yuv420p10le", "-f", "rawvideo", "-"]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    digest = hashlib.sha256()
    decoded_bytes = 0
    while True:
        chunk = process.stdout.read(8 * 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
        decoded_bytes += len(chunk)
    stderr = process.stderr.read()
    status = process.wait()
    if status != 0:
        raise RuntimeError(
            f"grain-off decode failed ({status}) for {path}: "
            f"{stderr.decode(errors='replace')[-2000:]}")
    if width is not None and height is not None:
        # yuv420p10le: 2 bytes for each luma sample and one quarter as many
        # 2-byte samples in each of the two chroma planes = 3*W*H bytes/frame.
        expected_bytes = frames * width * height * 3
        if decoded_bytes != expected_bytes:
            raise RuntimeError(
                f"grain-off decode returned {decoded_bytes} bytes, expected "
                f"{expected_bytes} ({frames} frames) for {path}")
    return digest.hexdigest()


def require_isolated(pre, post):
    """Prove the pair differs only in its luma scaling-point arrays."""
    frames, pre_info, post_info = aligned_frame_count(pre, post)
    pre_hash = grain_off_hash(
        pre, frames, pre_info["width"], pre_info["height"])
    post_hash = grain_off_hash(
        post, frames, post_info["width"], post_info["height"])
    pre_entries = probe_grain_entries(pre, frames)
    post_entries = probe_grain_entries(post, frames)
    changed_curves = 0
    field_differences = []
    for frame in range(frames):
        left, right = pre_entries[frame], post_entries[frame]
        for field in ("random_seed", "params", "ar_coeffs", "limit_output_range"):
            if left[field] != right[field]:
                field_differences.append((frame, field))
        left_y = left["scaling_points"]["y"]
        right_y = right["scaling_points"]["y"]
        if ([point[0] for point in left_y]
                != [point[0] for point in right_y]):
            field_differences.append(
                (frame, "scaling_points.y.locations"))
        for plane in ("cb", "cr"):
            if (left["scaling_points"][plane]
                    != right["scaling_points"][plane]):
                field_differences.append(
                    (frame, f"scaling_points.{plane}"))
        changed_curves += (
            [point[1] for point in left_y]
            != [point[1] for point in right_y])
    failures = []
    if pre_hash != post_hash:
        failures.append(f"grain-off SHA-256 differs: {pre_hash} != {post_hash}")
    if field_differences:
        preview = ", ".join(f"f{frame}:{field}" for frame, field in field_differences[:8])
        failures.append(
            f"{len(field_differences)} non-scaling frame fields differ ({preview})")
    if not changed_curves:
        failures.append("no luma scaling curve changed")
    if failures:
        raise RuntimeError(
            "candidate pair is not an isolated luma-strength experiment:\n  "
            + "\n  ".join(failures))
    return {
        "frames": frames,
        "grain_off_sha256": pre_hash,
        "changed_luma_curves": changed_curves,
    }


def run_vmaf(ref, enc, tag, work=WORK):
    width = probe_video(ref)["width"]
    suffix = "_4k" if width >= 3000 else ""
    models = {
        "vmaf": f"version=vmaf{suffix}_v0.6.1",
        "vmaf_neg": f"version=vmaf{suffix}_v0.6.1neg",
    }
    document, frames = vmaf_run(ref, enc, tag, work=work, models=models)
    return document["pooled_metrics"], frames


def _identity(path):
    stat = os.stat(path)
    return {
        "path": os.path.abspath(path),
        "bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _write_json(path, value):
    temporary = f"{path}.tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, path)


def copy_reference_color_tags(reference, source, output):
    """Stream-copy one arm while restoring the reference's colour tags."""
    reference_probe = probe_video(reference)
    colors = color_signature(reference_probe)
    if any(value is None for value in colors.values()):
        raise RuntimeError(
            f"reference has incomplete color metadata: {colors}")
    manifest_path = f"{output}.color-manifest.json"
    manifest = {
        "reference": _identity(reference),
        "source": _identity(source),
        "color": colors,
    }
    reusable = False
    if os.path.isfile(output) and os.path.isfile(manifest_path):
        try:
            with open(manifest_path, encoding="utf-8") as handle:
                reusable = json.load(handle) == manifest
            if reusable:
                require_matching_color(reference_probe, probe_video(output))
        except (json.JSONDecodeError, RuntimeError):
            reusable = False
    if not reusable:
        temporary = f"{output}.tmp.mkv"
        command = [
            FFMPEG, "-v", "error", "-nostdin", "-y", "-i", source,
            "-map", "0:v:0", "-c:v", "copy", "-an", "-sn", "-dn",
            "-color_range", colors["color_range"],
            "-colorspace", colors["color_space"],
            "-color_trc", colors["color_transfer"],
            "-color_primaries", colors["color_primaries"], temporary]
        run(command, timeout=600)
        os.replace(temporary, output)
        require_matching_color(reference_probe, probe_video(output))
        _write_json(manifest_path, manifest)
    return output


def cvvdp_video_score(rows):
    if not rows or not isinstance(rows[-1], list) or not rows[-1]:
        raise ValueError("CVVDP output has no final video score")
    return float(rows[-1][0])


def score_arm(reference, path, label, arm, work, display_model):
    tag = f"{label}-{arm}"
    pooled, frames = run_vmaf(reference, path, tag, work=work)
    ssimu2 = sorted(value[0] for value in ffvship(
        reference, path, tag, "SSIMULACRA2", f"ssimu2-{tag}.json",
        frames, work=work))
    butter = ffvship(
        reference, path, tag, "Butteraugli", f"butter-{tag}.json",
        frames, work=work)
    cvvdp = ffvship(
        reference, path, tag, "CVVDP", f"cvvdp-{tag}.json",
        frames, work=work, display_model=display_model)
    return {
        "arm": arm,
        "path": os.path.abspath(path),
        "frames": frames,
        "bytes": os.path.getsize(path),
        "vmaf": pooled["vmaf"]["mean"],
        "vmaf_neg": pooled["vmaf_neg"]["mean"],
        "psnr_y": pooled["psnr_y"]["mean"],
        "ssim": pooled["float_ssim"]["mean"],
        "ciede": pooled["ciede2000"]["mean"],
        "ssimu2": statistics.mean(ssimu2),
        "ssimu2_p5": pct(ssimu2, 5),
        "butter_2norm": statistics.mean(row[0] for row in butter),
        "butter_max_p95": pct(sorted(row[2] for row in butter), 95),
        "cvvdp": cvvdp_video_score(cvvdp),
    }


def score_explicit_pair(args):
    os.makedirs(args.work, exist_ok=True)
    baseline, candidate = args.baseline, args.candidate
    if args.copy_reference_color_tags:
        baseline = copy_reference_color_tags(
            args.reference, baseline,
            os.path.join(args.work, f"{args.label}-baseline-color.mkv"))
        candidate = copy_reference_color_tags(
            args.reference, candidate,
            os.path.join(args.work, f"{args.label}-candidate-color.mkv"))
    isolation = require_isolated(baseline, candidate)
    reference_probe = probe_video(args.reference)
    for path in (baseline, candidate):
        count, _, distorted_probe = aligned_frame_count(args.reference, path)
        if count != isolation["frames"]:
            raise RuntimeError(
                f"reference pair has {count} frames but treatment has "
                f"{isolation['frames']}")
        require_matching_color(reference_probe, distorted_probe)
    display_model = args.display_model
    if display_model == "auto":
        display_model = (
            "standard_hdr_pq"
            if reference_probe.get("color_transfer") == "smpte2084"
            else ("standard_4k" if reference_probe["width"] >= 3000
                  else "standard_fhd"))
    arms = [
        score_arm(args.reference, baseline, args.label, "baseline",
                  args.work, display_model),
        score_arm(args.reference, candidate, args.label, "candidate",
                  args.work, display_model),
    ]
    metric_names = (
        "vmaf", "vmaf_neg", "psnr_y", "ssim", "ciede", "ssimu2",
        "ssimu2_p5", "butter_2norm", "butter_max_p95", "cvvdp")
    delta = {name: arms[1][name] - arms[0][name] for name in metric_names}
    report = {
        "label": args.label,
        "reference": os.path.abspath(args.reference),
        "isolation": isolation,
        "color": color_signature(reference_probe),
        "cvvdp_display_model": display_model,
        "baseline_synth": args.baseline_synth,
        "candidate_synth": args.candidate_synth,
        "arms": arms,
        "candidate_minus_baseline": delta,
        "interpretation": {
            "higher_is_better": [
                "vmaf", "vmaf_neg", "psnr_y", "ssim", "ciede",
                "ssimu2", "ssimu2_p5", "cvvdp"],
            "lower_is_better": ["butter_2norm", "butter_max_p95"],
        },
    }
    output = args.output or os.path.join(
        args.work, f"{args.label}-scores.json")
    _write_json(output, report)
    print(json.dumps(report, indent=2, sort_keys=True), flush=True)


def audit_historical():
    os.makedirs(WORK, exist_ok=True)
    rows = []
    for title, srcname in SOURCES.items():
        ref = os.path.join(SRC, srcname)
        pre = os.path.join(PRE, f"{title}-motion_on.mkv")
        post = os.path.join(POST, f"{title}-q29.mkv")
        if not os.path.isfile(pre) or not os.path.isfile(post):
            print(f"MISSING pair for {title}", flush=True)
            continue
        isolation = require_isolated(pre, post)
        print(json.dumps({"title": title, "isolation": isolation}), flush=True)
        for arm, path in (("pre", pre), ("post", post)):
            if not os.path.isfile(path):
                print(f"MISSING {path}", flush=True)
                continue
            fm, frames = run_vmaf(ref, path, f"{title}-{arm}")
            row = dict(title=title, arm=arm,
                       frames=frames,
                       synth=SYNTH[title][0 if arm == "pre" else 1],
                       vmaf=round(fm["vmaf"]["mean"], 3),
                       vmaf_neg=round(fm["vmaf_neg"]["mean"], 3),
                       psnr_y=round(fm["psnr_y"]["mean"], 3),
                       ssim=round(fm["float_ssim"]["mean"], 5),
                       ciede=round(fm["ciede2000"]["mean"], 3),
                       bytes=os.path.getsize(path))
            rows.append(row)
            print(json.dumps(row), flush=True)
    with open(os.path.join(WORK, "scores-isolated.json"), "w", encoding="utf-8") as handle:
        json.dump(rows, handle, indent=1)
        handle.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference")
    parser.add_argument("--baseline")
    parser.add_argument("--candidate")
    parser.add_argument("--label", default="isolated-grain-strength")
    parser.add_argument("--work", default=WORK)
    parser.add_argument("--output", default="")
    parser.add_argument("--display-model", default="auto")
    parser.add_argument("--baseline-synth", type=float)
    parser.add_argument("--candidate-synth", type=float)
    parser.add_argument("--copy-reference-color-tags", action="store_true")
    parser.add_argument(
        "--audit-historical", action="store_true",
        help="prove that the retained historical corpus is not isolated")
    args = parser.parse_args()
    if args.audit_historical:
        audit_historical()
        return
    missing = [name for name in ("reference", "baseline", "candidate")
               if not getattr(args, name)]
    if missing:
        parser.error(
            "explicit mode requires --reference, --baseline and --candidate")
    score_explicit_pair(args)


if __name__ == "__main__":
    main()
