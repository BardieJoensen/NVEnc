#!/usr/bin/env python3
"""Does changing only luma grain strength toward truth improve FR metrics?

The historical candidates below were initially believed to differ only in leak
closure.  The 2026-08-02 audit disproved that: their grain-disabled bases and
some emitted AR entries differ.  This script now checks those invariants before
scoring and deliberately rejects those arms.  Point PRE/POST at a controlled
replay before using it for a new result.

  pre-closure   sourcefit-corpus-20260801/<T>-motion_on.mkv   mean synth 0.893
  post-closure  sourcefit-leakclose-20260802/<T>-q29.mkv      mean synth 0.959

For a valid experiment the decoded grain-off pixels, bitstream seed, AR model
and every non-luma-scaling field must be identical on every frame.  At least one
luma scaling curve must differ.

Scored at native 4K against the lossless originals, 4K models, dav1d decode so
film grain is actually applied.
"""
import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emission_audit import probe_grain_entries
from review_score import FFMPEG, aligned_frame_count, vmaf_run

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
        changed_curves += left["scaling_points"]["y"] != right["scaling_points"]["y"]
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


def run_vmaf(ref, enc, tag):
    models = {"vmaf": "version=vmaf_4k_v0.6.1", "vmaf_neg": "version=vmaf_4k_v0.6.1neg"}
    document, frames = vmaf_run(ref, enc, tag, work=WORK, models=models)
    return document["pooled_metrics"], frames


def main():
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


if __name__ == "__main__":
    main()
