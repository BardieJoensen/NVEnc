#!/usr/bin/env python3
"""Multi-title FGS evaluation campaign.

For each title: extracts a clip, encodes the configured pipeline variants,
builds a clean FFV1 reference from the decoded base layer (DV-safe), and
scores VMAF (4K/HD model by resolution), SSIMULACRA2 (FFVship), CIEDE2000 +
PSNR/SSIM (user's CUDA vmaf feature extractors), chroma drift (signalstats),
and grain-retention HF sigma.  Results land in a CSV.

Titles and variants are configured in the TITLES/VARIANTS tables below.
Work dir: /tmp/nvenc-fgs-tests/campaign (heavy intermediates are deleted per
title unless --keep).

Usage: python3 tests/fgs/campaign.py [--titles taxi,dune] [--variants fgs,plain]
       [--seconds 60] [--frames 600] [--work /tmp/nvenc-fgs-tests/campaign] [--keep]
"""
import argparse
import csv
import json
import os
import re
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

# variant name -> command builder(src_clip, out_path, table_path) -> list[list[str]] of commands to run in order
def v_fgs_retain(retain, denoiser="motion"):
    def build(src, out, tbl):
        fgs = f"denoise=auto,chroma=auto,denoiser={denoiser}"
        if retain > 0.0:
            fgs += f",retain={retain:g}"
        return [[NVENCC, "--avhw", "--codec", "av1", "--output-depth", "10", "--qvbr", "26", *TUNED, *COLOR,
                 "--av1-film-grain", fgs, "--film-grain-table-out", tbl,
                 "-i", src, "-o", out]]
    return build


def v_fgs(src, out, tbl):
    return v_fgs_retain(0.0, "motion")(src, out, tbl)

def v_plain(src, out, tbl):
    return [[NVENCC, "--avhw", "--codec", "av1", "--output-depth", "10", "--qvbr", "26", *TUNED, *COLOR,
             "-i", src, "-o", out]]

VARIANTS = {
    "fgs": v_fgs,
    "fgs_r25": v_fgs_retain(0.25),
    "fgs_r50": v_fgs_retain(0.50),
    "fgs_r75": v_fgs_retain(0.75),
    "fgs_r90": v_fgs_retain(0.90),
    "fgs_fft3d": v_fgs_retain(0.0, "fft3d"),
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


def extract_clip(src, start, dst, seconds):
    if not os.path.exists(dst):
        # Accurate post-input seeking avoids retaining a long GOP of preroll;
        # pre-input stream-copy seeking made nominal 3 s clips almost 12 s.
        run(["ffmpeg", "-v", "error", "-y", "-i", src, "-ss", start, "-t", str(seconds),
             "-map", "0:v:0", "-an", "-c:v", "copy", dst])


def make_ref(clip, ref, frames):
    if not os.path.exists(ref):
        run(["ffmpeg", "-v", "error", "-y", "-i", clip, "-vframes", str(frames), "-an",
             "-c:v", "ffv1", "-pix_fmt", "yuv420p10le", ref])


def score(ref, enc, tag, d, height, frames):
    out = {}
    model = "version=vmaf_4k_v0.6.1" if height > 1200 else "version=vmaf_v0.6.1"
    vmaf_json = os.path.join(d, f"vmaf-{tag}.json")
    run(["ffmpeg", "-v", "error", "-c:v", "libdav1d", "-i", enc, "-i", ref, "-lavfi",
         f"[0:v]trim=end_frame={frames},setpts=PTS-STARTPTS[d];[1:v]setpts=PTS-STARTPTS[r];"
         f"[d][r]libvmaf=log_fmt=json:log_path={vmaf_json}:n_threads=20:model={model}", "-f", "null", "-"])
    p = json.load(open(vmaf_json))["pooled_metrics"]["vmaf"]
    out["vmaf"], out["vmaf_min"] = round(p["mean"], 2), round(p["min"], 2)

    ssimu_json = os.path.join(d, f"ssimu2-{tag}.json")
    run(["docker", "run", "--rm", "--gpus", "all", "-v", f"{d}:/data", "--entrypoint", "FFVship", FFVSHIP_IMG,
         "-s", f"/data/{os.path.basename(ref)}", "-e", f"/data/{os.path.basename(enc)}",
         "--end", str(frames), "-m", "SSIMULACRA2", "--json", f"/data/ssimu2-{tag}.json"])
    s = sorted(x[0] for x in json.load(open(ssimu_json)))
    out["ssimu2"], out["ssimu2_p5"] = round(statistics.mean(s), 2), round(s[int(len(s) * 0.05)], 2)

    # user's CUDA extractors over y4m fifos.  Writers run with stdio detached
    # from the capture pipes (a crashed vmaf must not deadlock the runner on
    # orphaned writers) and are cleaned up by captured PID -- never by pattern
    # matching, which twice managed to SIGTERM its own shell because the
    # writer command text appears inside the shell's own command line.
    feat_json = os.path.join(d, f"feat-{tag}.json")
    rp, dp = os.path.join(d, f"rp-{tag}"), os.path.join(d, f"dp-{tag}")
    fifo_cmd = (
        # plain ';' sequencing: an '&&' chain ending in 'cmd &' would background
        # the whole chain, racing vmaf ahead of mkfifo
        f"rm -f {rp} {dp}; mkfifo {rp} {dp} || exit 1; "
        f"ffmpeg -v error -i {ref} -frames:v {frames} -pix_fmt yuv420p10le -strict -1 -f yuv4mpegpipe -y {rp} >/dev/null 2>&1 & w1=$!; "
        f"ffmpeg -v error -c:v libdav1d -i {enc} -frames:v {frames} -pix_fmt yuv420p10le -strict -1 -f yuv4mpegpipe -y {dp} >/dev/null 2>&1 & w2=$!; "
        f"{VMAF} --reference {rp} --distorted {dp} --no_prediction "
        f"--feature psnr_cuda --feature ssim_cuda --feature ciede_cuda --json --output {feat_json}; st=$?; "
        f"kill $w1 $w2 2>/dev/null; wait 2>/dev/null; rm -f {rp} {dp}; exit $st")
    try:
        shell(fifo_cmd, timeout=900)
    except Exception:
        shell(fifo_cmd, timeout=900)  # one retry; transient CUDA-init failures observed
    fm = json.load(open(feat_json))["pooled_metrics"]
    out["psnr_y"] = round(fm["psnr_y"]["mean"], 2)
    out["ssim"] = round(fm["float_ssim"]["mean"], 4)
    out["ciede2000"] = round(fm["ciede2000"]["mean"], 2)
    return out


def hf_sigma(path, height, frames=(6, 10, 14), decoder=None, filmgrain=None):
    import numpy as np
    W = 3840 if height > 1200 else 1920
    H = 2160 if height > 1200 else 1080
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
    for name, src, start, note in TITLES:
        if name not in wanted:
            continue
        d = os.path.join(work, name)
        os.makedirs(d, exist_ok=True)
        clip = os.path.join(d, "clip.mkv")
        ref = os.path.join(d, "ref.mkv")
        title_ok = True
        print(f"== {name}: {note}")
        extract_clip(src, start, clip, args.seconds)
        make_ref(clip, ref, args.frames)
        _, height = probe_res(clip)
        src_hf = hf_sigma(clip, height)
        rows.append({"title": name, "variant": "source", "mb": round(os.path.getsize(clip) / 1e6, 1),
                     "hf_sigma": src_hf, "note": note})
        print(f"   source: {rows[-1]['mb']}MB HF={src_hf}")
        for var in variants:
            if var in PIPELINE_VARIANTS:
                print(f"   [skip] {var}: run separately (CPU-heavy)")
                continue
            out = os.path.join(d, f"{var}.mkv")
            tbl = os.path.join(d, f"{var}.tbl")
            try:
                encode_seconds = None
                if not os.path.exists(out):
                    encode_seconds = 0.0
                    for cmd in VARIANTS[var](clip, out, tbl):
                        encode_seconds += run(cmd).elapsed_seconds
                row = {"title": name, "variant": var,
                       "mb": round(os.path.getsize(out) / 1e6, 1),
                       "encode_seconds": round(encode_seconds, 2) if encode_seconds is not None else None}
                row.update(score(ref, out, var, d, height, args.frames))
                row["hf_sigma"] = hf_sigma(out, height, decoder="libdav1d", filmgrain=1)
                row["base_hf_sigma"] = hf_sigma(out, height, decoder="libdav1d", filmgrain=0)
                if os.path.isfile(tbl):
                    entries = filmgrn.load(tbl)
                    row["grain_entries"] = len(entries)
                    row["grain_coverage_seconds"] = round(sum(
                        entry["end"] - entry["start"] for entry in entries) / 10_000_000.0, 3)
                rows.append(row)
                print(f"   {var}: {row}")
            except Exception as e:
                print(f"   {var}: FAILED - {e}")
                rows.append({"title": name, "variant": var, "note": f"FAILED {e}"})
                title_ok = False
        if title_ok and not args.keep and os.path.exists(ref):
            os.remove(ref)  # 3.7GB each; regenerable (kept on failure for cheap retries)
    out_csv = os.path.join(work, "results.csv")
    fields = ["title", "variant", "mb", "vmaf", "vmaf_min", "ssimu2", "ssimu2_p5",
              "psnr_y", "ssim", "ciede2000", "hf_sigma", "base_hf_sigma",
              "encode_seconds", "grain_entries", "grain_coverage_seconds", "note"]
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    out_json = os.path.join(work, "results.json")
    with open(out_json, "w") as output:
        json.dump({"seconds": args.seconds, "frames": args.frames,
                   "titles": wanted, "variants": variants, "rows": rows},
                  output, indent=2)
        output.write("\n")
    print(f"\nresults: {out_csv}")
    print(f"results: {out_json}")


if __name__ == "__main__":
    main()
