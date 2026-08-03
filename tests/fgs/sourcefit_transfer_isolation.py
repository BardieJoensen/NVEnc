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
from collections import Counter
import json
import os
from pathlib import Path
import sys

import numpy as np


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


def _y4m_layout(handle) -> tuple[int, int, int, int]:
    header = handle.readline().decode("ascii", errors="strict").strip()
    if not header.startswith("YUV4MPEG2 "):
        raise RuntimeError("not a Y4M stream")
    tokens = header.split()
    width = int(next(token[1:] for token in tokens if token.startswith("W")))
    height = int(next(token[1:] for token in tokens if token.startswith("H")))
    chroma = next(token[1:] for token in tokens if token.startswith("C"))
    if not chroma.startswith("420p10"):
        raise RuntimeError(f"expected 10-bit 4:2:0 Y4M, got {chroma}")
    luma_samples = width * height
    chroma_samples = 2 * ((width + 1) // 2) * ((height + 1) // 2)
    return width, height, luma_samples, chroma_samples


def _histogram_quantile(histogram: np.ndarray, fraction: float) -> int | None:
    total = int(histogram.sum())
    if total == 0:
        return None
    target = max(1, int(np.ceil(total * fraction)))
    return int(np.searchsorted(np.cumsum(histogram), target))


def compare_y4m_bases(left: Path, right: Path, frames: int) -> dict:
    """Stream a sample-exact raw-base comparison without retaining frames."""
    changed_luma = 0
    luma_samples_total = 0
    signed_sum = 0
    absolute_sum = 0
    minimum = None
    maximum = None
    delta_histogram: Counter[int] = Counter()
    changed_luma_levels = np.zeros(256, dtype=np.int64)
    changed_chroma = 0
    chroma_samples_total = 0

    with left.open("rb") as left_handle, right.open("rb") as right_handle:
        left_layout = _y4m_layout(left_handle)
        right_layout = _y4m_layout(right_handle)
        if left_layout != right_layout:
            raise RuntimeError(f"Y4M layout mismatch: {left_layout} != {right_layout}")
        _, _, luma_samples, chroma_samples = left_layout
        luma_bytes = luma_samples * 2
        chroma_bytes = chroma_samples * 2

        for frame in range(frames):
            left_marker = left_handle.readline()
            right_marker = right_handle.readline()
            if not left_marker.startswith(b"FRAME") or not right_marker.startswith(b"FRAME"):
                raise RuntimeError(f"missing Y4M frame marker at frame {frame}")
            left_luma_raw = left_handle.read(luma_bytes)
            right_luma_raw = right_handle.read(luma_bytes)
            left_chroma_raw = left_handle.read(chroma_bytes)
            right_chroma_raw = right_handle.read(chroma_bytes)
            if min(map(len, (
                    left_luma_raw, right_luma_raw,
                    left_chroma_raw, right_chroma_raw))) == 0:
                raise RuntimeError(f"truncated Y4M payload at frame {frame}")
            if len(left_luma_raw) != luma_bytes or len(right_luma_raw) != luma_bytes:
                raise RuntimeError(f"truncated Y4M luma at frame {frame}")
            if len(left_chroma_raw) != chroma_bytes or len(right_chroma_raw) != chroma_bytes:
                raise RuntimeError(f"truncated Y4M chroma at frame {frame}")

            left_luma = np.frombuffer(left_luma_raw, dtype="<u2")
            right_luma = np.frombuffer(right_luma_raw, dtype="<u2")
            delta = right_luma.astype(np.int32) - left_luma.astype(np.int32)
            changed = delta != 0
            count = int(np.count_nonzero(changed))
            changed_luma += count
            luma_samples_total += luma_samples
            signed_sum += int(delta.sum(dtype=np.int64))
            absolute_sum += int(np.abs(delta).sum(dtype=np.int64))
            if count:
                changed_delta = delta[changed]
                local_min = int(changed_delta.min())
                local_max = int(changed_delta.max())
                minimum = local_min if minimum is None else min(minimum, local_min)
                maximum = local_max if maximum is None else max(maximum, local_max)
                values, counts = np.unique(changed_delta, return_counts=True)
                delta_histogram.update({
                    int(value): int(value_count)
                    for value, value_count in zip(values, counts)
                })
                changed_luma_levels += np.bincount(
                    np.minimum(255, left_luma[changed] >> 2), minlength=256)

            left_chroma = np.frombuffer(left_chroma_raw, dtype="<u2")
            right_chroma = np.frombuffer(right_chroma_raw, dtype="<u2")
            changed_chroma += int(np.count_nonzero(left_chroma != right_chroma))
            chroma_samples_total += chroma_samples

        if left_handle.read(1) or right_handle.read(1):
            raise RuntimeError(f"Y4M streams contain more than {frames} frames")

    return {
        "direction": "source-fit base minus residual-fit base",
        "frames": frames,
        "luma": {
            "samples": luma_samples_total,
            "changed_samples": changed_luma,
            "changed_fraction": changed_luma / luma_samples_total,
            "signed_mean_10bit_codes": signed_sum / luma_samples_total,
            "absolute_mean_10bit_codes": absolute_sum / luma_samples_total,
            "absolute_mean_changed_10bit_codes": (
                absolute_sum / changed_luma if changed_luma else 0.0),
            "minimum_delta_10bit_codes": minimum,
            "maximum_delta_10bit_codes": maximum,
            "delta_histogram": {
                str(value): delta_histogram[value]
                for value in sorted(delta_histogram)
            },
            "changed_input_luma_8bit": {
                "p05": _histogram_quantile(changed_luma_levels, 0.05),
                "p50": _histogram_quantile(changed_luma_levels, 0.50),
                "p95": _histogram_quantile(changed_luma_levels, 0.95),
                "maximum": (
                    int(np.flatnonzero(changed_luma_levels)[-1])
                    if changed_luma else None),
            },
        },
        "chroma": {
            "samples": chroma_samples_total,
            "changed_samples": changed_chroma,
            "changed_fraction": changed_chroma / chroma_samples_total,
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

    base_delta = compare_y4m_bases(
        bases["residual"], bases["source"], args.frames)
    records["base_luma_delta"] = base_delta
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
        "base_luma_delta": base_delta,
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
