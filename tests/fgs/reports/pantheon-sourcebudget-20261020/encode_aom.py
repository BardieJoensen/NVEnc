#!/usr/bin/env python3
"""Bounded libaom two-pass source-budget experiment (previewable, no sweep)."""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path(os.environ.get("PANTHEON_SOURCEBUDGET_ROOT", "/tmp/downloads/codex-work/pantheon-sourcebudget-20261020"))
CASE = "e05-1440"
FIXTURE = ROOT / "fixtures" / CASE
WORKER = ROOT / "worker"
FFMPEG = Path("/usr/bin/ffmpeg")
FFPROBE = Path("/usr/bin/ffprobe")
ACTIVE_RECEIPT = None
ACTIVE_RUN = None
EXPECTED_INPUT_SHA = "232abb5ffee869be4bedf682aa103c166eb473bb3fdad5daf28956cca60148d4"

def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()

def utc(): return dt.datetime.now(dt.timezone.utc).isoformat()

def capture(argv, cwd=None):
    p = subprocess.run(argv, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return {"argv": argv, "returncode": p.returncode, "stdout": p.stdout, "stderr": p.stderr}

def probe(path: Path, packets=False):
    args = [str(FFPROBE), "-v", "error", "-select_streams", "v:0"]
    args += ["-show_packets", "-show_entries", "packet=pts_time,dts_time,size,flags"] if packets else ["-show_streams", "-show_format"]
    r = capture(args + ["-of", "json", str(path)])
    if r["returncode"]: raise RuntimeError(f"ffprobe failed: {r['stderr']}")
    return json.loads(r["stdout"] or "{}")

def linked_libaom():
    r = capture(["ldd", str(FFMPEG)])
    paths = re.findall(r"(\/[^ ]*libaom\.so[^ ]*)", r["stdout"])
    exact = Path("/usr/lib/x86_64-linux-gnu/libaom.so.3.8.2")
    if not exact.is_file(): raise RuntimeError("installed libaom 3.8.2 is missing")
    if r["returncode"] or not paths or any(Path(p).resolve() != exact for p in paths):
        raise RuntimeError(f"unexpected linked libaom paths: {paths}")
    out = {p: {"sha256": sha(Path(p)) if Path(p).is_file() else None} for p in paths}
    out[str(exact)] = {"sha256": sha(exact), "version": "3.8.2"}
    return out

def main():
    global ACTIVE_RECEIPT, ACTIVE_RUN
    ap = argparse.ArgumentParser()
    ap.add_argument("case", choices=[CASE]); ap.add_argument("tag"); ap.add_argument("request_kbps", type=int)
    ap.add_argument("--tune", choices=["ssim", "psnr"], default="ssim")
    ap.add_argument("--preview", action="store_true", help="write command preview and exit without encoding")
    a = ap.parse_args()
    if a.request_kbps <= 0 or not re.fullmatch(r"[A-Za-z0-9_.-]+", a.tag): ap.error("invalid tag or bitrate")
    validity = json.loads((FIXTURE / "validity.json").read_text())
    source = float(validity["source_mbps"]); fps = float(validity["fps"])
    inp = FIXTURE / "input10.y4m"
    run = WORKER / "runs" / CASE / ("aom-" + a.tag)
    run.mkdir(parents=True, exist_ok=False)
    ACTIVE_RUN = run
    if sha(inp) != EXPECTED_INPUT_SHA: raise RuntimeError("fixture input SHA is not the historical 336-frame input")
    shutil.copy2(Path(__file__).resolve(), run / "measured-runner.py")
    script_sha = sha(run / "measured-runner.py")
    ffv = capture([str(FFMPEG), "-version"])
    av = capture([str(FFMPEG), "-hide_banner", "-encoders"])
    if "libaom-av1" not in av["stdout"]: raise RuntimeError("/usr/bin/ffmpeg lacks libaom-av1")
    stats = run / "aom-pass.log"
    ivf = run / "out.ivf"
    common = ["nice", "-n", "10", "taskset", "-c", "0-7", str(FFMPEG), "-hide_banner", "-loglevel", "verbose", "-y", "-f", "yuv4mpegpipe",
              "-i", str(inp), "-frames:v", "336", "-c:v", "libaom-av1", "-pix_fmt", "yuv420p10le",
              "-usage", "good", "-cpu-used", "4", "-threads", "4", "-row-mt", "1", "-tiles", "1x1",
              "-tune", a.tune, "-aq-mode", "variance", "-denoise-noise-level", "0", "-auto-alt-ref", "1",
              "-arnr-strength", "0", "-lag-in-frames", "25", "-g", "161", "-color_range", "tv",
              "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-b:v", f"{a.request_kbps}k"]
    pass1 = common + ["-pass", "1", "-passlogfile", str(stats), "-f", "null", "/dev/null"]
    pass2 = common + ["-pass", "2", "-passlogfile", str(stats), "-f", "ivf", str(ivf)]
    receipt = {"status": "prepared", "case": CASE, "tag": run.name, "encoder_stack": "libaom-3.8.2-ffmpeg", "created_utc": utc(),
               "request_kbps": a.request_kbps, "source_mbps": source, "target_99_5_mbps": source*.995,
               "input": {"path": str(inp), "sha256": sha(inp)}, "expected_input_sha256": EXPECTED_INPUT_SHA,
               "ffmpeg": {"path": str(FFMPEG), "sha256": sha(FFMPEG), "version": ffv, "linked_libaom": linked_libaom()},
               "validity": {"path": str(FIXTURE/"validity.json"), "sha256": sha(FIXTURE/"validity.json"), "source_mbps": source, "fps": fps},
               "historical_input_validation": {"path": str(FIXTURE/"historical-input-validation.json"), "sha256": sha(FIXTURE/"historical-input-validation.json")},
               "script": {"path": str(run / "measured-runner.py"), "sha256": script_sha},
               "executed_source": str(Path(__file__).resolve()),
               "ffprobe": {"path": str(FFPROBE), "sha256": sha(FFPROBE), "version": capture([str(FFPROBE), "-version"])},
               "commands": {"pass1": pass1, "pass2": pass2}, "settings": {
                   "usage": "good", "cpu_used": 4, "threads": 4, "row_mt": 1, "tiles": "1x1",
                   "tune": a.tune, "aq_mode": "variance", "denoise_noise_level": 0,
                   "auto_alt_ref": 1, "arnr_strength": 0, "lag_in_frames": 25, "g": 161,
                   "film_grain": "not requested"}}
    ACTIVE_RECEIPT = receipt
    (run / "command.json").write_text(json.dumps(receipt, indent=2) + "\n")
    if a.preview: print(json.dumps(receipt, indent=2)); return 0
    env = {k:v for k,v in os.environ.items() if not k.startswith("PANTHEON_")}
    logs = {}
    start = time.monotonic()
    for n, cmd in (("pass1", pass1), ("pass2", pass2)):
        before = {str(p): sha(p) for p in run.glob("aom-pass*") if p.is_file()}
        receipt["status"] = n + "_running"
        (run / "command.json").write_text(json.dumps(receipt, indent=2) + "\n")
        t = time.monotonic()
        with (run / f"{n}.log").open("w") as log:
            r = subprocess.run(cmd, cwd=run, env=env, stdout=log, stderr=subprocess.STDOUT, check=False)
        elapsed = time.monotonic()-t
        after = {str(p): sha(p) for p in run.glob("aom-pass*") if p.is_file()}
        logs[n] = {"returncode": r.returncode, "seconds": elapsed, "before_stats": before, "after_stats": after,
                   "log": {"path":str(run / f"{n}.log"),"sha256":sha(run / f"{n}.log")},
                   "stats_sizes": {p: Path(p).stat().st_size for p in after}}
        receipt["passes"] = logs; receipt["status"] = n + ("_failed" if r.returncode else "_complete")
        (run / "command.json").write_text(json.dumps(receipt, indent=2) + "\n")
        if r.returncode: raise RuntimeError(f"{n} failed; see {run}/{n}.log")
        expected_stats = stats.with_name(stats.name + "-0.log")
        if n == "pass1" and (not expected_stats.is_file() or expected_stats.stat().st_size == 0): raise RuntimeError(f"missing nonempty expected stats file {expected_stats}")
        if n == "pass1":
            snap = run / "pass1-stats.snapshot"
            shutil.copy2(expected_stats, snap)
            logs[n]["pass1_stats_snapshot"] = {"path": str(snap), "sha256": sha(snap), "size": snap.stat().st_size}
        if n == "pass2" and (before != after or sha(expected_stats) != logs["pass1"]["pass1_stats_snapshot"]["sha256"]): raise RuntimeError("pass2 changed pass1 stats")
        (run / "command.json").write_text(json.dumps(receipt, indent=2) + "\n")
    receipt["status"] = "validating"
    (run / "command.json").write_text(json.dumps(receipt, indent=2) + "\n")
    mkv = run / "out.mkv"
    r = capture(["/usr/bin/ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(ivf), "-c", "copy", str(mkv)])
    if r["returncode"]: raise RuntimeError("IVF to MKV remux failed")
    istream = probe(ivf).get("streams", [{}])[0]; mstream = probe(mkv).get("streams", [{}])[0]
    for s in (istream, mstream):
        if (s.get("codec_name"), s.get("width"), s.get("height"), s.get("pix_fmt")) != ("av1", 1920, 1080, "yuv420p10le") or any(s.get(k) not in (v, str(v)) for k,v in (("color_space","bt709"),("color_transfer","bt709"),("color_primaries","bt709"),("color_range","tv"))):
            raise RuntimeError(f"unexpected stream metadata: {s}")
    ip = probe(ivf, True).get("packets", []); mp = probe(mkv, True).get("packets", [])
    ip.sort(key=lambda x: float(x["pts_time"])); mp.sort(key=lambda x: float(x["pts_time"]))
    if abs(float(ip[0]["pts_time"])) > 1e-6 or abs(float(mp[0]["pts_time"])) > 1e-6: raise RuntimeError("nonzero packet origin")
    if len(ip) != 336 or len(mp) != 336 or len({x["pts_time"] for x in mp}) != 336: raise RuntimeError("packet count/PTS uniqueness failure")
    if any(abs((float(b["pts_time"])-float(a["pts_time"])) - 1/fps) > 1e-6 for a,b in zip(ip,ip[1:])): raise RuntimeError("IVF cadence failure")
    if any(abs((float(p["pts_time"])-float(mp[0]["pts_time"]))*fps-i) >= .03 for i,p in enumerate(mp)): raise RuntimeError("MKV cadence failure")
    actual = sum(int(x["size"]) for x in mp[96:]) * 8 / (240/fps) / 1e6
    receipt.update({"status":"encoded" if source*.99 <= actual <= source else "rate_gate_failed", "returncode":0, "wall_seconds":sum(x["seconds"] for x in logs.values()), "validation_seconds":time.monotonic()-start-sum(x["seconds"] for x in logs.values()), "passes":logs,
                    "ivf_sha256":sha(ivf), "mkv_sha256":sha(mkv), "ivf_packets":ip, "mkv_packets":mp,
                    "mkv_output":{"path":str(mkv),"sha256":sha(mkv),"stream":mstream},
                    "packet_window":{"fps":fps,"selected_indices":[96,336],"selected_seconds":240/fps,"packet_count":336,
                                     "actual_mbps":actual,"source_mbps":source,"within_source_ceiling":actual<=source,
                                     "decisive_rate_gate":source*.99 <= actual <= source,
                                     "ivf_packets":ip,"mkv_packets":mp,
                                     "ivf_minus_mkv_packet_bytes":[int(a["size"])-int(b["size"]) for a,b in zip(ip,mp)]},
                    "ivf_actual_mbps":sum(int(x["size"]) for x in ip[96:]) * 8 / (240/fps) / 1e6,
                    "actual_mbps":actual, "within_cap":actual <= source, "within_99_floor":actual >= source*.99,
                    "decisive_rate_gate":source*.99 <= actual <= source})
    after_input_sha = sha(inp); receipt["input_after_sha256"] = after_input_sha
    if after_input_sha != receipt["input"]["sha256"]: raise RuntimeError("input changed during encode")
    (run / "packet-window.json").write_text(json.dumps(receipt["packet_window"], indent=2) + "\n")
    (run / "command.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return 0 if receipt["decisive_rate_gate"] else 1

if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as e:
        if ACTIVE_RECEIPT is not None:
            ACTIVE_RECEIPT.update(status="validation_failed", reason=str(e))
            (ACTIVE_RUN / "command.json").write_text(json.dumps(ACTIVE_RECEIPT, indent=2) + "\n")
        print(f"encode_aom.py: {e}", file=sys.stderr)
        raise
