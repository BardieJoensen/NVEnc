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
EXPECTED_STATS_SHA = "aa3f8940549354587cd0f417108b257999f3f303871d397f3dbeb7dd1da55d81"
R3_RECEIPT = ROOT / "worker" / "runs" / CASE / "aom-psnr-1x2" / "command.json"
R3_REQUEST_KBPS = 11671
EXPECTED_R3_RECEIPT_SHA = "fc1fbfc56dd660ce46e99cc2ccf98ee8633dd09aff7976031dd8a1c036265bbb"

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
    ap.add_argument("case", choices=[CASE]); ap.add_argument("tag")
    ap.add_argument("--preview", action="store_true", help="write command preview and exit without encoding")
    a = ap.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", a.tag): ap.error("invalid tag")
    forbidden = {k: os.environ.get(k) for k in ("LD_PRELOAD", "LD_LIBRARY_PATH", "LD_AUDIT", "AOM_TU_TRACE_FD", "AOM_TRACE_PATH", "AOM_TRACE_FD", "AOM_NEUTRALIZE_SOURCE") if os.environ.get(k)}
    if forbidden: raise RuntimeError(f"forbidden dynamic/trace environment overrides before subprocess: {sorted(forbidden)}")
    if shutil.disk_usage(ROOT).free < 130 * (1 << 30): raise RuntimeError("less than 130 GiB free at preflight")
    if not R3_RECEIPT.is_file(): raise RuntimeError(f"missing bound R3 receipt: {R3_RECEIPT}")
    r3 = json.loads(R3_RECEIPT.read_text())
    if sha(R3_RECEIPT) != EXPECTED_R3_RECEIPT_SHA: raise RuntimeError("R3 receipt SHA drift")
    if not (r3.get("status") == "encoded" and r3.get("returncode") == 0 and r3.get("decisive_rate_gate") is True): raise RuntimeError("R3 receipt is not a successful decisive encoded control")
    if r3.get("request_kbps") != R3_REQUEST_KBPS: raise RuntimeError("R3 request receipt drift")
    validity = json.loads((FIXTURE / "validity.json").read_text())
    source = float(validity["source_mbps"]); fps = float(validity["fps"])
    inp = FIXTURE / "input10.y4m"
    run = ROOT / "worker" / "aom-qmax-r7" / "runs" / CASE / ("qmax-" + a.tag)
    run.mkdir(parents=True, exist_ok=False)
    ACTIVE_RUN = run
    ACTIVE_RECEIPT = {"status": "preflight_started", "case": CASE, "tag": run.name, "created_utc": utc(), "run": str(run)}
    (run / "command.json").write_text(json.dumps(ACTIVE_RECEIPT, indent=2) + "\n")
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
              "-tune", "psnr", "-aq-mode", "variance", "-denoise-noise-level", "0", "-auto-alt-ref", "1",
              "-arnr-strength", "0", "-lag-in-frames", "25", "-g", "161", "-qmin", "0", "-qmax", "8", "-color_range", "tv",
              "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-b:v", f"{R3_REQUEST_KBPS}k"]
    pass1 = common + ["-pass", "1", "-passlogfile", str(stats), "-f", "null", "/dev/null"]
    pass2 = common + ["-pass", "2", "-passlogfile", str(stats), "-f", "ivf", str(ivf)]
    def normalize(cmd):
        out = list(cmd)
        if "-qmin" in out or "-qmax" in out:
            raise RuntimeError("baseline command unexpectedly contains qmin/qmax")
        if "-passlogfile" not in out: raise RuntimeError("command lacks passlogfile")
        j = out.index("-passlogfile")
        out[j + 1] = "<STATS>"
        out[-1] = "<OUTPUT>" if out[-1] != "/dev/null" else out[-1]
        return out
    def candidate_without_q(cmd):
        out=[]; i=0; qmin=[]; qmax=[]
        while i < len(cmd):
            if cmd[i] in ("-qmin", "-qmax"):
                if i + 1 >= len(cmd): raise RuntimeError("truncated q bound")
                (qmin if cmd[i] == "-qmin" else qmax).append(cmd[i+1])
                i += 2; continue
            out.append(cmd[i]); i += 1
        if qmin != ["0"] or qmax != ["8"]: raise RuntimeError(f"candidate q bounds drift: qmin={qmin} qmax={qmax}")
        return normalize(out)
    expected_identity = {"ffmpeg_sha256": r3["ffmpeg"]["sha256"], "ffprobe_sha256": r3["ffprobe"]["sha256"], "linked_libaom": r3["ffmpeg"]["linked_libaom"], "validity_sha256": r3["validity"]["sha256"], "historical_input_sha256": r3["historical_input_validation"]["sha256"], "input_sha256": r3["input"]["sha256"], "r3_receipt_sha256": EXPECTED_R3_RECEIPT_SHA}
    def current_identity():
        return {"ffmpeg_sha256": sha(FFMPEG), "ffprobe_sha256": sha(FFPROBE), "linked_libaom": linked_libaom(), "validity_sha256": sha(FIXTURE / "validity.json"), "historical_input_sha256": sha(FIXTURE / "historical-input-validation.json"), "input_sha256": sha(inp), "r3_receipt_sha256": sha(R3_RECEIPT)}
    identity_start = current_identity()
    if identity_start != expected_identity: raise RuntimeError("installed/input/provenance identity differs from R3")
    receipt = {"status": "prepared", "case": CASE, "tag": run.name, "encoder_stack": "libaom-3.8.2-ffmpeg-qmax8-diagnostic", "created_utc": utc(),
               "request_kbps": R3_REQUEST_KBPS,
               "bound_r3_receipt": {"path": str(R3_RECEIPT), "sha256": sha(R3_RECEIPT), "expected_sha256": EXPECTED_R3_RECEIPT_SHA},
               "identity_start": identity_start, "expected_identity": expected_identity, "source_mbps": source, "target_99_5_mbps": source*.995,
               "input": {"path": str(inp), "sha256": sha(inp)}, "expected_input_sha256": EXPECTED_INPUT_SHA,
               "expected_pass1_stats_sha256": EXPECTED_STATS_SHA,
               "ffmpeg": {"path": str(FFMPEG), "sha256": sha(FFMPEG), "version": ffv, "linked_libaom": linked_libaom()},
               "validity": {"path": str(FIXTURE/"validity.json"), "sha256": sha(FIXTURE/"validity.json"), "source_mbps": source, "fps": fps},
               "historical_input_validation": {"path": str(FIXTURE/"historical-input-validation.json"), "sha256": sha(FIXTURE/"historical-input-validation.json")},
               "script": {"path": str(run / "measured-runner.py"), "sha256": script_sha},
               "executed_source": str(Path(__file__).resolve()),
               "ffprobe": {"path": str(FFPROBE), "sha256": sha(FFPROBE), "version": capture([str(FFPROBE), "-version"])},
               "commands": {"pass1": pass1, "pass2": pass2}, "settings": {
                   "usage": "good", "cpu_used": 4, "threads": 4, "row_mt": 1, "tiles": "1x1",
                   "tune": "psnr", "aq_mode": "variance", "qmin": 0, "qmax": 8, "denoise_noise_level": 0,
                   "auto_alt_ref": 1, "arnr_strength": 0, "lag_in_frames": 25, "g": 161,
                   "film_grain": "not requested", "scope": "unconstrained qmax mechanism diagnostic; not a matched practical candidate",
                   "practical_candidate": False, "matched_rate_claim": False}}
    r3cmd = r3.get("commands", {})
    for name, cmd in (("pass1", pass1), ("pass2", pass2)):
        if name not in r3cmd: raise RuntimeError(f"R3 receipt lacks {name} command")
        candidate = candidate_without_q(cmd)
        baseline = normalize(r3cmd[name])
        if candidate != baseline:
            raise RuntimeError(f"R3 command drift in {name}; only qmin/qmax and fresh paths may differ")
    receipt["command_binding"] = {"baseline": "R3 exact command after removing only qmin/qmax and canonicalizing output paths", "pass1_equal_except_qmax_paths": True, "pass2_equal_except_qmax_paths": True}
    receipt["environment_policy"] = {"forbidden_overrides": ["LD_PRELOAD", "LD_LIBRARY_PATH", "LD_AUDIT", "AOM_TU_TRACE_FD", "AOM_TRACE_PATH", "AOM_TRACE_FD", "AOM_NEUTRALIZE_SOURCE"], "observed_forbidden": sorted(forbidden), "trace_disabled": not bool(forbidden)}
    receipt["resource_preflight"] = {"free_bytes": shutil.disk_usage(ROOT).free, "minimum_free_bytes": 130 * (1 << 30)}
    ACTIVE_RECEIPT = receipt
    (run / "command.json").write_text(json.dumps(receipt, indent=2) + "\n")
    if a.preview: print(json.dumps(receipt, indent=2)); return 0
    forbidden = {k: os.environ.get(k) for k in ("LD_PRELOAD", "LD_LIBRARY_PATH", "LD_AUDIT", "AOM_TU_TRACE_FD", "AOM_TRACE_PATH", "AOM_TRACE_FD", "AOM_NEUTRALIZE_SOURCE") if os.environ.get(k)}
    receipt["environment_policy"] = {"forbidden_overrides": ["LD_PRELOAD", "LD_LIBRARY_PATH", "LD_AUDIT", "AOM_TU_TRACE_FD", "AOM_TRACE_PATH", "AOM_TRACE_FD", "AOM_NEUTRALIZE_SOURCE"], "observed_forbidden": sorted(forbidden)}
    (run / "command.json").write_text(json.dumps(receipt, indent=2) + "\n")
    if forbidden:
        raise RuntimeError(f"forbidden dynamic/trace environment overrides: {sorted(forbidden)}")
    env = {k:v for k,v in os.environ.items() if not k.startswith("PANTHEON_")}
    logs = {}
    start = time.monotonic()
    for n, cmd in (("pass1", pass1), ("pass2", pass2)):
        before = {str(p): sha(p) for p in run.glob("aom-pass*") if p.is_file()}
        receipt["status"] = n + "_running"
        (run / "command.json").write_text(json.dumps(receipt, indent=2) + "\n")
        pass_start_utc = utc(); t = time.monotonic()
        with (run / f"{n}.log").open("w") as log:
            r = subprocess.run(cmd, cwd=run, env=env, stdout=log, stderr=subprocess.STDOUT, check=False)
        elapsed = time.monotonic()-t; pass_end_utc = utc()
        after = {str(p): sha(p) for p in run.glob("aom-pass*") if p.is_file()}
        logs[n] = {"returncode": r.returncode, "seconds": elapsed, "start_utc": pass_start_utc, "end_utc": pass_end_utc, "before_stats": before, "after_stats": after,
                   "log": {"path":str(run / f"{n}.log"),"sha256":sha(run / f"{n}.log")},
                   "stats_sizes": {p: Path(p).stat().st_size for p in after}}
        receipt["passes"] = logs; receipt["status"] = n + ("_failed" if r.returncode else "_complete")
        (run / "command.json").write_text(json.dumps(receipt, indent=2) + "\n")
        if r.returncode: raise RuntimeError(f"{n} failed; see {run}/{n}.log")
        logs[n]["identity_after"] = current_identity()
        if logs[n]["identity_after"] != expected_identity: raise RuntimeError(f"identity changed after {n}")
        expected_stats = stats.with_name(stats.name + "-0.log")
        if n == "pass1" and (not expected_stats.is_file() or expected_stats.stat().st_size == 0): raise RuntimeError(f"missing nonempty expected stats file {expected_stats}")
        if n == "pass1":
            if sha(expected_stats) != EXPECTED_STATS_SHA:
                raise RuntimeError(f"pass1 stats SHA mismatch: expected {EXPECTED_STATS_SHA}, got {sha(expected_stats)}")
            snap = run / "pass1-stats.snapshot"
            shutil.copy2(expected_stats, snap)
            logs[n]["pass1_stats_snapshot"] = {"path": str(snap), "sha256": sha(snap), "size": snap.stat().st_size}
        if n == "pass2" and (before != after or sha(expected_stats) != EXPECTED_STATS_SHA or sha(expected_stats) != logs["pass1"]["pass1_stats_snapshot"]["sha256"]): raise RuntimeError("pass2 changed pass1 stats or failed expected baseline identity")
        (run / "command.json").write_text(json.dumps(receipt, indent=2) + "\n")
    receipt["status"] = "validating"
    (run / "command.json").write_text(json.dumps(receipt, indent=2) + "\n")
    mkv = run / "out.mkv"
    remux_cmd = ["/usr/bin/ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(ivf), "-c", "copy", str(mkv)]
    remux_t0 = time.monotonic(); r = capture(remux_cmd); remux_seconds = time.monotonic() - remux_t0
    (run / "remux.log").write_text(r["stdout"] + r["stderr"])
    receipt["remux"] = {"argv": remux_cmd, "returncode": r["returncode"], "seconds": remux_seconds, "log": {"path": str(run / "remux.log"), "sha256": sha(run / "remux.log")}}
    (run / "command.json").write_text(json.dumps(receipt, indent=2) + "\n")
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
    receipt.update({"status":"diagnostic_encoded", "returncode":0, "wall_seconds":sum(x["seconds"] for x in logs.values()), "validation_seconds":time.monotonic()-start-sum(x["seconds"] for x in logs.values()), "passes":logs,
                    "ivf_sha256":sha(ivf), "mkv_sha256":sha(mkv), "ivf_packets":ip, "mkv_packets":mp,
                    "remux":{"argv":remux_cmd,"returncode":r["returncode"],"seconds":remux_seconds,"log":{"path":str(run/"remux.log"),"sha256":sha(run/"remux.log")}},
                    "mkv_output":{"path":str(mkv),"sha256":sha(mkv),"stream":mstream},
                    "packet_window":{"fps":fps,"selected_indices":[96,336],"selected_seconds":240/fps,"packet_count":336,
                                     "actual_mbps":actual,"source_mbps":source,"within_source_ceiling":actual<=source,
                                     "decisive_rate_gate":source*.99 <= actual <= source,
                                     "ivf_packets":ip,"mkv_packets":mp,
                                     "ivf_minus_mkv_packet_bytes":[int(a["size"])-int(b["size"]) for a,b in zip(ip,mp)]},
                    "ivf_actual_mbps":sum(int(x["size"]) for x in ip[96:]) * 8 / (240/fps) / 1e6,
                    "full_window_rates": {"ivf_mbps": sum(int(x["size"]) for x in ip) * 8 / (336/fps) / 1e6, "mkv_mbps": sum(int(x["size"]) for x in mp) * 8 / (336/fps) / 1e6, "scored_ivf_mbps": sum(int(x["size"]) for x in ip[96:]) * 8 / (240/fps) / 1e6, "scored_mkv_mbps": actual},
                    "final_end_utc": utc(), "identity_final": current_identity(), "actual_mbps":actual, "within_cap":actual <= source, "within_99_floor":actual >= source*.99,
                    "rate_eligibility": {"within_cap": actual <= source, "within_99_floor": actual >= source*.99, "decisive_rate_gate": source*.99 <= actual <= source},
                    "decisive_rate_gate":source*.99 <= actual <= source, "practical_candidate": False})
    if receipt["identity_final"] != expected_identity: raise RuntimeError("final installed/input/provenance identity differs from R3")
    after_input_sha = sha(inp); receipt["input_after_sha256"] = after_input_sha
    if after_input_sha != receipt["input"]["sha256"]: raise RuntimeError("input changed during encode")
    (run / "packet-window.json").write_text(json.dumps(receipt["packet_window"], indent=2) + "\n")
    (run / "command.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return 0

if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as e:
        if ACTIVE_RECEIPT is not None:
            ACTIVE_RECEIPT.update(status="validation_failed", reason=str(e))
            (ACTIVE_RUN / "command.json").write_text(json.dumps(ACTIVE_RECEIPT, indent=2) + "\n")
        print(f"encode_aom.py: {e}", file=sys.stderr)
        raise
