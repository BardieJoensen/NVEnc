#!/usr/bin/env python3
"""Replay fine and coarse AV1 grain at matched luma energy on one clean base.

This is a controlled metric-sensitivity experiment, not an encoder option.
It answers a narrow question left open by the bilateral source-fit audit:
does a full-reference metric penalise the source-fitted, spatially correlated
grain more than production's finer residual-fitted grain when delivered luma
energy is held constant?

The replay deliberately removes other explanations:

* both arms encode the same saved grain-disabled base with the same binary;
* one model is selected from the same source timestamp in each table;
* one static update covers the entire replay and both use the same table seed;
* luma strength is flat across the signal range and chroma grain is disabled;
* the coarse scaling integer is searched until decoded luma sigma matches;
* decoded grain-off pixels, frame timeline and emitted seeds must be identical.

Only the active luma AR model (including its grain-scale representation) and
the scalar needed to match its realised energy are allowed to differ.  The
script records actual decoded lag-1/lag-2 and normalized spectra, then scores
both arms against the source and against their common re-encoded clean base.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import filmgrn  # noqa: E402
import quality_metrics  # noqa: E402
import review_score  # noqa: E402
from emission_audit import probe_grain_entries  # noqa: E402
from integrated_architecture import (  # noqa: E402
    CONTROLLED_ENCODE,
    complete_task,
    identity,
    partial_path,
    publish_outputs,
    run_logged,
    write_json,
)


TABLE_TIMEBASE = 10_000_000
DEFAULT_WORK = (
    "/media/merged-storage/media/test-encodes/"
    "sourcefit-amplitude-match-20260803"
)
DEFAULT_FINE_TABLE = (
    "/media/merged-storage/media/test-encodes/"
    "sourcefit-integrated-20260803/The_Shining/production.tbl"
)
DEFAULT_COARSE_TABLE = (
    "/media/merged-storage/media/test-encodes/"
    "sourcefit-bilateral-quality-20260803/The_Shining/bilateral-source.tbl"
)
DEFAULT_BASE = (
    "/media/merged-storage/media/test-encodes/"
    "sourcefit-integrated-20260803/quality-crops/"
    "The_Shining-production-base.mkv"
)
DEFAULT_REFERENCE = (
    "/media/merged-storage/media/test-encodes/"
    "sourcefit-integrated-20260803/quality-crops/The_Shining-reference.mkv"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def entry_at_seconds(entries: list[dict], seconds: float) -> dict:
    timestamp = int(round(seconds * TABLE_TIMEBASE))
    matches = [
        entry for entry in entries
        if entry["start"] <= timestamp < entry["end"]
        and entry["apply_grain"] and entry["update_parameters"]
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected one updated grain entry at {seconds:.6f}s, "
            f"found {len(matches)}")
    return matches[0]


def equivalent_scale(value: int, source_entry: dict, target_entry: dict) -> int:
    """Represent the same effective flat curve under another grain shift."""
    difference = (
        target_entry["params"]["grain_scale_shift"]
        - source_entry["params"]["grain_scale_shift"]
    )
    represented = value * (2.0 ** difference)
    return int(round(represented))


def static_luma_table(
    source_entry: dict,
    end_timestamp: int,
    scaling_value: int,
    seed: int,
) -> list[dict]:
    """Make one full-duration, luma-only, flat-strength table entry."""
    if not 1 <= scaling_value <= 255:
        raise ValueError(f"scaling value {scaling_value} is outside 1..255")
    entry = copy.deepcopy(source_entry)
    entry.update({
        "start": 0,
        "end": end_timestamp,
        "apply_grain": True,
        "random_seed": seed,
        "update_parameters": True,
    })
    entry["params"]["chroma_scaling_from_luma"] = 0
    entry["scaling_points"]["y"] = [
        [0, scaling_value], [255, scaling_value]
    ]
    entry["scaling_points"]["cb"] = []
    entry["scaling_points"]["cr"] = []
    return [entry]


def candidate_scales(initial: int, fine_sigma: float, coarse_sigma: float) -> list[int]:
    if fine_sigma <= 0.0 or coarse_sigma <= 0.0:
        raise ValueError("calibration sigma must be positive")
    predicted = int(round(initial * fine_sigma / coarse_sigma))
    values = {initial, predicted - 1, predicted, predicted + 1}
    return sorted(value for value in values if 1 <= value <= 255)


def encode_command(
    binary: Path,
    base: Path,
    table: Path,
    output: Path,
    frames: int,
) -> list[str]:
    return [
        str(binary), "--avsw", "-i", str(base),
        *CONTROLLED_ENCODE,
        "--frames", str(frames),
        "--film-grain-table", str(table),
        "--log-level", "debug", "-o", str(output),
    ]


def run_encode(
    label: str,
    binary: Path,
    base: Path,
    table: Path,
    output: Path,
    frames: int,
    work: Path,
) -> None:
    partial = partial_path(output)
    command = encode_command(binary, base, table, partial, frames)
    manifest = work / f"{label}-encode.task.json"
    expected = {
        "command": command,
        "binary": identity(binary, include_hash=True),
        "base": identity(base),
        "table": identity(table, include_hash=True),
    }
    if complete_task(manifest, expected, [output]):
        print(f"[resume] encode {label}", flush=True)
        return
    if output.exists():
        raise RuntimeError(f"{output} exists without a matching task manifest")
    elapsed = run_logged(command, os.environ.copy(), work / f"{label}-encode.log")
    publish_outputs([partial], [output])
    write_json(manifest, {
        "input": expected,
        "outputs": [identity(output, include_hash=True)],
        "elapsed_seconds": elapsed,
    })


def decode_command(
    ffmpeg: Path,
    encoded: Path,
    output: Path,
    frames: int,
    filmgrain: int,
) -> list[str]:
    return [
        str(ffmpeg), "-hide_banner", "-nostdin", "-v", "error", "-xerror",
        "-c:v", "libdav1d", "-filmgrain", str(filmgrain),
        "-i", str(encoded), "-map", "0:v:0", "-frames:v", str(frames),
        "-an", "-sn", "-dn", "-pix_fmt", "yuv420p10le",
        "-f", "rawvideo", "-y", str(output),
    ]


def run_decode(
    label: str,
    encoded: Path,
    output: Path,
    frames: int,
    filmgrain: int,
    ffmpeg: Path,
    expected_bytes: int,
    work: Path,
) -> None:
    partial = partial_path(output)
    command = decode_command(ffmpeg, encoded, partial, frames, filmgrain)
    manifest = work / f"{label}-decode-{filmgrain}.task.json"
    expected = {
        "command": command,
        "binary": identity(ffmpeg, include_hash=True),
        "encoded": identity(encoded, include_hash=True),
    }
    if complete_task(manifest, expected, [output]):
        if output.stat().st_size != expected_bytes:
            raise RuntimeError(f"cached raw decode has wrong size: {output}")
        print(f"[resume] decode {label} grain={filmgrain}", flush=True)
        return
    if output.exists():
        raise RuntimeError(f"{output} exists without a matching task manifest")
    elapsed = run_logged(
        command, os.environ.copy(), work / f"{label}-decode-{filmgrain}.log")
    if partial.stat().st_size != expected_bytes:
        raise RuntimeError(
            f"{partial}: decoded {partial.stat().st_size} bytes, "
            f"expected {expected_bytes}")
    publish_outputs([partial], [output])
    write_json(manifest, {
        "input": expected,
        "outputs": [identity(output)],
        "elapsed_seconds": elapsed,
    })


def run_arm(
    label: str,
    source_entry: dict,
    scale: int,
    end_timestamp: int,
    seed: int,
    binary: Path,
    base: Path,
    ffmpeg: Path,
    frames: int,
    width: int,
    height: int,
    work: Path,
) -> dict:
    table = work / f"{label}.tbl"
    entries = static_luma_table(source_entry, end_timestamp, scale, seed)
    table_text = filmgrn.dumps(entries)
    if table.exists() and table.read_text(encoding="utf-8") != table_text:
        raise RuntimeError(f"{table} exists with different table parameters")
    if not table.exists():
        filmgrn.write(table, entries)
    encoded = work / f"{label}.mkv"
    grain_on = work / f"{label}-on.raw"
    grain_off = work / f"{label}-off.raw"
    run_encode(label, binary, base, table, encoded, frames, work)
    expected_bytes = frames * width * height * 3
    run_decode(
        label, encoded, grain_on, frames, 1, ffmpeg, expected_bytes, work)
    run_decode(
        label, encoded, grain_off, frames, 0, ffmpeg, expected_bytes, work)
    return {
        "label": label,
        "scale": scale,
        "table": str(table.resolve()),
        "encoded": str(encoded.resolve()),
        "grain_on": str(grain_on.resolve()),
        "grain_off": str(grain_off.resolve()),
        "encoded_bytes": encoded.stat().st_size,
    }


def prior_metrics(arm: dict, work: Path) -> dict | None:
    """Bootstrap a cache from this harness's immediately preceding report."""
    report_path = work / "report.json"
    if not report_path.is_file():
        return None
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    for previous in report.get("arms", {}).values():
        if (
            previous.get("label") == arm["label"]
            and previous.get("encoded") == arm["encoded"]
            and previous.get("grain_on") == arm["grain_on"]
            and previous.get("grain_off") == arm["grain_off"]
            and previous.get("encoded_bytes") == arm["encoded_bytes"]
            and isinstance(previous.get("metrics"), dict)
        ):
            return previous["metrics"]
    return None


def cached_sigma(arm: dict, width: int, height: int, work: Path) -> float:
    """Measure decoded luma RMS without paying for full texture diagnostics."""
    output = work / f"{arm['label']}-sigma.json"
    grain_on = Path(arm["grain_on"])
    grain_off = Path(arm["grain_off"])
    expected = {
        "grain_on": identity(grain_on),
        "grain_off": identity(grain_off),
        "width": width,
        "height": height,
        "bits": 10,
    }
    if output.is_file():
        document = json.loads(output.read_text(encoding="utf-8"))
        if document.get("input") == expected:
            return float(document["sigma_8bit"])
    previous = prior_metrics(arm, work)
    if previous is not None and previous.get("sigma_8bit") is not None:
        sigma = float(previous["sigma_8bit"])
        write_json(output, {"input": expected, "sigma_8bit": sigma})
        return sigma
    on_reader = quality_metrics.LumaReader(str(grain_on), width, height, 10)
    off_reader = quality_metrics.LumaReader(str(grain_off), width, height, 10)
    if on_reader.frames != off_reader.frames:
        raise RuntimeError("grain-on and grain-off frame counts differ")
    energy = 0.0
    for frame in range(on_reader.frames):
        difference = (
            on_reader.luma(frame).astype("float64")
            - off_reader.luma(frame).astype("float64")
        )
        energy += float((difference * difference).sum())
    sigma = math.sqrt(energy / (on_reader.frames * width * height)) / 4.0
    write_json(output, {"input": expected, "sigma_8bit": sigma})
    return sigma


def cached_grain_metrics(arm: dict, width: int, height: int, work: Path) -> dict:
    output = work / f"{arm['label']}-grain-metrics.json"
    grain_on = Path(arm["grain_on"])
    grain_off = Path(arm["grain_off"])
    expected = {
        "grain_on": identity(grain_on),
        "grain_off": identity(grain_off),
        "width": width,
        "height": height,
        "bits": 10,
    }
    if output.is_file():
        document = json.loads(output.read_text(encoding="utf-8"))
        if document.get("input") == expected:
            return document["metrics"]
    previous = prior_metrics(arm, work)
    if previous is not None:
        write_json(output, {"input": expected, "metrics": previous})
        return previous
    metrics = quality_metrics.grain_metrics(
        str(grain_on), str(grain_off), width, height, 10)
    write_json(output, {"input": expected, "metrics": metrics})
    return metrics


def audit_isolation(fine: dict, coarse: dict, frames: int) -> dict:
    """Fail unless the replay differs only in active luma texture and scale."""
    fine_path, coarse_path = fine["encoded"], coarse["encoded"]
    aligned, fine_probe, coarse_probe = review_score.aligned_frame_count(
        fine_path, coarse_path)
    if aligned != frames:
        raise RuntimeError(f"replay has {aligned} aligned frames, expected {frames}")
    fine_hash = sha256(Path(fine["grain_off"]))
    coarse_hash = sha256(Path(coarse["grain_off"]))
    if fine_hash != coarse_hash:
        raise RuntimeError(
            f"grain-off pixels differ: {fine_hash} != {coarse_hash}")
    fine_entries = probe_grain_entries(fine_path, frames)
    coarse_entries = probe_grain_entries(coarse_path, frames)
    seed_mismatches = []
    unexpected = []
    changed_ar = 0
    for frame in range(frames):
        left, right = fine_entries[frame], coarse_entries[frame]
        if left["random_seed"] != right["random_seed"]:
            seed_mismatches.append(frame)
        if left["limit_output_range"] != right["limit_output_range"]:
            unexpected.append((frame, "limit_output_range"))
        for plane in ("cb", "cr"):
            if left["scaling_points"][plane] or right["scaling_points"][plane]:
                unexpected.append((frame, f"active {plane} scaling"))
        if ([point[0] for point in left["scaling_points"]["y"]]
                != [point[0] for point in right["scaling_points"]["y"]]):
            unexpected.append((frame, "luma scaling locations"))
        for entry, arm in ((left, "fine"), (right, "coarse")):
            values = [point[1] for point in entry["scaling_points"]["y"]]
            if not values or len(set(values)) != 1:
                unexpected.append((frame, f"{arm} luma curve is not flat"))
        left_params = dict(left["params"])
        right_params = dict(right["params"])
        left_params.pop("grain_scale_shift", None)
        right_params.pop("grain_scale_shift", None)
        if left_params != right_params:
            unexpected.append((frame, "non-grain-scale parameters"))
        changed_ar += left["ar_coeffs"]["y"] != right["ar_coeffs"]["y"]
    if seed_mismatches:
        raise RuntimeError(
            f"bitstream seeds differ on {len(seed_mismatches)} frames")
    if unexpected:
        preview = ", ".join(f"f{frame}:{field}" for frame, field in unexpected[:8])
        raise RuntimeError(
            f"replay has {len(unexpected)} unexpected field differences ({preview})")
    if changed_ar != frames:
        raise RuntimeError(
            f"luma AR differs on {changed_ar}/{frames} frames, expected all")
    return {
        "frames": frames,
        "grain_off_sha256": fine_hash,
        "identical_seed_frames": frames,
        "changed_luma_ar_frames": changed_ar,
        "fine_color": review_score.color_signature(fine_probe),
        "coarse_color": review_score.color_signature(coarse_probe),
    }


def cached_isolation(fine: dict, coarse: dict, frames: int, work: Path) -> dict:
    output = work / "isolation.json"
    expected = {
        "fine_encoded": identity(Path(fine["encoded"]), include_hash=True),
        "coarse_encoded": identity(Path(coarse["encoded"]), include_hash=True),
        "fine_grain_off": identity(Path(fine["grain_off"])),
        "coarse_grain_off": identity(Path(coarse["grain_off"])),
        "frames": frames,
    }
    if output.is_file():
        document = json.loads(output.read_text(encoding="utf-8"))
        if document.get("input") == expected:
            return document["isolation"]
    report_path = work / "report.json"
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        old_fine = report.get("arms", {}).get("fine", {})
        old_coarse = report.get("arms", {}).get("coarse", {})
        if (
            old_fine.get("label") == fine["label"]
            and old_coarse.get("label") == coarse["label"]
            and report.get("geometry", {}).get("frames") == frames
            and isinstance(report.get("isolation"), dict)
        ):
            isolation = report["isolation"]
            write_json(output, {"input": expected, "isolation": isolation})
            return isolation
    isolation = audit_isolation(fine, coarse, frames)
    write_json(output, {"input": expected, "isolation": isolation})
    return isolation


def lossless_base_command(
    ffmpeg: Path, encoded: Path, output: Path, frames: int,
) -> list[str]:
    return [
        str(ffmpeg), "-hide_banner", "-nostdin", "-v", "error", "-xerror",
        "-c:v", "libdav1d", "-filmgrain", "0", "-i", str(encoded),
        "-map", "0:v:0", "-frames:v", str(frames),
        "-an", "-sn", "-dn", "-fps_mode", "passthrough",
        "-c:v", "ffv1", "-level", "3", "-coder", "1", "-context", "1",
        "-g", "1", "-slicecrc", "1", "-pix_fmt", "yuv420p10le",
        "-color_range", "tv", "-colorspace", "bt2020nc",
        "-color_trc", "smpte2084", "-color_primaries", "bt2020",
        "-y", str(output),
    ]


def make_lossless_base(
    fine: dict, frames: int, ffmpeg: Path, work: Path,
) -> Path:
    output = work / "common-reencoded-base.mkv"
    partial = partial_path(output)
    command = lossless_base_command(
        ffmpeg, Path(fine["encoded"]), partial, frames)
    manifest = work / "common-reencoded-base.task.json"
    expected = {
        "command": command,
        "binary": identity(ffmpeg, include_hash=True),
        "encoded": identity(Path(fine["encoded"]), include_hash=True),
    }
    if not complete_task(manifest, expected, [output]):
        if output.exists():
            raise RuntimeError(f"{output} exists without a matching task manifest")
        elapsed = run_logged(
            command, os.environ.copy(), work / "common-reencoded-base.log")
        publish_outputs([partial], [output])
        write_json(manifest, {
            "input": expected,
            "outputs": [identity(output, include_hash=True)],
            "elapsed_seconds": elapsed,
        })
    return output


def pooled_metrics(reference: Path, distorted: Path, tag: str, work: Path) -> dict:
    models = {
        "vmaf": "version=vmaf_v0.6.1",
        "vmaf_neg": "version=vmaf_v0.6.1neg",
    }
    document, frames = review_score.vmaf_run(
        str(reference), str(distorted), tag, work=str(work), models=models)
    pooled = document["pooled_metrics"]
    vmaf_frames = sorted(row["metrics"]["vmaf"] for row in document["frames"])
    return {
        "frames": frames,
        "vmaf": pooled["vmaf"]["mean"],
        "vmaf_p1": review_score.pct(vmaf_frames, 1),
        "vmaf_neg": pooled["vmaf_neg"]["mean"],
        "psnr_y": pooled["psnr_y"]["mean"],
        "ssim": pooled["float_ssim"]["mean"],
        "ciede2000": pooled["ciede2000"]["mean"],
    }


def metric_delta(coarse: dict, fine: dict) -> dict:
    return {
        name: coarse[name] - fine[name]
        for name in ("vmaf", "vmaf_p1", "vmaf_neg", "psnr_y", "ssim", "ciede2000")
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nvencc", type=Path, required=True)
    parser.add_argument("--fine-table", type=Path, default=Path(DEFAULT_FINE_TABLE))
    parser.add_argument("--coarse-table", type=Path, default=Path(DEFAULT_COARSE_TABLE))
    parser.add_argument("--base", type=Path, default=Path(DEFAULT_BASE))
    parser.add_argument("--reference", type=Path, default=Path(DEFAULT_REFERENCE))
    parser.add_argument("--work", type=Path, default=Path(DEFAULT_WORK))
    parser.add_argument("--decode-ffmpeg", type=Path,
                        default=Path("/usr/local/bin/ffmpeg"))
    parser.add_argument("--encode-ffmpeg", type=Path,
                        default=Path("/usr/bin/ffmpeg"))
    parser.add_argument("--ffprobe", type=Path,
                        default=Path("/usr/local/bin/ffprobe"))
    parser.add_argument("--model-time", type=float, default=6.0)
    parser.add_argument("--fine-scale", type=int, default=32)
    parser.add_argument(
        "--coarse-scale", type=int, default=0,
        help="reuse a previously measured coarse scale and skip calibration search")
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--max-relative-amplitude-error", type=float, default=0.01)
    parser.add_argument("--no-score", action="store_true")
    args = parser.parse_args()

    required = (
        args.nvencc, args.fine_table, args.coarse_table, args.base,
        args.reference, args.decode_ffmpeg, args.encode_ffmpeg, args.ffprobe,
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        parser.error("missing inputs: " + ", ".join(missing))
    args.work.mkdir(parents=True, exist_ok=True)

    review_score.FFMPEG = str(args.decode_ffmpeg.resolve())
    review_score.FFPROBE = str(args.ffprobe.resolve())
    base_probe = review_score.probe_video(str(args.base.resolve()))
    reference_probe = review_score.probe_video(str(args.reference.resolve()))
    frames = len(base_probe["timestamps"])
    if len(reference_probe["timestamps"]) != frames:
        raise RuntimeError("base and source reference frame counts differ")
    width, height = base_probe["width"], base_probe["height"]
    if (width, height) != (reference_probe["width"], reference_probe["height"]):
        raise RuntimeError("base and source reference dimensions differ")
    if base_probe["pix_fmt"] != "yuv420p10le":
        raise RuntimeError(f"expected a 10-bit 4:2:0 base, got {base_probe['pix_fmt']}")
    review_score.require_matching_color(reference_probe, base_probe)

    fine_entries = filmgrn.load(args.fine_table)
    coarse_entries = filmgrn.load(args.coarse_table)
    fine_entry = entry_at_seconds(fine_entries, args.model_time)
    coarse_entry = entry_at_seconds(coarse_entries, args.model_time)
    end_timestamp = max(
        max(entry["end"] for entry in fine_entries),
        max(entry["end"] for entry in coarse_entries),
    )
    initial_coarse_scale = equivalent_scale(
        args.fine_scale, fine_entry, coarse_entry)

    print("[run] fine reference", flush=True)
    fine = run_arm(
        f"fine-scale{args.fine_scale:03d}", fine_entry, args.fine_scale,
        end_timestamp, args.seed, args.nvencc.resolve(), args.base.resolve(),
        args.decode_ffmpeg.resolve(), frames, width, height, args.work.resolve())
    fine_sigma = cached_sigma(fine, width, height, args.work.resolve())
    coarse_arms = {}
    if args.coarse_scale:
        scales = [args.coarse_scale]
    else:
        print("[run] coarse calibration", flush=True)
        initial = run_arm(
            f"coarse-scale{initial_coarse_scale:03d}", coarse_entry,
            initial_coarse_scale, end_timestamp, args.seed,
            args.nvencc.resolve(), args.base.resolve(),
            args.decode_ffmpeg.resolve(), frames, width, height,
            args.work.resolve())
        initial_sigma = cached_sigma(
            initial, width, height, args.work.resolve())
        scales = candidate_scales(
            initial_coarse_scale, fine_sigma, initial_sigma)
        coarse_arms[initial_coarse_scale] = initial
    for scale in scales:
        if scale in coarse_arms:
            continue
        print(f"[run] coarse scale search {scale}", flush=True)
        coarse_arms[scale] = run_arm(
            f"coarse-scale{scale:03d}", coarse_entry, scale, end_timestamp,
            args.seed, args.nvencc.resolve(), args.base.resolve(),
            args.decode_ffmpeg.resolve(), frames, width, height,
            args.work.resolve())
    coarse_sigmas = {
        scale: cached_sigma(arm, width, height, args.work.resolve())
        for scale, arm in coarse_arms.items()
    }
    target_sigma = fine_sigma
    coarse = min(
        coarse_arms.values(),
        key=lambda arm: abs(coarse_sigmas[arm["scale"]] - target_sigma))
    coarse_sigma = coarse_sigmas[coarse["scale"]]
    relative_error = coarse_sigma / target_sigma - 1.0
    if abs(relative_error) > args.max_relative_amplitude_error:
        raise RuntimeError(
            f"best coarse luma sigma differs by {relative_error:+.3%}; "
            "amplitude match failed")

    isolation = cached_isolation(fine, coarse, frames, args.work.resolve())
    fine["metrics"] = cached_grain_metrics(
        fine, width, height, args.work.resolve())
    coarse["metrics"] = cached_grain_metrics(
        coarse, width, height, args.work.resolve())
    report = {
        "scope": "fixed-base, fixed-seed, flat-luma, luma-only texture replay",
        "inputs": {
            "binary": identity(args.nvencc.resolve(), include_hash=True),
            "base": identity(args.base.resolve(), include_hash=True),
            "reference": identity(args.reference.resolve(), include_hash=True),
            "fine_table": identity(args.fine_table.resolve(), include_hash=True),
            "coarse_table": identity(args.coarse_table.resolve(), include_hash=True),
            "model_time_seconds": args.model_time,
            "seed": args.seed,
        },
        "geometry": {"width": width, "height": height, "frames": frames},
        "isolation": isolation,
        "calibration": {
            "fine_scale": args.fine_scale,
            "initial_coarse_scale": initial_coarse_scale,
            "searched_coarse_scales": sorted(coarse_arms),
            "searched_coarse_sigmas_8bit": coarse_sigmas,
            "selected_coarse_scale": coarse["scale"],
            "fine_sigma_8bit": target_sigma,
            "coarse_sigma_8bit": coarse_sigma,
            "coarse_over_fine_sigma": 1.0 + relative_error,
        },
        "arms": {"fine": fine, "coarse": coarse},
    }

    if not args.no_score:
        common_base = make_lossless_base(
            fine, frames, args.encode_ffmpeg.resolve(), args.work.resolve())
        scoring_work = args.work.resolve() / "metrics"
        scoring_work.mkdir(exist_ok=True)
        scores = {}
        for reference_name, reference in (
                ("source", args.reference.resolve()),
                ("common_base", common_base.resolve())):
            arms = {}
            for arm_name, arm in (("fine", fine), ("coarse", coarse)):
                print(f"[score] {reference_name} {arm_name}", flush=True)
                arms[arm_name] = pooled_metrics(
                    reference, Path(arm["encoded"]),
                    f"shining-{reference_name}-{arm_name}", scoring_work)
            scores[reference_name] = {
                "arms": arms,
                "coarse_minus_fine": metric_delta(arms["coarse"], arms["fine"]),
            }
        report["scores"] = scores
        report["common_reencoded_base"] = identity(common_base, include_hash=True)

    output = args.work.resolve() / "report.json"
    write_json(output, report)
    print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
