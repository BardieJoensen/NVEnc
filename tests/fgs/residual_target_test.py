#!/usr/bin/env python3
"""Is the grain model fitted to the wrong thing?

With the production default (`modelFromSource(false)`, NVEncFilterFilmGrain.cu:1730)
the model target is `residual_at(src, denoised)` -- what the denoiser *removed*,
not the source's grain (NVEncFilterFilmGrain.cu:681).  The code comment at
:613-622 already calls this lossy and names the source fit as the correction.

The earlier "denoiser response shape" elimination compared bilateral against
fft3d.  That asks *which* denoiser, and cannot falsify *whether the residual is
the right target at all* -- both denoisers share the target.  So this was never
actually tested.

`modelsrc=on` switches the target to plane-removed source flat blocks.  A first
pass over three weak-to-middling titles moved the delivered slope from +0.726 to
+0.898, but every title over-delivered afterwards, which looks more like a
global gain change than a fix.  Three titles spanning source HF 1.5..6.0 cannot
tell those apart.  This run adds the strong-grain end.

The standard is the one this project already set (measure_rank_gate.py:10-16):

    weak-grain sources    retention should fall toward 1.0
    strong-grain sources  retention should NOT move

Both arms run on the same binary, and the delivered amplitude is the synthesized
component with the base layer's own high-frequency energy removed -- decoded out
of the same bitstream with dav1d synthesis off, so there is no alignment risk
between the two measurements.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from base_floor import CASES, hf_energy
from deployed_verification import aligned
from measure_rank_gate import resolve

BIN = Path("/home/bardie/.cache/fgs-gate/builds/pin-4b611c92-measure-rank/build-gate/nvencc")
OUT = Path("/tmp/downloads/residual-target-20260808")

COMMON = ("--codec av1 --output-depth 10 --max-bitrate 50000 "
          "--preset quality --tune hq --lookahead 32 --lookahead-level 3 "
          "--aq --aq-temporal "
          "--colormatrix auto --colorprim auto --transfer auto --colorrange auto")
FGS_OFF = "denoise=auto,chroma=auto,denoiser=bilateral"
FGS_ON = FGS_OFF + ",modelsrc=on"


def duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nk=1:nw=1", str(path)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def cut(source: Path, ref: Path, seek: float, frames: int) -> None:
    """Lossless cut, with the seek clamped to the source.

    The retained clips under keep-original are only a few seconds long, so the
    corpus-wide seek of 1500s runs off the end of them and yields an empty file
    that still 'succeeds'.  Clamp instead, and verify frames came out.
    """
    if ref.is_file():
        return
    dur = duration(source)
    ss = seek if dur > seek + frames / 24.0 + 1.0 else 0.0
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(ss), "-i", str(source),
                    "-frames:v", str(frames), "-an", "-c:v", "ffvhuff",
                    "-pix_fmt", "yuv420p10le", str(ref)], check=True)
    if not ref.is_file() or ref.stat().st_size == 0:
        raise RuntimeError(f"{ref.name}: cut produced nothing (seek {ss}, duration {dur})")


def encode(ref: Path, out: Path, qvbr: int, modelsrc: bool) -> int:
    if out.is_file():
        return out.stat().st_size
    fgs = FGS_ON if modelsrc else FGS_OFF
    r = subprocess.run([str(BIN), "--avsw", "-i", str(ref), "--av1-film-grain", fgs]
                       + COMMON.split() + ["--qvbr", str(qvbr), "-o", str(out)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{out.name}:\n{r.stderr[-1200:]}")
    blob = r.stderr + r.stdout
    # The flag is silently ignored unless its preconditions hold, and this
    # project has already shipped one KAT that tested the wrong arm.
    if modelsrc and "modelsrc=on" not in blob:
        raise RuntimeError(f"{out.name}: modelsrc did not take effect")
    if not modelsrc and "modelsrc=on" in blob:
        raise RuntimeError(f"{out.name}: control arm enabled modelsrc")
    return out.stat().st_size


def measure(ref: Path, enc: Path, frames: int) -> dict:
    played = hf_energy(enc, frames, filmgrain=True)
    base = hf_energy(enc, frames, filmgrain=False)
    synth = float(np.sqrt(max(0.0, played ** 2 - base ** 2)))
    return {"played": played, "base": base, "synth": synth}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--seek", type=float, default=1500.0)
    p.add_argument("--frames", type=int, default=192)
    args = p.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for cls, name, raw, qvbr in CASES:
        source = resolve(raw)
        if source is None:
            print(f"skip {name}: no source", file=sys.stderr)
            continue
        ref = OUT / f"{name}-ref.mkv"
        try:
            cut(source, ref, args.seek, args.frames)
        except Exception as exc:
            print(f"skip {name}: {exc}", file=sys.stderr)
            continue
        src = hf_energy(ref, args.frames)
        if src <= 0:
            print(f"skip {name}: no measurable source grain", file=sys.stderr)
            continue

        row = {"class": cls, "qvbr": qvbr, "src": src}
        ok = True
        for tag, ms in (("off", False), ("on", True)):
            enc = OUT / f"{name}-{tag}.mkv"
            try:
                size = encode(ref, enc, qvbr, ms)
            except Exception as exc:
                print(f"  {name} {tag}: {exc}", file=sys.stderr)
                ok = False
                break
            good, lag0, lag1 = aligned(ref, enc)
            if not good:
                print(f"  {name} {tag}: MISALIGNED ({lag0:.3f}/{lag1:.3f})", file=sys.stderr)
                ok = False
                break
            m = measure(ref, enc, args.frames)
            m["bytes"] = size
            m["retention"] = m["synth"] / src
            row[tag] = m
        if not ok:
            continue
        print(f"\n### [{cls}] {name} qvbr{qvbr}  src {src:.3f}", flush=True)
        for tag in ("off", "on"):
            m = row[tag]
            print(f"  modelsrc={tag:3} synth {m['synth']:6.3f}  retention {m['retention']:.3f}"
                  f"  {m['bytes']/1e6:7.2f}MB", flush=True)
        rows.append((name, row))
        (OUT / "residual-target.json").write_text(
            json.dumps({n: r for n, r in rows}, indent=2) + "\n")

    if not rows:
        print("no titles measured", file=sys.stderr)
        return 1

    print("\n=== delivered grain / source grain ===")
    print(f"{'title':16} {'class':7} {'src':>7} {'off':>8} {'on':>8} {'change':>9} {'size':>8}")
    for name, r in rows:
        o, n2 = r["off"], r["on"]
        print(f"{name:16} {r['class']:7} {r['src']:7.3f} {o['retention']:8.3f} "
              f"{n2['retention']:8.3f} {n2['retention']-o['retention']:+9.3f} "
              f"{1-n2['bytes']/o['bytes']:+7.1%}")

    weak = [r for _, r in rows if r["class"] == "weak"]
    strong = [r for _, r in rows if r["class"] == "strong"]
    src = np.array([r["src"] for _, r in rows])
    for tag in ("off", "on"):
        got = np.array([r[tag]["synth"] for _, r in rows])
        ret = got / src
        print(f"\n  modelsrc={tag}: slope {np.polyfit(np.log(src), np.log(got), 1)[0]:+.3f}"
              f"   spread {ret.min():.3f}..{ret.max():.3f} ({ret.max()-ret.min():.3f})"
              f"   mean |ret-1| {np.abs(ret-1).mean():.3f}")
    if weak and strong:
        dw = sum(r["on"]["retention"] - r["off"]["retention"] for r in weak) / len(weak)
        ds = sum(r["on"]["retention"] - r["off"]["retention"] for r in strong) / len(strong)
        print(f"\n  mean change   weak {dw:+.3f}   strong {ds:+.3f}")
        print("  a fix moves weak toward 1.0 and leaves strong alone;")
        print("  both moving the same way is a global gain change, not a fix.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
