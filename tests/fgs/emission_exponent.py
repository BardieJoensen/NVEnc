#!/usr/bin/env python3
"""Is the analyser's amplitude response a power law rather than a floor?

`FINDINGS-2026-08-06-FLOOR-ABLATION.md` exonerated both noise floors, so the
one-defect relationship -- over-delivery at low signal, log-log slope `-0.414`
-- has to come from the estimator itself.

Reading the emitted tables suggests why.  Grain-free animation emits scaling
point values in the same range as grainy film (medians 56--158 against
93--168); almost all of the amplitude difference is carried by the power-of-two
shift.  Emission is barely tracking the source.

That is the signature of a compressive response, not a floor.  If delivered
amplitude goes as `source^b`, then the ratio `delivered/source` goes as
`source^(b-1)`, and the measured `-0.414` implies `b ~ 0.59`.  A floor would
give `b = 0` in the affected region and `b = 1` outside it -- a knee, not a
straight line -- and the one-defect scatter is straight across the whole range.

`b = 0.5` has an obvious candidate cause: a standard deviation used where a
variance belongs, or the reverse, somewhere in the strength fit.  This script
measures `b` directly, on one consistent instrument, rather than inferring it
from pooled heterogeneous cells.

Source signal is measured the way the analyser measures it -- per-block
standard deviation over the flattest blocks -- so that the regressor is the
same quantity the encoder is responding to, not a proxy.  Emitted amplitude is
the normalised curve RMS, which is the analyser's own estimate.

This is a diagnosis of the estimator's response shape.  It is not a quality
claim and no fitted coefficient from it should be applied as a correction:
`FINDINGS-2026-08-06-ONE-DEFECT.md` explicitly names a global compensating
curve as the corpus-derived scalar this project has already rejected six times.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import statistics
import sys
from pathlib import Path

import numpy as np

from floor_separation import curve_rms

ANIM = Path("/tmp/downloads/animation-gate-20260806")
FILM = Path("/media/merged-storage/media/test-encodes/keep-original")
OUT = Path("/tmp/downloads/emission-exponent-20260806")

SOURCES = {
    "LongHalloween": ANIM / "LongHalloween-O.mkv",
    "PoppyHill": ANIM / "PoppyHill-O.mkv",
    "Kiki": ANIM / "Kiki-O.mkv",
    "The_Deer_Hunter": FILM / "clip_The_Deer_Hunter.mkv",
    "Taxi_Driver": FILM / "clip_Taxi_Driver-ref288.mkv",
    "The_Shining": FILM / "clip_The_Shining-ref288.mkv",
    "Casino": FILM / "clip_Casino-ref288.mkv",
    "Scarface": FILM / "clip_Scarface-ref288.mkv",
    "Interstellar": FILM / "clip_Interstellar.mkv",
}

FGS = "denoise=auto,chroma=auto,denoiser=bilateral,modelsrc=on"


def encode(binary: Path, source: Path, output: Path, table: Path, qvbr: int) -> None:
    command = [
        str(binary), "--avsw", "-i", str(source), "--codec", "av1",
        "--output-depth", "10", "--qvbr", str(qvbr), "--max-bitrate", "50000",
        "--preset", "quality", "--tune", "hq", "--aq", "--aq-temporal",
        "--colormatrix", "auto", "--colorprim", "auto", "--transfer", "auto",
        "--colorrange", "auto", "--av1-film-grain", FGS,
        "--film-grain-table-out", str(table), "--log-level", "debug",
        "-o", str(output),
    ]
    env = dict(os.environ)
    env.pop("NVENC_FGS_TEST_MIN_NOISE", None)
    result = subprocess.run(command, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"encode failed for {output.name}:\n{result.stderr[-1500:]}")
    if "test-only noise floors" in (result.stderr + result.stdout):
        raise RuntimeError(f"{output.name}: a floor override leaked into the control")


def active_crop(path: Path) -> str | None:
    """Letterbox bars are perfectly flat and would win any flatness ranking.

    The first pass of this measurement reported sigma exactly 0.000 on five
    titles, every one of them 2.35:1 -- the selector was measuring the bars.
    The encoder never sees them as candidates because its own admission
    requires sigma >= minSigma, so cropping here restores the comparison
    rather than imposing a new one.
    """
    result = subprocess.run(
        ["ffmpeg", "-v", "info", "-nostdin", "-i", str(path), "-vf",
         "cropdetect=24:2:0", "-frames:v", "48", "-f", "null", "-"],
        capture_output=True, text=True)
    crops = [line.split("crop=")[-1].strip()
             for line in result.stderr.splitlines() if "crop=" in line]
    return crops[-1] if crops else None


def source_sigma(path: Path, frames: int, block: int = 32,
                 flat_fraction: float = 0.25, admission: float = 2.0) -> float:
    """Per-block sd over the flattest blocks -- the analyser's own measure.

    Flatness is ranked by mean absolute gradient so that strong grain does not
    disqualify a block for being noisy; that is the same trap
    `flat_block_finder` works around by taking a score percentile.
    """
    crop = active_crop(path)
    if crop:
        w, h = (int(v) for v in crop.split(":")[:2])
        vf = ["-vf", f"crop={crop}"]
    else:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height", "-of", "json", str(path)],
            capture_output=True, text=True)
        stream = json.loads(probe.stdout)["streams"][0]
        w, h = stream["width"], stream["height"]
        vf = []
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-nostdin", "-i", str(path)] + vf
        + ["-frames:v", str(frames), "-pix_fmt", "gray10le", "-f", "rawvideo", "-"],
        capture_output=True)
    data = np.frombuffer(result.stdout, np.uint16).astype(np.float64)
    n = min(frames, data.size // (w * h))
    if n < 1:
        raise RuntimeError(f"{path.name}: no frames decoded")
    data = data[:n * w * h].reshape(n, h, w)
    by, bx = h // block, w // block
    tiles = (data[:, :by * block, :bx * block]
             .reshape(n, by, block, bx, block)
             .transpose(0, 1, 3, 2, 4)
             .reshape(n, by * bx, block, block))

    # Separate structure from noise before ranking.  Ranking by raw pixel
    # gradient finds *uniform* blocks, not flat-but-grainy ones -- the exact
    # bias NVEncFilterFilmGrain.cu:2400 documents ("strong grain inflates the
    # gradient metrics, so strict-threshold selection alone samples only the
    # weakest-grain regions and biases the strength curve").  Structure is the
    # 8x8 mean-pooled block; noise is what the pooling removes.
    pool = block // 8
    coarse = tiles.reshape(n, by * bx, 8, pool, 8, pool).mean(axis=(3, 5))
    structure = coarse.reshape(n, by * bx, 64).std(axis=2)
    upsampled = np.repeat(np.repeat(coarse, pool, axis=2), pool, axis=3)
    noise = (tiles - upsampled).reshape(n, by * bx, block * block).std(axis=2)

    keep = max(1, int(structure.shape[1] * flat_fraction))
    order = np.argsort(structure, axis=1)[:, :keep]
    flat_noise = np.take_along_axis(noise, order, axis=1)

    # Digital animation contains genuinely uniform blocks -- sd exactly 0, real
    # content rather than a measurement artifact.  The encoder never fits them:
    # admission at :2425 requires `sigma >= minSigma && score > 0`.  Matching
    # that admission is what makes this the regressor the analyser actually
    # responded to.  The ablation showed the floor excludes nothing among
    # already-admitted blocks, so this cannot smuggle the floor back in.
    admitted = flat_noise[flat_noise >= admission]
    if admitted.size == 0:
        raise RuntimeError(
            f"{path.name}: no flat block reaches the admission floor {admission}; "
            "the analyser would have no model to fit either")
    return float(np.median(admitted))


def fit_loglog(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    lx = [math.log(x) for x in xs]
    ly = [math.log(y) for y in ys]
    n = len(lx)
    mx, my = statistics.mean(lx), statistics.mean(ly)
    sxy = sum((a - mx) * (b - my) for a, b in zip(lx, ly))
    sxx = sum((a - mx) ** 2 for a in lx)
    syy = sum((b - my) ** 2 for b in ly)
    slope = sxy / sxx
    r = sxy / math.sqrt(sxx * syy)
    t = r * math.sqrt((n - 2) / (1 - r * r)) if abs(r) < 1 else float("inf")
    return slope, r, t


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True)
    parser.add_argument("--qvbr", type=int, default=25)
    parser.add_argument("--frames", type=int, default=24)
    args = parser.parse_args()

    binary = Path(args.binary)
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for title, source in SOURCES.items():
        if not source.is_file():
            print(f"skip {title}: no source", file=sys.stderr)
            continue
        table = OUT / f"{title}.tbl"
        encoded = OUT / f"{title}.mkv"
        if not table.is_file():
            encode(binary, source, encoded, table, args.qvbr)
        sigma = source_sigma(source, args.frames)
        emitted = curve_rms(table)["y"]
        rows.append((title, sigma, emitted))
        print(f"{title:17} source_sigma={sigma:8.3f}  emitted={emitted:.5f}",
              flush=True)

    if len(rows) < 4:
        print("too few cells to fit", file=sys.stderr)
        return 1

    xs = [r[1] for r in rows]
    ys = [r[2] for r in rows]
    b, r, t = fit_loglog(xs, ys)
    print(f"\n=== emitted amplitude vs source sigma, log-log ===")
    print(f"exponent b = {b:.3f}   r = {r:.3f}   t = {t:.2f}   n = {len(rows)}")
    print(f"implied ratio slope (b-1) = {b - 1:.3f}"
          f"   [one-defect measured -0.414]")
    print()
    print("  b = 1.0  correct tracking")
    print("  b = 0.5  a standard deviation where a variance belongs, or reverse")
    print("  b = 0.0  fixed emission regardless of source (a pure floor)")

    (OUT / "emission-exponent.json").write_text(json.dumps(
        {"rows": [{"title": a, "source_sigma": s, "emitted": e} for a, s, e in rows],
         "exponent": b, "r": r, "t": t}, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
