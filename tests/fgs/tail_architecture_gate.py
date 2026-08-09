#!/usr/bin/env python3
"""Run the production-tail FGS architecture gate on exact retained sources.

The corpus is frozen from the provenance-corrected production population: two
lower-tail titles, a predeclared next-low fallback, two centre controls and two
upper-tail titles.  The fallback preserves two independent lower-title
decisions if a frozen title lacks three temporally measurable scenes.  Five fixed
positions from every original are decoded to lossless progressive FFV1 clips
and concatenated into one 600-frame reel.  No deinterlacing, interpolation or
source-library transcode is allowed into the experiment.

Five arms keep the architectural variables separate:

* ``plain``: production binary, no film-grain synthesis;
* ``production``: production binary and residual-fitted bilateral FGS;
* ``candidate-control``: research binary with the same residual path;
* ``source``: research binary, source-static texture fitting; and
* ``response``: the source arm plus guarded texture-response closure.

Every output receives a complete libdav1d decode.  Grain-disabled FFV1 decodes
are used for aligned base-fidelity metrics; the direct AV1 outputs are decoded
with synthesis both on and off by ``temporal_grain_report.py`` on one
source-derived flat/static mask.  Finished-frame VMAF is intentionally absent:
independently seeded correct grain is positionally different and is penalised
by full-reference image metrics.

Tasks are command/source/binary manifested, resumable and publish only from
``.partial`` paths.  This script never touches Tdarr or a production setting.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from fractions import Fraction
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import general_content_gate as common  # noqa: E402
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


SCENE_FRACTIONS = (0.150, 0.325, 0.500, 0.675, 0.850)
# A frozen source-only grid.  Every eligible point is retained; frames with
# fewer than eight static flat blocks are reported as unmeasurable rather than
# replaced after inspecting an encode.  A scene is graded with at least three
# usable pairs, and a title must retain at least three independently graded
# scenes.  Sparse scenes remain in base-quality and byte measurements.
SAMPLE_OFFSETS = tuple(range(6, 115, 6))
ARMS = ("plain", "production", "candidate-control", "source", "response")
FGS = "denoise=auto,chroma=auto,denoiser=bilateral"
RESEARCH_PREFIX = "NVENC_FGS_TEST_"
MEASUREMENT_VERSION = "scene-grid-v2-zero-safe"


@dataclass(frozen=True)
class Title:
    name: str
    source: str
    library: str
    tail: str
    production_mean: float
    production_range: tuple[float, float]
    qvbr: int = 30
    decoded_rate: str | None = None


TITLES = (
    Title(
        "Korra_S02E12",
        "/media/merged-storage/media/downloads/long-term-seeding/tv-shows/"
        "The.Legend.of.Korra.S02.1080p.BluRay.Remux.DTS-HD.MA5.1.H.264-NTb/"
        "The.Legend.of.Korra.S02E12.1080p.BluRay.Remux.DTS-HD.MA5.1.H.264-NTb.mkv",
        "/media/merged-storage/media/tv-shows/The Legend of Korra (2012)/Season 02/"
        "The Legend of Korra (2012) - S02E12 - Harmonic Convergence "
        "[Bluray-1080p Remux][DTS-HD MA 5.1][h264]-NTb.mkv",
        "low", 0.690, (0.343, 0.981), qvbr=34),
    Title(
        "Korra_S02E07",
        "/media/merged-storage/media/downloads/long-term-seeding/tv-shows/"
        "The.Legend.of.Korra.S02.1080p.BluRay.Remux.DTS-HD.MA5.1.H.264-NTb/"
        "The.Legend.of.Korra.S02E07.1080p.BluRay.Remux.DTS-HD.MA5.1.H.264-NTb.mkv",
        "/media/merged-storage/media/tv-shows/The Legend of Korra (2012)/Season 02/"
        "The Legend of Korra (2012) - S02E07 - Beginnings 1 "
        "[Bluray-1080p Remux][DTS-HD MA 5.1][h264]-NTb.mkv",
        "low", 0.801, (0.652, 0.925), qvbr=34),
    Title(
        "HIMYM_S04E17",
        "/media/merged-storage/media/downloads/long-term-seeding/tv-shows/"
        "How.I.Met.Your.Mother.S04.2008.BluRay.1080p.Remux.AVC.DTS-HDMA.5.1-BluHD/"
        "How.I.Met.Your.Mother.S04E17.The.Front.Porch.BluRay.1080p.Remux."
        "AVC.DTS-HDMA.5.1-BluHD.mkv",
        "/media/merged-storage/media/tv-shows/How I Met Your Mother (2005)/Season 04/"
        "How I Met Your Mother (2005) - S04E17 - The Front Porch "
        "[Bluray-1080p Remux][DTS-HD MA 5.1][AVC]-BluHD.mkv",
        "low-fallback", 0.863, (0.466, 1.017)),
    Title(
        "Abbott_S02E02",
        "/media/merged-storage/media/downloads/long-term-seeding/tv-shows/"
        "Abbott.Elementary.S02.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb/"
        "Abbott.Elementary.S02E02.Wrong.Delivery.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb.mkv",
        "/media/merged-storage/media/tv-shows/Abbott Elementary (2021)/Season 02/"
        "Abbott Elementary (2021) - S02E02 - Wrong Delivery "
        "[AMZN][WEBDL-1080p][EAC3 5.1][h264]-NTb.mkv",
        "centre", 0.995, (0.791, 1.199)),
    Title(
        "Planet_Earth_S01E06",
        "/media/merged-storage/media/downloads/long-term-seeding/tv-shows/"
        "Planet.Earth.S01.Bluray.1080p.VC1.Remux/"
        "Planet.Earth.S01E06.Ice.Worlds.Bluray.1080p.VC1.Remux.mkv",
        "/media/merged-storage/media/tv-shows/Planet Earth (2006)/Season 01/"
        "Planet Earth (2006) - S01E06 - Ice Worlds "
        "[Bluray-1080p Remux][AC3 5.1][VC1]-Mattman2586.mkv",
        "centre", 0.976, (0.724, 1.139), decoded_rate="24000/1001"),
    Title(
        "HIMYM_S09E15",
        "/media/merged-storage/media/downloads/long-term-seeding/tv-shows/"
        "How.I.Met.Your.Mother.S09.1080p.DSNP.WEB-DL.DDP5.1.H.264-FLUX/"
        "How.I.Met.Your.Mother.S09E15.Unpause.1080p.DSNP.WEB-DL.DDP5.1.H.264-FLUX.mkv",
        "/media/merged-storage/media/tv-shows/How I Met Your Mother (2005)/Season 09/"
        "How I Met Your Mother (2005) - S09E15 - Unpause "
        "[DSNP][WEBDL-1080p][EAC3 5.1][h264]-FLUX.mkv",
        "high", 1.508, (0.876, 2.032)),
    Title(
        "Trying_S02E06",
        "/media/merged-storage/media/downloads/long-term-seeding/tv-shows/"
        "Trying.S02.1080p.ATVP.WEB-DL.DDP5.1.Atmos.H.264-NTb/"
        "Trying.S02E06.A.Long.Way.Down.1080p.ATVP.WEB-DL.DDP5.1.Atmos.H.264-NTb.mkv",
        "/media/merged-storage/media/tv-shows/Trying (2020)/Season 02/"
        "Trying (2020) - S02E06 - A Long Way Down "
        "[ATVP][WEBDL-1080p][EAC3 Atmos 5.1][h264]-NTb.mkv",
        "high", 1.341, (1.211, 1.562)),
)


def title_map() -> dict[str, Title]:
    return {title.name: title for title in TITLES}


def arm_environment(arm: str, inherited: dict[str, str] | None = None) -> dict[str, str]:
    """Return a clean environment; no ambient research hook may leak in."""
    env = dict(os.environ if inherited is None else inherited)
    for key in tuple(env):
        if key.startswith(RESEARCH_PREFIX):
            del env[key]
    if arm in ("source", "response"):
        env["NVENC_FGS_TEST_SOURCE_STATIC"] = "on"
    if arm == "response":
        env["NVENC_FGS_TEST_TEXTURE_LEAK"] = "response"
    if arm not in ARMS:
        raise ValueError(arm)
    return env


def fgs_options(arm: str) -> str | None:
    if arm == "plain":
        return None
    if arm in ("production", "candidate-control"):
        return FGS
    if arm in ("source", "response"):
        return FGS + ",modelsrc=on"
    raise ValueError(arm)


def binary_for(arm: str, production: Path, candidate: Path) -> Path:
    if arm in ("plain", "production"):
        return production
    if arm in ("candidate-control", "source", "response"):
        return candidate
    raise ValueError(arm)


def extract_command(
    ffmpeg: Path, source: Path, output: Path, start: float, frames: int,
    stream: dict, decoded_rate: str | None = None,
) -> list[str]:
    filters = "setpts=PTS-STARTPTS,setfield=prog"
    rate_args = []
    fps_mode = "passthrough"
    if decoded_rate is not None:
        rate = Fraction(decoded_rate)
        filters = (
            f"settb=AVTB,setpts=N*{rate.denominator}/{rate.numerator}/TB,"
            "setfield=prog")
        # setpts first assigns every decoded picture an exact consecutive film
        # timestamp.  CFR then writes the correct stream-rate metadata; because
        # the input to that stage is already exact CFR, no picture is duplicated
        # or dropped (also gated by the requested/decoded frame count).
        rate_args = ["-r", decoded_rate]
        fps_mode = "cfr"
    return [
        str(ffmpeg), "-hide_banner", "-nostdin", "-v", "error", "-xerror",
        "-ss", f"{start:.6f}", "-i", str(source), "-map", "0:v:0",
        "-frames:v", str(frames), "-an", "-sn", "-dn",
        "-vf", filters, *rate_args, "-fps_mode", fps_mode,
        "-c:v", "ffv1", "-level", "3", "-coder", "1", "-context", "1",
        "-g", "1", "-slicecrc", "1", "-pix_fmt", "yuv420p10le",
        *common.color_args(stream), "-y", str(output),
    ]


def concat_command(ffmpeg: Path, list_path: Path, output: Path) -> list[str]:
    return [
        str(ffmpeg), "-hide_banner", "-nostdin", "-v", "error", "-xerror",
        "-f", "concat", "-safe", "0", "-i", str(list_path),
        "-map", "0:v:0", "-an", "-sn", "-dn", "-c", "copy", "-y",
        str(output),
    ]


def encode_command(
    binary: Path, source: Path, output: Path, table: Path | None, arm: str,
    qvbr: int,
) -> list[str]:
    command = [
        str(binary), "--avsw", "-i", str(source), "--codec", "av1",
        "--output-depth", "10", "--qvbr", str(qvbr), "--max-bitrate",
        "50000", "--preset", "quality", "--tune", "hq", "--lookahead",
        "32", "--lookahead-level", "3", "--aq", "--aq-temporal",
        "--colormatrix", "auto", "--colorprim", "auto", "--transfer", "auto",
        "--colorrange", "auto", "--master-display", "copy", "--max-cll", "copy",
    ]
    options = fgs_options(arm)
    if options is not None:
        if table is None:
            raise ValueError(f"{arm}: FGS arm requires a table")
        command += [
            "--av1-film-grain", options,
            "--film-grain-table-out", str(table),
        ]
    command += ["--log-level", "debug", "-o", str(output)]
    return command


def decode_base_command(
    ffmpeg: Path, encoded: Path, output: Path, frames: int, stream: dict,
) -> list[str]:
    return [
        str(ffmpeg), "-hide_banner", "-nostdin", "-v", "error", "-xerror",
        "-c:v", "libdav1d", "-filmgrain", "0", "-i", str(encoded),
        "-map", "0:v:0", "-frames:v", str(frames), "-an", "-sn", "-dn",
        "-fps_mode", "passthrough", "-c:v", "ffv1", "-level", "3",
        "-coder", "1", "-context", "1", "-g", "1", "-slicecrc", "1",
        "-pix_fmt", "yuv420p10le", *common.color_args(stream), "-y", str(output),
    ]


def full_decode_command(ffmpeg: Path, encoded: Path) -> list[str]:
    return [
        str(ffmpeg), "-hide_banner", "-nostdin", "-v", "error", "-xerror",
        "-c:v", "libdav1d", "-filmgrain", "1", "-i", str(encoded),
        "-map", "0:v:0", "-an", "-sn", "-dn", "-f", "null", "-",
    ]


def temporal_command(
    report_script: Path, source: Path, encoded: dict[str, Path], plane: str,
    frames: list[int], output: Path, minimum_frames: int = 3,
) -> list[str]:
    command = [
        sys.executable, str(report_script), "--source", str(source),
        "--plane", plane, "--bits", "10", "--flat-selector", "production",
        "--luma-bins", "8", "--frames", ",".join(map(str, frames)),
        "--skip-thin", "--minimum-frames", str(minimum_frames),
        "--json-out", str(output),
    ]
    for arm in ARMS:
        command += ["--arm", f"{arm}={encoded[arm]}"]
    return command


def validate_encode_log(arm: str, path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    if "film-grain: ignoring" in text:
        raise RuntimeError(f"{arm}: encoder ignored a film-grain control; see {path}")
    if arm != "plain" and "fgs-model" not in text:
        raise RuntimeError(f"{arm}: no fgs-model diagnostics; see {path}")
    if arm == "response" and "responseGain=" not in text:
        raise RuntimeError(f"{arm}: response hook did not emit responseGain; see {path}")


def run_task(
    name: str, command: list[str], env: dict[str, str], expected: dict,
    partials: list[Path], outputs: list[Path], manifest: Path, log: Path,
    validate_log=None, validate_outputs=None, hash_outputs: bool = False,
) -> dict:
    if complete_task(manifest, expected, outputs):
        if validate_outputs is not None:
            validate_outputs(outputs)
        print(f"[resume] {name}", flush=True)
        return json.loads(manifest.read_text(encoding="utf-8"))
    existing = [str(path) for path in outputs if path.exists()]
    if existing:
        raise RuntimeError(f"{name}: outputs exist without matching manifest: {existing}")
    print(f"[run] {name}", flush=True)
    elapsed = run_logged(command, env, log)
    if validate_log is not None:
        validate_log(log)
    if validate_outputs is not None:
        validate_outputs(partials)
    publish_outputs(partials, outputs)
    record = {
        "input": expected,
        "outputs": [identity(path, include_hash=hash_outputs) for path in outputs],
        "elapsed_seconds": elapsed,
        "log": str(log.resolve()),
    }
    write_json(manifest, record)
    return record


def run_check(
    name: str, command: list[str], expected: dict, manifest: Path, log: Path,
) -> dict:
    if complete_task(manifest, expected, [log]):
        print(f"[resume] {name}", flush=True)
        return json.loads(manifest.read_text(encoding="utf-8"))
    print(f"[run] {name}", flush=True)
    elapsed = run_logged(command, arm_environment("plain"), log)
    record = {
        "input": expected,
        "outputs": [identity(log)],
        "elapsed_seconds": elapsed,
        "log": str(log.resolve()),
    }
    write_json(manifest, record)
    return record


def cached_hashed_identity(path: Path, cache: Path) -> dict:
    current = identity(path)
    if cache.is_file():
        try:
            recorded = json.loads(cache.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            recorded = {}
        if all(recorded.get(key) == current[key] for key in current):
            return recorded
    print(f"[hash] {path}", flush=True)
    result = identity(path, include_hash=True)
    write_json(cache, result)
    return result


def stream_md5(path: Path, ffmpeg: Path) -> str:
    result = subprocess.run([
        str(ffmpeg), "-hide_banner", "-nostdin", "-v", "error", "-xerror",
        "-i", str(path), "-map", "0:v:0", "-c", "copy", "-f", "md5", "-",
    ], capture_output=True, text=True, check=False, timeout=1800)
    if result.returncode:
        raise RuntimeError(f"stream MD5 failed for {path}: {result.stderr[-2000:]}")
    value = result.stdout.strip()
    if not value.startswith("MD5=") or len(value) != 36:
        raise RuntimeError(f"unexpected stream MD5 for {path}: {value!r}")
    return value[4:]


def source_pair(title: Title, ffprobe: Path) -> tuple[Path, Path, dict, dict, dict]:
    source, library = Path(title.source), Path(title.library)
    if not source.is_file():
        raise RuntimeError(f"{title.name}: missing retained source: {source}")
    if not library.is_file():
        raise RuntimeError(f"{title.name}: missing library selector: {library}")
    source_stream = common.probe_stream(source, ffprobe)
    library_stream = common.probe_stream(library, ffprobe)
    if (source_stream["width"], source_stream["height"]) != (
            library_stream["width"], library_stream["height"]):
        raise RuntimeError(f"{title.name}: source/library geometry mismatch")
    duration_delta = abs(source_stream["duration"] - library_stream["duration"])
    duration_ratio = duration_delta / source_stream["duration"]
    if duration_ratio > 0.01:
        raise RuntimeError(
            f"{title.name}: source/library duration differs by {duration_ratio:.3%}")
    validation = {
        "source_verification": verify_source(str(source)),
        "same_geometry": True,
        "duration_ratio": duration_ratio,
        "library_selector_only": True,
    }
    return source, library, source_stream, library_stream, validation


def scene_starts(
    stream: dict, frames: int, decoded_rate: str | None = None,
) -> list[float]:
    rate = Fraction(decoded_rate or stream["avg_frame_rate"])
    if rate <= 0:
        raise RuntimeError(f"invalid frame rate {stream['avg_frame_rate']}")
    clip_seconds = frames / float(rate)
    latest = max(0.0, stream["duration"] - clip_seconds - 1.0)
    return [min(stream["duration"] * fraction, latest) for fraction in SCENE_FRACTIONS]


def metric_summary(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    summary = {
        "plane": document["plane"],
        "truth": document["truth"],
        "requested_frames": len(document["requested_frames"]),
        "measured_frames": len(document["frames"]),
        "skipped_frames": document["skipped_frames"],
        "arms": {},
    }
    for arm, record in document["arms"].items():
        summary["arms"][arm] = {
            "base_amplitude": record["base"]["amplitude_ratio"]["mean"],
            "synth_amplitude": record["synth"]["amplitude_ratio"]["mean"],
            "total_amplitude": record["total"]["amplitude_ratio"]["mean"],
            "texture_mae": record["total_axis_error_to_truth"]["mean"],
            "texture_p95": record["total_axis_error_to_truth"]["p95"],
            "variance_closure_error": record["variance_closure"]["error"],
        }
    return summary


def validate_temporal_report(
    path: Path, scene_frames: int, expected_scene: int,
) -> dict:
    summary = metric_summary(path)
    document = json.loads(path.read_text(encoding="utf-8"))
    count = 0
    for frame in document["frames"]:
        scene = frame // scene_frames
        if scene != expected_scene:
            raise RuntimeError(
                f"temporal sample {frame} belongs to scene {scene}, "
                f"expected {expected_scene}")
        count += 1
    summary["scene"] = expected_scene + 1
    summary["gradable"] = count >= 3
    return summary


def score_bases(
    title: str, reel: Path, bases: dict[str, Path], metric_dir: Path,
    full: bool,
) -> list[dict]:
    rows = []
    for arm in ARMS:
        print(f"[score] {title} {arm} grain-disabled base", flush=True)
        rows.append(common.score_pair(
            reel, bases[arm], title, arm, "base", metric_dir, full=full))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--work", default="/media/merged-storage/media/test-encodes/"
        "sourcefit-tail-gate-20260809")
    parser.add_argument(
        "--production-nvencc", default="/opt/docker-apps/build/tdarr-node/nvencc")
    parser.add_argument(
        "--candidate-nvencc", default="/home/bardie/.cache/fgs-gate/builds/"
        "pin-b1697415-1786280543/build-gate/nvencc")
    parser.add_argument("--ffmpeg", default="/usr/local/bin/ffmpeg")
    parser.add_argument("--ffprobe", default="/usr/local/bin/ffprobe")
    parser.add_argument("--scene-frames", type=int, default=120)
    parser.add_argument("--titles", default=",".join(title.name for title in TITLES))
    parser.add_argument(
        "--stop-after", choices=("prepare", "encode", "measure", "score"),
        default="score")
    parser.add_argument(
        "--full-metrics", action="store_true",
        help="also run SSIMULACRA2 and Butteraugli on grain-disabled bases")
    args = parser.parse_args()
    if args.scene_frames <= max(SAMPLE_OFFSETS) + 1:
        parser.error(f"--scene-frames must exceed {max(SAMPLE_OFFSETS) + 1}")

    work = Path(args.work).resolve()
    production = Path(args.production_nvencc).resolve()
    candidate = Path(args.candidate_nvencc).resolve()
    ffmpeg, ffprobe = Path(args.ffmpeg).resolve(), Path(args.ffprobe).resolve()
    report_script = Path(__file__).with_name("temporal_grain_report.py").resolve()
    for executable in (production, candidate, ffmpeg, ffprobe, report_script):
        if not executable.is_file():
            parser.error(f"missing executable: {executable}")

    selected = [value.strip() for value in args.titles.split(",") if value.strip()]
    catalog = title_map()
    unknown = sorted(set(selected).difference(catalog))
    if unknown:
        parser.error(f"unknown titles: {', '.join(unknown)}")

    task_dir, reel_dir = work / "tasks", work / "reels"
    metric_dir, report_dir = work / "metrics", work / "grain-reports"
    for directory in (task_dir, reel_dir, metric_dir, report_dir):
        directory.mkdir(parents=True, exist_ok=True)
    review_score.FFMPEG = str(ffmpeg)
    review_score.FFPROBE = str(ffprobe)
    total_frames = args.scene_frames * len(SCENE_FRACTIONS)
    manifest = {
        "purpose": "tail-first source-fit architecture gate; no production mutation",
        "scene_fractions": SCENE_FRACTIONS,
        "scene_frames": args.scene_frames,
        "sample_offsets": SAMPLE_OFFSETS,
        "measurement_version": MEASUREMENT_VERSION,
        "arms": ARMS,
        "production_binary": identity(production, include_hash=True),
        "candidate_binary": identity(candidate, include_hash=True),
        "titles": {},
    }
    encoded_by_title: dict[str, dict[str, Path]] = {}
    bases_by_title: dict[str, dict[str, Path]] = {}
    reels: dict[str, Path] = {}

    for name in selected:
        title = catalog[name]
        source, library, source_stream, library_stream, validation = source_pair(
            title, ffprobe)
        source_id = cached_hashed_identity(source, task_dir / f"{name}-source.json")
        starts = scene_starts(source_stream, args.scene_frames, title.decoded_rate)
        clips = []
        for index, start in enumerate(starts):
            clip = reel_dir / f"{name}-scene{index + 1}.mkv"
            clip_partial = partial_path(clip)
            command = extract_command(
                ffmpeg, source, clip_partial, start, args.scene_frames,
                source_stream, title.decoded_rate)
            expected = {
                "command": command,
                "source": source_id,
                "binary": identity(ffmpeg, include_hash=True),
            }
            def validate_scene(paths: list[Path]) -> None:
                common.require_frames(paths[0], args.scene_frames)
                extracted_stream = common.probe_stream(paths[0], ffprobe)
                if extracted_stream.get("field_order") not in (
                        None, "unknown", "progressive"):
                    raise RuntimeError(
                        f"{name} scene {index + 1}: extracted field order is "
                        f"{extracted_stream.get('field_order')}")

            run_task(
                f"{name}-scene{index + 1}-extract", command,
                arm_environment("plain"), expected, [clip_partial], [clip],
                task_dir / f"{name}-scene{index + 1}-extract.task.json",
                task_dir / f"{name}-scene{index + 1}-extract.log",
                validate_outputs=validate_scene)
            clips.append(clip)

        concat_list = task_dir / f"{name}-concat.txt"
        concat_lines = "".join(
            f"file {shlex.quote(str(path.resolve()))}\n" for path in clips)
        if not concat_list.is_file() or concat_list.read_text(encoding="utf-8") != concat_lines:
            concat_list.write_text(concat_lines, encoding="utf-8")
        reel = reel_dir / f"{name}-reel.mkv"
        reel_partial = partial_path(reel)
        command = concat_command(ffmpeg, concat_list, reel_partial)
        expected = {
            "command": command,
            "scenes": [identity(path, include_hash=True) for path in clips],
            "binary": identity(ffmpeg, include_hash=True),
        }
        run_task(
            f"{name}-concat", command, arm_environment("plain"), expected,
            [reel_partial], [reel], task_dir / f"{name}-concat.task.json",
            task_dir / f"{name}-concat.log",
            validate_outputs=lambda paths: common.require_frames(
                paths[0], total_frames),
            hash_outputs=True)
        reel_probe = common.require_frames(reel, total_frames)
        reel_stream = common.probe_stream(reel, ffprobe)
        reels[name] = reel
        title_record = {
            "tail": title.tail,
            "production_selector": {
                "mean": title.production_mean, "range": title.production_range},
            "qvbr": title.qvbr,
            "source": source_id,
            "source_stream": source_stream,
            "library": identity(library),
            "library_stream": library_stream,
            "pair_validation": validation,
            "scene_starts": starts,
            "reel": identity(reel, include_hash=True),
            "reel_color": review_score.color_signature(reel_probe),
            "arms": {},
        }
        manifest["titles"][name] = title_record
        write_json(work / "manifest.json", manifest)

        if args.stop_after == "prepare":
            continue

        title_dir = work / name
        title_dir.mkdir(parents=True, exist_ok=True)
        encoded_by_title[name], bases_by_title[name] = {}, {}
        for arm in ARMS:
            binary = binary_for(arm, production, candidate)
            env = arm_environment(arm)
            encoded = title_dir / f"{arm}.mkv"
            encoded_partial = partial_path(encoded)
            table = None if arm == "plain" else title_dir / f"{arm}.tbl"
            table_partial = None if table is None else partial_path(table)
            outputs = [encoded] + ([] if table is None else [table])
            partials = [encoded_partial] + ([] if table is None else [table_partial])
            command = encode_command(
                binary, reel, encoded_partial, table_partial, arm, title.qvbr)
            selected_env = {
                key: value for key, value in env.items()
                if key.startswith(RESEARCH_PREFIX)
            }
            expected = {
                "command": command,
                "environment": selected_env,
                "source": identity(reel, include_hash=True),
                "binary": identity(binary, include_hash=True),
            }
            encode_record = run_task(
                f"{name}-{arm}-encode", command, env, expected, partials, outputs,
                task_dir / f"{name}-{arm}-encode.task.json",
                task_dir / f"{name}-{arm}-encode.log",
                validate_log=lambda path, arm=arm: validate_encode_log(arm, path),
                validate_outputs=lambda paths: common.require_frames(
                    paths[0], total_frames),
                hash_outputs=True)
            encoded_probe = common.require_frames(encoded, total_frames)
            review_score.require_matching_color(reel_probe, encoded_probe)
            encoded_by_title[name][arm] = encoded

            decode_command = full_decode_command(ffmpeg, encoded)
            decode_expected = {
                "command": decode_command,
                "source": identity(encoded, include_hash=True),
                "binary": identity(ffmpeg, include_hash=True),
            }
            decode_record = run_check(
                f"{name}-{arm}-full-dav1d", decode_command, decode_expected,
                task_dir / f"{name}-{arm}-full-dav1d.task.json",
                task_dir / f"{name}-{arm}-full-dav1d.log")

            base = title_dir / f"{arm}-base.mkv"
            base_partial = partial_path(base)
            command = decode_base_command(
                ffmpeg, encoded, base_partial, total_frames, reel_stream)
            expected = {
                "command": command,
                "source": identity(encoded, include_hash=True),
                "binary": identity(ffmpeg, include_hash=True),
            }
            base_record = run_task(
                f"{name}-{arm}-base", command, arm_environment("plain"), expected,
                [base_partial], [base], task_dir / f"{name}-{arm}-base.task.json",
                task_dir / f"{name}-{arm}-base.log",
                validate_outputs=lambda paths: common.require_frames(
                    paths[0], total_frames))
            base_probe = common.require_frames(base, total_frames)
            review_score.require_matching_color(reel_probe, base_probe)
            bases_by_title[name][arm] = base
            arm_record = {
                "encode": encode_record,
                "encoded": identity(encoded, include_hash=True),
                "video_stream_md5": stream_md5(encoded, ffmpeg),
                "dav1d": decode_record,
                "base": base_record,
                "base_pixel_sha256": common.decoded_pixel_hash(base, ffmpeg),
            }
            if table is not None:
                arm_record["table"] = {
                    "identity": identity(table, include_hash=True),
                    "summary": common.table_summary(table),
                }
            title_record["arms"][arm] = arm_record
            write_json(work / "manifest.json", manifest)

        if args.stop_after == "encode":
            continue

        for plane in ("y", "u", "v"):
            plane_records = []
            for scene in range(len(SCENE_FRACTIONS)):
                sample_frames = [
                    scene * args.scene_frames + offset
                    for offset in SAMPLE_OFFSETS
                ]
                stem = (
                    f"{name}-scene{scene + 1}-{plane}-{MEASUREMENT_VERSION}")
                report = report_dir / f"{stem}.json"
                report_partial = partial_path(report)
                command = temporal_command(
                    report_script, reel, encoded_by_title[name], plane,
                    sample_frames, report_partial, minimum_frames=0)
                expected = {
                    "command": command,
                    "source": identity(reel, include_hash=True),
                    "arms": {
                        arm: identity(path, include_hash=True)
                        for arm, path in encoded_by_title[name].items()
                    },
                    "measurement": identity(report_script, include_hash=True),
                    "scene": scene + 1,
                }
                def validate(paths: list[Path], scene: int = scene) -> dict:
                    return validate_temporal_report(
                        paths[0], args.scene_frames, scene)
                run_task(
                    f"{name}-scene{scene + 1}-{plane}-temporal", command,
                    arm_environment("plain"), expected, [report_partial], [report],
                    task_dir / f"{stem}.task.json",
                    task_dir / f"{stem}.log",
                    validate_outputs=validate)
                plane_records.append({
                    "identity": identity(report, include_hash=True),
                    "summary": validate_temporal_report(
                        report, args.scene_frames, scene),
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

    if args.stop_after in ("prepare", "encode"):
        print(f"manifest: {work / 'manifest.json'}", flush=True)
        return 0

    if args.stop_after == "measure":
        print(f"manifest: {work / 'manifest.json'}", flush=True)
        return 0

    scores = []
    for name in selected:
        scores.extend(score_bases(
            name, reels[name], bases_by_title[name], metric_dir,
            full=args.full_metrics))
        write_json(metric_dir / "base-scores.json", scores)

    comparisons = {}
    for name in selected:
        arms = manifest["titles"][name]["arms"]
        comparisons[name] = {
            "production_vs_candidate_control": {
                "stream_identical": (
                    arms["production"]["video_stream_md5"]
                    == arms["candidate-control"]["video_stream_md5"]),
                "base_pixel_identical": (
                    arms["production"]["base_pixel_sha256"]
                    == arms["candidate-control"]["base_pixel_sha256"]),
                "table_identical": (
                    arms["production"]["table"]["identity"]["sha256"]
                    == arms["candidate-control"]["table"]["identity"]["sha256"]),
            },
            "encoded_bytes": {
                arm: arms[arm]["encoded"]["size"] for arm in ARMS
            },
        }
    result = {
        "manifest": str((work / "manifest.json").resolve()),
        "warning": (
            "VMAF/SSIM/PSNR are grain-disabled base metrics. Finished-frame "
            "full-reference scores must not rank independently seeded grain."),
        "base_scores": scores,
        "comparisons": comparisons,
    }
    write_json(work / "result.json", result)
    print(f"result: {work / 'result.json'}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        raise SystemExit(130)
