#!/usr/bin/env python3
"""Per-scene target-quality encoding with NVEncC --dynamic-rc zones (experiment).

Av1an-style target quality, but without chunked encoding: an analysis pass picks
one QVBR per scene, then ONE continuous NVEncC encode applies the schedule with
`--dynamic-rc start=S,end=E,qvbr=Q`, keeping the film-grain analyzer, lookahead
and GOP state continuous.

Pipeline (stages are cached in the work dir):
  1. scenes   ffmpeg scene detection -> merge < 2 s, cap > 10 s          scenes.json
  2. base     NVEncC `--codec raw` with the production args = the denoised
              base picture the encoder is fed (grain-free reference)      base.mkv (ffv1)
  3. probes   one `--trim` run per probe QVBR over a short sample of every
              scene; decoded WITHOUT film-grain synthesis and scored per
              frame (VMAF) against the matching base frames              probe_q*.json
  4. plan     per-scene QVBR that just reaches the target (interpolated, clamped
              to [20, 40]); target auto-picked so predicted size == fixed QVBR N
  5. final    single encode with the zones                               final.mkv
  6. score    per-scene scores (grain-aware + standard vs original)       score-<tag>.json

Usage:
  target_quality.py run  --src CLIP --work DIR [--match-qvbr 30 | --target 93.5]
  target_quality.py fixed --src CLIP --work DIR --qvbr 28
  target_quality.py score --src CLIP --work DIR --tag final [--tag q30 ...]
Requires the tdarr-node container (nvencc) and the campaign.py scoring tools.
Pure helpers (merge_scenes, solve_qvbr, predict_size, pick_target, zone_args)
are covered by test_target_quality.py.
"""
import argparse
import json
import math
import os
import re
import shlex
import shutil
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

NODE = "tdarr-node"
HOST_TEMP = "/tmp/downloads/tdarr-temp/"
NODE_TEMP = "/temp/"
MAX_BITRATE = 50000
Q_MIN, Q_MAX = 20.0, 40.0

BASE_ARGS = ["--avsw", "--output-depth", "10", "--max-bitrate", str(MAX_BITRATE), "--preset", "quality",
             "--tune", "hq", "--lookahead", "32", "--lookahead-level", "3", "--aq", "--aq-temporal",
             "--av1-film-grain", "denoise=auto,chroma=auto,denoiser=bilateral"]


# ---------------------------------------------------------------- pure helpers
def merge_scenes(cuts, total, fps, min_s=2.0, max_s=10.0):
    """cuts: sorted frame indices where a new scene starts. Returns [(start, end_exclusive)].

    Scenes shorter than min_s are merged into the shorter neighbour (shortest
    first); scenes longer than max_s are then split into equal parts <= max_s.
    """
    min_len, max_len = int(round(min_s * fps)), int(round(max_s * fps))
    bounds = sorted({c for c in cuts if 0 < c < total})
    edges = [0] + bounds + [total]
    scenes = [[edges[i], edges[i + 1]] for i in range(len(edges) - 1)]
    while len(scenes) > 1:
        i = min(range(len(scenes)), key=lambda k: scenes[k][1] - scenes[k][0])
        if scenes[i][1] - scenes[i][0] >= min_len:
            break
        if i == 0:
            j = 1
        elif i == len(scenes) - 1:
            j = i - 1
        else:
            left, right = scenes[i - 1], scenes[i + 1]
            j = i - 1 if (left[1] - left[0]) <= (right[1] - right[0]) else i + 1
        a, b = sorted((i, j))
        scenes[a] = [scenes[a][0], scenes[b][1]]
        del scenes[b]
    out = []
    for s, e in scenes:
        n = max(1, math.ceil((e - s) / max_len))
        step = (e - s) / n
        pts = [s + int(round(step * k)) for k in range(n)] + [e]
        out += [(pts[k], pts[k + 1]) for k in range(n)]
    return out


def sample_range(start, end, n):
    """Representative sub-sample of a scene: whole scene, or n frames from its middle."""
    if end - start <= n:
        return start, end
    s = start + (end - start - n) // 2
    return s, s + n


def solve_qvbr(points, target, lo=Q_MIN, hi=Q_MAX, step=0.5):
    """points: [(qvbr, score)]. Highest QVBR whose score still reaches target.

    Scores are forced monotone non-increasing in qvbr, interpolated piecewise
    linearly and extrapolated with the end slopes; clamped to [lo, hi] and
    snapped to `step`.
    """
    pts = sorted(points)
    qs = [p[0] for p in pts]
    ss = []
    for _, s in pts:
        ss.append(min(s, ss[-1]) if ss else s)
    if target >= ss[0]:
        # even the lowest probed QVBR misses the target: extrapolate downward
        slope = (ss[1] - ss[0]) / (qs[1] - qs[0]) if len(qs) > 1 else 0.0
        q = lo if slope >= -1e-9 else qs[0] + (target - ss[0]) / slope
    elif target <= ss[-1]:
        slope = (ss[-1] - ss[-2]) / (qs[-1] - qs[-2]) if len(qs) > 1 else 0.0
        q = hi if slope >= -1e-9 else qs[-1] + (target - ss[-1]) / slope
    else:
        q = qs[-1]
        for k in range(len(qs) - 1):
            if ss[k] >= target >= ss[k + 1]:
                if ss[k] == ss[k + 1]:
                    q = qs[k + 1]
                else:
                    q = qs[k] + (ss[k] - target) / (ss[k] - ss[k + 1]) * (qs[k + 1] - qs[k])
                break
    q = min(hi, max(lo, q))
    return round(q / step) * step


def predict_size(points, q):
    """points: [(qvbr, bytes_per_frame)] -> log-linear interpolation/extrapolation."""
    pts = sorted(points)
    if len(pts) == 1:
        return pts[0][1]
    if q <= pts[0][0]:
        a, b = pts[0], pts[1]
    elif q >= pts[-1][0]:
        a, b = pts[-2], pts[-1]
    else:
        a, b = next((pts[k], pts[k + 1]) for k in range(len(pts) - 1) if pts[k][0] <= q <= pts[k + 1][0])
    la, lb = math.log(max(a[1], 1.0)), math.log(max(b[1], 1.0))
    return math.exp(la + (lb - la) * (q - a[0]) / (b[0] - a[0]))


def plan_for_target(scenes, target):
    """scenes: dicts with len, score_pts, size_pts -> (qvbrs, predicted total bytes)."""
    qs = [solve_qvbr(s["score_pts"], target) for s in scenes]
    return qs, sum(s["len"] * predict_size(s["size_pts"], q) for s, q in zip(scenes, qs))


def pick_target(scenes, match_qvbr, lo=60.0, hi=100.0):
    """Bisect the score target so predicted total size equals the fixed-QVBR size."""
    want = sum(s["len"] * predict_size(s["size_pts"], match_qvbr) for s in scenes)
    for _ in range(40):
        mid = (lo + hi) / 2
        _, size = plan_for_target(scenes, mid)
        if size > want:   # too many bits: lower the target
            hi = mid
        else:
            lo = mid
    return round((lo + hi) / 2, 3), want


def zone_args(scenes, qvbrs, default_q, max_bitrate=MAX_BITRATE):
    """--dynamic-rc args (inclusive input frame ranges). Scenes at default_q need no zone."""
    out = []
    for (s, e), q in zip(scenes, qvbrs):
        if abs(q - default_q) < 1e-9:
            continue
        out += ["--dynamic-rc", f"start={s},end={e - 1},qvbr={q:g},max-bitrate={max_bitrate}"]
    return out


def trim_arg(ranges):
    return ",".join(f"{s}:{e - 1}" for s, e in ranges)


def pctl(vals, p):
    v = sorted(vals)
    return v[min(len(v) - 1, max(0, int(len(v) * p / 100.0)))]


def summarize(per_scene):
    """per_scene: list of per-scene mean scores -> worst / p10 / mean."""
    return {"worst": round(min(per_scene), 2), "p10": round(pctl(per_scene, 10), 2),
            "mean": round(statistics.mean(per_scene), 2)}


# ----------------------------------------------------------------- tool helpers
def cpath(p):
    return NODE_TEMP + p[len(HOST_TEMP):] if p.startswith(HOST_TEMP) else p


def sh(cmd, timeout=7200):
    r = subprocess.run(["bash", "-o", "pipefail", "-c", cmd], capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError(f"failed ({r.returncode}): {cmd[:300]}\n{r.stderr[-1500:]}")
    return r


def gpu_wait(min_free_mib=6144, timeout=1800):
    t0 = time.time()
    while True:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True).stdout.split()
        if out and int(out[0]) >= min_free_mib:
            return
        if time.time() - t0 > timeout:
            raise RuntimeError("GPU VRAM stayed below threshold")
        time.sleep(20)


def nvencc_cmd(args):
    return "docker exec %s nvencc %s" % (NODE, " ".join(shlex.quote(cpath(a)) for a in args))


def run_nvencc(args, log=None):
    gpu_wait()
    t0 = time.time()
    r = sh(nvencc_cmd(args))
    if log:
        open(log, "w").write(r.stdout[-6000:] + r.stderr[-2000:])
    return time.time() - t0


def probe_info(path):
    r = sh(f"ffprobe -v error -select_streams v:0 -count_packets -show_entries "
           f"stream=avg_frame_rate,nb_read_packets -of json {shlex.quote(path)}")
    st = json.loads(r.stdout)["streams"][0]
    n, d = st["avg_frame_rate"].split("/")
    return float(n) / float(d), int(st["nb_read_packets"])


def packet_sizes(path):
    r = sh(f"ffprobe -v error -select_streams v:0 -show_entries packet=size,pts_time -of csv=p=0 {shlex.quote(path)}")
    rows = [l.split(",") for l in r.stdout.split() if l]
    rows.sort(key=lambda x: float(x[0]))   # presentation order
    return [int(x[1]) for x in rows]


# --------------------------------------------------------------------- stages
def detect_scenes(clip, fps, total, thr=0.3):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", clip, "-an", "-vf",
                        f"scale=480:-2,select='gt(scene,{thr})',showinfo", "-f", "null", "-"],
                       capture_output=True, text=True)
    cuts = [int(round(float(m) * fps)) for m in re.findall(r"pts_time:([\d.]+)", r.stderr)]
    return merge_scenes(cuts, total, fps), len(cuts)


def make_base(clip, work):
    base = os.path.join(work, "base.mkv")
    if os.path.exists(base):
        return base, 0.0
    gpu_wait()
    t0 = time.time()
    sh(nvencc_cmd(["-i", clip] + BASE_ARGS + ["--codec", "raw", "-o", "-"]) +
       f" | ffmpeg -v error -y -strict -1 -i - -c:v ffv1 -level 3 -slices 16 -g 1 {shlex.quote(base + '.part.mkv')}"
       f" && mv {shlex.quote(base + '.part.mkv')} {shlex.quote(base)}")
    return base, time.time() - t0


def vmaf_frames(ref_path, dist_path, out_json, select_ranges=None, nframes=None):
    """Per-frame VMAF + PSNR of `dist` decoded WITHOUT film-grain synthesis vs `ref` (grain-free base)."""
    import campaign
    if os.path.exists(out_json):
        return json.load(open(out_json))
    q = shlex.quote
    d = os.path.dirname(out_json)
    rp, dp = os.path.join(d, "rp.fifo"), os.path.join(d, "dp.fifo")
    vf = ""
    if select_ranges:
        expr = "+".join(f"between(n\\,{s}\\,{e - 1})" for s, e in select_ranges)
        vf = f"-vf {q('select=' + chr(39) + expr + chr(39) + ',setpts=N/FRAME_RATE/TB')}"
    cmd = (f"rm -f {q(rp)} {q(dp)}; mkfifo {q(rp)} {q(dp)} || exit 1; "
           f"ffmpeg -v error -i {q(ref_path)} {vf} -pix_fmt yuv420p10le -strict -1 -f yuv4mpegpipe -y {q(rp)} >/dev/null 2>&1 & w1=$!; "
           f"ffmpeg -v error -c:v libdav1d -export_side_data film_grain -i {q(dist_path)} -pix_fmt yuv420p10le -strict -1 "
           f"-f yuv4mpegpipe -y {q(dp)} >/dev/null 2>&1 & w2=$!; "
           f"{q(campaign.VMAF)} --reference {q(rp)} --distorted {q(dp)} --gpumask 0 --model "
           f"{q('version=vmaf_v0.6.1:name=vmaf')} --feature psnr_cuda --json --output {q(out_json)}; st=$?; "
           f"kill $w1 $w2 2>/dev/null; wait 2>/dev/null; rm -f {q(rp)} {q(dp)}; exit $st")
    gpu_wait()
    sh(cmd, timeout=1800)
    doc = json.load(open(out_json))
    if any(f["metrics"].get("vmaf") is None for f in doc["frames"]):
        os.remove(out_json)
        raise RuntimeError("null vmaf frames: wrong VMAF build?")
    return doc


def frame_series(doc, key="vmaf"):
    return [f["metrics"][key] for f in sorted(doc["frames"], key=lambda f: f["frameNum"])]


def probe_stage(clip, base, work, scenes, qvbrs, probe_frames):
    ranges = [sample_range(s, e, probe_frames) for s, e in scenes]
    lens = [e - s for s, e in ranges]
    res = {"ranges": ranges, "times": {}, "scores": {}, "bytes_per_frame": {}}
    for q in qvbrs:
        enc = os.path.join(work, f"probe_q{q:g}.mkv")
        if not os.path.exists(enc):
            res["times"][f"encode_q{q:g}"] = run_nvencc(
                ["-i", clip, "--trim", trim_arg(ranges)] + BASE_ARGS + ["--codec", "av1", "--qvbr", f"{q:g}", "-o", enc],
                os.path.join(work, f"probe_q{q:g}.log"))
        t0 = time.time()
        doc = vmaf_frames(base, enc, os.path.join(work, f"probe_q{q:g}.json"), select_ranges=ranges)
        res["times"][f"score_q{q:g}"] = time.time() - t0
        v, sizes = frame_series(doc), packet_sizes(enc)
        if len(v) != sum(lens) or len(sizes) != sum(lens):
            raise RuntimeError(f"probe q{q:g}: frame count {len(v)}/{len(sizes)} != {sum(lens)}")
        o, sc, bp = 0, [], []
        for n in lens:
            sc.append(statistics.mean(v[o:o + n]))
            bp.append(sum(sizes[o:o + n]) / n)
            o += n
        res["scores"][q], res["bytes_per_frame"][q] = sc, bp
    return res


def build_plan(scenes, probes, qvbrs, match_qvbr, target):
    sc = [{"len": e - s, "score_pts": [(q, probes["scores"][q][i]) for q in qvbrs],
           "size_pts": [(q, probes["bytes_per_frame"][q][i]) for q in qvbrs]} for i, (s, e) in enumerate(scenes)]
    want = None
    if target is None:
        target, want = pick_target(sc, match_qvbr)
    q_sel, pred = plan_for_target(sc, target)
    return {"target": target, "qvbrs": q_sel, "predicted_bytes": pred, "predicted_fixed_bytes": want}


def final_encode(clip, work, scenes, qvbrs, default_q, out, tag):
    args = ["-i", clip] + BASE_ARGS + ["--codec", "av1", "--qvbr", f"{default_q:g}"]
    if qvbrs:
        args += zone_args(scenes, qvbrs, default_q)
    args += ["-o", out]
    t = run_nvencc(args, os.path.join(work, f"{tag}.log"))
    return t, args


def score_encode(clip, base, work, scenes, tag, height=1080):
    """Per-scene scores: grain-aware (no-grain decode vs base) and standard (vs original)."""
    import campaign
    enc = os.path.join(work, f"{tag}.mkv")
    d = os.path.join(work, f"score-{tag}")
    os.makedirs(d, exist_ok=True)
    for src, name in ((clip, "ref.mkv"), (enc, "enc.mkv")):
        dst = os.path.join(d, name)
        if not os.path.exists(dst):
            try:
                os.link(src, dst)
            except OSError:   # protected_hardlinks: files written by the container are root-owned
                shutil.copyfile(src, dst)
    nframes = scenes[-1][1]
    doc = vmaf_frames(base, enc, os.path.join(d, "grainaware.json"))
    ga = frame_series(doc)
    gpsnr = frame_series(doc, "psnr_y")
    camp = campaign.score(os.path.join(d, "ref.mkv"), os.path.join(d, "enc.mkv"), tag, d, height, nframes)
    vm = frame_series(json.load(open(os.path.join(d, f"metrics-cuda-{tag}.json"))), "vmaf")
    su = [x[0] for x in json.load(open(os.path.join(d, f"ssimu2-{tag}.json")))]
    sizes = packet_sizes(enc)
    series = {"ga_vmaf": ga, "ga_psnr": gpsnr, "vmaf": vm, "ssimu2": su}
    rep = {"tag": tag, "bytes": os.path.getsize(enc), "campaign": camp, "scenes": []}
    for i, (s, e) in enumerate(scenes):
        row = {"start": s, "end": e, "bytes": sum(sizes[s:e]), "mbps": round(sum(sizes[s:e]) * 8 / ((e - s) / 24) / 1e6, 3)}
        for k, v in series.items():
            row[k] = round(statistics.mean(v[s:e]), 3)
        rep["scenes"].append(row)
    rep["summary"] = {k: summarize([r[k] for r in rep["scenes"]]) for k in series}
    rep["frame_p1"] = {k: round(pctl(v, 1), 2) for k, v in series.items()}
    json.dump(rep, open(os.path.join(work, f"score-{tag}.json"), "w"), indent=1)
    return rep


def ensure_clip(args):
    if args.start is None:
        return args.src
    clip = os.path.join(args.work, "clip.mkv")
    if not os.path.exists(clip):
        sh(f"ffmpeg -v error -y -ss {args.start} -t {args.seconds} -i {shlex.quote(args.src)} -map 0:v:0 -c copy {shlex.quote(clip)}")
    return clip


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["run", "fixed", "score"])
    ap.add_argument("--src", required=True)
    ap.add_argument("--work", required=True, help="must be under " + HOST_TEMP)
    ap.add_argument("--start", type=float)
    ap.add_argument("--seconds", type=float, default=300)
    ap.add_argument("--probe-qvbrs", default="24,30,36")
    ap.add_argument("--probe-frames", type=int, default=48)
    ap.add_argument("--match-qvbr", type=float, default=30.0, help="pick target so predicted size equals this fixed QVBR")
    ap.add_argument("--target", type=float, help="explicit grain-aware VMAF target (overrides --match-qvbr)")
    ap.add_argument("--default-qvbr", type=float, default=30.0)
    ap.add_argument("--qvbr", type=float, help="fixed")
    ap.add_argument("--tag", action="append")
    ap.add_argument("--scene-threshold", type=float, default=0.3)
    args = ap.parse_args()
    os.makedirs(args.work, exist_ok=True)
    clip = ensure_clip(args)
    fps, total = probe_info(clip)
    times = {}
    sp = os.path.join(args.work, "scenes.json")
    if os.path.exists(sp):
        scenes = [tuple(x) for x in json.load(open(sp))["scenes"]]
    else:
        t0 = time.time()
        scenes, ncuts = detect_scenes(clip, fps, total, args.scene_threshold)
        times["scene_detect"] = time.time() - t0
        json.dump({"scenes": scenes, "raw_cuts": ncuts, "fps": fps, "frames": total, "t": times["scene_detect"]}, open(sp, "w"))
    if args.cmd == "fixed":
        out = os.path.join(args.work, f"q{args.qvbr:g}.mkv")
        t, _ = final_encode(clip, args.work, scenes, None, args.qvbr, out, f"q{args.qvbr:g}")
        json.dump({"qvbr": args.qvbr, "encode_s": t, "bytes": os.path.getsize(out)}, open(os.path.join(args.work, f"q{args.qvbr:g}.time.json"), "w"))
        print(f"fixed q{args.qvbr:g}: {t:.0f}s {os.path.getsize(out) / 1e6:.1f} MB")
        return
    base, times["base"] = make_base(clip, args.work)
    if args.cmd == "score":
        for tag in args.tag:
            r = score_encode(clip, base, args.work, scenes, tag)
            print(tag, r["bytes"], json.dumps(r["summary"]))
        return
    qvbrs = [float(x) for x in args.probe_qvbrs.split(",")]
    probes = probe_stage(clip, base, args.work, scenes, qvbrs, args.probe_frames)
    plan = build_plan(scenes, probes, qvbrs, args.match_qvbr, args.target)
    tag = "final" if args.target is None else f"final_t{args.target:g}"
    out = os.path.join(args.work, f"{tag}.mkv")
    t, enc_args = final_encode(clip, args.work, scenes, plan["qvbrs"], args.default_qvbr, out, tag)
    report = {"clip": clip, "fps": fps, "frames": total, "scenes": [
        {"start": s, "end": e, "qvbr": plan["qvbrs"][i],
         "probe_vmaf": {f"{q:g}": round(probes["scores"][q][i], 2) for q in qvbrs},
         "probe_bytes_per_frame": {f"{q:g}": round(probes["bytes_per_frame"][q][i]) for q in qvbrs}}
        for i, (s, e) in enumerate(scenes)],
        "target": plan["target"], "predicted_bytes": plan["predicted_bytes"],
        "predicted_fixed_bytes": plan["predicted_fixed_bytes"], "final_bytes": os.path.getsize(out),
        "final_args": enc_args, "times": dict(times, probes=probes["times"], final_encode=t)}
    json.dump(report, open(os.path.join(args.work, f"report-{tag}.json"), "w"), indent=1)
    print(f"target {plan['target']} final {os.path.getsize(out) / 1e6:.1f} MB (predicted {plan['predicted_bytes'] / 1e6:.1f}) encode {t:.0f}s")


if __name__ == "__main__":
    main()
