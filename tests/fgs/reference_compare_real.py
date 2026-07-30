#!/usr/bin/env python3
"""libaom oracle check on REAL film, as a pass/fail regression guard.

WHY THIS EXISTS ALONGSIDE reference_compare.py
`reference_compare.py` already runs libaom as an oracle, and it is the right
design -- but it runs on synthetic fixtures, and that is exactly the gap the
2026-07-29 sampling-aliasing bug walked through. A fixed 8x8 sampling lattice
inflated the fitted AR gain about 2x, halving signalled grain strength. All 17
GPU known-answer fixtures passed, because synthetic fine grain does not alias
against a regular lattice: you need real photochemical grain whose spatial scale
beats against the lattice pitch. Only film exposed it, and only by accident.

So this is the same oracle comparison pointed at real clips, with a tolerance,
so the next bias of that kind fails a check instead of shipping.

WHY AN ORACLE AND NOT A SELF-CONSISTENCY TEST
The bug was invisible to every self-referential signal. Encoded files got
SMALLER, VMAF and SSIMULACRA2 got BETTER (they are full-reference and score
synthesised grain as error), CAMBI stayed clean, and the AR coefficient *shape*
still looked plausible -- only the gain was wrong. Comparing NVEncC against
NVEncC cannot detect a shared bias. libaom fitting the same (noisy, clean) pair
can, and did: AR gain 2.02 oracle vs 4.25 fixed lattice vs 2.04 staggered.

WHAT IT ASSERTS
For each clip, libaom's noise_model is fitted to the SAME pair NVEncC used --
the original frames and NVEncC's own emitted clean base -- so the comparison
isolates model FITTING and does not confound it with separation differences.
The guarded quantity is the luma scaling-curve RMS ratio, NVEncC over libaom,
because signalled strength is what the bug corrupted. 1.0 is agreement; the
shipped bug would read near 0.5.

That ratio MUST be weighted by the source's luma occupancy. `filmgrn._curve`
expands the scaling points to all 256 luma levels and `_rms` averages them
equally, so on a dark film most of the curve is scored at brightness levels the
film barely contains. Unweighted, Taxi Driver reads 0.814 against libaom while
Silo reads 1.047 -- which invites the conclusion that coarse grain is still
under-signalled. It is not: Taxi's AR coefficient shape matches libaom at 0.9995
cosine similarity and its decoded grain sigma is within -6.6%..+3.3%. The 0.814
was empty luma bins, not a deficit. Both numbers are printed so the artifact
stays visible, but the pass/fail guard uses the weighted one.

The AR cosine similarity is reported alongside because it answers the
complementary question -- whether the model's texture SHAPE is right, independent
of its amplitude -- and it is the signal that showed the raw ratio was misleading.

CLIP SELECTION IS THE POINT
At least one clip must be COARSE film grain. A suite of fine-grain clips
reproduces the blind spot this check exists to close. The defaults pair a coarse
35mm case (Taxi Driver, lag-one correlation 0.82) with a fine digital one
(Silo, 0.40-0.51) so both ends of the kernel-adaptation range are covered.

Clips live outside the repo -- they are copyrighted source -- so paths are
arguments. Nothing here ships film.
"""
import argparse, json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import filmgrn                                                  # noqa: E402
import reference_compare as rc                                  # noqa: E402
import texture_metrics                                           # noqa: E402

# NVEncC over libaom on the luma scaling-curve RMS. Sol's corrected build lands
# within -6.6%..+3.3% on decoded sigma; this is deliberately looser so it is a
# bias detector rather than a flaky exact-match, while still failing hard on the
# ~2x class of error that actually shipped.
MIN_RATIO, MAX_RATIO = 0.80, 1.25

DEFAULT_CLIPS = [
    # label,      path,                                                          expect
    ("taxi_coarse", "/media/merged-storage/media/test-encodes/keep-original/ms_Taxi_Driver_20.mkv", "coarse"),
    ("silo_fine",   "/media/merged-storage/media/test-encodes/silo-retest/clip_S03E01.mkv",         "fine"),
]


def sh(argv, **kw):
    return subprocess.run(argv, capture_output=True, text=True, **kw)


def probe(path, entries, stream="v:0"):
    a = ["ffprobe", "-v", "error"] + (["-select_streams", stream] if stream else [])
    return sh(a + ["-show_entries", entries, "-of", "default=nw=1:nk=1", path]).stdout.strip().split("\n")


def luma_occupancy(src, frames):
    """256-bin normalised luma histogram of the source.

    The scaling curve is indexed 0-255, so 10-bit samples are folded down to
    the same domain. Weighting by this makes the curve comparison reflect the
    brightnesses the film actually uses.
    """
    import numpy as np
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", src, "-vframes", str(frames),
         "-pix_fmt", "gray", "-f", "rawvideo", "-"],
        capture_output=True, timeout=3600)
    if r.returncode or not r.stdout:
        return None
    a = np.frombuffer(r.stdout, dtype=np.uint8)
    hist = np.bincount(a, minlength=256).astype(np.float64)
    total = hist.sum()
    return (hist / total) if total else None


def weighted_rms(values, weights):
    import numpy as np
    v = np.asarray(values, dtype=np.float64)
    if weights is None:
        return float(np.sqrt((v * v).mean()))
    w = np.asarray(weights, dtype=np.float64)
    wsum = w.sum()
    if wsum <= 0:
        return float(np.sqrt((v * v).mean()))
    return float(np.sqrt((w * v * v).sum() / wsum))


def curve_ratio(cand, ref, weights):
    """Occupancy-weighted candidate/reference RMS of the luma scaling curve.

    Replicates filmgrn._curve_comparison's shift normalisation rather than
    reaching into it, so filmgrn stays untouched.
    """
    cc = filmgrn._curve(cand["scaling_points"]["y"])
    rc = filmgrn._curve(ref["scaling_points"]["y"])
    cs = cand["params"]["scaling_shift"] + cand["params"]["grain_scale_shift"]
    rs = ref["params"]["scaling_shift"] + ref["params"]["grain_scale_shift"]
    cc = [v / (1 << cs) for v in cc]
    rc = [v / (1 << rs) for v in rc]
    ref_w = weighted_rms(rc, weights)
    return (weighted_rms(cc, weights) / ref_w) if ref_w else None


def to_y4m(src, dst, frames):
    """10-bit y4m. -strict -1 is required: high-bit-depth y4m is non-standard."""
    return sh(["ffmpeg", "-v", "error", "-y", "-i", src, "-map", "0:v:0",
               "-vframes", str(frames), "-pix_fmt", "yuv420p10le",
               "-strict", "-1", "-f", "yuv4mpegpipe", dst], timeout=3600)


def synthesize_table(nvencc, clean, table, prefix, bits, frames):
    """Apply one table to the common clean input and decode grain on/off."""
    encoded = prefix + ".mkv"
    grain_on = prefix + "-on.raw"
    grain_off = prefix + "-off.raw"
    argv = [
        nvencc, "--codec", "av1", "--cqp", "20",
        "--film-grain-table", table,
    ]
    if bits > 8:
        argv.extend(["--output-depth", str(bits)])
    argv.extend(["-i", clean, "-o", encoded])
    commands = {"encode": rc.run(argv)}
    pixel_format = "yuv420p" if bits == 8 else "yuv420p10le"
    for enabled, output, name in (
            (1, grain_on, "decode_on"), (0, grain_off, "decode_off")):
        commands[name] = rc.run([
            "ffmpeg", "-v", "error", "-y", "-c:v", "libdav1d",
            "-filmgrain", str(enabled), "-i", encoded,
            "-frames:v", str(frames), "-pix_fmt", pixel_format,
            "-f", "rawvideo", output,
        ])
    return {
        "encoded": encoded,
        "grain_on": grain_on,
        "grain_off": grain_off,
        "grain_off_sha256": rc.sha256(grain_off),
        "encoded_bytes": os.path.getsize(encoded),
        "commands": commands,
    }


def check_clip(label, path, expect, nvencc, aom, frames, work, denoiser,
               measure_texture=False, keep_texture_media=False):
    if not os.path.exists(path):
        return {"label": label, "status": "SKIP", "reason": "clip missing"}
    wh = probe(path, "stream=width,height")
    if len(wh) < 2 or not wh[0].isdigit():
        return {"label": label, "status": "SKIP", "reason": "cannot probe geometry"}
    w, h = int(wh[0]), int(wh[1])
    bits = 10

    src_y4m = os.path.join(work, f"{label}_src.y4m")
    clean   = os.path.join(work, f"{label}_clean.y4m")
    nv_tbl  = os.path.join(work, f"{label}_nvenc.tbl")
    aom_tbl = os.path.join(work, f"{label}_aom.tbl")
    src_raw = os.path.join(work, f"{label}_src.raw")
    cln_raw = os.path.join(work, f"{label}_clean.raw")

    if to_y4m(path, src_y4m, frames).returncode:
        return {"label": label, "status": "SKIP", "reason": "y4m conversion failed"}

    # NVEncC emits its clean base and its fitted table together
    try:
        _, nv_entries = rc.run_nvenc(nvencc, src_y4m, clean, nv_tbl, bits, denoiser)
    except Exception as e:
        return {"label": label, "status": "FAIL", "reason": f"nvencc: {e}"}
    if not nv_entries:
        return {"label": label, "status": "FAIL", "reason": "nvencc emitted no grain table"}

    # libaom fits the SAME pair, so this isolates fitting rather than separation
    rc.convert_y4m_to_raw(src_y4m, src_raw, bits)
    rc.convert_y4m_to_raw(clean, cln_raw, bits)
    try:
        _, aom_entries = rc.run_aom(aom, src_raw, cln_raw, aom_tbl, w, h, bits)
    except Exception as e:
        return {"label": label, "status": "FAIL", "reason": f"libaom: {e}"}

    nv_rep = filmgrn.representative(nv_entries)
    aom_rep = filmgrn.representative(aom_entries)
    cmp_ = filmgrn.compare(nv_rep, aom_rep)
    y = cmp_.get("scaling", {}).get("y") or {}
    raw_ratio = y.get("rms_ratio")
    cosine = (cmp_.get("coefficients", {}).get("y") or {}).get("cosine")
    weights = luma_occupancy(src_y4m, frames)
    ratio = curve_ratio(nv_rep, aom_rep, weights) if (nv_rep and aom_rep) else None
    if ratio is None:
        return {"label": label, "status": "FAIL", "reason": "no luma curve to compare"}
    ok = MIN_RATIO <= ratio <= MAX_RATIO
    result = {
        "label": label,
        "expect": expect,
        "status": "PASS" if ok else "FAIL",
        "rms_ratio": round(ratio, 4),
        "rms_ratio_unweighted": round(raw_ratio, 4) if raw_ratio else None,
        "ar_cosine": round(cosine, 5) if cosine else None,
        "relative_rmse": round(y.get("relative_rmse") or 0, 4),
    }
    texture_media = []
    if measure_texture:
        try:
            nv_synthesis = synthesize_table(
                nvencc, clean, nv_tbl,
                os.path.join(work, f"{label}_texture_nvenc"),
                bits, frames)
            aom_synthesis = synthesize_table(
                nvencc, clean, aom_tbl,
                os.path.join(work, f"{label}_texture_libaom"),
                bits, frames)
            texture_media.extend([
                nv_synthesis["encoded"], nv_synthesis["grain_on"],
                nv_synthesis["grain_off"], aom_synthesis["encoded"],
                aom_synthesis["grain_on"], aom_synthesis["grain_off"],
            ])
            same_base = (
                nv_synthesis["grain_off_sha256"]
                == aom_synthesis["grain_off_sha256"])
            texture = texture_metrics.analyze_raw_texture(
                src_raw, cln_raw,
                {
                    "nvenc": (
                        nv_synthesis["grain_on"],
                        nv_synthesis["grain_off"]),
                    "libaom": (
                        aom_synthesis["grain_on"],
                        aom_synthesis["grain_off"]),
                },
                w, h, bits, frame_count=frames)
            texture["common_synthesis_base"] = {
                "identical": same_base,
                "nvenc_grain_off_sha256": (
                    nv_synthesis["grain_off_sha256"]),
                "libaom_grain_off_sha256": (
                    aom_synthesis["grain_off_sha256"]),
            }
            texture["synthesis"] = {
                "nvenc": {
                    "encoded_bytes": nv_synthesis["encoded_bytes"],
                    "commands": nv_synthesis["commands"],
                },
                "libaom": {
                    "encoded_bytes": aom_synthesis["encoded_bytes"],
                    "commands": aom_synthesis["commands"],
                },
            }
            result["texture"] = texture
            result["texture_status"] = (
                "MEASURED" if same_base else "INVALID")
            if not same_base:
                result["status"] = "FAIL"
                result["texture_reason"] = (
                    "NVEnc and libaom arms did not decode to a common "
                    "grain-off base")
        except Exception as error:
            result["status"] = "FAIL"
            result["texture_status"] = "FAIL"
            result["texture_reason"] = str(error)
    cleanup = (
        [] if keep_texture_media
        else [src_y4m, clean, src_raw, cln_raw, *texture_media])
    for cleanup_path in cleanup:
        if os.path.exists(cleanup_path):
            os.remove(cleanup_path)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nvencc", required=True)
    ap.add_argument("--aom-noise-model", required=True,
                    help="libaom examples/noise_model, see build_aom_reference.sh")
    ap.add_argument("--clip", action="append", metavar="LABEL=PATH",
                    help="override the defaults; repeatable")
    ap.add_argument("--frames", type=int, default=24)
    ap.add_argument("--denoiser", default="bilateral")
    ap.add_argument("--work", default=None)
    ap.add_argument("--json-out", default=None)
    ap.add_argument(
        "--texture", action="store_true",
        help="synthesize NVEnc and libaom tables on the same clean base and "
             "emit per-luma texture descriptors")
    ap.add_argument(
        "--keep-texture-media", action="store_true",
        help="keep source, clean, encoded, and grain-on/off intermediates")
    args = ap.parse_args()

    clips = DEFAULT_CLIPS
    if args.clip:
        clips = []
        for spec in args.clip:
            label, _, path = spec.partition("=")
            clips.append((label, path, "unspecified"))

    work = args.work or tempfile.mkdtemp(prefix="fgsoracle-")
    os.makedirs(work, exist_ok=True)
    print(f"nvencc : {sh([args.nvencc, '--version']).stdout.splitlines()[0]}")
    print(f"oracle : {args.aom_noise_model}")
    print(f"guard  : luma scaling RMS ratio in [{MIN_RATIO}, {MAX_RATIO}]\n")
    print(f"{'clip':<14}{'grain':<12}{'weighted':>10}{'raw':>8}{'AR cos':>9}  status")

    results, failed, coarse_seen = [], 0, False
    for label, path, expect in clips:
        r = check_clip(label, path, expect, args.nvencc, args.aom_noise_model,
                       args.frames, work, args.denoiser,
                       args.texture, args.keep_texture_media)
        results.append(r)
        if r["status"] == "FAIL":
            failed += 1
        if r.get("expect") == "coarse" and r["status"] == "PASS":
            coarse_seen = True
        if r["status"] in ("SKIP",):
            print(f"{label:<14}{expect:<12}{'':>10}{'':>8}{'':>9}  SKIP ({r['reason']})")
        elif "rms_ratio" in r:
            print(f"{label:<14}{expect:<12}{r['rms_ratio']:>10.3f}"
                  f"{(r['rms_ratio_unweighted'] or 0):>8.3f}"
                  f"{(r['ar_cosine'] or 0):>9.4f}  {r['status']}")
            if "texture" in r:
                def metric(value):
                    return "n/a" if value is None else f"{value:.4f}"
                for arm in ("nvenc", "libaom"):
                    summary = r["texture"]["comparisons"][
                        f"{arm}_vs_source"]["core"]["occupancy_weighted"]
                    print(
                        f"  texture {arm:<7} "
                        f"spectrum-TV={metric(summary['spectrum_total_variation'])} "
                        f"ACF-RMSE={metric(summary['acf_rmse'])}")
                print(
                    f"  common synthesis base: "
                    f"{r['texture']['common_synthesis_base']['identical']}")
        else:
            print(f"{label:<14}{expect:<12}{'':>10}{'':>8}{'':>9}  {r['status']} ({r['reason']})")

    if not coarse_seen:
        # a fine-grain-only pass recreates the blind spot this check closes
        print("\nWARNING: no COARSE clip passed. Aliasing bias is scale-dependent and "
              "fine grain cannot detect it -- this run does not close the gap.")
    if args.json_out:
        json.dump(results, open(args.json_out, "w"), indent=2)
        print(f"\njson: {args.json_out}")
    print(f"\n{len(results)} clip(s), {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
