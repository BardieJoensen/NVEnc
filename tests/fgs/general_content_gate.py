#!/usr/bin/env python3
"""Gate bilateral source fitting on ordinary real content.

The six-film architecture gate answers whether source fitting improves film
grain.  It does not answer whether the unchanged bilateral separator is safe
on material that has little or no film grain.  This harness asks that second
question without inventing a routing threshold.

Four arms keep build drift and model-source effects separate:

* ``plain``: deployed r4069, no FGS;
* ``deployed``: deployed r4069 and the live bilateral/residual analyser;
* ``candidate-control``: candidate binary, bilateral/residual analyser; and
* ``bilateral-source``: the same candidate binary with ``modelsrc=on``.

The corpus includes the labelled Drag Race and Stormester failures, studio
detail, clean digital video, animation, and a grain-positive Silo control.
Every source is an original H.264 download rather than a library AV1 encode.
Clips are cut losslessly at one-third duration.  The flow's actual operating
point is reproduced: QVBR 29 for ordinary content and QVBR 34 for animation,
with quality/HQ, AQ and temporal AQ enabled.

FGS arms are decoded twice with dav1d: grain disabled (``base``) and enabled
(``finished``).  Finished-frame full-reference metrics are reported but must
not be used as a grain-routing oracle: independently seeded synthesis is
penalised by construction.  Base results and direct base-to-base comparisons
are the separator/build-safety evidence.

No media is stored in git.  Tasks are command/source/binary manifested,
resumable, and publish from ``.partial`` paths only after successful exit.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import filmgrn  # noqa: E402
import review_score  # noqa: E402
from campaign import verify_source  # noqa: E402
from integrated_architecture import (  # noqa: E402
    complete_task,
    identity,
    partial_path,
    publish_outputs,
    run_logged,
    write_json,
)


@dataclass(frozen=True)
class Title:
    name: str
    source: str
    content_class: str
    expectation: str
    qvbr: int = 29
    seek_fraction: float = 0.33


TITLES = (
    Title(
        "Drag_Race",
        "/media/merged-storage/media/downloads/long-term-seeding/tv-shows/"
        "RuPauls.Drag.Race.S12.1080p.AMZN.WEB-DL.DDP2.0.H.264-TEPES/"
        "RuPauls.Drag.Race.S12E03.Worlds.Worst.1080p.AMZN.WEB-DL."
        "DDP2.0.H.264-TEPES.mkv",
        "saturated studio / hard chroma edges",
        "labelled production FGS negative",
    ),
    Title(
        "Stormester",
        "/media/merged-storage/media/downloads/long-term-seeding/tv-shows/"
        "Stormester.S10E01.DANiSH.1080p.WEB-DL.H.264.AAC2.0-SHOWTiME/"
        "Stormester.S10E01.DANiSH.1080p.WEB-DL.H.264.AAC2.0-SHOWTiME.mkv",
        "bright studio / graphics",
        "labelled production FGS negative",
    ),
    Title(
        "Big_Brother",
        "/media/merged-storage/media/downloads/long-term-seeding/tv-shows/"
        "Big.Brother.US.S28E11.1080p.AMZN.WEB-DL.DDP2.0.H.264-NTb.mkv",
        "studio / non-grain high-frequency structure",
        "known AV1 grain-model representation limit",
    ),
    Title(
        "Supergirl",
        "/media/merged-storage/media/downloads/long-term-seeding/movies/"
        "Supergirl.2026.1080p.MA.WEB-DL.DDP5.1.Atmos.x264-Draken02.mkv",
        "modern clean digital",
        "clean-content control",
    ),
    Title(
        "Rick_and_Morty",
        "/media/merged-storage/media/downloads/long-term-seeding/tv-shows/"
        "Rick.and.Morty.S09.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb/"
        "Rick.and.Morty.S09E01.Theres.Something.About.Morty.1080p.AMZN."
        "WEB-DL.DDP5.1.H.264-NTb.mkv",
        "2D animation",
        "clean-edge and QVBR-34 transfer control",
        qvbr=34,
    ),
    Title(
        "Silo",
        "/media/merged-storage/media/downloads/long-term-seeding/tv-shows/"
        "Silo.S01.1080p.ATVP.WEB-DL.DDP5.1.H.264-NTb/"
        "Silo.S01E01.Freedom.Day.1080p.ATVP.WEB-DL.DDP5.1.H.264-NTb.mkv",
        "fine digital grain",
        "grain-positive control",
    ),
)

ARMS = ("plain", "deployed", "candidate-control", "bilateral-source")
FGS = "denoise=auto,chroma=auto,denoiser=bilateral"


def title_map() -> dict[str, Title]:
    return {title.name: title for title in TITLES}


def probe_stream(path: Path, ffprobe: Path) -> dict:
    result = subprocess.run([
        str(ffprobe), "-v", "error", "-select_streams", "v:0",
        "-show_entries",
        "format=duration:stream=codec_name,width,height,pix_fmt,avg_frame_rate,"
        "color_range,color_space,color_transfer,color_primaries,field_order",
        "-of", "json", str(path),
    ], capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(f"could not probe {path}: {result.stderr[-2000:]}")
    document = json.loads(result.stdout)
    streams = document.get("streams", [])
    if len(streams) != 1:
        raise RuntimeError(f"{path}: expected exactly one selected video stream")
    stream = streams[0]
    stream["duration"] = float(document["format"]["duration"])
    return stream


def color_args(stream: dict) -> list[str]:
    mapping = (
        ("color_range", "-color_range"),
        ("color_space", "-colorspace"),
        ("color_transfer", "-color_trc"),
        ("color_primaries", "-color_primaries"),
    )
    command = []
    for field, option in mapping:
        value = stream.get(field)
        if value and value not in ("unknown", "reserved"):
            command += [option, str(value)]
    return command


def extract_command(
    ffmpeg: Path,
    source: Path,
    output: Path,
    start: float,
    frames: int,
    stream: dict,
) -> list[str]:
    return [
        str(ffmpeg), "-hide_banner", "-nostdin", "-v", "error", "-xerror",
        "-ss", f"{start:.6f}", "-i", str(source), "-map", "0:v:0",
        "-frames:v", str(frames), "-an", "-sn", "-dn",
        "-fps_mode", "passthrough", "-c:v", "ffv1", "-level", "3",
        "-coder", "1", "-context", "1", "-g", "1", "-slicecrc", "1",
        "-pix_fmt", "yuv420p10le", *color_args(stream), "-y", str(output),
    ]


def fgs_options(arm: str) -> str | None:
    if arm == "plain":
        return None
    if arm in ("deployed", "candidate-control"):
        return FGS
    if arm == "bilateral-source":
        return FGS + ",modelsrc=on"
    raise ValueError(arm)


def encode_command(
    binary: Path,
    source: Path,
    output: Path,
    table: Path | None,
    arm: str,
    qvbr: int,
) -> list[str]:
    command = [
        str(binary), "--avsw", "-i", str(source), "--codec", "av1",
        "--output-depth", "10", "--qvbr", str(qvbr), "--max-bitrate",
        "50000", "--preset", "quality", "--tune", "hq", "--aq",
        "--aq-temporal", "--colormatrix", "auto", "--colorprim", "auto",
        "--transfer", "auto", "--colorrange", "auto", "--master-display",
        "copy", "--max-cll", "copy",
    ]
    options = fgs_options(arm)
    if options is not None:
        command += ["--av1-film-grain", options]
        if table is None:
            raise ValueError(f"{arm}: FGS arm requires a grain table")
        command += ["--film-grain-table-out", str(table)]
    command += ["--log-level", "debug", "-o", str(output)]
    return command


def decode_command(
    ffmpeg: Path,
    encoded: Path,
    output: Path,
    frames: int,
    filmgrain: int,
    stream: dict,
) -> list[str]:
    return [
        str(ffmpeg), "-hide_banner", "-nostdin", "-v", "error", "-xerror",
        "-c:v", "libdav1d", "-filmgrain", str(filmgrain), "-i", str(encoded),
        "-map", "0:v:0", "-frames:v", str(frames), "-an", "-sn", "-dn",
        "-fps_mode", "passthrough", "-c:v", "ffv1", "-level", "3",
        "-coder", "1", "-context", "1", "-g", "1", "-slicecrc", "1",
        "-pix_fmt", "yuv420p10le", *color_args(stream), "-y", str(output),
    ]


def run_task(
    name: str,
    command: list[str],
    expected: dict,
    partials: list[Path],
    outputs: list[Path],
    manifest: Path,
    log: Path,
) -> dict:
    if complete_task(manifest, expected, outputs):
        print(f"[resume] {name}", flush=True)
        return json.loads(manifest.read_text(encoding="utf-8"))
    existing = [str(path) for path in outputs if path.exists()]
    if existing:
        raise RuntimeError(
            f"{name}: outputs exist without matching task manifest: {existing}")
    print(f"[run] {name}", flush=True)
    elapsed = run_logged(command, os.environ.copy(), log)
    publish_outputs(partials, outputs)
    record = {
        "input": expected,
        "outputs": [identity(path) for path in outputs],
        "elapsed_seconds": elapsed,
        "log": str(log.resolve()),
    }
    write_json(manifest, record)
    return record


def require_frames(path: Path, frames: int) -> dict:
    probe = review_score.probe_video(str(path))
    count = len(probe["timestamps"])
    if count != frames:
        raise RuntimeError(f"{path}: {count} packets, expected {frames}")
    return probe


def table_summary(path: Path) -> dict:
    entries = filmgrn.load(path)
    duration = sum(entry["end"] - entry["start"] for entry in entries)
    applied = [entry for entry in entries if entry["apply_grain"]]
    updates = [
        entry for entry in entries
        if entry["apply_grain"] and entry["update_parameters"]
    ]
    grain_duration = sum(entry["end"] - entry["start"] for entry in applied)
    summary = {
        "entries": len(entries),
        "grain_updates": len(updates),
        "grain_interval_fraction": (
            grain_duration / duration if duration else 0.0),
        "mean_scaling_points": {},
        "mean_normalized_curve_rms": {},
    }
    for plane in ("y", "cb", "cr"):
        counts = [len(entry["scaling_points"][plane]) for entry in updates]
        amplitudes = []
        for entry in updates:
            points = entry["scaling_points"][plane]
            if not points:
                continue
            shift = (entry["params"]["scaling_shift"]
                     + entry["params"]["grain_scale_shift"])
            curve = filmgrn._curve(points)
            amplitudes.append(
                (sum(value * value for value in curve) / len(curve)) ** 0.5
                / (1 << shift))
        summary["mean_scaling_points"][plane] = (
            statistics.mean(counts) if counts else 0.0)
        summary["mean_normalized_curve_rms"][plane] = (
            statistics.mean(amplitudes) if amplitudes else 0.0)
    return summary


def decoded_pixel_hash(path: Path, ffmpeg: Path) -> str:
    result = subprocess.run([
        str(ffmpeg), "-hide_banner", "-nostdin", "-v", "error", "-xerror",
        "-i", str(path), "-map", "0:v:0", "-an", "-sn", "-dn",
        "-f", "hash", "-hash", "sha256", "-",
    ], capture_output=True, text=True, check=False, timeout=1800)
    if result.returncode:
        raise RuntimeError(f"pixel hash failed for {path}: {result.stderr[-2000:]}")
    line = result.stdout.strip()
    prefix = "SHA256="
    if not line.startswith(prefix) or len(line) != len(prefix) + 64:
        raise RuntimeError(f"unexpected hash output for {path}: {line!r}")
    return line[len(prefix):]


def score_pair(
    reference: Path,
    distorted: Path,
    title: str,
    arm: str,
    kind: str,
    metric_dir: Path,
    full: bool = True,
) -> dict:
    tag = f"{title}-{arm}-{kind}"
    expected_frames = len(review_score.probe_video(str(reference))["timestamps"])
    document, frames = review_score.vmaf_run(
        str(reference), str(distorted), tag, work=str(metric_dir),
        limit=expected_frames)
    if frames != expected_frames:
        raise RuntimeError(
            f"{tag}: scored {frames} frames, expected {expected_frames}")
    pooled = document["pooled_metrics"]
    vmaf_frames = sorted(
        frame["metrics"]["vmaf"] for frame in document["frames"])
    row = {
        "title": title,
        "arm": arm,
        "kind": kind,
        "frames": frames,
        "bytes": distorted.stat().st_size,
        "vmaf": round(pooled["vmaf"]["mean"], 4),
        "vmaf_p1": round(review_score.pct(vmaf_frames, 1), 4),
        "vmaf_neg": round(pooled["vmaf_neg"]["mean"], 4),
        "psnr_y": round(pooled["psnr_y"]["mean"], 4),
        "ssim": round(pooled["float_ssim"]["mean"], 7),
        "ciede2000": round(pooled["ciede2000"]["mean"], 4),
    }
    if not full:
        return row
    ssimu2 = sorted(row_[0] for row_ in review_score.ffvship(
        str(reference), str(distorted), tag, "SSIMULACRA2",
        f"ssimu2-{tag}.json", frames, work=str(metric_dir)))
    butter = review_score.ffvship(
        str(reference), str(distorted), tag, "Butteraugli",
        f"butter-{tag}.json", frames, work=str(metric_dir))
    row.update({
        "ssimulacra2_mean": round(statistics.mean(ssimu2), 4),
        "ssimulacra2_p5": round(review_score.pct(ssimu2, 5), 4),
        "butteraugli_2norm_mean": round(
            statistics.mean(value[0] for value in butter), 5),
        "butteraugli_max_p95": round(
            review_score.pct(sorted(value[2] for value in butter), 95), 5),
    })
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--work",
        default="/media/merged-storage/media/test-encodes/"
                "sourcefit-general-gate-20260803")
    parser.add_argument("--production-nvencc", default="/opt/docker-apps/build/tdarr-node/nvencc")
    parser.add_argument(
        "--candidate-nvencc",
        default="/home/bardie/.cache/fgs-gate/builds/"
                "pin-603c2eea-1785764448/build-gate/nvencc")
    parser.add_argument("--ffmpeg", default="/usr/local/bin/ffmpeg")
    parser.add_argument("--ffprobe", default="/usr/local/bin/ffprobe")
    parser.add_argument("--frames", type=int, default=600)
    parser.add_argument("--titles", default=",".join(title.name for title in TITLES))
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--encode-only", action="store_true")
    parser.add_argument("--score-only", action="store_true")
    parser.add_argument(
        "--vmaf-only", action="store_true",
        help="skip SSIMULACRA2 and Butteraugli while retaining strict VMAF/PSNR")
    args = parser.parse_args()
    phase_flags = sum((args.prepare_only, args.encode_only, args.score_only))
    if phase_flags > 1:
        parser.error("choose at most one of --prepare-only, --encode-only, --score-only")
    if args.frames < 2:
        parser.error("--frames must be at least 2")

    work = Path(args.work).resolve()
    production = Path(args.production_nvencc).resolve()
    candidate = Path(args.candidate_nvencc).resolve()
    ffmpeg = Path(args.ffmpeg).resolve()
    ffprobe = Path(args.ffprobe).resolve()
    for executable in (production, candidate, ffmpeg, ffprobe):
        if not executable.is_file():
            parser.error(f"missing executable: {executable}")
    selected = [value.strip() for value in args.titles.split(",") if value.strip()]
    catalog = title_map()
    unknown = sorted(set(selected).difference(catalog))
    if unknown:
        parser.error(f"unknown titles: {', '.join(unknown)}")

    clip_dir = work / "clips"
    task_dir = work / "tasks"
    metric_dir = work / "metrics"
    for directory in (clip_dir, task_dir, metric_dir):
        directory.mkdir(parents=True, exist_ok=True)
    review_score.FFMPEG = str(ffmpeg)
    review_score.FFPROBE = str(ffprobe)

    run_manifest = {
        "purpose": "general-content safety and routing evidence for bilateral source fitting",
        "frames": args.frames,
        "production_binary": identity(production, include_hash=True),
        "candidate_binary": identity(candidate, include_hash=True),
        "titles": {},
    }
    decoded: dict[tuple[str, str, str], Path] = {}

    for name in selected:
        title = catalog[name]
        source = Path(title.source)
        if not source.is_file():
            raise RuntimeError(f"{name}: missing original source: {source}")
        source_note = verify_source(str(source))
        source_stream = probe_stream(source, ffprobe)
        start = source_stream["duration"] * title.seek_fraction
        clip = clip_dir / f"{name}.mkv"
        clip_partial = partial_path(clip)
        command = extract_command(
            ffmpeg, source, clip_partial, start, args.frames, source_stream)
        expected = {
            "command": command,
            "source": identity(source),
            "source_verification": source_note,
            "binary": identity(ffmpeg, include_hash=True),
        }
        run_task(
            f"{name}-extract", command, expected, [clip_partial], [clip],
            task_dir / f"{name}-extract.task.json",
            task_dir / f"{name}-extract.log")
        clip_probe = require_frames(clip, args.frames)
        clip_color = review_score.color_signature(clip_probe)
        title_record = {
            "class": title.content_class,
            "expectation": title.expectation,
            "qvbr": title.qvbr,
            "seek_fraction": title.seek_fraction,
            "seek_seconds": start,
            "source": identity(source, include_hash=True),
            "source_verification": source_note,
            "clip": identity(clip, include_hash=True),
            "clip_color": clip_color,
            "arms": {},
        }
        run_manifest["titles"][name] = title_record
        write_json(work / "manifest.json", run_manifest)
        if args.prepare_only:
            continue

        title_dir = work / name
        title_dir.mkdir(parents=True, exist_ok=True)
        for arm in ARMS:
            binary = production if arm in ("plain", "deployed") else candidate
            encoded = title_dir / f"{arm}.mkv"
            encoded_partial = partial_path(encoded)
            table = None if arm == "plain" else title_dir / f"{arm}.tbl"
            table_partial = None if table is None else partial_path(table)
            outputs = [encoded] + ([] if table is None else [table])
            partials = [encoded_partial] + ([] if table_partial is None else [table_partial])
            command = encode_command(
                binary, clip, encoded_partial, table_partial, arm, title.qvbr)
            expected = {
                "command": command,
                "source": identity(clip),
                "binary": identity(binary, include_hash=True),
            }
            record = run_task(
                f"{name}-{arm}-encode", command, expected, partials, outputs,
                task_dir / f"{name}-{arm}-encode.task.json",
                task_dir / f"{name}-{arm}-encode.log")
            encoded_probe = require_frames(encoded, args.frames)
            review_score.require_matching_color(clip_probe, encoded_probe)
            arm_record = {
                "encode": record,
                "encoded": identity(encoded, include_hash=True),
            }
            if table is not None:
                arm_record["table"] = {
                    "identity": identity(table, include_hash=True),
                    "summary": table_summary(table),
                }

            kinds = ("finished",) if arm == "plain" else ("base", "finished")
            for kind in kinds:
                output = title_dir / f"{arm}-{kind}.mkv"
                output_partial = partial_path(output)
                filmgrain = 0 if kind == "base" else 1
                command = decode_command(
                    ffmpeg, encoded, output_partial, args.frames, filmgrain,
                    source_stream)
                expected = {
                    "command": command,
                    "source": identity(encoded),
                    "binary": identity(ffmpeg, include_hash=True),
                }
                decode_record = run_task(
                    f"{name}-{arm}-{kind}-dav1d", command, expected,
                    [output_partial], [output],
                    task_dir / f"{name}-{arm}-{kind}-decode.task.json",
                    task_dir / f"{name}-{arm}-{kind}-decode.log")
                output_probe = require_frames(output, args.frames)
                review_score.require_matching_color(clip_probe, output_probe)
                decoded[(name, arm, kind)] = output
                arm_record[kind] = {
                    "decode": decode_record,
                    "identity": identity(output),
                    "pixel_sha256": decoded_pixel_hash(output, ffmpeg),
                }
            title_record["arms"][arm] = arm_record
            write_json(work / "manifest.json", run_manifest)
        if args.encode_only:
            continue

    if args.prepare_only or args.encode_only:
        return 0

    # Score after every title has passed full dav1d decode.  This keeps a
    # malformed candidate from producing a partial quality table that looks
    # like a successful corpus run.
    if args.score_only:
        manifest_path = work / "manifest.json"
        if not manifest_path.is_file():
            raise RuntimeError("--score-only requires an existing manifest")
        run_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for name in selected:
            title_dir = work / name
            for arm in ARMS:
                kinds = ("finished",) if arm == "plain" else ("base", "finished")
                for kind in kinds:
                    path = title_dir / f"{arm}-{kind}.mkv"
                    if not path.is_file():
                        raise RuntimeError(f"missing decoded output: {path}")
                    decoded[(name, arm, kind)] = path

    rows = []
    for name in selected:
        reference = clip_dir / f"{name}.mkv"
        for arm in ARMS:
            kinds = ("finished",) if arm == "plain" else ("base", "finished")
            for kind in kinds:
                print(f"[score] {name} {arm} {kind}", flush=True)
                row = score_pair(
                    reference, decoded[(name, arm, kind)], name, arm, kind,
                    metric_dir, full=not args.vmaf_only)
                rows.append(row)
                print(json.dumps(row, sort_keys=True), flush=True)
                write_json(metric_dir / "scores.json", rows)

        # Direct base comparisons answer whether candidate source fitting
        # changed the separator output, independent of grain in the source.
        for left, right, label in (
            ("deployed", "candidate-control", "build-drift"),
            ("candidate-control", "bilateral-source", "modelsrc-base-delta"),
        ):
            left_path = decoded[(name, left, "base")]
            right_path = decoded[(name, right, "base")]
            left_hash = run_manifest["titles"][name]["arms"][left]["base"]["pixel_sha256"]
            right_hash = run_manifest["titles"][name]["arms"][right]["base"]["pixel_sha256"]
            if left_hash == right_hash:
                row = {
                    "title": name,
                    "arm": f"{left}-vs-{right}",
                    "kind": label,
                    "frames": args.frames,
                    "pixel_identical": True,
                }
            else:
                row = score_pair(
                    left_path, right_path, name, f"{left}-vs-{right}",
                    label, metric_dir, full=False)
                row["pixel_identical"] = False
            rows.append(row)
            print(json.dumps(row, sort_keys=True), flush=True)
            write_json(metric_dir / "scores.json", rows)

    write_json(work / "result.json", {
        "manifest": str((work / "manifest.json").resolve()),
        "warning": (
            "Finished-frame full-reference metrics penalise independent grain; "
            "do not route on their absolute values."),
        "scores": rows,
    })
    print(f"\nresult: {work / 'result.json'}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        raise SystemExit(130)
