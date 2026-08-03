#!/usr/bin/env python3
"""Separate source-fit base, grain-table, and combined size effects.

The ordinary corpus gate found one large outlier: enabling ``modelsrc`` grew
Silo by 26% although the bilateral separator was unchanged.  A direct encode
cannot tell whether that comes from the strength-dependent luma level
compensation in the clean base or from NVENC seeing a different grain table.

This harness first runs the candidate in raw analysis mode twice, producing a
residual-fit and a source-fit clean base plus their respective tables.  It then
encodes the full 2 x 3 factorial:

* residual-fit or source-fit clean base; and
* no table, residual-fit table, or source-fit table.

Comparing bases under a fixed table isolates the base. Comparing tables over a
fixed base isolates table/encoder interaction. Every AV1 arm is fully decoded
with dav1d and all work is resumable through task manifests. No result changes
an encoder default or a Tdarr route.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import general_content_gate as gate  # noqa: E402
from integrated_architecture import (  # noqa: E402
    identity,
    partial_path,
    run_logged,
    sha256,
    write_json,
)


BASES = ("residual", "source")
TABLES = ("none", "residual", "source")


def analysis_options(base: str) -> str:
    if base == "residual":
        return gate.FGS
    if base == "source":
        return gate.FGS + ",modelsrc=on"
    raise ValueError(base)


def analysis_command(
    binary: Path, source: Path, output: Path, table: Path, base: str,
) -> list[str]:
    return [
        str(binary), "--avsw", "-i", str(source), "--codec", "raw",
        "--output-depth", "10", "--av1-film-grain", analysis_options(base),
        "--film-grain-table-out", str(table), "--log-level", "debug",
        "-o", str(output),
    ]


def fixed_encode_command(
    binary: Path, source: Path, output: Path, table: Path | None, qvbr: int,
) -> list[str]:
    command = [
        str(binary), "--avsw", "-i", str(source), "--codec", "av1",
        "--output-depth", "10", "--qvbr", str(qvbr), "--max-bitrate",
        "50000", "--preset", "quality", "--tune", "hq", "--aq",
        "--aq-temporal", "--colormatrix", "auto", "--colorprim", "auto",
        "--transfer", "auto", "--colorrange", "auto", "--master-display",
        "copy", "--max-cll", "copy",
    ]
    if table is not None:
        command += ["--film-grain-table", str(table)]
    command += ["--log-level", "debug", "-o", str(output)]
    return command


def decode_command(ffmpeg: Path, encoded: Path, frames: int) -> list[str]:
    return [
        str(ffmpeg), "-hide_banner", "-nostdin", "-v", "error", "-xerror",
        "-c:v", "libdav1d", "-filmgrain", "0", "-i", str(encoded),
        "-map", "0:v:0", "-frames:v", str(frames), "-an", "-sn", "-dn",
        "-f", "null", "-",
    ]


def ratio_percent(numerator: int, denominator: int) -> float:
    return round((numerator / denominator - 1.0) * 100.0, 4)


def size_decomposition(sizes: dict[str, int]) -> dict:
    key = lambda base, table: f"{base}-base_{table}-table"
    return {
        "combined_source_vs_residual_percent": ratio_percent(
            sizes[key("source", "source")], sizes[key("residual", "residual")]),
        "base_effect_percent": {
            table: ratio_percent(
                sizes[key("source", table)], sizes[key("residual", table)])
            for table in TABLES
        },
        "source_table_effect_percent": {
            base: ratio_percent(
                sizes[key(base, "source")], sizes[key(base, "residual")])
            for base in BASES
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        default="/media/merged-storage/media/test-encodes/"
                "sourcefit-general-gate-20260803/clips/Silo.mkv")
    parser.add_argument(
        "--work",
        default="/media/merged-storage/media/test-encodes/"
                "sourcefit-silo-transfer-20260803")
    parser.add_argument(
        "--candidate-nvencc",
        default="/home/bardie/.cache/fgs-gate/builds/"
                "pin-603c2eea-1785764448/build-gate/nvencc")
    parser.add_argument("--ffmpeg", default="/usr/local/bin/ffmpeg")
    parser.add_argument("--ffprobe", default="/usr/local/bin/ffprobe")
    parser.add_argument("--frames", type=int, default=600)
    parser.add_argument("--qvbr", type=int, default=29)
    args = parser.parse_args()

    source = Path(args.source).resolve()
    work = Path(args.work).resolve()
    binary = Path(args.candidate_nvencc).resolve()
    ffmpeg = Path(args.ffmpeg).resolve()
    ffprobe = Path(args.ffprobe).resolve()
    for path in (source, binary, ffmpeg, ffprobe):
        if not path.is_file():
            parser.error(f"missing input: {path}")
    if args.frames < 2:
        parser.error("--frames must be at least 2")

    task_dir = work / "tasks"
    task_dir.mkdir(parents=True, exist_ok=True)
    gate.review_score.FFPROBE = str(ffprobe)

    bases: dict[str, Path] = {}
    tables: dict[str, Path] = {}
    binary_identity = identity(binary, include_hash=True)
    records = {
        "purpose": "isolate source-fit base and table size effects",
        "source": identity(source),
        "candidate_binary": binary_identity,
        "frames": args.frames,
        "qvbr": args.qvbr,
        "analysis": {},
        "encodes": {},
    }

    for base in BASES:
        output = work / f"{base}-base.y4m"
        table = work / f"{base}.tbl"
        output_partial = partial_path(output)
        table_partial = partial_path(table)
        command = analysis_command(
            binary, source, output_partial, table_partial, base)
        expected = {
            "command": command,
            "source": identity(source),
            "binary": binary_identity,
        }
        record = gate.run_task(
            f"{base}-analysis", command, expected,
            [output_partial, table_partial], [output, table],
            task_dir / f"{base}-analysis.task.json",
            task_dir / f"{base}-analysis.log")
        gate.require_frames(output, args.frames)
        bases[base] = output
        tables[base] = table
        records["analysis"][base] = {
            "task": record,
            "base": identity(output),
            "table": {**identity(table), "sha256": sha256(table)},
            "table_summary": gate.table_summary(table),
        }
        write_json(work / "manifest.json", records)

    sizes: dict[str, int] = {}
    for base in BASES:
        for table_name in TABLES:
            name = f"{base}-base_{table_name}-table"
            output = work / f"{name}.mkv"
            output_partial = partial_path(output)
            table = None if table_name == "none" else tables[table_name]
            command = fixed_encode_command(
                binary, bases[base], output_partial, table, args.qvbr)
            expected = {
                "command": command,
                "source": identity(bases[base]),
                "table": None if table is None else identity(table),
                "binary": binary_identity,
            }
            record = gate.run_task(
                name, command, expected, [output_partial], [output],
                task_dir / f"{name}.task.json",
                task_dir / f"{name}.log")
            gate.require_frames(output, args.frames)
            decode = decode_command(ffmpeg, output, args.frames)
            elapsed = run_logged(
                decode, os.environ.copy(), task_dir / f"{name}-dav1d.log")
            sizes[name] = output.stat().st_size
            records["encodes"][name] = {
                "task": record,
                "output": {**identity(output), "sha256": sha256(output)},
                "dav1d": {
                    "command": decode,
                    "elapsed_seconds": elapsed,
                    "full_decode": True,
                    "filmgrain": 0,
                },
            }
            write_json(work / "manifest.json", records)

    result = {
        "manifest": str((work / "manifest.json").resolve()),
        "encoded_bytes": sizes,
        "decomposition": size_decomposition(sizes),
    }
    write_json(work / "result.json", result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        raise SystemExit(130)
