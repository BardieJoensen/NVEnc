#!/usr/bin/env python3
"""Multi-title FGS evaluation campaign.

For each title: extracts a clip, encodes the configured pipeline variants,
builds a clean lossless (ffvhuff) reference from the decoded base layer
because FFMS2 cannot read DV dual-layer HEVC, and scores VMAF/VMAF-NEG +
CIEDE2000 + PSNR/SSIM with the user's CUDA libvmaf feature extractors,
SSIMULACRA2 and Butteraugli with FFVship/CUDA, and grain-retention HF sigma.
The FFVship and vmaf phases run concurrently -- one is GPU-bound, the other
CPU-decode-bound.  Results are checkpointed after every row in CSV and JSON.

Titles and variants are configured in the TITLES/VARIANTS tables below.
Work dir: /tmp/nvenc-fgs-tests/campaign (heavy intermediates are deleted per
title unless --keep).

Usage: python3 tests/fgs/campaign.py [--titles taxi,dune] [--variants fgs,plain]
       [--seconds 60] [--frames 600] [--work /tmp/nvenc-fgs-tests/campaign] [--keep]
"""
import argparse
import concurrent.futures
import csv
import json
import os
import re
import shlex
import statistics
import subprocess
import sys
import time

import filmgrn

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NVENCC = os.environ.get("NVENCC", os.path.join(REPO, "build-fgs-cuda", "nvencc"))
SVT = os.environ.get("SVTAV1", "")   # SvtAv1EncApp path; svt/hybrid variants skipped if empty
VMAF = os.environ.get("VMAF_BIN", os.path.expanduser("~/git-repos/vmaf/libvmaf/build/tools/vmaf"))
FFVSHIP_IMG = "docker-apps/video-metrics:cuda13.3.0"
WORK = os.environ.get("FGS_CAMPAIGN_DIR", "/tmp/nvenc-fgs-tests/campaign")
CLIP_SECONDS = 60
REF_FRAMES = 600

COLOR = ("--colorrange auto --colormatrix auto --colorprim auto --transfer auto "
         "--chromaloc auto --max-cll copy --master-display copy").split()
TUNED = "--preset p7 --multipass 2pass-full --lookahead 32 --lookahead-level 3 --aq-temporal".split()

# (name, source path, clip start, class notes)
TITLES = [
    ("taxi",    "/media/merged-storage/media/movies/Taxi Driver (1976) [tmdbid-103]/Taxi Driver (1976) [tmdbid-103] - [Remux-2160p Proper][DTS-HD MA 5.1][DV HDR10][HEVC]-FraMeSToR.mkv", "00:30:00", "heavy 35mm grain, 4K PQ remux"),
    ("shining", "/media/merged-storage/media/movies/The Shining (1980)/The Shining (1980) [tmdbid-694] - [Remux-2160p][DTS-HD MA 5.1][DV HDR10Plus][HEVC]-FraMeSToR.mkv", "00:40:00", "heavy 35mm grain, 4K PQ remux"),
    ("casino",  "/media/merged-storage/media/movies/Casino (1995)/Casino (1995) [tmdbid-524] - [Remux-2160p][DTS-X 7.1][HDR10][HEVC]-EPSiLON.mkv", "00:35:00", "35mm grain, 4K HDR10 remux"),
    ("deerhunter", "/media/merged-storage/media/movies/The Deer Hunter (1978) [tmdbid-11778]/The Deer Hunter (1978) [tmdbid-11778] - [Hybrid][Remux-2160p][DTS-HD MA 5.1][DV HDR10][HEVC]-FraMeSToR.mkv", "00:45:00", "heavy 35mm grain, 4K PQ remux"),
    ("interstellar", "/media/merged-storage/media/movies/Interstellar (2014) [tmdbid-157336]/Interstellar (2014) [tmdbid-157336] - [Hybrid][Remux-2160p][DTS-HD MA 5.1][DV HDR10][HEVC]-FraMeSToR.mkv", "00:50:00", "mixed IMAX/35mm grain, 4K PQ remux"),
    ("dune",    "/media/merged-storage/media/movies/Dune (2021) [tmdbid-438631]/Dune (2021) [tmdbid-438631] - [Hybrid][Remux-2160p][TrueHD Atmos 7.1][DV HDR10Plus][HEVC]-WiLDCAT.mkv", "00:20:00", "fine digital grain, 4K PQ (library AV1)"),
    # normal 1080p content classes
    ("1883",    "/media/merged-storage/media/tv-shows/1883 (2021)/Season 01/1883 (2021) - S01E01 - 1883 [AMZN][WEBDL-1080p][EAC3 5.1][h264]-NTb.mkv", "00:15:00", "1080p prestige TV, film-look WEB-DL (HEVC)"),
    ("adventure", "/media/merged-storage/media/tv-shows/Adventure Time/Season 8/Adventure Time - S08E02 - Don't Look WEBRip-1080p.mkv", "00:03:00", "1080p 2D animation (library AV1)"),
    ("ballerina", "/media/merged-storage/media/movies/Ballerina (2025)/Ballerina (2025) [tmdbid-541671] - [Remux-1080p][TrueHD Atmos 7.1][AVC]-CiNEPHiLES.mkv", "00:25:00", "1080p modern clean digital (library AV1)"),
    ("minecraft", "/media/merged-storage/media/movies/A Minecraft Movie (2025)/A Minecraft Movie (2025) [tmdbid-950387] - [Remux-1080p Proper][TrueHD Atmos 7.1][AVC]-TRiToN.mkv", "00:20:00", "1080p CGI (HEVC library file)"),
    ("28days",  "/media/merged-storage/media/movies/28 Days Later (2002) [tmdbid-170]/28 Days Later 2002 REPACK BluRay 1080p DTS-HD MA 5 1 AVC HYBRID REMUX-FraMeSToR.mkv", "00:20:00", "1080p gritty DV-era source (library AV1)"),
]


def reader_args(src):
    codec = subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name", "-of", "default=nw=1:nk=1", src],
        text=True).strip()
    # CUVID cannot open the lossless FFV1 clips used when packet-copy seeking
    # is unsafe.  Decode those with libavcodec; encoding and FGS stay on GPU.
    return ["--avsw"] if codec == "ffv1" else ["--avhw"]


# variant name -> command builder(src_clip, out_path, table_path) -> list[list[str]] of commands to run in order
def v_fgs_retain(retain, denoiser="motion"):
    def build(src, out, tbl):
        fgs = f"denoise=auto,chroma=auto,denoiser={denoiser}"
        if retain == "auto":
            fgs += ",retain=auto"
        elif retain > 0.0:
            fgs += f",retain={retain:g}"
        return [[NVENCC, *reader_args(src), "--codec", "av1", "--output-depth", "10", "--qvbr", "26", *TUNED, *COLOR,
                 "--av1-film-grain", fgs, "--film-grain-table-out", tbl,
                 "--log-level", "debug",
                 "-i", src, "-o", out]]
    return build


def v_fgs(src, out, tbl):
    return v_fgs_retain(0.0, "motion")(src, out, tbl)

def v_plain(src, out, tbl):
    return [[NVENCC, *reader_args(src), "--codec", "av1", "--output-depth", "10", "--qvbr", "26", *TUNED, *COLOR,
             "-i", src, "-o", out]]

VARIANTS = {
    "fgs": v_fgs,
    "fgs_r25": v_fgs_retain(0.25),
    "fgs_r50": v_fgs_retain(0.50),
    "fgs_r75": v_fgs_retain(0.75),
    "fgs_r90": v_fgs_retain(0.90),
    "fgs_fft3d": v_fgs_retain(0.0, "fft3d"),
    "fgs_fft3d_auto": v_fgs_retain("auto", "fft3d"),
    "fgs_fft3d_r25": v_fgs_retain(0.25, "fft3d"),
    "fgs_fft3d_r50": v_fgs_retain(0.50, "fft3d"),
    "fgs_bilateral": v_fgs_retain(0.0, "bilateral"),
    "plain": v_plain,
}
# svt / hybrid variants are shell pipelines, handled specially
PIPELINE_VARIANTS = ("svt", "hybrid")


def run(cmd, timeout=1800, **kw):
    started = time.monotonic()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)
    r.elapsed_seconds = time.monotonic() - started
    if r.returncode != 0:
        raise RuntimeError(f"cmd failed ({r.returncode}): {cmd if isinstance(cmd,str) else ' '.join(cmd)}\n{r.stderr[-1500:]}")
    return r


def analyzer_diagnostics(log):
    values = [(float(risk), float(retain)) for risk, retain in
              re.findall(r"risk=([0-9.]+) retain=([0-9.]+)", log)]
    if not values:
        return {}
    risks, retains = zip(*values)
    return {
        "detail_risk_mean": round(statistics.mean(risks), 3),
        "retain_mean": round(statistics.mean(retains), 3),
        "retain_min": min(retains),
        "retain_max": max(retains),
    }


def shell(cmd, timeout=1800):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"pipeline failed ({r.returncode}): {cmd}\n{r.stderr[-1500:]}")
    return r


def probe_res(path):
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
             "-of", "csv=p=0", path])
    w, h = r.stdout.strip().split(",")[:2]
    return int(w), int(h)


def valid_video(path):
    if not os.path.isfile(path) or os.path.getsize(path) < 4096:
        return False
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", path],
        capture_output=True, text=True)
    # ffprobe appends a CSV separator when stream side-data is present.
    return r.returncode == 0 and bool(re.fullmatch(r"\d+,\d+,?\s*", r.stdout))


def extract_clip(src, start, dst, seconds, frames):
    if valid_video(dst):
        return
    if os.path.exists(dst):
        os.unlink(dst)
    # Prefer indexed input seeking.  Some long-GOP sources retain too much
    # keyframe preroll or make an invalid Matroska fragment; both cases fall
    # back to a frame-accurate lossless transcode below.
    try:
        run(["ffmpeg", "-v", "error", "-y", "-ss", start, "-i", src, "-t", str(seconds),
             "-map", "0:v:0", "-an", "-c:v", "copy", dst])
        if valid_video(dst):
            duration = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                  "-of", "default=nw=1:nk=1", dst]).stdout.strip())
            if duration <= seconds + 1.0:
                return
    except RuntimeError:
        pass
    # A few Matroska inputs cannot be cut into a valid packet-copy fragment at
    # the selected timestamp.  Re-encode those clips losslessly; pre-input
    # seeking is frame-accurate when transcoding and avoids decoding from 0.
    if os.path.exists(dst):
        os.unlink(dst)
    run(["ffmpeg", "-v", "error", "-y", "-ss", start, "-i", src, "-t", str(seconds),
         "-frames:v", str(frames),
         "-map", "0:v:0", "-an", "-c:v", "ffv1", "-level", "3",
         "-pix_fmt", "yuv420p10le", dst])
    if not valid_video(dst):
        raise RuntimeError(f"could not extract a valid clip from {src}")


def make_ref(clip, ref, frames):
    """Build the lossless reference FFVship scores against.

    ffvhuff rather than ffv1: FFMS2 decodes ffv1 badly, and the reference is
    decoded twice per variant (SSIMULACRA2 and Butteraugli).  Measured
    2026-07-27 on 120 4K frames -- SSIMULACRA2 6458ms -> 2532ms and Butteraugli
    8480ms -> 6613ms, with bit-identical scores, plus the encode itself halving
    (4204ms -> 2091ms).  Costs ~37% more disk (656MB -> 902MB per 120 frames).

    This reference exists only because FFMS2 cannot read DV dual-layer HEVC:
    pointing FFVship at the packet-copied clip scores -48.13 against the
    correct 15.44.  vmaf does not need it -- see vmaf_run.
    """
    codec = run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=codec_name", "-of", "default=nw=1:nk=1",
                 clip]).stdout.strip()
    if codec == "ffvhuff":
        return clip
    if not os.path.exists(ref):
        run(["ffmpeg", "-v", "error", "-y", "-i", clip, "-vframes", str(frames), "-an",
             "-c:v", "ffvhuff", "-pix_fmt", "yuv420p10le", ref])
    return ref


def pct(sorted_vals, p):
    """p-th percentile of an already-sorted list, clamped to valid indices."""
    if not sorted_vals:
        return None
    return sorted_vals[min(len(sorted_vals) - 1, max(0, int(len(sorted_vals) * p / 100.0)))]


def ffvship(ref, enc, tag, d, frames, metric, out_name):
    # --cache-index lets the second metric over the same pair reuse the FFMS2
    # index instead of rebuilding it (~550ms per variant at 4K/120f)
    out_json = os.path.join(d, out_name)
    if not os.path.isfile(out_json):
        run(["docker", "run", "--rm", "--gpus", "all", "-v", f"{d}:/data", "--entrypoint", "FFVship", FFVSHIP_IMG,
             "-s", f"/data/{os.path.basename(ref)}", "-e", f"/data/{os.path.basename(enc)}",
             "--end", str(frames), "-m", metric, "--cache-index",
             "--json", f"/data/{out_name}"])
    return json.load(open(out_json))


def vmaf_run(ref, enc, models, feat_json, tag, frames):
    """Score every model in `models` in one pass over fifo-fed 10-bit y4m.

    `models` maps output key -> model spec, e.g. {"vmaf": "version=vmaf_v0.6.1"}.
    Each is passed as its own --model with name= set to the key, so the pooled
    metrics come back under those names.

    `ref` should be the extracted clip, not the lossless intermediate.  vmaf
    consumes ffmpeg-decoded y4m, and make_ref's intermediate is built from that
    exact same decode, so the pixels are identical by construction -- verified
    bit-identical across vmaf/vmaf_neg/psnr_y/ssim/ciede2000/motion on a DV
    title.  Skipping the intermediate avoids re-decoding it: 4144ms -> 3024ms
    per variant at 4K/120f.  Unlike FFMS2, ffmpeg reads DV dual-layer HEVC
    correctly, so the clip is safe here even though it is not safe for FFVship.

    Scoring both models in one invocation decodes the reference once, so a
    second invocation would near-double the phase for nothing.

    This requires a libvmaf containing the accumulator-memset stream fix
    (`cuda: zero motion/vif accumulators on the picture stream`).  Without it,
    two models plus the CUDA feature extractors race: measured 2026-07-27 over
    30 runs, 25 distinct pooled means, 21 zeroed integer_motion frames and 2
    null frames.  The null check below is the tripwire if VMAF_BIN ever points
    at a build predating that fix.

    Writers run with stdio detached from the capture pipes (a crashed vmaf must
    not deadlock the runner on orphaned writers) and are cleaned up by captured
    PID -- never by pattern matching, which twice managed to SIGTERM its own
    shell because the writer command text appears inside the shell's own
    command line.
    """
    d = os.path.dirname(feat_json)
    rp, dp = os.path.join(d, f"rp-{tag}"), os.path.join(d, f"dp-{tag}")
    q = shlex.quote
    model_args = " ".join(f"--model {q(spec + ':name=' + key)}"
                          for key, spec in models.items())
    fifo_cmd = (
        # plain ';' sequencing: an '&&' chain ending in 'cmd &' would background
        # the whole chain, racing vmaf ahead of mkfifo
        f"rm -f {q(rp)} {q(dp)}; mkfifo {q(rp)} {q(dp)} || exit 1; "
        f"ffmpeg -v error -i {q(ref)} -frames:v {frames} -pix_fmt yuv420p10le -strict -1 -f yuv4mpegpipe -y {q(rp)} >/dev/null 2>&1 & w1=$!; "
        f"ffmpeg -v error -c:v libdav1d -i {q(enc)} -frames:v {frames} -pix_fmt yuv420p10le -strict -1 -f yuv4mpegpipe -y {q(dp)} >/dev/null 2>&1 & w2=$!; "
        f"{q(VMAF)} --reference {q(rp)} --distorted {q(dp)} --gpumask 0 {model_args} "
        f"--feature psnr_cuda --feature ssim_cuda --feature ciede_cuda --json --output {q(feat_json)}; st=$?; "
        f"kill $w1 $w2 2>/dev/null; wait 2>/dev/null; rm -f {q(rp)} {q(dp)}; exit $st")
    if not os.path.isfile(feat_json):
        try:
            shell(fifo_cmd, timeout=900)
        except Exception:
            shell(fifo_cmd, timeout=900)  # one retry; transient CUDA-init failures observed
    doc = json.load(open(feat_json))
    for key in models:
        nulls = sum(1 for f in doc["frames"] if f["metrics"].get(key) is None)
        if nulls:
            raise RuntimeError(
                f"{os.path.basename(feat_json)}: {nulls} frame(s) scored null for "
                f"'{key}' -- pooled means are unusable.  VMAF_BIN is probably a build "
                "without the accumulator-memset stream fix; delete the json and rerun")
    return doc["pooled_metrics"]


def score(ref, enc, tag, d, height, frames, clip=None):
    """Score one encode.  The two tracks below run concurrently.

    `clip` is optional and only an optimisation: when given, vmaf reads the
    source clip instead of `ref`, skipping a decode of the lossless
    intermediate (4144ms -> 3024ms at 4K/120f).  The pixels are identical
    either way because make_ref builds the intermediate from that same ffmpeg
    decode.  Omitting it is always correct, just slower -- external callers
    (matched_rate_sweep.py) that only have a reference keep working unchanged.

    FFVship saturates the GPU (Butteraugli measured at 85% mean utilisation)
    while the vmaf track spends most of its time on CPU-bound decode of the
    reference and the AV1 encode (52% GPU).  Overlapping them recovers most of
    the shorter track: measured 2026-07-27 at 4K/120f, 13.2s -> 10.2s wall,
    reproducible, with ssimu2, butteraugli and every vmaf pooled metric
    bit-identical to the sequential run.  Contention costs about 1s against the
    ideal, which is why this is ~24% and not ~30%.

    The two FFVship calls stay sequential *within* their track so the second
    reuses the cached FFMS2 index.

    Per-phase t_* values now overlap, so they no longer sum to wall time --
    t_score_wall is the number to read for total cost.
    """
    out = {}
    uhd = height > 1200
    model = "version=vmaf_4k_v0.6.1" if uhd else "version=vmaf_v0.6.1"
    model_neg = "version=vmaf_4k_v0.6.1neg" if uhd else "version=vmaf_v0.6.1neg"
    vmaf_ref = clip or ref

    def ffvship_track():
        r = {}
        t0 = time.monotonic()
        s = sorted(x[0] for x in ffvship(ref, enc, tag, d, frames, "SSIMULACRA2", f"ssimu2-{tag}.json"))
        r["ssimu2"], r["ssimu2_p5"] = round(statistics.mean(s), 2), round(pct(s, 5), 2)
        r["t_ssimu2"] = round(time.monotonic() - t0, 1)

        # Butteraugli rows are [2norm, 3norm, maxnorm]; lower is better.  The
        # max norm is the localized-artifact signal that mean-pooled SSIMU2 and
        # VMAF average away, so the tail (p95) is the number worth reading.
        t0 = time.monotonic()
        b = ffvship(ref, enc, tag, d, frames, "Butteraugli", f"butter-{tag}.json")
        r["butter_2norm"] = round(statistics.mean(x[0] for x in b), 3)
        r["butter_max_p95"] = round(pct(sorted(x[2] for x in b), 95), 2)
        r["t_butteraugli"] = round(time.monotonic() - t0, 1)
        return r

    def vmaf_track():
        # The local libvmaf build supplies CUDA versions of the model's ADM,
        # VIF, and motion extractors as well as PSNR, SSIM, and CIEDE2000.
        # gpumask=0 explicitly selects them.  Model prediction itself is a tiny
        # CPU step.
        #
        # NEG penalises enhancement (sharpening, contrast) that is not in the
        # source.  Grain synthesis adds structure that was never there, so for
        # FGS variants the neg score is the honest one and vmaf-minus-neg is the
        # size of the enhancement bonus the default model is handing out.  Both
        # models ride the same decode.
        r = {}
        t0 = time.monotonic()
        fm = vmaf_run(vmaf_ref, enc, {"vmaf": model, "vmaf_neg": model_neg},
                      os.path.join(d, f"metrics-cuda-{tag}.json"), tag, frames)
        r["vmaf"] = round(fm["vmaf"]["mean"], 2)
        r["vmaf_min"] = round(fm["vmaf"]["min"], 2)
        r["vmaf_neg"] = round(fm["vmaf_neg"]["mean"], 2)
        r["vmaf_neg_gap"] = round(r["vmaf"] - r["vmaf_neg"], 2)
        r["psnr_y"] = round(fm["psnr_y"]["mean"], 2)
        r["ssim"] = round(fm["float_ssim"]["mean"], 4)
        r["ciede2000"] = round(fm["ciede2000"]["mean"], 2)
        r["t_vmaf"] = round(time.monotonic() - t0, 1)
        return r

    wall = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        tracks = [pool.submit(ffvship_track), pool.submit(vmaf_track)]
        # exceptions surface here; the executor's shutdown still joins the other
        # track, so a failure cannot leave a writer or fifo behind
        for future in tracks:
            out.update(future.result())
    out["t_score_wall"] = round(time.monotonic() - wall, 1)
    return out


def hf_sigma(path, width, height, frames=(6, 10, 14), decoder=None, filmgrain=None):
    import numpy as np
    W, H = width, height
    fp = W * H * 3 // 2
    tmp = "/tmp/hfprobe.yuv"
    cmd = ["ffmpeg", "-v", "error", "-y"]
    if decoder:
        cmd += ["-c:v", decoder]
    if filmgrain is not None:
        cmd += ["-filmgrain", str(filmgrain)]
    cmd += ["-i", path, "-vframes", str(max(frames) + 2), "-pix_fmt", "yuv420p10le",
            "-vf", f"scale={W}:{H}", "-f", "rawvideo", tmp]
    run(cmd)
    mm = np.memmap(tmp, dtype=np.uint16, mode="r")
    vals = []
    for f in frames:
        a = mm[f * fp:f * fp + W * H].reshape(H, W).astype(np.float64)
        b = (a[0:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, 0:-2] + a[1:-1, 2:] + a[1:-1, 1:-1] * 4) / 8
        vals.append(float((a[1:-1, 1:-1] - b).std()) * (8 / 5.0) ** 0.5)
    os.remove(tmp)
    return round(sum(vals) / len(vals), 2)


def write_results(work, args, wanted, variants, rows):
    out_csv = os.path.join(work, "results.csv")
    fields = ["title", "variant", "mb", "vmaf", "vmaf_min", "vmaf_neg", "vmaf_neg_gap",
              "ssimu2", "ssimu2_p5", "butter_2norm", "butter_max_p95",
              "psnr_y", "ssim", "ciede2000", "hf_sigma", "base_hf_sigma",
              "encode_seconds", "grain_entries", "grain_coverage_seconds",
              "detail_risk_mean", "retain_mean", "retain_min", "retain_max",
              # phase timings, to show where a campaign run actually spends time
              "t_ssimu2", "t_butteraugli", "t_vmaf", "t_hf_sigma", "t_score_wall", "note"]
    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    out_json = os.path.join(work, "results.json")
    with open(out_json, "w") as output:
        json.dump({"seconds": args.seconds, "frames": args.frames,
                   "titles": wanted, "variants": variants,
                   "metric_backends": {
                       "vmaf": "libvmaf CUDA ADM/VIF/motion + CPU model prediction",
                       "psnr_ssim_ciede2000": "libvmaf CUDA",
                       "ssimulacra2": "FFVship CUDA",
                   },
                   "rows": rows}, output, indent=2)
        output.write("\n")
    return out_csv, out_json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--titles", default=",".join(t[0] for t in TITLES))
    ap.add_argument("--variants", default="fgs,plain")
    ap.add_argument("--seconds", type=float, default=CLIP_SECONDS)
    ap.add_argument("--frames", type=int, default=REF_FRAMES)
    ap.add_argument("--work", default=WORK)
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()
    if args.seconds <= 0 or args.frames <= 0:
        ap.error("--seconds and --frames must be positive")
    work = os.path.abspath(args.work)
    os.makedirs(work, exist_ok=True)
    wanted = args.titles.split(",")
    variants = args.variants.split(",")
    rows = []
    result_path = os.path.join(work, "results.json")
    recorded_titles = list(wanted)
    recorded_variants = list(variants)
    if os.path.isfile(result_path):
        try:
            with open(result_path) as previous_file:
                previous = json.load(previous_file)
            if previous.get("seconds") == args.seconds and previous.get("frames") == args.frames:
                # A follow-up invocation can add variants without rescoring
                # everything already in the campaign.  Requested pairs are
                # replaced, so rerunning a failed/new implementation is safe.
                rows = [row for row in previous.get("rows", [])
                        if row.get("title") not in wanted
                        or (row.get("variant") != "source"
                            and row.get("variant") not in variants)]
                recorded_titles = list(dict.fromkeys(previous.get("titles", []) + wanted))
                recorded_variants = list(dict.fromkeys(previous.get("variants", []) + variants))
        except (OSError, ValueError, TypeError):
            pass
    for name, src, start, note in TITLES:
        if name not in wanted:
            continue
        d = os.path.join(work, name)
        os.makedirs(d, exist_ok=True)
        clip = os.path.join(d, "clip.mkv")
        ref = os.path.join(d, "ref.mkv")
        title_ok = True
        print(f"== {name}: {note}")
        try:
            extract_clip(src, start, clip, args.seconds, args.frames)
            ref = make_ref(clip, ref, args.frames)
            width, height = probe_res(clip)
            src_hf = hf_sigma(clip, width, height)
        except Exception as e:
            print(f"   source: FAILED - {e}")
            rows.append({"title": name, "variant": "source", "note": f"FAILED {e}"})
            write_results(work, args, recorded_titles, recorded_variants, rows)
            continue
        rows.append({"title": name, "variant": "source", "mb": round(os.path.getsize(clip) / 1e6, 1),
                     "hf_sigma": src_hf, "note": note})
        print(f"   source: {rows[-1]['mb']}MB HF={src_hf}")
        write_results(work, args, recorded_titles, recorded_variants, rows)
        for var in variants:
            if var in PIPELINE_VARIANTS:
                print(f"   [skip] {var}: run separately (CPU-heavy)")
                continue
            out = os.path.join(d, f"{var}.mkv")
            tbl = os.path.join(d, f"{var}.tbl")
            try:
                encode_seconds = None
                encode_log = ""
                if not valid_video(out):
                    if os.path.exists(out):
                        os.unlink(out)
                    encode_seconds = 0.0
                    for cmd in VARIANTS[var](clip, out, tbl):
                        result = run(cmd)
                        encode_seconds += result.elapsed_seconds
                        encode_log += result.stdout + result.stderr
                    with open(os.path.join(d, f"{var}.log"), "w") as log_file:
                        log_file.write(encode_log)
                else:
                    log_path = os.path.join(d, f"{var}.log")
                    if os.path.isfile(log_path):
                        with open(log_path) as log_file:
                            encode_log = log_file.read()
                row = {"title": name, "variant": var,
                       "mb": round(os.path.getsize(out) / 1e6, 1),
                       "encode_seconds": round(encode_seconds, 2) if encode_seconds is not None else None}
                row.update(analyzer_diagnostics(encode_log))
                row.update(score(ref, out, var, d, height, args.frames, clip=clip))
                # dav1d stays here regardless of what score() uses: the grain-off
                # base layer needs libdav1d's -filmgrain 0, which NVDEC/av1_cuvid
                # does not expose (it applies bitstream grain unconditionally).
                t0 = time.monotonic()
                row["hf_sigma"] = hf_sigma(out, width, height, decoder="libdav1d", filmgrain=1)
                row["base_hf_sigma"] = hf_sigma(out, width, height, decoder="libdav1d", filmgrain=0)
                row["t_hf_sigma"] = round(time.monotonic() - t0, 1)
                if os.path.isfile(tbl):
                    entries = filmgrn.load(tbl)
                    row["grain_entries"] = len(entries)
                    row["grain_coverage_seconds"] = round(sum(
                        entry["end"] - entry["start"] for entry in entries) / 10_000_000.0, 3)
                rows.append(row)
                print(f"   {var}: {row}")
                write_results(work, args, recorded_titles, recorded_variants, rows)
            except Exception as e:
                print(f"   {var}: FAILED - {e}")
                rows.append({"title": name, "variant": var, "note": f"FAILED {e}"})
                title_ok = False
                write_results(work, args, recorded_titles, recorded_variants, rows)
        if title_ok and not args.keep and ref != clip and os.path.exists(ref):
            os.remove(ref)  # 3.7GB each; regenerable (kept on failure for cheap retries)
    out_csv, out_json = write_results(work, args, recorded_titles, recorded_variants, rows)
    print(f"\nresults: {out_csv}")
    print(f"results: {out_json}")


if __name__ == "__main__":
    main()
