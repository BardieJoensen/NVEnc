#!/usr/bin/env python3
"""Prepare and score the integrated architecture's quality guard rails.

The grain statistics remain the objective.  These full-reference scores are
guard rails: independently positioned AV1 grain is penalised even when its
distribution is correct.  Grain-disabled ``base`` and grain-enabled
``finished`` decodes are therefore reported separately, with a same-QVBR
``plain`` anchor that makes that bias visible.

Every input is decoded to the same lossless 1920x1080 centre crop with explicit
limited-range BT.2020/PQ metadata before scoring.  Crop tasks and metric tasks
are resumable and include strict frame/timeline validation through
``review_score``.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics

import review_score
from integrated_architecture import (
    CANDIDATE_ARMS,
    TITLES,
    complete_task,
    identity,
    partial_path,
    publish_outputs,
    run_logged,
    write_json,
)


ARMS = ("plain", "production", *CANDIDATE_ARMS)
DEFAULT_ARMS = ("plain", "production", "causal", "paired")
CROP = "crop=1920:1080:960:540"
COLOR = (
    "-color_range", "tv",
    "-colorspace", "bt2020nc",
    "-color_trc", "smpte2084",
    "-color_primaries", "bt2020",
)


def crop_command(
    ffmpeg: Path,
    source: Path,
    output: Path,
    frames: int,
    filmgrain: int | None = None,
) -> list[str]:
    command = [str(ffmpeg), "-hide_banner", "-nostdin", "-v", "error"]
    if filmgrain is not None:
        command += ["-c:v", "libdav1d", "-filmgrain", str(filmgrain)]
    command += [
        "-i", str(source), "-map", "0:v:0", "-frames:v", str(frames),
        "-vf", CROP, "-an", "-sn", "-dn", "-fps_mode", "passthrough",
        "-c:v", "ffv1", "-level", "3", "-coder", "1", "-context", "1",
        "-g", "1", "-slicecrc", "1", "-pix_fmt", "yuv420p10le",
        *COLOR, "-y", str(output),
    ]
    return command


def prepare_crop(
    name: str,
    source: Path,
    output: Path,
    frames: int,
    ffmpeg: Path,
    log_dir: Path,
    filmgrain: int | None = None,
) -> None:
    output_partial = partial_path(output)
    command = crop_command(ffmpeg, source, output_partial, frames, filmgrain)
    manifest = log_dir / f"{name}.task.json"
    log = log_dir / f"{name}.log"
    expected = {
        "command": command,
        "environment": {},
        "source": identity(source),
        "binary": identity(ffmpeg, include_hash=True),
    }
    if complete_task(manifest, expected, [output]):
        print(f"[resume] crop {name}", flush=True)
        return
    if output.exists():
        raise RuntimeError(f"{name}: crop exists without a matching manifest")
    print(f"[run] crop {name}", flush=True)
    elapsed = run_logged(command, os.environ.copy(), log)
    publish_outputs([output_partial], [output])
    write_json(manifest, {
        "input": expected,
        "outputs": [identity(output)],
        "log": str(log.resolve()),
        "elapsed_seconds": elapsed,
    })


def score_pair(
    reference: Path,
    distorted: Path,
    title: str,
    arm: str,
    kind: str,
    metric_dir: Path,
) -> dict:
    tag = f"{title}-{arm}-{kind}"
    document, frames = review_score.vmaf_run(
        str(reference), str(distorted), tag, work=str(metric_dir))
    pooled = document["pooled_metrics"]
    ssimu2 = sorted(row[0] for row in review_score.ffvship(
        str(reference), str(distorted), tag, "SSIMULACRA2",
        f"ssimu2-{tag}.json", frames, work=str(metric_dir)))
    butter = review_score.ffvship(
        str(reference), str(distorted), tag, "Butteraugli",
        f"butter-{tag}.json", frames, work=str(metric_dir))
    vmaf_frames = sorted(
        frame["metrics"]["vmaf"] for frame in document["frames"])
    return {
        "title": title,
        "arm": arm,
        "kind": kind,
        "frames": frames,
        "vmaf": round(pooled["vmaf"]["mean"], 4),
        "vmaf_p1": round(review_score.pct(vmaf_frames, 1), 4),
        "vmaf_neg": round(pooled["vmaf_neg"]["mean"], 4),
        "psnr_y": round(pooled["psnr_y"]["mean"], 4),
        "ssim": round(pooled["float_ssim"]["mean"], 7),
        "ciede2000": round(pooled["ciede2000"]["mean"], 4),
        "ssimulacra2_mean": round(statistics.mean(ssimu2), 4),
        "ssimulacra2_p5": round(review_score.pct(ssimu2, 5), 4),
        "butteraugli_2norm_mean": round(
            statistics.mean(row[0] for row in butter), 5),
        "butteraugli_max_p95": round(
            review_score.pct(sorted(row[2] for row in butter), 95), 5),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-root",
        default="/media/merged-storage/media/test-encodes/keep-original")
    parser.add_argument(
        "--work",
        default="/media/merged-storage/media/test-encodes/"
                "sourcefit-integrated-20260803")
    parser.add_argument("--ffmpeg", default="/usr/local/bin/ffmpeg")
    parser.add_argument("--ffprobe", default="/usr/local/bin/ffprobe")
    parser.add_argument("--titles", default=",".join(TITLES))
    parser.add_argument("--arms", default=",".join(DEFAULT_ARMS))
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--score-only", action="store_true")
    args = parser.parse_args()
    if args.prepare_only and args.score_only:
        parser.error("--prepare-only and --score-only are mutually exclusive")

    source_root = Path(args.source_root).resolve()
    work = Path(args.work).resolve()
    ffmpeg = Path(args.ffmpeg).resolve()
    ffprobe = Path(args.ffprobe).resolve()
    for executable in (ffmpeg, ffprobe):
        if not executable.is_file():
            parser.error(f"missing executable: {executable}")
    titles = [value.strip() for value in args.titles.split(",") if value.strip()]
    arms = [value.strip() for value in args.arms.split(",") if value.strip()]
    unknown_titles = sorted(set(titles).difference(TITLES))
    unknown_arms = sorted(set(arms).difference(ARMS))
    if unknown_titles:
        parser.error(f"unknown titles: {', '.join(unknown_titles)}")
    if unknown_arms:
        parser.error(f"unknown arms: {', '.join(unknown_arms)}")

    crop_dir = work / "quality-crops"
    log_dir = work / "reports" / "quality-crop-tasks"
    metric_dir = work / "reports" / "quality-metrics"
    for directory in (crop_dir, log_dir, metric_dir):
        directory.mkdir(parents=True, exist_ok=True)

    review_score.FFMPEG = str(ffmpeg)
    review_score.FFPROBE = str(ffprobe)
    prepared: dict[tuple[str, str, str], Path] = {}
    references: dict[str, Path] = {}
    for title in titles:
        source = source_root / f"clip_{title}.mkv"
        if not source.is_file():
            raise RuntimeError(f"missing source: {source}")
        frames = len(review_score.probe_video(str(source))["timestamps"])
        reference = crop_dir / f"{title}-reference.mkv"
        references[title] = reference
        if not args.score_only:
            prepare_crop(
                f"{title}-reference", source, reference, frames, ffmpeg,
                log_dir)
        for arm in arms:
            encoded = work / title / f"{arm}.mkv"
            if not encoded.is_file():
                raise RuntimeError(f"missing encoded arm: {encoded}")
            kinds = ("finished",) if arm == "plain" else ("base", "finished")
            for kind in kinds:
                crop = crop_dir / f"{title}-{arm}-{kind}.mkv"
                prepared[(title, arm, kind)] = crop
                if not args.score_only:
                    prepare_crop(
                        f"{title}-{arm}-{kind}", encoded, crop, frames,
                        ffmpeg, log_dir, filmgrain=0 if kind == "base" else 1)

    if args.prepare_only:
        return 0

    rows = []
    for title in titles:
        for arm in arms:
            kinds = ("finished",) if arm == "plain" else ("base", "finished")
            for kind in kinds:
                distorted = prepared[(title, arm, kind)]
                if not references[title].is_file() or not distorted.is_file():
                    raise RuntimeError(f"missing prepared crop: {distorted}")
                print(f"[score] {title} {arm} {kind}", flush=True)
                row = score_pair(
                    references[title], distorted, title, arm, kind, metric_dir)
                rows.append(row)
                print(json.dumps(row, sort_keys=True), flush=True)
                write_json(metric_dir / "scores.json", rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
