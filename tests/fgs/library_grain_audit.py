#!/usr/bin/env python3
"""Audit which library transcodes carry synthesized film grain.

FGS entered the production Tdarr flow on 2026-07-29 and the encode template
applies `--av1-film-grain` unconditionally.  The 2026-07-16 campaign had
already measured what that does to non-grain content -- worst-frame VMAF
collapsing to 31--60 against plain's 94--96, while saving little or nothing and
sometimes producing *larger* files -- and recorded a content gate as
"MANDATORY before flow integration".  This establishes whether that gate exists
in practice.

Detection is behavioural rather than parsed.  An AV1 stream signals grain in
its frame headers, and a decoder applies it only when asked, so decoding the
same frames twice through dav1d -- once with film grain applied, once with
`filmgrain=0` -- and comparing hashes answers the question exactly:

    differing hashes  ->  the stream carries grain the decoder synthesized
    identical hashes  ->  no grain in the stream

That is decisive and needs no reference, which matters because the originals
for most of the library are long gone.

Whether grain *should* be there is a separate judgement and this script does
not make it.  It reports presence and strength, and flags the class where the
answer is unambiguous: animation and other grain-free digital sources, where
any synthesized grain was invented.

Read-only.  Nothing is re-encoded, moved or deleted.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

# Titles whose sources carry no photochemical grain.  Deliberately a
# conservative list of strong signals rather than a genre guess: a false
# positive here would accuse the encoder of a defect it did not commit.
ANIMATION_HINTS = (
    "animation", "animated", "pixar", "ghibli", "studio ghibli", "dreamworks",
    "kiki", "poppy hill", "spirited away", "totoro", "mononoke", "howl",
    "ponyo", "arrietty", "marnie", "wind rises", "grave of the fireflies",
    "toy story", "wall-e", "ratatouille", "incredibles", "coco", "soul",
    "inside out", "up (", "finding nemo", "monsters inc", "shrek", "kung fu panda",
    "how to train your dragon", "spider-verse", "spiderverse", "arcane",
    "long halloween", "batman year one", "justice league", "invincible",
    "rick and morty", "simpsons", "south park", "bluey", "avatar the last",
)


def is_grainless_source(path: Path) -> bool:
    text = str(path).lower()
    return any(hint in text for hint in ANIMATION_HINTS)


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=codec_name,width,height", "-of", "json", str(path)],
        capture_output=True, text=True)
    try:
        s = json.loads(out.stdout)["streams"][0]
    except Exception:
        return {}
    return s


def decode_hash(path: Path, frames: int, filmgrain: bool, seek: float) -> str | None:
    """Hash of decoded luma, with film grain applied or suppressed."""
    command = [
        "ffmpeg", "-v", "error", "-nostdin",
        "-ss", str(seek),
        "-c:v", "libdav1d",
    ]
    if not filmgrain:
        command += ["-filmgrain", "0"]
    command += ["-i", str(path), "-frames:v", str(frames),
                "-map", "0:v:0", "-pix_fmt", "gray10le", "-f", "rawvideo", "-"]
    result = subprocess.run(command, capture_output=True)
    if result.returncode != 0 or not result.stdout:
        return None
    return hashlib.sha1(result.stdout).hexdigest()


def grain_strength(path: Path, frames: int, seek: float) -> float | None:
    """Mean |grain| in 10-bit code values: the difference the decoder applies."""
    import numpy as np
    raw = {}
    for tag, fg in (("on", True), ("off", False)):
        command = ["ffmpeg", "-v", "error", "-nostdin", "-ss", str(seek),
                   "-c:v", "libdav1d"]
        if not fg:
            command += ["-filmgrain", "0"]
        command += ["-i", str(path), "-frames:v", str(frames), "-map", "0:v:0",
                    "-pix_fmt", "gray10le", "-f", "rawvideo", "-"]
        r = subprocess.run(command, capture_output=True)
        if r.returncode != 0 or not r.stdout:
            return None
        raw[tag] = np.frombuffer(r.stdout, np.uint16).astype(np.float64)
    n = min(raw["on"].size, raw["off"].size)
    if n == 0:
        return None
    return float(np.abs(raw["on"][:n] - raw["off"][:n]).mean())


def audit_one(path: Path, frames: int, seek: float) -> dict | None:
    info = probe(path)
    if not info:
        return None
    row = {
        "path": str(path),
        "codec": info.get("codec_name"),
        "height": info.get("height"),
        "grainless_source": is_grainless_source(path),
        "bytes": path.stat().st_size,
    }
    if info.get("codec_name") != "av1":
        row["grain"] = None
        return row
    on = decode_hash(path, frames, True, seek)
    off = decode_hash(path, frames, False, seek)
    if on is None or off is None:
        row["grain"] = None
        row["error"] = "decode failed"
        return row
    row["grain"] = (on != off)
    if row["grain"]:
        row["grain_strength"] = grain_strength(path, frames, seek)
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", required=True,
                        help="file of paths, one per line, relative to --root")
    parser.add_argument("--root", default="/media/merged-storage/media")
    parser.add_argument("--frames", type=int, default=6)
    parser.add_argument("--seek", type=float, default=300.0,
                        help="seconds in, to land past titles/black")
    parser.add_argument("--jobs", type=int, default=6)
    parser.add_argument("--json-out", default="")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    root = Path(args.root)
    paths = [root / line.strip() for line in Path(args.list).read_text().splitlines()
             if line.strip()]
    if args.limit:
        paths = paths[:args.limit]

    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(audit_one, p, args.frames, args.seek): p for p in paths}
        for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            row = fut.result()
            if row:
                rows.append(row)
            if i % 25 == 0:
                print(f"  ...{i}/{len(paths)}", file=sys.stderr, flush=True)

    av1 = [r for r in rows if r["codec"] == "av1"]
    grained = [r for r in av1 if r.get("grain")]
    grainless_src = [r for r in rows if r["grainless_source"]]
    misfires = [r for r in grainless_src if r.get("grain")]

    print(f"\n=== audited {len(rows)} files ===")
    print(f"  AV1 (flow output)          {len(av1)}")
    print(f"  of those carrying grain    {len(grained)}")
    print(f"  grain-free source titles   {len(grainless_src)}")
    print(f"  ** synthesized onto those  {len(misfires)} **")

    if misfires:
        print("\n=== grain synthesized onto grain-free sources ===")
        for r in sorted(misfires, key=lambda r: -(r.get("grain_strength") or 0))[:25]:
            s = r.get("grain_strength")
            print(f"  {s if s is None else round(s, 2):>6}  "
                  f"{Path(r['path']).name[:88]}")

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(rows, indent=2) + "\n")
        print(f"\nwrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
