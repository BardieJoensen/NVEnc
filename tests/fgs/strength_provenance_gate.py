#!/usr/bin/env python3
"""Isolate AV1 FGS texture fitting from strength-curve provenance.

This is a child experiment of ``tail_architecture_gate.py``.  It consumes the
exact retained reels and three reference arms from that gate; it never seeks a
source again and never touches Tdarr.  A pinned candidate first reproduces the
accepted source/static arm as a no-hook control.  The run is rejected unless
that control has the same video elementary stream, film-grain table and
grain-disabled pixels as its parent.

Two treatment arms then keep source-derived AR texture while changing only the
statistics used to fit the scaling curves:

* ``texture-residual-all`` uses residual strength for Y, U and V;
* ``texture-source-yu`` uses source strength for Y/U and residual strength for V.

Every new stream receives a complete libdav1d decode.  Temporal reports reuse
the parent's frozen source-only scene grid and ratio-of-means amplitude oracle.
The response closure remains a read-only reference; it is not layered onto a
provenance treatment until this localization experiment identifies one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import emission_audit  # noqa: E402
import filmgrn  # noqa: E402
import general_content_gate as common  # noqa: E402
import review_score  # noqa: E402
import tail_architecture_gate as tail  # noqa: E402
from integrated_architecture import identity, partial_path, write_json  # noqa: E402


REFERENCE_ARMS = ("production", "source", "response")
CONTROL_ARM = "source-control"
EXPERIMENT_ARMS = ("texture-residual-all", "texture-source-yu")
NEW_ARMS = (CONTROL_ARM, *EXPERIMENT_ARMS)
REPORT_ARMS = (*REFERENCE_ARMS, *EXPERIMENT_ARMS)
MEASUREMENT_VERSION = "strength-provenance-v1-ratio-of-means"
HOOK = "NVENC_FGS_TEST_STRENGTH_PROVENANCE"
HOOK_VALUE = {
    "texture-residual-all": "residual-all",
    "texture-source-yu": "source-yu",
}
ACTIVATION = {
    "texture-residual-all": (
        "source AR texture with residual strength on Y/U/V (test only)."),
    "texture-source-yu": (
        "source AR texture/strength on Y/U with residual strength on V "
        "(test only)."),
}


def arm_environment(
    arm: str, inherited: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build a clean source/static environment for one new arm."""
    if arm not in NEW_ARMS:
        raise ValueError(arm)
    env = tail.arm_environment("source", inherited)
    if arm in HOOK_VALUE:
        env[HOOK] = HOOK_VALUE[arm]
    return env


def validate_encode_log(arm: str, path: Path) -> None:
    """Fail closed if a test hook was absent, ignored or unexpectedly active."""
    text = path.read_text(encoding="utf-8", errors="replace")
    tail.validate_encode_log("source", path)
    if "fitting the test-only source model from temporally static blocks" not in text:
        raise RuntimeError(f"{arm}: source/static model hook was not active; see {path}")
    if "film-grain: ignoring" in text:
        raise RuntimeError(f"{arm}: encoder ignored a film-grain control; see {path}")
    activations = [value for value in ACTIVATION.values() if value in text]
    if arm == CONTROL_ARM:
        if activations:
            raise RuntimeError(
                f"{arm}: a strength-provenance hook leaked into the control; see {path}")
    elif activations != [ACTIVATION[arm]]:
        raise RuntimeError(
            f"{arm}: expected exactly one strength-provenance activation; see {path}")


def temporal_command(
    report_script: Path, source: Path, encoded: dict[str, Path], plane: str,
    frames: list[int], output: Path,
) -> list[str]:
    command = [
        sys.executable, str(report_script), "--source", str(source),
        "--plane", plane, "--bits", "10", "--flat-selector", "production",
        "--luma-bins", "8", "--frames", ",".join(map(str, frames)),
        "--skip-thin", "--minimum-frames", "0", "--json-out", str(output),
    ]
    for arm in REPORT_ARMS:
        command += ["--arm", f"{arm}={encoded[arm]}"]
    return command


def validate_parent(parent: dict, selected: list[str] | None = None) -> None:
    """Reject stale, partial or differently sampled parent measurements."""
    expected = {
        "measurement_version": tail.MEASUREMENT_VERSION,
        "scene_frames": 120,
        "scene_fractions": list(tail.SCENE_FRACTIONS),
        "sample_offsets": list(tail.SAMPLE_OFFSETS),
    }
    for key, value in expected.items():
        if parent.get(key) != value:
            raise RuntimeError(
                f"parent {key} is {parent.get(key)!r}; expected {value!r}")
    titles = parent.get("titles", {})
    names = list(titles) if selected is None else selected
    for name in names:
        if name not in titles:
            raise RuntimeError(f"parent lacks selected title {name}")
        title = titles[name]
        if set(REFERENCE_ARMS).difference(title.get("arms", {})):
            raise RuntimeError(f"{name}: parent lacks a required reference arm")
        for plane in ("y", "u", "v"):
            reports = title.get("grain_reports", {}).get(plane, [])
            if len(reports) != len(tail.SCENE_FRACTIONS):
                raise RuntimeError(f"{name}/{plane}: parent report grid is incomplete")
            for record in reports:
                path = Path(record["identity"]["path"])
                if tail.MEASUREMENT_VERSION not in path.name:
                    raise RuntimeError(
                        f"{name}/{plane}: parent report is not the corrected v3 oracle: {path}")
                # Parsing is intentional: a renamed legacy report must not pass.
                tail.metric_summary(path)


def decoded_av1_pixel_hash(path: Path, ffmpeg: Path) -> str:
    """Hash the played pixels with dav1d synthesis explicitly enabled."""
    result = subprocess.run([
        str(ffmpeg), "-hide_banner", "-nostdin", "-v", "error", "-xerror",
        "-c:v", "libdav1d", "-filmgrain", "1", "-i", str(path),
        "-map", "0:v:0", "-an", "-sn", "-dn", "-f", "hash",
        "-hash", "sha256", "-",
    ], capture_output=True, text=True, check=False, timeout=1800)
    if result.returncode:
        raise RuntimeError(
            f"played-pixel hash failed for {path}: {result.stderr[-2000:]}")
    line = result.stdout.strip()
    if not line.startswith("SHA256=") or len(line) != 71:
        raise RuntimeError(f"unexpected played-pixel hash for {path}: {line!r}")
    return line[7:]


def table_semantic_hash(path: Path) -> str:
    """Hash decoded table semantics, ignoring redundant curve control points."""
    canonical = []
    for entry in filmgrn.load(path):
        canonical.append({
            "start": entry["start"],
            "end": entry["end"],
            "apply_grain": entry["apply_grain"],
            "random_seed": entry["random_seed"],
            "update_parameters": entry["update_parameters"],
            "params": entry["params"],
            "curves": {
                plane: filmgrn._curve(entry["scaling_points"][plane])
                for plane in ("y", "cb", "cr")
            },
            "ar_coeffs": entry["ar_coeffs"],
        })
    payload = json.dumps(
        canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def control_isolation(parent_arm: dict, control: dict) -> dict:
    checks = {
        "video_stream_identical": (
            parent_arm["video_stream_md5"] == control["video_stream_md5"]),
        "table_identical": (
            parent_arm["table"]["identity"]["sha256"]
            == control["table"]["identity"]["sha256"]),
        "base_pixels_identical": (
            parent_arm["base_pixel_sha256"] == control["base_pixel_sha256"]),
        "table_semantics_identical": (
            parent_arm["table_semantic_sha256"]
            == control["table_semantic_sha256"]),
        "played_pixels_identical": (
            parent_arm["finished_pixel_sha256"]
            == control["finished_pixel_sha256"]),
    }
    # Raw table/stream identity is diagnostic.  A simplifier may choose a
    # different redundant point on a perfectly flat scaling segment; decoded
    # curve semantics and played pixels are the correctness boundary.
    checks["passed"] = all(checks[key] for key in (
        "base_pixels_identical", "table_semantics_identical",
        "played_pixels_identical"))
    return checks


def stream_texture_isolation(
    control_path: Path, treatment_path: Path, frames: int,
) -> dict:
    """Compare actual per-frame AV1 AR fields, not only table accumulators."""
    control = emission_audit.probe_grain_entries(
        str(control_path), frames, required_frames=[])
    treatment = emission_audit.probe_grain_entries(
        str(treatment_path), frames, required_frames=[])
    presence_mismatch = 0
    jointly_grained = 0
    identical = 0
    plane_identical = {plane: 0 for plane in ("y", "cb", "cr")}
    parameter_identical = 0
    for frame in range(frames):
        left, right = control.get(frame), treatment.get(frame)
        if (left is None) != (right is None):
            presence_mismatch += 1
            continue
        if left is None:
            continue
        jointly_grained += 1
        parameters_match = all(
            left["params"][key] == right["params"][key]
            for key in ("ar_coeff_lag", "ar_coeff_shift", "grain_scale_shift"))
        parameter_identical += parameters_match
        planes_match = {
            plane: left["ar_coeffs"][plane] == right["ar_coeffs"][plane]
            for plane in ("y", "cb", "cr")
        }
        for plane, matched in planes_match.items():
            plane_identical[plane] += matched
        identical += parameters_match and all(planes_match.values())
    return {
        "frames": frames,
        "grain_presence_mismatch_frames": presence_mismatch,
        "jointly_grained_frames": jointly_grained,
        "all_texture_fields_identical_frames": identical,
        "texture_parameters_identical_frames": parameter_identical,
        "ar_coefficients_identical_frames": plane_identical,
        "fully_isolated": (
            presence_mismatch == 0 and jointly_grained > 0
            and identical == jointly_grained),
    }


def new_arm_record(
    name: str, arm: str, candidate: Path, reel: Path, reel_probe: dict,
    reel_stream: dict, qvbr: int, total_frames: int, title_dir: Path,
    task_dir: Path, ffmpeg: Path,
) -> tuple[dict, Path, Path]:
    env = arm_environment(arm)
    encoded = title_dir / f"{arm}.mkv"
    table = title_dir / f"{arm}.tbl"
    encoded_partial, table_partial = partial_path(encoded), partial_path(table)
    command = tail.encode_command(
        candidate, reel, encoded_partial, table_partial, "source", qvbr)
    expected = {
        "command": command,
        "environment": {
            key: value for key, value in env.items()
            if key.startswith(tail.RESEARCH_PREFIX)
        },
        "source": identity(reel, include_hash=True),
        "binary": identity(candidate, include_hash=True),
    }
    encode = tail.run_task(
        f"{name}-{arm}-encode", command, env, expected,
        [encoded_partial, table_partial], [encoded, table],
        task_dir / f"{name}-{arm}-encode.task.json",
        task_dir / f"{name}-{arm}-encode.log",
        validate_log=lambda path: validate_encode_log(arm, path),
        validate_outputs=lambda paths: common.require_frames(paths[0], total_frames),
        hash_outputs=True)
    encoded_probe = common.require_frames(encoded, total_frames)
    review_score.require_matching_color(reel_probe, encoded_probe)

    decode_command = tail.full_decode_command(ffmpeg, encoded)
    decode = tail.run_check(
        f"{name}-{arm}-full-dav1d", decode_command, {
            "command": decode_command,
            "source": identity(encoded, include_hash=True),
            "binary": identity(ffmpeg, include_hash=True),
        }, task_dir / f"{name}-{arm}-full-dav1d.task.json",
        task_dir / f"{name}-{arm}-full-dav1d.log")

    base = title_dir / f"{arm}-base.mkv"
    base_partial = partial_path(base)
    base_command = tail.decode_base_command(
        ffmpeg, encoded, base_partial, total_frames, reel_stream)
    base_record = tail.run_task(
        f"{name}-{arm}-base", base_command, tail.arm_environment("plain"), {
            "command": base_command,
            "source": identity(encoded, include_hash=True),
            "binary": identity(ffmpeg, include_hash=True),
        }, [base_partial], [base], task_dir / f"{name}-{arm}-base.task.json",
        task_dir / f"{name}-{arm}-base.log",
        validate_outputs=lambda paths: common.require_frames(paths[0], total_frames))
    base_probe = common.require_frames(base, total_frames)
    review_score.require_matching_color(reel_probe, base_probe)
    record = {
        "encode": encode,
        "encoded": identity(encoded, include_hash=True),
        "video_stream_md5": tail.stream_md5(encoded, ffmpeg),
        "dav1d": decode,
        "base": base_record,
        "base_pixel_sha256": common.decoded_pixel_hash(base, ffmpeg),
        "table": {
            "identity": identity(table, include_hash=True),
            "summary": common.table_summary(table),
        },
        "table_semantic_sha256": table_semantic_hash(table),
    }
    if arm == CONTROL_ARM:
        record["finished_pixel_sha256"] = decoded_av1_pixel_hash(encoded, ffmpeg)
    return record, encoded, base


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--parent-work", default="/media/merged-storage/media/test-encodes/"
        "sourcefit-tail-gate-20260809")
    parser.add_argument(
        "--work", default="/media/merged-storage/media/test-encodes/"
        "sourcefit-strength-provenance-20260809")
    parser.add_argument("--candidate-nvencc", required=True)
    parser.add_argument("--ffmpeg", default="/usr/local/bin/ffmpeg")
    parser.add_argument("--ffprobe", default="/usr/local/bin/ffprobe")
    parser.add_argument("--titles", default="")
    parser.add_argument(
        "--stop-after", choices=("encode", "measure"), default="measure")
    args = parser.parse_args()

    parent_work, work = Path(args.parent_work).resolve(), Path(args.work).resolve()
    parent_path = parent_work / "manifest.json"
    candidate = Path(args.candidate_nvencc).resolve()
    ffmpeg, ffprobe = Path(args.ffmpeg).resolve(), Path(args.ffprobe).resolve()
    report_script = Path(__file__).with_name("temporal_grain_report.py").resolve()
    for executable in (candidate, ffmpeg, ffprobe, report_script):
        if not executable.is_file():
            parser.error(f"missing executable: {executable}")
    if not parent_path.is_file():
        parser.error(f"missing parent manifest: {parent_path}")
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    selected = ([value.strip() for value in args.titles.split(",") if value.strip()]
                or list(parent["titles"]))
    unknown = sorted(set(selected).difference(parent["titles"]))
    if unknown:
        parser.error(f"unknown parent titles: {', '.join(unknown)}")
    validate_parent(parent, selected)

    task_dir, report_dir = work / "tasks", work / "grain-reports"
    for directory in (work, task_dir, report_dir):
        directory.mkdir(parents=True, exist_ok=True)
    review_score.FFMPEG, review_score.FFPROBE = str(ffmpeg), str(ffprobe)
    emission_audit.FFPROBE = str(ffprobe)
    total_frames = parent["scene_frames"] * len(parent["scene_fractions"])
    manifest = {
        "purpose": "source AR texture / strength-provenance isolation; no production mutation",
        "measurement_version": MEASUREMENT_VERSION,
        "parent": identity(parent_path, include_hash=True),
        "parent_measurement_version": parent["measurement_version"],
        "candidate_binary": identity(candidate, include_hash=True),
        "scene_frames": parent["scene_frames"],
        "scene_fractions": parent["scene_fractions"],
        "sample_offsets": parent["sample_offsets"],
        "reference_arms": REFERENCE_ARMS,
        "new_arms": NEW_ARMS,
        "report_arms": REPORT_ARMS,
        "titles": {},
    }

    for name in selected:
        source_title = parent["titles"][name]
        reel = Path(source_title["reel"]["path"])
        if identity(reel, include_hash=True) != source_title["reel"]:
            raise RuntimeError(f"{name}: retained reel identity changed")
        reel_probe = common.require_frames(reel, total_frames)
        reel_stream = common.probe_stream(reel, ffprobe)
        title_dir = work / name
        title_dir.mkdir(parents=True, exist_ok=True)
        references = {
            arm: Path(source_title["arms"][arm]["encoded"]["path"])
            for arm in REFERENCE_ARMS
        }
        for arm, path in references.items():
            if identity(path, include_hash=True) != source_title["arms"][arm]["encoded"]:
                raise RuntimeError(f"{name}/{arm}: parent reference identity changed")
        title_record = {
            "tail": source_title["tail"],
            "qvbr": source_title["qvbr"],
            "reel": source_title["reel"],
            "references": {
                arm: source_title["arms"][arm] for arm in REFERENCE_ARMS},
            "arms": {},
        }
        manifest["titles"][name] = title_record
        write_json(work / "manifest.json", manifest)

        encoded = dict(references)
        bases = {}
        for arm in NEW_ARMS:
            record, encoded_path, base_path = new_arm_record(
                name, arm, candidate, reel, reel_probe, reel_stream,
                source_title["qvbr"], total_frames, title_dir, task_dir, ffmpeg)
            title_record["arms"][arm] = record
            encoded[arm] = encoded_path
            bases[arm] = base_path
            write_json(work / "manifest.json", manifest)

        parent_source = dict(source_title["arms"]["source"])
        parent_source_path = references["source"]
        parent_source_table = Path(parent_source["table"]["identity"]["path"])
        parent_source["finished_pixel_sha256"] = decoded_av1_pixel_hash(
            parent_source_path, ffmpeg)
        parent_source["table_semantic_sha256"] = table_semantic_hash(
            parent_source_table)
        title_record["parent_source_oracles"] = {
            "finished_pixel_sha256": parent_source["finished_pixel_sha256"],
            "table_semantic_sha256": parent_source["table_semantic_sha256"],
        }
        isolation = control_isolation(
            parent_source, title_record["arms"][CONTROL_ARM])
        title_record["control_isolation"] = isolation
        if not isolation["passed"]:
            write_json(work / "manifest.json", manifest)
            raise RuntimeError(f"{name}: pinned no-hook control did not reproduce parent source arm")
        for arm in EXPERIMENT_ARMS:
            title_record["arms"][arm]["base_vs_control_identical"] = (
                title_record["arms"][arm]["base_pixel_sha256"]
                == title_record["arms"][CONTROL_ARM]["base_pixel_sha256"])
            title_record["arms"][arm]["stream_texture_isolation"] = (
                stream_texture_isolation(encoded[CONTROL_ARM], encoded[arm], total_frames))
        write_json(work / "manifest.json", manifest)
        if args.stop_after == "encode":
            continue

        measured = {arm: encoded[arm] for arm in REPORT_ARMS}
        for plane in ("y", "u", "v"):
            plane_records = []
            for scene in range(len(parent["scene_fractions"])):
                sample_frames = [
                    scene * parent["scene_frames"] + offset
                    for offset in parent["sample_offsets"]
                ]
                stem = f"{name}-scene{scene + 1}-{plane}-{MEASUREMENT_VERSION}"
                report = report_dir / f"{stem}.json"
                report_partial = partial_path(report)
                command = temporal_command(
                    report_script, reel, measured, plane, sample_frames,
                    report_partial)
                expected = {
                    "command": command,
                    "source": identity(reel, include_hash=True),
                    "arms": {
                        arm: identity(path, include_hash=True)
                        for arm, path in measured.items()
                    },
                    "measurement": identity(report_script, include_hash=True),
                    "scene": scene + 1,
                }
                tail.run_task(
                    f"{name}-scene{scene + 1}-{plane}-temporal", command,
                    tail.arm_environment("plain"), expected, [report_partial], [report],
                    task_dir / f"{stem}.task.json", task_dir / f"{stem}.log",
                    validate_outputs=lambda paths, scene=scene: tail.validate_temporal_report(
                        paths[0], parent["scene_frames"], scene))
                plane_records.append({
                    "identity": identity(report, include_hash=True),
                    "summary": tail.validate_temporal_report(
                        report, parent["scene_frames"], scene),
                })
                title_record.setdefault("grain_reports", {})[plane] = plane_records
                write_json(work / "manifest.json", manifest)
            gradable = sum(record["summary"]["gradable"] for record in plane_records)
            title_record.setdefault("temporal_coverage", {})[plane] = {
                "gradable_scenes": gradable,
                "required_scenes": 3,
                "title_gradable": gradable >= 3,
            }
            write_json(work / "manifest.json", manifest)

    print(f"manifest: {work / 'manifest.json'}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        raise SystemExit(130)
