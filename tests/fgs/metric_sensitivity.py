#!/usr/bin/env python3
"""Does making the grain more correct improve VMAF?

Two candidates differ in exactly one thing: leak closure.  Both are qvbr 29,
motion separation, modelsrc=on, same sources, same selector.

  pre-closure   sourcefit-corpus-20260801/<T>-motion_on.mkv   mean synth 0.893
  post-closure  sourcefit-leakclose-20260802/<T>-q29.mkv      mean synth 0.959

Post-closure is measurably closer to the source's true grain amplitude on five
of six titles and removes essentially all corpus-mean bias (-0.069 -> -0.004).
If FR metrics reward correct grain, post-closure should score higher.  If they
reward *absent* grain, it should score lower, because the only thing that
changed is that there is now more synthesised grain on the picture.

Scored at native 4K against the lossless originals, 4K models, dav1d decode so
film grain is actually applied.
"""
import json, os, shlex, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from review_score import VMAF, FRAMES, shell

WORK = "/media/merged-storage/media/test-encodes/correctness-vmaf-20260802"
SRC = "/media/merged-storage/media/test-encodes/keep-original"
PRE = "/media/merged-storage/media/test-encodes/sourcefit-corpus-20260801"
POST = "/media/merged-storage/media/test-encodes/sourcefit-leakclose-20260802"

SOURCES = {
    "Casino": "clip_Casino-ref288.mkv",
    "Interstellar": "clip_Interstellar.mkv",
    "Scarface": "clip_Scarface-ref288.mkv",
    "Taxi_Driver": "clip_Taxi_Driver-ref288.mkv",
    "The_Deer_Hunter": "clip_The_Deer_Hunter.mkv",
    "The_Shining": "clip_The_Shining-ref288.mkv",
}
# mean synthesis amplitude vs source truth, from FINDINGS-2026-08-02-LEAK-CLOSURE
SYNTH = {"Casino": (0.889, 0.959), "Interstellar": (0.914, 0.993),
         "Scarface": (0.956, 1.001), "Taxi_Driver": (0.874, 0.956),
         "The_Deer_Hunter": (0.835, 0.902), "The_Shining": (0.892, 0.942)}


def run_vmaf(ref, enc, tag):
    feat = os.path.join(WORK, f"vmaf-{tag}.json")
    models = {"vmaf": "version=vmaf_4k_v0.6.1", "vmaf_neg": "version=vmaf_4k_v0.6.1neg"}
    rp, dp = os.path.join(WORK, f"rp-{tag}"), os.path.join(WORK, f"dp-{tag}")
    q = shlex.quote
    margs = " ".join(f"--model {q(s + ':name=' + k)}" for k, s in models.items())
    cmd = (
        f"rm -f {q(rp)} {q(dp)}; mkfifo {q(rp)} {q(dp)} || exit 1; "
        f"ffmpeg -v error -nostdin -i {q(ref)} -frames:v {FRAMES} -pix_fmt yuv420p10le -strict -1 -f yuv4mpegpipe -y {q(rp)} >/dev/null 2>&1 & w1=$!; "
        f"ffmpeg -v error -nostdin -c:v libdav1d -i {q(enc)} -frames:v {FRAMES} -pix_fmt yuv420p10le -strict -1 -f yuv4mpegpipe -y {q(dp)} >/dev/null 2>&1 & w2=$!; "
        f"{q(VMAF)} --reference {q(rp)} --distorted {q(dp)} --gpumask 0 {margs} "
        f"--feature psnr_cuda --feature ssim_cuda --feature ciede_cuda --json --output {q(feat)}; st=$?; "
        f"kill $w1 $w2 2>/dev/null; wait 2>/dev/null; rm -f {q(rp)} {q(dp)}; exit $st")
    if not os.path.isfile(feat):
        try:
            shell(cmd, timeout=3600)
        except Exception:
            shell(cmd, timeout=3600)
    doc = json.load(open(feat))
    for k in models:
        if any(f["metrics"].get(k) is None for f in doc["frames"]):
            raise RuntimeError(f"{tag}: null frames -- bad vmaf build")
    return doc["pooled_metrics"]


def main():
    os.makedirs(WORK, exist_ok=True)
    rows = []
    for title, srcname in SOURCES.items():
        ref = os.path.join(SRC, srcname)
        for arm, path in (("pre", os.path.join(PRE, f"{title}-motion_on.mkv")),
                          ("post", os.path.join(POST, f"{title}-q29.mkv"))):
            if not os.path.isfile(path):
                print(f"MISSING {path}", flush=True)
                continue
            fm = run_vmaf(ref, path, f"{title}-{arm}")
            row = dict(title=title, arm=arm,
                       synth=SYNTH[title][0 if arm == "pre" else 1],
                       vmaf=round(fm["vmaf"]["mean"], 3),
                       vmaf_neg=round(fm["vmaf_neg"]["mean"], 3),
                       psnr_y=round(fm["psnr_y"]["mean"], 3),
                       ssim=round(fm["float_ssim"]["mean"], 5),
                       ciede=round(fm["ciede2000"]["mean"], 3),
                       bytes=os.path.getsize(path))
            rows.append(row)
            print(json.dumps(row), flush=True)
    json.dump(rows, open(os.path.join(WORK, "scores.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
