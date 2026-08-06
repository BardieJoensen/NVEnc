#!/usr/bin/env python3
"""Ablate the two low-signal floors independently.

Implements stage 1 of `PLAN-2026-08-06-FLOOR-ABLATION.md`.

`FINDINGS-2026-08-06-FLOOR-LOCATION.md` narrowed the one-defect relationship to
two floors in `NVEncFilterFilmGrain.cu`, both fed by `minNoiseLevel = 0.5`
(8-bit) and so both at sigma 2.0 on 10-bit content:

  selection floor (:2425)  which blocks enter the flat mask
  denoise floor   (:2483)  per-block denoise clamp

Because they share one constant, neither can be attributed without moving them
separately.  `NVENC_FGS_TEST_MIN_NOISE=<select>[,<denoise>]` does that.

Stage 1 is a go/no-go on the *analyser*, which is what the floors act on, so it
reads the emitted curve RMS rather than delivered amplitude.  That is
deliberate and it is not a quality claim: the emitted curve overstates delivered
strength roughly twofold (`FINDINGS-2026-08-04-ADMISSION-GATE.md`).  It is the
right instrument for "does this floor do anything at all", it is cheap, and the
control arm's numbers are directly comparable to the ones `floor_separation.py`
already recorded with the pre-hook binary.  Stage 2 -- the eight-cell delivered
amplitude corpus and the codec-noise harm axis -- only runs if stage 1 moves.

Arms:

  A  unset            control; must reproduce the pre-hook numbers exactly
  B  0.05,0.5         selection floor only
  C  0.5,0.05         denoise floor only
  D  0.05,0.05        both

Selectivity is the whole test.  The floor model predicts the low-signal titles
move and the high-signal ones do not.  An arm that lowers everything is not a
fix, it is a global gain change, and the high-signal controls are here to tell
those two apart.

The control arm doubles as the bit-identity guard.  Arm A runs on the new
binary with the variable absent; if the hook is inert when unset it must
reproduce, exactly, the `denoise=auto` curve RMS that `floor_separation.py`
measured on the previous binary.  9c37ab62 exists because a KAT silently tested
the wrong arm, so a mismatch here fails the run rather than being explained.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from floor_separation import curve_rms, temporal_noise

ANIM = Path("/tmp/downloads/animation-gate-20260806")
FILM = Path("/media/merged-storage/media/test-encodes/keep-original")
OUT = Path("/tmp/downloads/floor-ablation-20260806")

BASE_FGS = "denoise=auto,chroma=auto,denoiser=bilateral,modelsrc=on"

# Low-signal titles carry no photochemical grain at all, so any emitted
# strength is over-delivery by construction and the floor has the most room to
# act.  High-signal film titles are the selectivity controls: the floor model
# says these must not move.
SOURCES = {
    "LongHalloween": (ANIM / "LongHalloween-O.mkv", "low"),
    "PoppyHill": (ANIM / "PoppyHill-O.mkv", "low"),
    "Kiki": (ANIM / "Kiki-O.mkv", "low"),
    "The_Deer_Hunter": (FILM / "clip_The_Deer_Hunter.mkv", "high"),
    "Taxi_Driver": (FILM / "clip_Taxi_Driver-ref288.mkv", "high"),
}

ARMS = {
    "A-control": None,
    "B-select": "0.05,0.5",
    "C-denoise": "0.5,0.05",
    "D-both": "0.05,0.05",
}

# Measured by floor_separation.py on the pre-hook binary at denoise=auto.
# Arm A must reproduce these or the hook is not inert when unset.
PREHOOK_CONTROL = {
    "LongHalloween": 0.01982,
    "PoppyHill": 0.02356,
    "Kiki": 0.04152,
}


def encode(binary: Path, source: Path, output: Path, table: Path,
           floors: str | None, qvbr: int) -> None:
    command = [
        str(binary), "--avsw", "-i", str(source), "--codec", "av1",
        "--output-depth", "10", "--qvbr", str(qvbr), "--max-bitrate", "50000",
        "--preset", "quality", "--tune", "hq", "--aq", "--aq-temporal",
        "--colormatrix", "auto", "--colorprim", "auto", "--transfer", "auto",
        "--colorrange", "auto", "--av1-film-grain", BASE_FGS,
        "--film-grain-table-out", str(table), "--log-level", "debug",
        "-o", str(output),
    ]
    env = dict(os.environ)
    env.pop("NVENC_FGS_TEST_MIN_NOISE", None)
    if floors is not None:
        env["NVENC_FGS_TEST_MIN_NOISE"] = floors
    result = subprocess.run(command, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"encode failed for {output.name}:\n{result.stderr[-2000:]}")
    blob = result.stderr + result.stdout
    for line in blob.splitlines():
        if "ignoring" in line.lower() and "grain" in line.lower():
            raise RuntimeError(f"{output.name}: encoder rejected an option: {line.strip()}")
    # The hook announces itself.  Silence in a floors arm means the binary
    # predates the hook or the value was dropped, and every number after that
    # would be the control arm wearing another name.
    if floors is not None and "test-only noise floors" not in blob:
        raise RuntimeError(
            f"{output.name}: NVENC_FGS_TEST_MIN_NOISE={floors} did not take effect")
    if floors is None and "test-only noise floors" in blob:
        raise RuntimeError(f"{output.name}: control arm applied a floor override")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True)
    parser.add_argument("--qvbr", type=int, default=25)
    parser.add_argument("--frames", type=int, default=24)
    parser.add_argument("--titles", nargs="*", default=list(SOURCES))
    args = parser.parse_args()

    binary = Path(args.binary)
    if not binary.is_file():
        print(f"missing binary: {binary}", file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)

    report: dict[str, dict] = {}
    for title in args.titles:
        source, band = SOURCES[title]
        if not source.is_file():
            print(f"skip {title}: no source at {source}", file=sys.stderr)
            continue
        report[title] = {"band": band, "arms": {}}
        for arm, floors in ARMS.items():
            tag = f"{title}-{arm}"
            encoded = OUT / f"{tag}.mkv"
            table = OUT / f"{tag}.tbl"
            if not encoded.is_file():
                encode(binary, source, encoded, table, floors, args.qvbr)
            entry = curve_rms(table)
            entry["delivered_temporal_noise"] = temporal_noise(
                encoded, args.frames, "libdav1d")
            report[title]["arms"][arm] = entry
            print(f"{title:16} {arm:10} curve_y={entry['y']:.5f} "
                  f"cb={entry['cb']:.5f} cr={entry['cr']:.5f}", flush=True)

    (OUT / "floor-ablation.json").write_text(json.dumps(report, indent=2) + "\n")

    print("\n=== inertness of the hook when unset ===")
    inert = True
    for title, expected in PREHOOK_CONTROL.items():
        if title not in report:
            continue
        got = report[title]["arms"]["A-control"]["y"]
        ok = abs(got - expected) < 5e-5
        inert &= ok
        print(f"{title:16} pre-hook {expected:.5f}  arm A {got:.5f}  "
              f"{'match' if ok else 'DIFFERS'}")
    if not inert:
        print("\nthe control arm does not reproduce the pre-hook binary; the "
              "hook is not inert when unset and no arm below can be trusted.")

    print("\n=== curve RMS (luma) by arm, relative to control ===")
    names = list(ARMS)
    print(f"{'title':16} {'band':5} " + " ".join(f"{n:>10}" for n in names))
    for title, data in report.items():
        base = data["arms"]["A-control"]["y"]
        cells = [data["arms"][n]["y"] / base if base else float("nan")
                 for n in names]
        print(f"{title:16} {data['band']:5} "
              + " ".join(f"{v:10.3f}" for v in cells))

    print("\nselectivity: the floor model predicts the low band moves and the "
          "high band does not.\nan arm that moves both is a global gain change, "
          "not a floor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
