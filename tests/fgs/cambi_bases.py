#!/usr/bin/env python3
"""CAMBI on the production and bilateral-source bases.

TESTING-SUITE.md lists CAMBI as a standing guard rail because banding is
invisible to every other instrument in the set.  The bilateral-source gate did
not run it, and it is the one change that specifically warrants it:
`kernel_fgs_level_compensate` deliberately adjusts the coded luma base near
black according to the signalled strength LUT, and a near-black level
adjustment on a dark gradient is exactly how banding is produced.

CAMBI is no-reference -- it scores the distorted input -- but libvmaf's CLI
requires a reference, so the source crop is passed and ignored.  It is a CPU
feature, so --threads is set per the standing rule; campaign.py passes none
because it only ever runs CUDA features.

Lower CAMBI is better (less banding).
"""
import json, os, shlex, statistics, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from review_score import VMAF, shell

PROD = "/media/merged-storage/media/test-encodes/sourcefit-integrated-20260803/quality-crops"
CAND = "/media/merged-storage/media/test-encodes/sourcefit-bilateral-quality-20260803/quality-crops"
WORK = "/media/merged-storage/media/test-encodes/cambi-bilateral-20260803"
TITLES = ["Casino", "Interstellar", "Scarface", "Taxi_Driver",
          "The_Deer_Hunter", "The_Shining"]


def cambi(ref, dist, tag):
    out = os.path.join(WORK, f"cambi-{tag}.json")
    rp, dp = os.path.join(WORK, f"rp-{tag}"), os.path.join(WORK, f"dp-{tag}")
    q = shlex.quote
    cmd = (
        f"rm -f {q(rp)} {q(dp)}; mkfifo {q(rp)} {q(dp)} || exit 1; "
        f"ffmpeg -v error -nostdin -i {q(ref)} -pix_fmt yuv420p10le -strict -1 -f yuv4mpegpipe -y {q(rp)} >/dev/null 2>&1 & w1=$!; "
        f"ffmpeg -v error -nostdin -i {q(dist)} -pix_fmt yuv420p10le -strict -1 -f yuv4mpegpipe -y {q(dp)} >/dev/null 2>&1 & w2=$!; "
        f"{q(VMAF)} --reference {q(rp)} --distorted {q(dp)} --no_prediction "
        f"--feature cambi --threads 16 --json --output {q(out)}; st=$?; "
        f"kill $w1 $w2 2>/dev/null; wait 2>/dev/null; rm -f {q(rp)} {q(dp)}; exit $st")
    if not os.path.isfile(out):
        shell(cmd, timeout=3600)
    doc = json.load(open(out))
    vals = [f["metrics"]["cambi"] for f in doc["frames"]
            if f["metrics"].get("cambi") is not None]
    if len(vals) != len(doc["frames"]):
        raise RuntimeError(f"{tag}: {len(doc['frames']) - len(vals)} null cambi frames")
    vals_sorted = sorted(vals)
    return {"mean": round(statistics.mean(vals), 5),
            "p95": round(vals_sorted[int(len(vals) * 0.95)], 5),
            "max": round(max(vals), 5),
            "frames": len(vals)}


def main():
    os.makedirs(WORK, exist_ok=True)
    rows = []
    for t in TITLES:
        ref = os.path.join(CAND, f"{t}-reference.mkv")
        for arm, path in (("production", os.path.join(PROD, f"{t}-production-base.mkv")),
                          ("bilateral-source", os.path.join(CAND, f"{t}-bilateral-source-base.mkv"))):
            if not os.path.isfile(path):
                print(f"MISSING {path}", flush=True)
                continue
            r = cambi(ref, path, f"{t}-{arm}")
            r.update(title=t, arm=arm)
            rows.append(r)
            print(json.dumps(r), flush=True)
    json.dump(rows, open(os.path.join(WORK, "cambi.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
