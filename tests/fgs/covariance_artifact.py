#!/usr/bin/env python3
"""Does covariance closure discount codec artifact?  Protocol: PLAN-2026-08-05.

`FINDINGS-2026-08-05-NEGATIVE-SPECIMEN.md` observed that the candidate
sometimes reconstructs an original's grain character from a recompressed source
that no longer contains it, and offered one untested explanation: the guarded
covariance response subtracts the encoded base's covariance from the AR fit,
and codec artifact lives largely in that base.

This varies only the closure strength and watches which reference the
synthesised texture moves toward.

    O   lossless clip from a 1080p AVC remux            (ground truth grain)
    C   x264 encode of O at a WEB-DL-like rate           (real-codec artifact)
    A0  modelsrc + source-static                         (no covariance closure)
    A1  + texture-leak=response                          (guarded, candidate)
    A2  + texture-leak=dynamic                           (full subtraction)

The previous run recompressed to AV1 and encoded AV1 again; that path does not
occur in production, where inputs are H.264/HEVC and AV1 is only the output.
x264 is therefore the artifact source here.

One report per (title, rate) with ``--source O`` and arms ``C, A0, A1, A2``, so
every layer sits on a single O-derived mask: ``truth`` is O's real grain and
C's ``total`` layer is the artifact.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import math  # noqa: E402

from negative_specimen import (  # noqa: E402
    CANDIDATE, FFMPEG, arm, axis_distance, decode_check, encode, frame_count,
    grain_report, run, truth_axis,
)
from temporal_grain_report import (  # noqa: E402
    average_acf, decode_selected, probe_size,
)
from source_fit import (  # noqa: E402
    field_acf, production_flat_blocks, static_flat_blocks,
)

WORK = "/tmp/downloads/fgs-covariance-20260805"
FRAMES = "10,58,106,154,202,250"
RATES = (5000, 2000)          # kbit/s, frozen: WEB-DL-like and harsh
TITLES = ("Train_to_Busan", "Tuner", "Quiz_Show")
FGS_OPTS = "denoise=auto,chroma=auto,denoiser=bilateral,modelsrc=on"

# The CUDA/dav1d ffmpeg build used for decoding carries no libx264, so C is
# produced by the system build.  Measurement still runs through FFMPEG.
X264_FFMPEG = os.environ.get("FGS_X264_FFMPEG", "/usr/bin/ffmpeg")

ARMS = {
    "A0_sourcefit": {"NVENC_FGS_TEST_SOURCE_STATIC": "on"},
    "A1_response": {"NVENC_FGS_TEST_SOURCE_STATIC": "on",
                    "NVENC_FGS_TEST_TEXTURE_LEAK": "response"},
    "A2_dynamic": {"NVENC_FGS_TEST_SOURCE_STATIC": "on",
                   "NVENC_FGS_TEST_TEXTURE_LEAK": "dynamic"},
}


def make_c(source, out, kbps, log, codec="libx264", depth=8, preset="medium"):
    """Software encode at a fixed bitrate -- the codecs real inputs arrive in.

    1080p sources are delivered as H.264; 4K is HEVC, and its artifact differs
    (larger transforms, SAO), so it must be measured rather than assumed to
    behave like x264.
    """
    if os.path.isfile(out):
        return out
    pix = "yuv420p" if depth == 8 else "yuv420p10le"
    run([X264_FFMPEG, "-hide_banner", "-nostdin", "-v", "error", "-i", source,
         "-map", "0:v:0", "-an", "-sn", "-dn", "-c:v", codec,
         "-preset", preset, "-b:v", f"{kbps}k", "-pix_fmt", pix,
         "-y", out], log=log)
    return out


def artifact_axis(source, recompressed, frames=FRAMES, bits=8):
    """C's own temporal texture, on the same O-derived mask the report uses.

    ``temporal_grain_report`` forces ``-c:v libdav1d`` for arms, so an H.264 C
    cannot be passed as one.  ``decode_selected`` only selects that decoder
    when ``filmgrain`` is set, so C decodes normally here, and the mask and
    field arithmetic below mirror the tool exactly: production flat blocks from
    the source, the 0.8..1.3 static subset, then (n - n+1)/sqrt(2).
    """
    width, height = probe_size(source)
    if probe_size(recompressed) != (width, height):
        raise RuntimeError("C dimensions do not match O")
    indices = sorted({f for frame in [int(v) for v in frames.split(",")]
                      for f in (frame, frame + 1)})
    src = decode_selected(source, width, height, indices, bits=bits)
    dist = decode_selected(recompressed, width, height, indices, bits=bits)
    rows = []
    for frame in [int(v) for v in frames.split(",")]:
        candidates, _, _ = production_flat_blocks(src[frame], bits)
        static = static_flat_blocks(src[frame], src[frame + 1], candidates,
                                    lo=0.8, hi=1.3)
        if len(static) < 8:
            continue
        rows.append(field_acf(
            (dist[frame] - dist[frame + 1]) / math.sqrt(2.0),
            static, detrend=False, bs=32))
    return average_acf(rows) if rows else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", default=WORK)
    parser.add_argument("--titles", default="")
    parser.add_argument("--rates", default="")
    parser.add_argument("--codec", default="libx264")
    parser.add_argument("--depth", type=int, default=8)
    parser.add_argument("--preset", default="medium")
    parser.add_argument("--suffix", default="")
    args = parser.parse_args()

    titles = args.titles.split(",") if args.titles else list(TITLES)
    rates = [int(r) for r in args.rates.split(",")] if args.rates else list(RATES)
    rows = []

    for title in titles:
        source = os.path.join(args.work, f"{title}-O.mkv")
        if not os.path.isfile(source):
            print(f"MISSING {source}", flush=True)
            continue
        for kbps in rates:
            tag = f"{title}-{kbps}k{args.suffix}"
            d = os.path.join(args.work, tag)
            os.makedirs(d, exist_ok=True)

            recompressed = make_c(source, f"{d}/C.mp4", kbps, f"{d}/C.log",
                                  codec=args.codec, depth=args.depth,
                                  preset=args.preset)
            arms = [("C_x264", recompressed)]
            plain = encode(CANDIDATE, recompressed, f"{d}/A_plain.mkv", 29,
                           args.depth, log=f"{d}/A_plain.log")
            decode_check(plain, log=f"{d}/A_plain-dav1d.log")
            arms.append(("A_plain", plain))
            for label, env in ARMS.items():
                out = encode(CANDIDATE, recompressed, f"{d}/{label}.mkv", 29,
                             args.depth, fgs=FGS_OPTS, env=env,
                             log=f"{d}/{label}.log")
                decode_check(out, log=f"{d}/{label}-dav1d.log")
                arms.append((label, out))

            counts = {label: frame_count(path) for label, path in arms[1:]}
            if len(set(counts.values())) != 1:
                raise RuntimeError(f"{tag}: frame counts differ {counts}")

            report = grain_report(source, arms[1:], f"{d}/report-plain.json",
                                  args.depth, frames=FRAMES)
            o_axis = truth_axis(report)
            c_axis = artifact_axis(source, recompressed, bits=args.depth)

            row = {"title": title, "rate_kbps": kbps, "reference": "O",
                   "o_grain_axis": o_axis, "c_artifact_axis": c_axis,
                   "c_bytes": os.path.getsize(recompressed), "arms": {}}
            row["plain"] = {
                "total_amp": arm(report, "A_plain")["total"]["amplitude_ratio"]["mean"],
                "total_axis_error_to_O":
                    arm(report, "A_plain")["total_axis_error_to_truth"]["mean"],
                "bytes": os.path.getsize(f"{d}/A_plain.mkv"),
            }
            for label in ARMS:
                synth = arm(report, label)["synth"]["axis"]
                row["arms"][label] = {
                    "synth_axis": synth,
                    "synth_to_o": axis_distance(synth, o_axis),
                    "synth_to_c": axis_distance(synth, c_axis),
                    "synth_amp": arm(report, label)["synth"]["amplitude_ratio"]["mean"],
                    "total_amp": arm(report, label)["total"]["amplitude_ratio"]["mean"],
                    "total_axis_error_to_O":
                        arm(report, label)["total_axis_error_to_truth"]["mean"],
                    "bytes": os.path.getsize(f"{d}/{label}.mkv"),
                }
            rows.append(row)
            print(json.dumps(row), flush=True)
            with open(os.path.join(args.work,
                                   f"covariance-plain{args.suffix}.json"), "w",
                      encoding="utf-8") as handle:
                json.dump(rows, handle, indent=1)

    print(f"\ncells: {len(rows)}", flush=True)


if __name__ == "__main__":
    main()
