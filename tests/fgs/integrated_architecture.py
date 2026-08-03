#!/usr/bin/env python3
"""Run the six-film source-fit architecture gate reproducibly.

This harness deliberately separates four questions:

* ``plain`` is the compression denominator;
* ``production`` is the deployed r4069 bilateral/residual analyser;
* ``bilateral-source`` keeps the bilateral separator but fits the grain model
  from source flat blocks, isolating model quality from motion separation;
* ``bilateral-source-chroma-global`` and ``-local`` keep that exact luma path
  while testing aggregate versus per-luma-bin temporal chroma closure;
* ``causal`` is source fitting with one past reference; and
* ``paired`` is source fitting with one past plus one future reference whose
  render confidence is paired at the weaker SAD.
* ``balanced`` is the same centred pair with total temporal exposure matched
  to the causal arm, so direction changes without doubling reference weight.
* ``balanced-detail`` and ``balanced-nofinish`` isolate the luma spatial
  finishing pass after that temporal operator.  They remain environment-only
  research arms and always retain the ordinary chroma finish.
* ``balanced-median-detail`` keeps the detail-aware finish but replaces the
  admitted previous/next average with a robust three-sample temporal median.

The source-fit arms use the QVBR-29/P4/no-AQ regime on which the temporal leak
transfer was calibrated.  A later production-settings transfer test must not be
silently mixed into this gate.

For every FGS arm the script writes both a direct AV1 encode and the lossless
pre-encode clean base.  The direct encode carries the rate-aware strength
closure; raw output intentionally does not, but the separator output itself is
the same and is the quantity needed by the closure and base-fidelity reports.

No copyrighted input or generated media is stored in the repository.  Tasks
are resumable through command/source/binary manifests and write to ``.partial``
paths before publishing their final outputs.  Direct streams and grain tables
are hashed.  Multi-gigabyte lossless clean bases record identity metadata but
are not re-read solely for a checksum; their source is hashed once per title.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time


TITLES = (
    "Casino",
    "Interstellar",
    "Scarface",
    "Taxi_Driver",
    "The_Deer_Hunter",
    "The_Shining",
)

MOTION_ARMS = (
    "causal",
    "paired",
    "balanced",
    "balanced-detail",
    "balanced-nofinish",
    "balanced-median-detail",
)
CHROMA_LEAK_ARMS = (
    "bilateral-source-chroma-global",
    "bilateral-source-chroma-local",
)
CANDIDATE_ARMS = (
    "bilateral-source",
    *CHROMA_LEAK_ARMS,
    *MOTION_ARMS,
)

RESEARCH_ENVIRONMENT = (
    "NVENC_FGS_TEST_CHROMA_LEAK",
    "NVENC_FGS_TEST_MOTION_CENTERED",
    "NVENC_FGS_TEST_MOTION_FINISH",
    "NVENC_FGS_TEST_MOTION_THSAD",
)

CONTROLLED_ENCODE = (
    "--codec", "av1",
    "--output-depth", "10",
    "--qvbr", "29",
    "--max-bitrate", "20000",
    "--preset", "p4",
    "--tune", "hq",
    "--colormatrix", "auto",
    "--colorprim", "auto",
    "--transfer", "auto",
    "--colorrange", "auto",
    "--master-display", "copy",
    "--max-cll", "copy",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def identity(path: Path, include_hash: bool = False) -> dict:
    stat = path.stat()
    result = {
        "path": str(path.resolve()),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }
    if include_hash:
        result["sha256"] = sha256(path)
    return result


def write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def partial_path(path: Path) -> Path:
    """Return a sibling temporary path while preserving format inference."""
    return path.with_name(f"{path.stem}.partial{path.suffix}")


def run_logged(command: list[str], env: dict[str, str], log: Path) -> float:
    log_partial = log.with_suffix(log.suffix + ".partial")
    started = time.monotonic()
    with log_partial.open("w", encoding="utf-8") as handle:
        handle.write("command: " + shlex.join(command) + "\n")
        selected = {
            key: env[key] for key in RESEARCH_ENVIRONMENT if key in env
        }
        handle.write("environment: " + json.dumps(selected, sort_keys=True) + "\n")
        handle.flush()
        result = subprocess.run(
            command, env=env, stdout=handle, stderr=subprocess.STDOUT,
            text=True, check=False)
        elapsed = time.monotonic() - started
        handle.write(f"\nreturncode: {result.returncode}\nelapsed_seconds: {elapsed:.6f}\n")
    if result.returncode:
        raise RuntimeError(
            f"command failed ({result.returncode}); see {log_partial}")
    os.replace(log_partial, log)
    return elapsed


def complete_task(manifest: Path, expected: dict, outputs: list[Path]) -> bool:
    if not manifest.is_file() or not all(path.is_file() for path in outputs):
        return False
    try:
        recorded = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return recorded.get("input") == expected


def publish_outputs(partials: list[Path], outputs: list[Path]) -> None:
    if len(partials) != len(outputs):
        raise ValueError("partial/output count mismatch")
    missing = [path for path in partials if not path.is_file()]
    if missing:
        raise RuntimeError(f"expected outputs were not written: {missing}")
    for partial, output in zip(partials, outputs):
        os.replace(partial, output)


def fgs_options(arm: str) -> str:
    if arm == "production":
        return "denoise=auto,chroma=auto,denoiser=bilateral"
    if arm == "bilateral-source" or arm in CHROMA_LEAK_ARMS:
        return "denoise=auto,chroma=auto,denoiser=bilateral,modelsrc=on"
    if arm in MOTION_ARMS:
        return "denoise=auto,chroma=auto,denoiser=motion,motion-refs=1,modelsrc=on"
    raise ValueError(arm)


def arm_environment(arm: str) -> dict[str, str]:
    env = os.environ.copy()
    if arm == "bilateral-source-chroma-global":
        env["NVENC_FGS_TEST_CHROMA_LEAK"] = "global"
    if arm == "bilateral-source-chroma-local":
        env["NVENC_FGS_TEST_CHROMA_LEAK"] = "local"
    if arm in MOTION_ARMS:
        env["NVENC_FGS_TEST_MOTION_THSAD"] = "640"
    if arm == "paired":
        env["NVENC_FGS_TEST_MOTION_CENTERED"] = "paired"
    if arm in ("balanced", "balanced-detail", "balanced-nofinish"):
        env["NVENC_FGS_TEST_MOTION_CENTERED"] = "paired-balanced"
    if arm == "balanced-median-detail":
        env["NVENC_FGS_TEST_MOTION_CENTERED"] = "paired-balanced-median"
    if arm == "balanced-detail":
        env["NVENC_FGS_TEST_MOTION_FINISH"] = "detail"
    if arm == "balanced-median-detail":
        env["NVENC_FGS_TEST_MOTION_FINISH"] = "detail"
    if arm == "balanced-nofinish":
        env["NVENC_FGS_TEST_MOTION_FINISH"] = "off"
    return env


def build_encode_command(
    binary: Path, source: Path, output: Path, table: Path | None, arm: str,
) -> list[str]:
    command = [str(binary), "--avsw", "-i", str(source), *CONTROLLED_ENCODE]
    if arm != "plain":
        command += ["--av1-film-grain", fgs_options(arm)]
        if table is not None:
            command += ["--film-grain-table-out", str(table)]
    command += ["--log-level", "debug", "-o", str(output)]
    return command


def build_clean_command(
    binary: Path, source: Path, output: Path, table: Path, arm: str,
) -> list[str]:
    return [
        str(binary), "--avsw", "-i", str(source),
        "--codec", "raw", "--output-depth", "10",
        "--av1-film-grain", fgs_options(arm),
        "--film-grain-table-out", str(table),
        "--log-level", "debug", "-o", str(output),
    ]


def validate_decode(encoded: Path, log: Path, ffmpeg: Path) -> dict:
    command = [
        str(ffmpeg), "-hide_banner", "-nostdin", "-v", "error", "-xerror",
        "-c:v", "libdav1d", "-i", str(encoded), "-map", "0:v:0",
        "-an", "-sn", "-dn", "-f", "null", "-",
    ]
    elapsed = run_logged(command, os.environ.copy(), log)
    return {"command": command, "elapsed_seconds": elapsed, "log": str(log.resolve())}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-root",
        default="/media/merged-storage/media/test-encodes/keep-original")
    parser.add_argument(
        "--work",
        default="/media/merged-storage/media/test-encodes/"
                "sourcefit-integrated-20260803")
    parser.add_argument("--candidate-nvencc", default="build-fgs-cuda/nvencc")
    parser.add_argument(
        "--production-nvencc", default="/opt/docker-apps/build/tdarr-node/nvencc")
    parser.add_argument("--ffmpeg", default="/usr/local/bin/ffmpeg")
    parser.add_argument("--titles", default=",".join(TITLES))
    parser.add_argument(
        "--arms", default="plain,production,causal,paired",
        help=("comma-separated subset of plain,production,bilateral-source,"
              "bilateral-source-chroma-global,"
              "bilateral-source-chroma-local,"
              "causal,paired,balanced,"
              "balanced-detail,balanced-nofinish,balanced-median-detail"))
    parser.add_argument("--skip-clean", action="store_true")
    parser.add_argument("--skip-decode", action="store_true")
    args = parser.parse_args()

    source_root = Path(args.source_root).resolve()
    work = Path(args.work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    candidate = Path(args.candidate_nvencc).resolve()
    production = Path(args.production_nvencc).resolve()
    ffmpeg = Path(args.ffmpeg).resolve()
    for binary in (candidate, production, ffmpeg):
        if not binary.is_file():
            parser.error(f"missing executable: {binary}")

    titles = [value.strip() for value in args.titles.split(",") if value.strip()]
    unknown_titles = sorted(set(titles).difference(TITLES))
    if unknown_titles:
        parser.error(f"unknown titles: {', '.join(unknown_titles)}")
    arms = [value.strip() for value in args.arms.split(",") if value.strip()]
    unknown_arms = sorted(set(arms).difference(
        ("plain", "production", *CANDIDATE_ARMS)))
    if unknown_arms:
        parser.error(f"unknown arms: {', '.join(unknown_arms)}")

    run_manifest = {
        "purpose": "quality-first six-film source-fit architecture gate",
        "settings": {
            "qvbr": 29,
            "max_bitrate": 20000,
            "preset": "p4",
            "tune": "hq",
            "aq": False,
            "motion_thsad": 640,
        },
        "candidate_binary": identity(candidate, include_hash=True),
        "production_binary": identity(production, include_hash=True),
        "titles": {},
    }

    for title in titles:
        title_work = work / title
        title_work.mkdir(parents=True, exist_ok=True)
        source = source_root / f"clip_{title}.mkv"
        if not source.is_file():
            raise RuntimeError(f"missing source: {source}")
        source_identity = identity(source)
        title_record = {
            "source": identity(source, include_hash=True),
            "arms": {},
        }
        print(f"\n== {title} ==", flush=True)
        for arm in arms:
            binary = production if arm in ("plain", "production") else candidate
            env = arm_environment(arm)
            arm_record: dict[str, object] = {}

            encoded = title_work / f"{arm}.mkv"
            encoded_partial = partial_path(encoded)
            table = None if arm == "plain" else title_work / f"{arm}.tbl"
            table_partial = None if table is None else partial_path(table)
            encode_outputs = [encoded] + ([] if table is None else [table])
            encode_partials = [encoded_partial] + ([] if table_partial is None else [table_partial])
            encode_command = build_encode_command(
                binary, source, encoded_partial, table_partial, arm)
            encode_name = f"{title}-{arm}-encode"
            encode_manifest = title_work / f"{encode_name}.task.json"
            expected = {
                "command": encode_command,
                "environment": {
                    key: env[key] for key in RESEARCH_ENVIRONMENT if key in env
                },
                "source": source_identity,
                "binary": identity(binary, include_hash=True),
            }
            if not complete_task(encode_manifest, expected, encode_outputs):
                existing = [str(path) for path in encode_outputs if path.exists()]
                if existing:
                    raise RuntimeError(
                        f"{encode_name}: outputs exist without a matching manifest: {existing}")
                print(f"[run] {encode_name}", flush=True)
                encode_log = title_work / f"{encode_name}.log"
                elapsed = run_logged(encode_command, env, encode_log)
                publish_outputs(encode_partials, encode_outputs)
                encode_record = {
                    "input": expected,
                    "outputs": [identity(path, include_hash=True) for path in encode_outputs],
                    "log": str(encode_log.resolve()),
                    "elapsed_seconds": elapsed,
                }
                write_json(encode_manifest, encode_record)
            else:
                print(f"[resume] {encode_name}", flush=True)
                encode_record = json.loads(encode_manifest.read_text(encoding="utf-8"))
            arm_record["encode"] = encode_record

            if arm != "plain" and not args.skip_clean:
                clean = title_work / f"{arm}-clean.y4m"
                clean_partial = partial_path(clean)
                raw_table = title_work / f"{arm}-raw.tbl"
                raw_table_partial = partial_path(raw_table)
                clean_outputs = [clean, raw_table]
                clean_partials = [clean_partial, raw_table_partial]
                clean_command = build_clean_command(
                    binary, source, clean_partial, raw_table_partial, arm)
                clean_name = f"{title}-{arm}-clean"
                clean_manifest = title_work / f"{clean_name}.task.json"
                clean_expected = {
                    "command": clean_command,
                    "environment": expected["environment"],
                    "source": expected["source"],
                    "binary": expected["binary"],
                }
                if not complete_task(clean_manifest, clean_expected, clean_outputs):
                    existing = [str(path) for path in clean_outputs if path.exists()]
                    if existing:
                        raise RuntimeError(
                            f"{clean_name}: outputs exist without a matching manifest: {existing}")
                    print(f"[run] {clean_name}", flush=True)
                    clean_log = title_work / f"{clean_name}.log"
                    elapsed = run_logged(clean_command, env, clean_log)
                    publish_outputs(clean_partials, clean_outputs)
                    clean_record = {
                        "input": clean_expected,
                        "outputs": [
                            identity(clean),
                            identity(raw_table, include_hash=True),
                        ],
                        "log": str(clean_log.resolve()),
                        "elapsed_seconds": elapsed,
                    }
                    write_json(clean_manifest, clean_record)
                else:
                    print(f"[resume] {clean_name}", flush=True)
                    clean_record = json.loads(clean_manifest.read_text(encoding="utf-8"))
                arm_record["clean"] = clean_record

            if not args.skip_decode:
                decode_log = title_work / f"{title}-{arm}-dav1d.log"
                decode_record = validate_decode(encoded, decode_log, ffmpeg)
                arm_record["dav1d"] = decode_record
            title_record["arms"][arm] = arm_record
        run_manifest["titles"][title] = title_record
        write_json(work / "manifest.json", run_manifest)

    print(f"\nmanifest: {work / 'manifest.json'}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        raise SystemExit(130)
