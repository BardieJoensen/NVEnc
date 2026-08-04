#!/usr/bin/env python3
"""Phase A: does source fitting damage non-grain content more than production?

Sources are the untouched originals under /tmp/downloads/movies -- never the
library, which holds the user's own transcodes.  A lossless FFV1 clip is cut
once per title and every arm is scored against that same clip.

Arms share the bilateral separator and rate; only the grain model changes.
The emitted .tbl is parsed for signalled strength, which is the actual
admission question: does the analyser engage on content that has no film grain.
"""
import json, os, shlex, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/home/bardie/git-repos/NVEnc/tests/fgs")
from review_score import VMAF, shell

WORK = "/media/merged-storage/media/test-encodes/admission-gate-20260804"
DL = "/tmp/downloads/movies"
PROD = "/opt/docker-apps/build/tdarr-node/nvencc"
CAND = ("/home/bardie/.cache/fgs-gate/builds/"
        "pin-ed2829b39d519e2bfc163a5ce5334759c453348d-1785807218/build-gate-static/nvencc")
FRAMES = 288

TITLES = {
    "DenTid": (f"{DL}/Den.Tid.Paa.Aaret.2018.NORDiC.1080p.WEB-DL.H.264.DDP5.1-RTBYTES/"
               "Den.Tid.Paa.Aaret.2018.NORDiC.1080p.WEB-DL.H.264.DDP5.1-RTBYTES.mkv", "00:30:00"),
    "Tuner": (f"{DL}/Tuner 2025 BluRay 1080p TrueHD Atmos 7 1 AVC REMUX-FraMeSToR/"
              "Tuner 2025 BluRay 1080p TrueHD Atmos 7 1 AVC REMUX-FraMeSToR.mkv", "00:35:00"),
    "TrainToBusan": (f"{DL}/Train.to.Busan.2016.Hybrid.1080p.BluRay.REMUX.AVC.DTS-X-EPSiLON.mkv",
                     "00:40:00"),
    "Sinister": (f"{DL}/Sinister.2012.BluRay.1080p.DTS-HD.MA.7.1.AVC.REMUX-FraMeSToR/"
                 "Sinister.2012.BluRay.1080p.DTS-HD.MA.7.1.AVC.REMUX-FraMeSToR.mkv", "00:35:00"),
}

# same rate/preset for every arm; only the grain model differs
BASE = ["--avsw", "--codec", "av1", "--output-depth", "10", "--qvbr", "29",
        "--max-bitrate", "20000", "--preset", "p4", "--tune", "hq"]
FGS = "denoise=auto,chroma=auto,denoiser=bilateral"


def run(cmd, env=None, log=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    p = subprocess.run(cmd, capture_output=True, text=True, env=e, timeout=7200)
    if log:
        open(log, "w").write(p.stdout + p.stderr)
    if p.returncode != 0:
        raise RuntimeError(f"failed: {' '.join(cmd[:6])}...\n{(p.stdout + p.stderr)[-2500:]}")
    return p


def make_clip(name, src, ts):
    """One lossless FFV1 clip per title; every arm is scored against it."""
    out = f"{WORK}/{name}-ref.mkv"
    if not os.path.isfile(out):
        run(["ffmpeg", "-v", "error", "-nostdin", "-ss", ts, "-i", src,
             "-frames:v", str(FRAMES), "-map", "0:v:0", "-an", "-sn", "-dn",
             "-c:v", "ffv1", "-level", "3", "-g", "1", "-pix_fmt", "yuv420p",
             "-y", out])
    return out


def encode(name, arm, ref):
    mkv, tbl = f"{WORK}/{name}-{arm}.mkv", f"{WORK}/{name}-{arm}.tbl"
    if os.path.isfile(mkv):
        return mkv, tbl
    binary, env, extra = PROD, {}, []
    if arm == "plain":
        pass
    elif arm == "production":
        extra = ["--av1-film-grain", FGS, "--film-grain-table-out", tbl]
    elif arm == "candidate":
        binary = CAND
        env = {"NVENC_FGS_TEST_SOURCE_STATIC": "on"}
        extra = ["--av1-film-grain", FGS + ",modelsrc=on", "--film-grain-table-out", tbl]
    t0 = time.monotonic()
    run([binary, "-i", ref] + BASE + extra + ["-o", mkv], env=env,
        log=f"{WORK}/{name}-{arm}.log")
    print(f"  {name}/{arm}: {os.path.getsize(mkv)} bytes, {time.monotonic()-t0:.1f}s", flush=True)
    return mkv, tbl


def table_strength(tbl):
    """Mean and max signalled luma scaling value across all emitted intervals.

    filmgrn1 lines carry the luma scaling points; a table that engages on clean
    content is the admission failure regardless of what it does to grain.
    """
    if not tbl or not os.path.isfile(tbl):
        return None
    vals, intervals, shifts, applied = [], 0, [], 0
    for line in open(tbl):
        p = line.split()
        if not p or p[0] == "filmgrn1":
            continue
        if p[0] == "E":                       # E start end apply_grain seed update
            intervals += 1
            if len(p) > 3 and p[3] != "0":
                applied += 1
            continue
        if p[0] == "p" and len(p) >= 6:       # p lag ar_shift grain_scale_shift scaling_shift ...
            shifts.append((int(p[3]), int(p[4])))
            continue
        if p[0] == "sY" and len(p) >= 3:      # sY n x0 y0 x1 y1 ...
            n = int(p[1])
            pts = [int(x) for x in p[2:2 + 2 * n]]
            vals.extend(pts[1::2])            # strength values only
    out = {"intervals": intervals, "applied": applied,
           "grain_scale_shift": shifts[0][0] if shifts else None,
           "scaling_shift": shifts[0][1] if shifts else None}
    out.update({"mean_point": round(sum(vals) / len(vals), 2) if vals else 0.0,
                "max_point": max(vals) if vals else 0})
    return out


def vmaf(ref, enc, tag):
    out = f"{WORK}/vmaf-{tag}.json"
    rp, dp = f"{WORK}/rp-{tag}", f"{WORK}/dp-{tag}"
    q = shlex.quote
    m = " ".join(f"--model {q(s + ':name=' + k)}" for k, s in
                 {"vmaf": "version=vmaf_v0.6.1", "vmaf_neg": "version=vmaf_v0.6.1neg"}.items())
    cmd = (f"rm -f {q(rp)} {q(dp)}; mkfifo {q(rp)} {q(dp)} || exit 1; "
           f"ffmpeg -v error -nostdin -i {q(ref)} -frames:v {FRAMES} -pix_fmt yuv420p10le -strict -1 -f yuv4mpegpipe -y {q(rp)} >/dev/null 2>&1 & w1=$!; "
           f"ffmpeg -v error -nostdin -c:v libdav1d -i {q(enc)} -frames:v {FRAMES} -pix_fmt yuv420p10le -strict -1 -f yuv4mpegpipe -y {q(dp)} >/dev/null 2>&1 & w2=$!; "
           f"{q(VMAF)} --reference {q(rp)} --distorted {q(dp)} --gpumask 0 {m} "
           f"--feature psnr_cuda --json --output {q(out)}; st=$?; "
           f"kill $w1 $w2 2>/dev/null; wait 2>/dev/null; rm -f {q(rp)} {q(dp)}; exit $st")
    if not os.path.isfile(out):
        shell(cmd, timeout=3600)
    doc = json.load(open(out))
    vals = sorted(f["metrics"]["vmaf"] for f in doc["frames"])
    p = doc["pooled_metrics"]
    return {"vmaf": round(p["vmaf"]["mean"], 3), "vmaf_neg": round(p["vmaf_neg"]["mean"], 3),
            "vmaf_min": round(vals[0], 2), "vmaf_p1": round(vals[max(0, len(vals) // 100)], 2),
            "psnr_y": round(p["psnr_y"]["mean"], 3)}


def main():
    os.makedirs(WORK, exist_ok=True)
    rows = []
    for name, (src, ts) in TITLES.items():
        if not os.path.isfile(src):
            print(f"MISSING SOURCE {src}", flush=True)
            continue
        print(f"[{name}]", flush=True)
        ref = make_clip(name, src, ts)
        for arm in ("plain", "production", "candidate"):
            mkv, tbl = encode(name, arm, ref)
            r = {"title": name, "arm": arm, "bytes": os.path.getsize(mkv)}
            r.update(vmaf(ref, mkv, f"{name}-{arm}"))
            r["table"] = table_strength(tbl) if arm != "plain" else None
            rows.append(r)
            print("  " + json.dumps(r), flush=True)
        json.dump(rows, open(f"{WORK}/results.json", "w"), indent=1)


if __name__ == "__main__":
    main()
