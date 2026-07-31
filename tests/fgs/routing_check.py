#!/usr/bin/env python3
"""Is heavy 35mm grain still better served by a plain tuned encode?

FINDINGS-2026-07-17 concluded that the coarsest stock is "the worst case for
this feature, not the best, and is better served by a plain tuned encode".
FINDINGS-2026-07-29 already superseded that for Taxi Driver after the
fixed-lattice correction, but only on one title and only on synthesis
amplitude. This runs the matched-rate routing question across the whole
real-film corpus.

For each clip: one plain tuned encode and one FGS encode at the same VBR
target, scored against the lossless source, plus grain energy and grain
structure. Optionally a third arm with an extra --av1-film-grain sub-option
(e.g. psd=on) to A/B an analyzer change on real film.

Read bytes, quality and grain retention together. Full-reference metrics are
structurally biased against synthesis because synthesized grain is a new random
realization, so a plain encode "winning" VMAF is not by itself a routing
argument -- see the header of matched_rate_sweep.py.

Usage:
  python3 tests/fgs/routing_check.py --clips clip_A.mkv,clip_B.mkv \
      [--rate 31700] [--frames 288] [--denoiser bilateral] [--extra psd=on]
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from campaign import NVENCC, COLOR, TUNED, run, score, hf_sigma
from matched_rate_sweep import grain_structure


def encode(clip, out, rate, fg):
    """Same arms as matched_rate_sweep.encode, but software-decoded.

    The preserved masters are lossless FFV1, which NVDEC cannot decode, so
    --avhw fails outright ("codec ffv1(yuv420p10le) unable to decode by
    cuvid"). Software decode is also the deterministic path for a fixed
    fixture, so nothing is lost by it here.
    """
    if os.path.exists(out):
        return out
    cmd = [NVENCC, "--avsw", "--codec", "av1", "--output-depth", "10",
           "--vbr", str(rate), "--max-bitrate", str(rate * 2), *TUNED, *COLOR]
    if fg:
        cmd += ["--av1-film-grain", fg]
    cmd += ["-i", clip, "-o", out]
    print(f"[encode] {os.path.basename(out)}", flush=True)
    run(cmd, timeout=3600)
    return out


def ffvhuff_ref(clip, frames):
    """Lossless reference for scoring; FFMS2 decodes ffv1 slowly."""
    ref = os.path.splitext(clip)[0] + f"-ref{frames}.mkv"
    if not os.path.exists(ref):
        print(f"[ref] {os.path.basename(ref)}", flush=True)
        run(["ffmpeg", "-v", "error", "-y", "-i", clip, "-frames:v", str(frames),
             "-map", "0:v:0", "-an", "-c:v", "ffvhuff", ref], timeout=3600)
    return ref


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", required=True, help="comma-separated source clips")
    ap.add_argument("--rate", type=int, default=31700, help="VBR kbps for every arm")
    ap.add_argument("--frames", type=int, default=288)
    ap.add_argument("--denoiser", default="bilateral", help="production default is bilateral")
    ap.add_argument("--extra", default="", help="extra --av1-film-grain sub-options for a third arm")
    ap.add_argument("--output", default="")
    args = ap.parse_args()

    results = {}
    for clip in args.clips.split(","):
        clip = clip.strip()
        name = os.path.splitext(os.path.basename(clip))[0].replace("clip_", "")
        d = os.path.dirname(os.path.abspath(clip))
        stem = os.path.join(d, "rc-" + name)
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=width,height", "-of", "csv=p=0", clip],
                           capture_output=True, text=True, check=True)
        w, h = (int(x) for x in r.stdout.strip().split(",")[:2])
        ref = ffvhuff_ref(clip, args.frames)

        fg = f"denoise=auto,chroma=auto,denoiser={args.denoiser}"
        arms = [("plain", None), ("fgs", fg)]
        if args.extra:
            arms.append((f"fgs+{args.extra}", f"{fg},{args.extra}"))

        src = {"hf": hf_sigma(clip, w, h), **grain_structure(clip, w, h)}
        print(f"\n=== {name}: source HF {src['hf']} acf {src['acf1']}/{src['acf2']}/{src['acf3']}",
              flush=True)
        row = {"_source": src}
        for tag, opt in arms:
            enc = encode(clip, f"{stem}-{tag.replace('+','_').replace('=','')}.mkv",
                         args.rate, opt)
            e = {"mb": round(os.path.getsize(enc) / 1e6, 1)}
            print(f"[score] {name}/{tag} ({e['mb']}MB)", flush=True)
            e.update(score(ref, enc, f"rc-{name}-{tag}", d, h, args.frames, clip=clip))
            e["hf"] = hf_sigma(enc, w, h, decoder="libdav1d")
            e.update(grain_structure(enc, w, h, decoder="libdav1d"))
            e["retention"] = round(e["hf"] / max(src["hf"], 1e-6), 3)
            row[tag] = e
        results[name] = row

        base = row["plain"]["mb"]
        for tag, _ in arms[1:]:
            d_pct = 100.0 * (row[tag]["mb"] - base) / max(base, 1e-9)
            print(f"  {tag}: {d_pct:+.1f}% bytes vs plain, retention {row[tag]['retention']}",
                  flush=True)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=1)
        print(f"\nwrote {args.output}")


if __name__ == "__main__":
    main()
