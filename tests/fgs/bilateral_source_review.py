#!/usr/bin/env python3
"""Build a blind production-vs-bilateral-source playback package.

This is the perceptual gate for the source-derived grain model with the trusted
bilateral separator held fixed.  Each input is decoded twice with libdav1d:
grain disabled exposes the coded base, while grain enabled exposes the actual
playback result.  Lossless 1920x1080 FFV1 crops prevent a review encode from
becoming another variable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import time


DEFAULT_TITLES = (
    "Casino", "Interstellar", "Taxi_Driver", "The_Deer_Hunter",
    "The_Shining",
)
ARMS = ("production bilateral/residual", "bilateral/source-fit")


def assignment(title: str) -> dict[str, str]:
    """Stable mixed A/B mapping, shared by base and finished variants."""
    bit = hashlib.sha256(
        f"bilateral-source-review-v2:{title}".encode("utf-8")).digest()[0] & 1
    ordered = ARMS if bit == 0 else ARMS[::-1]
    return {"A": ordered[0], "B": ordered[1]}


def input_for(arm: str, title: str, integrated: Path, bilateral: Path) -> Path:
    if arm == "production bilateral/residual":
        return integrated / title / "production.mkv"
    if arm == "bilateral/source-fit":
        return bilateral / title / "bilateral-source.mkv"
    raise ValueError(f"unknown arm {arm}")


def build_command(ffmpeg: Path, source: Path, output: Path, filmgrain: int) -> list[str]:
    return [
        str(ffmpeg), "-hide_banner", "-nostdin", "-y", "-v", "error",
        "-c:v", "libdav1d", "-filmgrain", str(filmgrain), "-i", str(source),
        "-map", "0:v:0", "-an", "-sn", "-dn",
        "-vf", "crop=1920:1080:(iw-1920)/2:(ih-1080)/2",
        "-fps_mode", "passthrough", "-pix_fmt", "yuv420p10le",
        "-c:v", "ffv1", "-level", "3", "-coder", "1", "-context", "1",
        "-g", "1", "-slicecrc", "1", str(output),
    ]


def identity(path: Path) -> dict:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def write_json(path: Path, value: object) -> None:
    partial = path.with_suffix(path.suffix + ".partial")
    partial.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.replace(partial, path)


def complete(manifest: Path, expected: dict, output: Path) -> bool:
    if not manifest.is_file() or not output.is_file():
        return False
    try:
        recorded = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return recorded.get("input") == expected


def validate(ffprobe: Path, output: Path) -> dict:
    result = subprocess.run([
        str(ffprobe), "-v", "error", "-select_streams", "v:0",
        "-show_entries",
        "stream=codec_name,width,height,pix_fmt,color_range,color_space,color_transfer,color_primaries,r_frame_rate",
        "-of", "json", str(output),
    ], check=True, capture_output=True, text=True)
    streams = json.loads(result.stdout).get("streams", [])
    if len(streams) != 1:
        raise RuntimeError(f"{output}: expected one video stream")
    stream = streams[0]
    expected = {
        "codec_name": "ffv1", "width": 1920, "height": 1080,
        "pix_fmt": "yuv420p10le",
        "color_range": "tv", "color_space": "bt2020nc",
        "color_transfer": "smpte2084", "color_primaries": "bt2020",
    }
    for key, value in expected.items():
        if stream.get(key) != value:
            raise RuntimeError(
                f"{output}: expected {key}={value}, got {stream.get(key)}")
    return stream


def render_readme() -> str:
    return """# Bilateral source-fit blind review, 2026-08-03

This package compares the deployed production film-grain path with the
quality-first two-operator architecture. Both use the same bilateral
separator. One fits AV1 grain texture from the separator residual; the other
fits it independently from source flat-block statistics. Nothing in this
package has been deployed to Tdarr.

Each title has four lossless 1920x1080 10-bit FFV1 centre crops:

- `A-base` and `B-base`: AV1 decoded with film grain disabled;
- `A-finished` and `B-finished`: the same streams decoded normally.

The mapping is consistent within a title and hidden in
`REVEAL-AFTER-REVIEW.md`. File size is irrelevant because these are lossless
review copies.

## Review order

1. Watch each base pair first. Since both arms use bilateral separation, look
   for any real-detail or black-level difference rather than motion ghosting.
2. Watch the finished pair at normal speed. Judge grain *scale* first: coarse
   film grain should not turn into fine electronic noise.
3. Judge strength separately. Inspect bright flat regions first -- skies,
   walls and faces in key light -- then dark weak-grain regions. Look for
   crawling colour noise, chroma blotches, lift, pumping or obvious
   under/over-graining.
4. Record title, A/B, timestamp and observation before opening the reveal.

Independent AV1 grain fields occupy different pixel positions. Do not score a
paused-frame grain-pattern mismatch; judge texture, strength, stability and
interaction with picture detail.

The strength report already flags the brightest populated luma band
(`0.375--0.500`) on Taxi Driver (low), Interstellar (high) and Deer Hunter
(high). Treat visible bright-band errors as confirmation of that known risk,
not a new result. Chroma V also changes from title-mean under-delivery in the
production arm to over-delivery in the source-fit arm; Deer Hunter U is the
largest U outlier. Note any visible colour crawl or blotches, but do not let
that replace the grain-texture judgement.

Taxi Driver is the coarse-grain and dark-chroma stress case. Interstellar is
the whole-title and thin bright-band over-delivery stress case. Deer Hunter
has the strongest measured bright-band error. Casino previously exposed
detail substitution, and The Shining checks correlated grain and amplitude.
"""


def render_reveal(mappings: dict[str, dict[str, str]]) -> str:
    lines = [
        "# Mapping — reveal after playback review", "",
        "Do not read this file until A/B observations have been recorded.", "",
        "| title | A | B |", "| --- | --- | --- |",
    ]
    for title, mapping in mappings.items():
        lines.append(
            f"| {title.replace('_', ' ')} | {mapping['A']} | {mapping['B']} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--integrated-root", type=Path,
        default=Path("/media/merged-storage/media/test-encodes/sourcefit-integrated-20260803"))
    parser.add_argument(
        "--bilateral-root", type=Path,
        default=Path("/media/merged-storage/media/test-encodes/sourcefit-bilateral-quality-20260803"))
    parser.add_argument(
        "--output", type=Path,
        default=Path("/media/merged-storage/media/test-encodes/sourcefit-bilateral-review-20260803"))
    parser.add_argument("--titles", default=",".join(DEFAULT_TITLES))
    parser.add_argument("--ffmpeg", type=Path, default=Path("/usr/bin/ffmpeg"))
    parser.add_argument("--ffprobe", type=Path, default=Path("/usr/local/bin/ffprobe"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    titles = tuple(value.strip() for value in args.titles.split(",") if value.strip())
    if not titles:
        parser.error("at least one title is required")
    blind = args.output / "blind"
    blind.mkdir(parents=True, exist_ok=True)
    mappings = {title: assignment(title) for title in titles}
    tasks = []
    for title in titles:
        for label in ("A", "B"):
            arm = mappings[title][label]
            source = input_for(
                arm, title, args.integrated_root, args.bilateral_root)
            if not source.is_file():
                raise SystemExit(f"missing review input: {source}")
            for variant, filmgrain in (("base", 0), ("finished", 1)):
                output = blind / f"{title}-{label}-{variant}.mkv"
                partial = output.with_name(output.stem + ".partial" + output.suffix)
                manifest = args.output / f"{title}-{label}-{variant}.task.json"
                command = build_command(args.ffmpeg, source, partial, filmgrain)
                expected = {
                    "source": identity(source),
                    "arm": arm,
                    "label": label,
                    "variant": variant,
                    "filmgrain": filmgrain,
                    "command": [str(output) if value == str(partial) else value
                                for value in command],
                }
                tasks.append((command, expected, output, partial, manifest))

    if args.dry_run:
        for command, _expected, output, _partial, _manifest in tasks:
            print(output.name + ": " + shlex.join(command))
        return 0

    for index, (command, expected, output, partial, manifest) in enumerate(tasks, 1):
        if complete(manifest, expected, output):
            print(f"[{index}/{len(tasks)}] cached {output.name}")
            continue
        started = time.monotonic()
        print(f"[{index}/{len(tasks)}] writing {output.name}", flush=True)
        result = subprocess.run(command, check=False)
        if result.returncode:
            raise RuntimeError(
                f"ffmpeg failed ({result.returncode}) while writing {partial}")
        stream = validate(args.ffprobe, partial)
        os.replace(partial, output)
        write_json(manifest, {
            "input": expected,
            "output": identity(output),
            "stream": stream,
            "elapsed_seconds": time.monotonic() - started,
        })

    (blind / "README.md").write_text(render_readme(), encoding="utf-8")
    (blind / "REVEAL-AFTER-REVIEW.md").write_text(
        render_reveal(mappings), encoding="utf-8")
    write_json(args.output / "manifest.json", {
        "scope": "blind bilateral residual-vs-source-fit quality review",
        "titles": list(titles),
        "files": [identity(output) for _command, _expected, output,
                  _partial, _manifest in tasks],
    })
    print(f"review package ready: {blind}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
