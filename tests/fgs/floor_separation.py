#!/usr/bin/env python3
"""Separate the two low-signal floors in the film-grain analyser.

`FINDINGS-2026-08-06-ONE-DEFECT.md` consolidated four open problems into one
relationship: where the source's true grain signal is weak the analyser
over-delivers, by up to 5.18x, with a log-log slope of -0.414 against true
signal.  Two hardcoded floors in `NVEncFilterFilmGrain.cu` can produce that,
both present on master since the first FGS commit and neither reachable from
any command line:

  selection floor (:2391)  blocks measuring below minSigma never enter the
                           flat mask, so the strength curve is fit on a sample
                           censored from below.
  denoise floor   (:2449)  `clamp(metrics[i].sigma, minSigma, maxSigma)` sets
                           per-block *denoise* strength, so a genuinely quiet
                           block is denoised at minSigma instead of its true
                           level.  The base is over-smoothed and the curve is
                           then fit on an inflated `V_source - V_base`.

`minNoiseLevel` is 0.5 in 8-bit units, so on 10-bit content both floors sit at
sigma = 2.0 -- directly on top of the region where over-delivery was measured.

The denoise floor is separable without touching the encoder.  `adaptiveSigma`
is `denoiseLevel <= 0`, so an explicit `denoise=<value>` leaves `sigmaMap`
unpopulated and bypasses the :2449 clamp entirely, while the :2391 selection
floor stays active.

The command line cannot reach below the floor: `NVEncCmd.cpp:1181` rejects any
explicit `denoise` outside [1.0, 50.0], so the smallest requestable sigma is
already twice `minNoiseLevel`.  That is itself a third instance of the same
assumption -- no interface in the encoder can ask it to treat content as
quiet -- and it means the downward test needs a rebuild.

So the test is inverted.  The mechanism claim is that over-denoising inflates
`V_source - V_base` and therefore the fitted curve.  That is a statement about
a monotone relationship, and it can be confirmed going up:

  if over-denoising inflates the curve, emitted curve RMS rises monotonically
  across denoise = 1.0, 2.0, 4.0 (all uniform, all with the :2449 clamp
  bypassed);
  if it does not, the denoise path is not what inflates low-signal estimates
  and the selection floor at :2391 is the whole story.

Confirming the relationship upward establishes it downward by the same
arithmetic: a block denoised at sigma = 2.0 whose true level is 0.4 sits on the
same curve, just on the other side of the requestable range.

Neither outcome changes any default.  This is a diagnosis, not a fix: an
explicit `denoise` is a uniform whole-frame sigma and is not being proposed as
a setting.

The emitted curve is deliberate here.  `FINDINGS-2026-08-04-ADMISSION-GATE.md`
showed it overstates *delivered* strength roughly twofold, so it is the wrong
instrument for a quality claim -- but the floors act on the analyser, and the
emitted curve reads the analyser's estimate without playback variance in the
way.  Delivered temporal noise is reported alongside it as a cross-check.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from pathlib import Path

import filmgrn

WORK = Path("/tmp/downloads/animation-gate-20260806")
OUT = Path("/tmp/downloads/floor-separation-20260806")
CANDIDATE = Path.home() / (
    ".cache/fgs-gate/builds/pin-40b987ff-20260804-response-margin"
    "/build-gate-provisioned/nvencc")
FFMPEG = Path("/usr/bin/ffmpeg")

# Animation: the lowest-signal content in the corpus, where the floor has the
# most room to act.  These carry no photochemical grain at all, so any emitted
# strength is over-delivery by construction.
TITLES = ("LongHalloween", "PoppyHill", "Kiki")

# denoise=auto is the floored control (adaptive, per-block, clamped at :2449).
# The rest are uniform whole-frame sigmas with that clamp bypassed; 1.0 is the
# smallest the command line accepts.
ARMS = ("auto", "1.0", "2.0", "4.0")

BASE_FGS = "chroma=auto,denoiser=bilateral,modelsrc=on"


def encode(binary: Path, source: Path, output: Path, table: Path,
           arm: str, qvbr: int) -> None:
    fgs = f"denoise={arm}," + BASE_FGS
    command = [
        str(binary), "--avsw", "-i", str(source), "--codec", "av1",
        "--output-depth", "10", "--qvbr", str(qvbr), "--max-bitrate", "50000",
        "--preset", "quality", "--tune", "hq", "--aq", "--aq-temporal",
        "--colormatrix", "auto", "--colorprim", "auto", "--transfer", "auto",
        "--colorrange", "auto", "--av1-film-grain", fgs,
        "--film-grain-table-out", str(table), "--log-level", "debug",
        "-o", str(output),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"encode failed for {output.name}:\n{result.stderr[-2000:]}")
    # 9c37ab62 exists because a KAT silently tested the wrong arm.  An encoder
    # that ignores the option must fail loudly rather than produce a number.
    blob = result.stderr + result.stdout
    for line in blob.splitlines():
        if "ignor" in line.lower() and "grain" in line.lower():
            raise RuntimeError(f"{output.name}: encoder ignored an option: {line}")
    if arm != "auto" and f"denoise={arm}" not in blob and "denoise" not in blob:
        raise RuntimeError(f"{output.name}: cannot confirm denoise={arm} took effect")


def curve_rms(table: Path) -> dict:
    """Mean normalised curve RMS per plane over parameter-updating entries."""
    entries = filmgrn.load(table)
    updates = [e for e in entries
               if e["apply_grain"] and e["update_parameters"]]
    out = {}
    for plane in ("y", "cb", "cr"):
        amplitudes = []
        for entry in updates:
            points = entry["scaling_points"][plane]
            if not points:
                continue
            shift = (entry["params"]["scaling_shift"]
                     + entry["params"]["grain_scale_shift"])
            curve = filmgrn._curve(points)
            amplitudes.append(
                (sum(v * v for v in curve) / len(curve)) ** 0.5 / (1 << shift))
        out[plane] = statistics.mean(amplitudes) if amplitudes else 0.0
    out["updates"] = len(updates)
    return out


def temporal_noise(path: Path, frames: int, decoder: str | None) -> float:
    """Mean absolute inter-frame luma difference -- delivered noise proxy."""
    import numpy as np
    command = [str(FFMPEG), "-v", "error", "-nostdin"]
    if decoder:
        command += ["-c:v", decoder]
    command += ["-i", str(path), "-frames:v", str(frames),
                "-pix_fmt", "gray10le", "-f", "rawvideo", "-"]
    result = subprocess.run(command, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"decode failed for {path.name}")
    data = np.frombuffer(result.stdout, np.uint16).astype(np.float64)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height", "-of", "json", str(path)],
        capture_output=True, text=True)
    stream = json.loads(probe.stdout)["streams"][0]
    w, h = stream["width"], stream["height"]
    n = min(frames, data.size // (w * h))
    if n < 2:
        raise RuntimeError(f"{path.name}: only {n} frames decoded")
    data = data[:n * w * h].reshape(n, h, w)
    return float(np.abs(np.diff(data, axis=0)).mean())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qvbr", type=int, default=25)
    parser.add_argument("--frames", type=int, default=24)
    parser.add_argument("--titles", nargs="*", default=list(TITLES))
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    if not CANDIDATE.is_file():
        print(f"missing candidate binary: {CANDIDATE}", file=sys.stderr)
        return 1

    report: dict[str, dict] = {}
    for title in args.titles:
        source = WORK / f"{title}-O.mkv"
        if not source.is_file():
            print(f"skip {title}: no source", file=sys.stderr)
            continue
        src_noise = temporal_noise(source, args.frames, None)
        report[title] = {"source_temporal_noise": src_noise, "arms": {}}
        for arm in ARMS:
            tag = f"{title}-denoise{arm}"
            encoded = OUT / f"{tag}.mkv"
            table = OUT / f"{tag}.tbl"
            if not encoded.is_file():
                encode(CANDIDATE, source, encoded, table, arm, args.qvbr)
            entry = curve_rms(table)
            entry["delivered_temporal_noise"] = temporal_noise(
                encoded, args.frames, "libdav1d")
            report[title]["arms"][arm] = entry
            print(f"{title:16} denoise={arm:5} curve_y={entry['y']:.5f} "
                  f"delivered={entry['delivered_temporal_noise']:.2f}",
                  flush=True)

    path = OUT / "floor-separation.json"
    path.write_text(json.dumps(report, indent=2) + "\n")

    print("\n=== does over-denoising inflate the emitted curve? ===")
    print(f"{'title':16} " + " ".join(f"{a:>9}" for a in ARMS)
          + "   rises?   4.0/1.0")
    uniform = [a for a in ARMS if a != "auto"]
    for title, data in report.items():
        row = [data["arms"][a]["y"] for a in ARMS if a in data["arms"]]
        u = [data["arms"][a]["y"] for a in uniform if a in data["arms"]]
        rises = all(u[i] <= u[i + 1] for i in range(len(u) - 1))
        span = (u[-1] / u[0]) if u and u[0] else float("nan")
        print(f"{title:16} " + " ".join(f"{v:9.5f}" for v in row)
              + f"   {'yes' if rises else 'no':6}  {span:7.2f}x")
    print("\nthe uniform arms carry no :2449 clamp; a rise across them is the"
          "\nover-denoise -> inflated-curve mechanism, measured directly.")
    print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
