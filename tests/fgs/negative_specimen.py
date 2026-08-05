#!/usr/bin/env python3
"""Construct a quality-labelled negative for film-grain admission.

`FINDINGS-2026-08-04-SHADOW-ADMISSION.md` closed by observing that no admission
rule can be validated, because every gate has only ever been tested on inputs
where source fitting helps: "Until a known harmful admission exists, this
conjunction cannot be called a validated safety gate."

This builds one with ground truth.  For a retained lossless original ``O``:

    C        = O recompressed at a harsh rate  (grain crushed, artifact added)
    C_plain  = plain encode of C
    C_fgs    = FGS encode of C (bilateral + source-static + guarded response)

``C``'s noise is codec artifact by construction, because ``O`` holds the real
grain and the noise appeared during compression.  The label is built, not
guessed from origin -- the mistake shadow admission had to correct.  ``O`` and
``C`` are also the same frames at the same resolution, so any signal that
separates them cannot be a resolution or genre effect.

The decisive measurement is which reference the synthesised texture resembles:

    harm  if  |synth_axis - C_noise_axis| < |synth_axis - O_grain_axis|

Everything is measured on **one** mask.  ``temporal_grain_report.py`` selects
flat/static blocks from whatever is passed as ``--source``, so the ground-truth
pass passes ``O`` and carries ``C`` itself as an arm; that arm's ``total``
layer is ``C``'s codec noise on exactly the blocks used for ``O``'s grain and
for the synthesis.  A second pass with ``--source C`` reproduces the current
adjudication standard on its own mask for the divergence column.  No aggregate
mixes the two references.

Protocol frozen in ``PLAN-2026-08-05-NEGATIVE-SPECIMEN.md``.  Offline
measurement only: no NVEncCore change, nothing deployed, ``modelsrc``
default-off.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

FFMPEG = os.environ.get("FGS_FFMPEG", "/usr/local/bin/ffmpeg")
AXES = ("h1", "h2", "v1", "v2")

PRODUCTION = os.environ.get("FGS_PRODUCTION_NVENCC",
                            "/opt/docker-apps/build/tdarr-node/nvencc")
CANDIDATE = os.environ.get("FGS_CANDIDATE_NVENCC", os.path.expanduser(
    "~/.cache/fgs-gate/builds/pin-40b987ff-20260804-response-margin/"
    "build-gate-provisioned/nvencc"))

# The guarded response arm needs all of these together.  Commit 9c37ab62 exists
# because a KAT run silently tested the wrong arm when they were not, so run()
# treats an "ignoring" line from the encoder as a hard failure.
CANDIDATE_ENV = {
    "NVENC_FGS_TEST_SOURCE_STATIC": "on",
    "NVENC_FGS_TEST_TEXTURE_LEAK": "response",
}
FGS_OPTS = "denoise=auto,chroma=auto,denoiser=bilateral,modelsrc=on"

FRAMES = "10,58,106,154,202,250"
RATES = (44, 50)          # frozen in the pre-registration after the rate probe
KEEP = "/media/merged-storage/media/test-encodes/keep-original"
GATE = "/media/merged-storage/media/test-encodes/admission-gate-20260804"

TITLES = {
    "Taxi_Driver":    (f"{KEEP}/clip_Taxi_Driver-ref288.mkv", 10),
    "The_Shining":    (f"{KEEP}/clip_The_Shining-ref288.mkv", 10),
    "Tuner":          (f"{GATE}/Tuner-ref.mkv", 8),
    "TrainToBusan":   (f"{GATE}/TrainToBusan-ref.mkv", 8),
}


def run(cmd, env=None, log=None, expect_hooks=False, timeout=14400):
    merged = dict(os.environ)
    if env:
        merged.update(env)
    proc = subprocess.run([str(part) for part in cmd], capture_output=True,
                          text=True, env=merged, timeout=timeout)
    output = proc.stdout + proc.stderr
    if log:
        with open(log, "w", encoding="utf-8") as handle:
            handle.write(output)
    if proc.returncode != 0:
        raise RuntimeError(
            f"failed: {' '.join(str(p) for p in cmd[:8])}\n{output[-3000:]}")
    if expect_hooks and "ignoring" in output:
        raise RuntimeError(
            "a research hook was ignored -- the wrong arm would have been "
            f"measured:\n{output[-2000:]}")
    return output


def decode_check(path, log=None):
    """Complete software decode.  A stream that cannot be played is not data."""
    run([FFMPEG, "-hide_banner", "-nostdin", "-v", "error", "-xerror",
         "-c:v", "libdav1d", "-i", path, "-map", "0:v:0", "-an", "-sn", "-dn",
         "-f", "null", "-"], log=log)


def frame_count(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
         "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", path],
        check=True, capture_output=True, text=True)
    return int(result.stdout.strip().rstrip(",") or 0)


def encode(binary, src, out, qvbr, depth, fgs=None, env=None, log=None):
    if os.path.isfile(out):
        return out
    cmd = [binary, "--avsw", "-i", src, "--codec", "av1",
           "--output-depth", depth, "--qvbr", qvbr,
           "--max-bitrate", 20000, "--preset", "p4", "--tune", "hq"]
    if fgs:
        cmd += ["--av1-film-grain", fgs,
                "--film-grain-table-out", os.path.splitext(out)[0] + ".tbl"]
    cmd += ["-o", out]
    run(cmd, env=env, log=log, expect_hooks=bool(env))
    return out


def grain_report(source, arms, out_json, bits, frames=FRAMES):
    if not os.path.isfile(out_json):
        cmd = [sys.executable, os.path.join(HERE, "temporal_grain_report.py"),
               "--source", source, "--plane", "y", "--bits", bits,
               "--frames", frames, "--flat-selector", "production",
               "--json-out", out_json]
        for label, path in arms:
            cmd += ["--arm", f"{label}={path}"]
        run(cmd, log=out_json + ".log")
    with open(out_json, encoding="utf-8") as handle:
        return json.load(handle)


def axis_distance(left, right):
    """Mean absolute difference across the four texture axes."""
    values = [abs(left[a] - right[a]) for a in AXES
              if left.get(a) is not None and right.get(a) is not None]
    return sum(values) / len(values) if values else None


def truth_axis(report):
    """Source-truth texture.  ``temporal_grain_report`` stores it at top level.

    When ``O`` is the ``--source`` this is O's real grain, measured on the same
    blocks every arm below is measured on.
    """
    return report.get("truth")


def arm(report, label):
    return report["arms"][label]


def verdict(report, fgs_label, recompressed_label, plain_label):
    """The decisive test on the ground-truth mask.

    ``truth`` is O's grain, because O was passed as --source.  The recompressed
    arm's ``total`` layer is C's codec noise on the same blocks.  Both clauses
    of the frozen pass condition are evaluated and reported separately so a
    partial result cannot be presented as a whole one.
    """
    o_axis = truth_axis(report)
    c_axis = arm(report, recompressed_label)["total"]["axis"]
    synth_axis = arm(report, fgs_label)["synth"]["axis"]
    to_o = axis_distance(synth_axis, o_axis)
    to_c = axis_distance(synth_axis, c_axis)

    fgs_total_err = arm(report, fgs_label)["total_axis_error_to_truth"]["mean"]
    plain_total_err = arm(report, plain_label)["total_axis_error_to_truth"]["mean"]
    fgs_amp = arm(report, fgs_label)["total"]["amplitude_ratio"]["mean"]
    plain_amp = arm(report, plain_label)["total"]["amplitude_ratio"]["mean"]

    clause_a = to_c is not None and to_o is not None and to_c < to_o
    # "no closer to O than C_plain is".  Reported as two sub-clauses because
    # texture and amplitude can disagree: adding energy can move played
    # amplitude toward O while the added texture is artifact-shaped.
    clause_b_texture = fgs_total_err >= plain_total_err
    clause_b_amplitude = abs(fgs_amp - 1.0) >= abs(plain_amp - 1.0)
    clause_b = clause_b_texture and clause_b_amplitude
    return {
        "o_grain_axis": o_axis,
        "c_noise_axis": c_axis,
        "fgs_synth_axis": synth_axis,
        "synth_to_o": to_o,
        "synth_to_c": to_c,
        "synth_matches": "codec_noise" if clause_a else "source_grain",
        "fgs_total_amp": fgs_amp,
        "plain_total_amp": plain_amp,
        "fgs_total_axis_error_to_O": fgs_total_err,
        "plain_total_axis_error_to_O": plain_total_err,
        "clause_a_synth_tracks_codec": clause_a,
        "clause_b_texture_not_closer": clause_b_texture,
        "clause_b_amplitude_not_closer": clause_b_amplitude,
        "clause_b_not_closer_to_O": clause_b,
        "valid_negative": clause_a and clause_b,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", default="/media/merged-storage/media/"
                        "test-encodes/negative-specimen-20260805")
    parser.add_argument("--titles", default="")
    parser.add_argument("--rates", default="")
    args = parser.parse_args()

    titles = [t for t in (args.titles.split(",") if args.titles else TITLES)
              if t in TITLES]
    rates = [int(r) for r in args.rates.split(",")] if args.rates else list(RATES)
    os.makedirs(args.work, exist_ok=True)
    rows = []

    for title in titles:
        source, depth = TITLES[title]
        if not os.path.isfile(source):
            print(f"MISSING {source}", flush=True)
            continue
        for rate in rates:
            tag = f"{title}-q{rate}"
            d = os.path.join(args.work, tag)
            os.makedirs(d, exist_ok=True)

            recompressed = encode(PRODUCTION, source, f"{d}/C.mkv", rate, depth,
                                  log=f"{d}/C.log")
            plain = encode(PRODUCTION, recompressed, f"{d}/C_plain.mkv", 29,
                           depth, log=f"{d}/C_plain.log")
            fgs = encode(CANDIDATE, recompressed, f"{d}/C_fgs.mkv", 29, depth,
                         fgs=FGS_OPTS, env=CANDIDATE_ENV, log=f"{d}/C_fgs.log")

            counts = {}
            for name, path in (("C", recompressed), ("C_plain", plain),
                               ("C_fgs", fgs)):
                decode_check(path, log=f"{d}/{name}-dav1d.log")
                counts[name] = frame_count(path)
            if len(set(counts.values())) != 1:
                raise RuntimeError(f"{tag}: frame counts differ {counts}")

            ground = grain_report(
                source, [("C", recompressed), ("C_plain", plain),
                         ("C_fgs", fgs)],
                f"{d}/report-vs-O.json", depth)
            # Secondary, and deliberately non-fatal: at harsh rates C can have
            # no static flat blocks on a frozen frame.  The decisive test is
            # the ground-truth pass above, so record the reason and continue
            # rather than dropping the specimen.
            try:
                current = grain_report(
                    recompressed, [("C_plain", plain), ("C_fgs", fgs)],
                    f"{d}/report-vs-C.json", depth)
            except RuntimeError as exc:
                current = None
                current_error = str(exc).strip().splitlines()[-1]

            row = {"title": title, "rate": rate, "reference": "O",
                   "frames": counts["C"],
                   "bytes": {k: os.path.getsize(v) for k, v in
                             (("C", recompressed), ("C_plain", plain),
                              ("C_fgs", fgs))}}
            row.update(verdict(ground, "C_fgs", "C", "C_plain"))
            row["c_retained_amp"] = \
                arm(ground, "C")["total"]["amplitude_ratio"]["mean"]
            # the current standard, on C's own mask and explicitly labelled
            row["vs_C_reference"] = {
                "fgs_total_amp":
                    arm(current, "C_fgs")["total"]["amplitude_ratio"]["mean"],
                "fgs_total_axis_error":
                    arm(current, "C_fgs")["total_axis_error_to_truth"]["mean"],
                "plain_total_axis_error":
                    arm(current, "C_plain")["total_axis_error_to_truth"]["mean"],
            } if current else {"unavailable": current_error}
            rows.append(row)
            print(json.dumps(row), flush=True)
            with open(os.path.join(args.work, "specimens.json"), "w",
                      encoding="utf-8") as handle:
                json.dump(rows, handle, indent=1)

    tracks = [r for r in rows if r["clause_a_synth_tracks_codec"]]
    valid = [r for r in rows if r["valid_negative"]]
    print(f"\nspecimens {len(rows)}: synthesis tracked codec noise on "
          f"{len(tracks)}/{len(rows)}; both frozen clauses met on "
          f"{len(valid)}/{len(rows)}", flush=True)


if __name__ == "__main__":
    main()
