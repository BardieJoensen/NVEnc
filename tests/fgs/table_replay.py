#!/usr/bin/env python3
"""Replay one or more film-grain tables over one fixed coded-base input.

This isolates table experiments from separator changes.  Each labelled table
is attached while the same base is encoded with the same NVENC settings, then
the result is fully decoded by dav1d with grain both disabled and enabled.
Tasks are resumable and bound to command, binary, base and table identities.
The script does not analyse or generate a grain model and cannot change a
production default.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from integrated_architecture import (  # noqa: E402
    complete_task,
    identity,
    partial_path,
    publish_outputs,
    run_logged,
    write_json,
)
from sourcefit_transfer_isolation import fixed_encode_command  # noqa: E402


def decode_command(ffmpeg: Path, encoded: Path, filmgrain: int) -> list[str]:
    return [
        str(ffmpeg), "-hide_banner", "-nostdin", "-v", "error", "-xerror",
        "-c:v", "libdav1d", "-filmgrain", str(filmgrain), "-i", str(encoded),
        "-map", "0:v:0", "-an", "-sn", "-dn", "-f", "null", "-",
    ]


def parse_tables(values: list[str]) -> dict[str, Path]:
    tables = {}
    for value in values:
        label, separator, path = value.partition("=")
        if not separator or not label or not path:
            raise ValueError(f"invalid --table {value!r}; expected LABEL=PATH")
        if label in tables:
            raise ValueError(f"duplicate table label: {label}")
        tables[label] = Path(path).resolve()
    return tables


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nvencc", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--table", action="append", required=True,
                        help="LABEL=filmgrn1.tbl; repeatable")
    parser.add_argument("--work", required=True)
    parser.add_argument("--ffmpeg", default="/usr/local/bin/ffmpeg")
    parser.add_argument("--qvbr", type=int, default=29)
    args = parser.parse_args()

    try:
        tables = parse_tables(args.table)
    except ValueError as error:
        parser.error(str(error))
    binary = Path(args.nvencc).resolve()
    base = Path(args.base).resolve()
    ffmpeg = Path(args.ffmpeg).resolve()
    work = Path(args.work).resolve()
    for path in (binary, base, ffmpeg, *tables.values()):
        if not path.is_file():
            parser.error(f"missing file: {path}")
    work.mkdir(parents=True, exist_ok=True)

    binary_id = identity(binary, include_hash=True)
    base_id = identity(base, include_hash=True)
    manifest = {
        "purpose": "fixed-base decoded table replay",
        "binary": binary_id,
        "base": base_id,
        "qvbr": args.qvbr,
        "arms": {},
    }
    for label, table in tables.items():
        output = work / f"{label}.mkv"
        output_partial = partial_path(output)
        command = fixed_encode_command(
            binary, base, output_partial, table, args.qvbr)
        expected = {
            "command": command,
            "binary": binary_id,
            "base": base_id,
            "table": identity(table, include_hash=True),
        }
        task = work / f"{label}-encode.task.json"
        if complete_task(task, expected, [output]):
            print(f"[resume] {label}-encode", flush=True)
            record = json.loads(task.read_text(encoding="utf-8"))
        else:
            if output.exists():
                raise RuntimeError(
                    f"{output} exists without a matching task manifest")
            print(f"[run] {label}-encode", flush=True)
            elapsed = run_logged(
                command, os.environ.copy(), work / f"{label}-encode.log")
            publish_outputs([output_partial], [output])
            record = {
                "input": expected,
                "outputs": [identity(output, include_hash=True)],
                "elapsed_seconds": elapsed,
            }
            write_json(task, record)

        decodes = {}
        for filmgrain in (0, 1):
            name = f"{label}-dav1d-grain{filmgrain}"
            command = decode_command(ffmpeg, output, filmgrain)
            print(f"[run] {name}", flush=True)
            elapsed = run_logged(
                command, os.environ.copy(), work / f"{name}.log")
            decodes[str(filmgrain)] = {
                "command": command,
                "elapsed_seconds": elapsed,
            }
        manifest["arms"][label] = {
            "table": expected["table"],
            "encode": record,
            "dav1d": decodes,
        }
        write_json(work / "manifest.json", manifest)

    print(f"manifest: {work / 'manifest.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
