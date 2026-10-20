#!/usr/bin/env python3
"""One fixed PSYEX policy, two-pass VBR; only requested bitrate may calibrate."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

ROOT = Path(os.environ.get("PANTHEON_SOURCEBUDGET_ROOT",
    "/tmp/downloads/codex-work/pantheon-sourcebudget-20261020"))
PSYROOT = ROOT / "worker/psyex-r8"
FIX = ROOT / "fixtures/e05-1440"
BUILD = PSYROOT / "build"
APP = BUILD / "bin/SvtAv1EncApp"
LIB = BUILD / "bin/libSvtAv1Enc.so.3.0.2"
INPUT_SHA = "232abb5ffee869be4bedf682aa103c166eb473bb3fdad5daf28956cca60148d4"
MANIFEST_SHA = "8cf0314d5ee329b662c32021020c8299ef47bb87681d87508328c1b28eeb5c69"
BUILD_RUNNER_SHA = "4cf939e20445e130970fdf09983a774e1f71adf1ea6240038cc557fe9ef66a7b"
APP_SHA = "f4867ae287fa34cc50f927b7aa52611973adbc7231785117e5d32ce077b2461c"
LIB_SHA = "cd408a2f31f871cf9da924dd943607e2b8aa2e5366e513fc82d959434414f20b"
POLICY = {
    "--preset": "4", "--tune": "0", "--psy-rd": "1.0", "--sharp-tx": "1",
    "--sharpness": "1", "--spy-rd": "0", "--hbd-mds": "1", "--complex-hvs": "0",
    "--noise-norm-strength": "1", "--noise-adaptive-filtering": "0",
    "--rc": "1", "--pred-struct": "2", "--keyint": "240", "--irefresh-type": "2",
    "--hierarchical-levels": "4", "--scd": "0", "--lp": "1",
    "--aq-mode": "2", "--enable-variance-boost": "1",
    "--variance-boost-strength": "2", "--variance-octile": "5", "--variance-boost-curve": "0",
    "--enable-qm": "1", "--qm-min": "4", "--qm-max": "15",
    "--chroma-qm-min": "10", "--chroma-qm-max": "15", "--qp-scale-compress-strength": "1",
    "--enable-tf": "1", "--tf-strength": "1", "--kf-tf-strength": "1",
    "--enable-overlays": "0", "--enable-dlf": "1", "--enable-cdef": "-1",
    "--enable-restoration": "-1", "--film-grain": "0", "--film-grain-denoise": "0",
    "--color-range": "0", "--color-primaries": "1", "--transfer-characteristics": "1",
    "--matrix-coefficients": "1", "--input-depth": "10", "--fps-num": "24",
    "--fps-denom": "1", "--progress": "0",
}

def sha(p):
    h = hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()

def ident(p):
    p = Path(p)
    return {"path": str(p), "sha256": sha(p), "size": p.stat().st_size}

def utc(): return dt.datetime.now(dt.timezone.utc).isoformat()

def capture(argv, **kw):
    p = subprocess.run(list(map(str, argv)), capture_output=True, text=True, **kw)
    return {"argv": list(map(str, argv)), "returncode": p.returncode,
            "stdout": p.stdout, "stderr": p.stderr}

def dump(p, obj): Path(p).write_text(json.dumps(obj, indent=2) + "\n")

def probe(p, packets=False):
    av = ["/usr/bin/ffprobe", "-v", "error", "-select_streams", "v:0"]
    av += ["-show_packets", "-show_entries", "packet=pts_time,dts_time,size,flags"] if packets else ["-show_streams"]
    r = capture(av + ["-of", "json", str(p)])
    assert r["returncode"] == 0, r["stderr"]
    return json.loads(r["stdout"])

def packet_rate(p, fps):
    packets = sorted(probe(p, True)["packets"], key=lambda p: float(p["pts_time"]))
    assert len(packets) == 336
    pts = [float(p["pts_time"]) for p in packets]
    assert abs(pts[0]) < 1e-6 and len(set(pts)) == 336
    assert all(abs(t - i / fps) <= .000501 for i, t in enumerate(pts))
    return {
        "path": str(p), "packets": packets, "selected_indices": [96, 336],
        "actual_mbps": sum(int(q["size"]) for q in packets[96:]) * 8 / (240 / fps) / 1e6,
        "full_mbps": sum(int(q["size"]) for q in packets) * 8 / (336 / fps) / 1e6,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tag"); ap.add_argument("request_kbps", type=int)
    ap.add_argument("--preview", action="store_true")
    a = ap.parse_args()
    assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", a.tag)
    assert 0 < a.request_kbps <= 30000
    for k in ("LD_LIBRARY_PATH", "LD_PRELOAD", "LD_AUDIT", "SVT_PSYEX_OBS_FD"):
        assert not os.environ.get(k), f"Inherited override {k}"
    assert shutil.disk_usage(ROOT).free >= 130 * (1 << 30)
    assert sha(PSYROOT / "measured-runner.sh") == BUILD_RUNNER_SHA
    assert sha(PSYROOT / "source-manifest-before.tsv") == sha(PSYROOT / "source-manifest-after.tsv") == MANIFEST_SHA
    build_log = (PSYROOT / "build-receipt.log").read_text()
    assert build_log.count("final_status=build_complete\n") == 1
    assert build_log.endswith("exit_code=0\n")
    # Bind every build artifact to the successful reviewed build's manifest.
    build_records = {}
    for row in (PSYROOT / "build-artifact-hashes.txt").read_text().splitlines():
        digest, name = row.split(maxsplit=1)
        name = name.lstrip("*")
        assert sha(name) == digest, f"Build artifact drift: {name}"
        build_records[name] = digest
    assert str(APP) in build_records and str(LIB) in build_records
    assert sha(APP) == APP_SHA and sha(LIB) == LIB_SHA
    assert sha(PSYROOT / "cpuinfo-audit.json") == "697dd77268d11f1f8a1a5003f6f6e05e1206d3686904fa3b1f05e5b499a43190"
    assert sha(PSYROOT / "cpuinfo-manifest.json") == "2374575a0aba9b941152770a2374ec048eb540868366bbbb46df846896a4a63f"
    cpuinfo_files = json.loads((PSYROOT / "cpuinfo-manifest.json").read_text())
    assert len(cpuinfo_files) == 570
    for rel, size, digest in cpuinfo_files:
        p = PSYROOT / "source/third_party/cpuinfo" / rel
        assert p.stat().st_size == size and sha(p) == digest
    inp = FIX / "input10.y4m"
    assert sha(inp) == INPUT_SHA
    with inp.open("rb") as f:
        header = f.readline().decode("ascii")
    assert all(x in header.split() for x in ("W1920", "H1080", "F24:1", "C420p10"))
    validity = json.loads((FIX / "validity.json").read_text())
    assert validity["fps"] == 24 and validity["source_mbps"] == 9.6765224
    hist = json.loads((FIX / "historical-input-validation.json").read_text())
    assert hist["all336_exact_Y4M_bytes_match_prior"] and hist["input"]["sha256"] == INPUT_SHA
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PANTHEON_", "SVT_PSYEX_"))}
    env["LD_LIBRARY_PATH"] = str(BUILD / "bin")
    ld = capture(["/usr/bin/ldd", APP], env=env)
    assert ld["returncode"] == 0
    m = re.search(r"libSvtAv1Enc\.so\.3\s+=>\s+(\S+)", ld["stdout"])
    assert m and Path(m.group(1)).resolve() == LIB.resolve()
    run = PSYROOT / "runs/e05-1440" / a.tag
    run.mkdir(parents=True, exist_ok=False)
    receipt = {"status": "prepared", "created_utc": utc(), "case": "e05-1440",
               "tag": a.tag, "request_kbps": a.request_kbps, "settings": POLICY,
               "source_mbps": validity["source_mbps"], "target_mbps": validity["source_mbps"] * .995,
               "build_records": build_records, "ldd": ld, "library_environment": env["LD_LIBRARY_PATH"],
               "source_commit": "59d1a025698f2ca7b4c4b0e833937dd15e382494",
               "input": ident(inp), "input_header": header, "binary": ident(APP), "library": ident(LIB),
               "validity": ident(FIX / "validity.json"),
               "historical_input_validation": ident(FIX / "historical-input-validation.json"),
               "build_receipt": ident(PSYROOT / "build-receipt.log"),
               "build_manifest": ident(PSYROOT / "build-artifact-hashes.txt"),
               "cpuinfo_audit": ident(PSYROOT / "cpuinfo-audit.json"),
               "cpuinfo_manifest": ident(PSYROOT / "cpuinfo-manifest.json"),
               "practical_scope": "Pinned bundled policy, no isolated psy-rd causality or playback claim."}
    try:
        shutil.copy2(__file__, run / "measured-runner.py")
        receipt["script"] = ident(run / "measured-runner.py")
        receipt["executed_script"] = ident(Path(__file__).resolve())
        identity_paths = [inp, APP, LIB, Path(__file__).resolve(), run / "measured-runner.py",
                          FIX / "validity.json", FIX / "historical-input-validation.json",
                          PSYROOT / "build-artifact-hashes.txt", PSYROOT / "build-receipt.log",
                          PSYROOT / "cpuinfo-audit.json", PSYROOT / "cpuinfo-manifest.json",
                          Path("/usr/bin/ffmpeg"), Path("/usr/bin/ffprobe"),
                          Path("/usr/bin/ldd"), Path("/usr/bin/nice"), Path("/usr/bin/taskset")]
        def identity(): return {str(p): sha(p) for p in identity_paths}
        receipt["identity_before"] = identity()
        stats = run / "pass.stats"
        common = ["/usr/bin/nice", "-n", "10", "/usr/bin/taskset", "-c", "0-7", str(APP), "-i", str(inp), "-n", "336"]
        for k, v in POLICY.items(): common += [k, v]
        common += ["--tbr", str(a.request_kbps), "--stats", str(stats)]
        commands = {
            "pass1": common + ["--pass", "1", "-b", str(run / "pass1.ivf")],
            "pass2": common + ["--pass", "2", "-b", str(run / "out.ivf"), "-o", str(run / "recon.yuv")],
        }
        receipt["commands"] = commands
        dump(run / "command.json", receipt)
        if a.preview: return
        receipt["resource_before"] = {
            "free_bytes": shutil.disk_usage(ROOT).free,
            "loadavg": Path("/proc/loadavg").read_text(),
            "meminfo": Path("/proc/meminfo").read_text(),
            "processes": capture(["ps", "-eo", "pid,pcpu,pmem,comm", "--sort=-pcpu"]),
        }
        receipt["passes"] = {}
        for key, cmd in commands.items():
            assert identity() == receipt["identity_before"]
            if key == "pass1": assert not stats.exists()
            else: assert sha(stats) == receipt["stats"]["sha256"]
            receipt["status"] = key + "_running"; dump(run / "command.json", receipt)
            t = time.monotonic(); started = utc()
            with (run / (key + ".log")).open("w") as log:
                proc = subprocess.run(cmd, cwd=run, env=env, stdout=log, stderr=subprocess.STDOUT)
            elapsed = time.monotonic() - t
            receipt["passes"][key] = {"seconds": elapsed, "start_utc": started, "end_utc": utc(),
                "returncode": proc.returncode, "log": ident(run / (key + ".log"))}
            dump(run / "command.json", receipt)
            assert proc.returncode == 0, f"{key} failed; inspect log"
            assert stats.stat().st_size > 0
            if key == "pass1":
                receipt["stats"] = ident(stats)
                shutil.copy2(stats, run / "pass1-stats.snapshot")
                receipt["stats_snapshot"] = ident(run / "pass1-stats.snapshot")
            else:
                assert sha(stats) == sha(run / "pass1-stats.snapshot") == receipt["stats"]["sha256"]
            assert identity() == receipt["identity_before"]
        log = (run / "pass2.log").read_text(errors="replace")
        effective = {
            "width / height / fps numerator / fps denominator": "1920 / 1080 / 24 / 1",
            "bit-depth / color format": "10 / YUV420",
            "preset / tune / pred struct": "4 / VQ / random access",
            "gop size / mini-gop size / key-frame type": "240 / 16 / key frame",
            "BRC mode / target bitrate (kbps)": "VBR / " + str(a.request_kbps),
            "AQ mode / Variance Boost strength / octile / curve": "2 / 2 / 5 / 0",
            "sharpness / luminance-based QP bias": "1 / 0",
            "temporal filtering strength": "1",
            "QP scale compress strength": "1.00",
            "Noise Normalization Strength": "1",
            "Keyframe TF Strength": "1", "PSY-RD Strength": "1.00",
            "spy-rd": "non", "noise adaptive filtering": "off",
        }
        for key, expected in effective.items():
            values = re.findall(r"SVT \[config\]: " + re.escape(key) + r"\s*:\s*([^\n]+)", log)
            assert len(values) == 1 and values[0].strip() == expected, (key, values, expected)
        receipt["effective_log_settings"] = effective
        ivf, mkv = run / "out.ivf", run / "out.mkv"
        receipt["remux"] = capture(["/usr/bin/ffmpeg", "-v", "error", "-n", "-i", ivf, "-c", "copy", mkv])
        assert receipt["remux"]["returncode"] == 0
        stream = probe(mkv)["streams"][0]
        assert (stream["codec_name"], stream["width"], stream["height"], stream["pix_fmt"]) == ("av1",1920,1080,"yuv420p10le")
        assert [stream.get(k) for k in ("color_range","color_space","color_transfer","color_primaries")] == ["tv","bt709","bt709","bt709"]
        assert stream["r_frame_rate"] == "24/1"
        receipt["stream"] = stream
        receipt["ivf_output"], receipt["mkv_output"], receipt["recon"] = ident(ivf), ident(mkv), ident(run / "recon.yuv")
        assert receipt["recon"]["size"] == 336 * 1920 * 1080 * 3
        window = {"ivf": packet_rate(ivf, 24), "mkv": packet_rate(mkv, 24)}
        window["ivf_minus_mkv_packet_bytes"] = [
            int(i["size"]) - int(m["size"])
            for i, m in zip(window["ivf"]["packets"], window["mkv"]["packets"])]
        window["container_note"] = "AV1 temporal delimiter OBUs may be removed during remux; compare decoded samples, count both payloads, use MKV consistently."
        actual = window["mkv"]["actual_mbps"]
        window.update(source_mbps=validity["source_mbps"], actual_mbps=actual,
            within_source_ceiling=actual <= validity["source_mbps"],
            decisive_rate_gate=.99 * validity["source_mbps"] <= actual <= validity["source_mbps"])
        dump(run / "packet-window.json", window)
        receipt["packet_window"] = ident(run / "packet-window.json")
        receipt["actual_mbps"], receipt["full_mbps"] = actual, window["mkv"]["full_mbps"]
        receipt["wall_seconds"] = sum(p["seconds"] for p in receipt["passes"].values())
        receipt["resource_after"] = {"loadavg": Path("/proc/loadavg").read_text(),
                                     "free_bytes": shutil.disk_usage(ROOT).free}
        receipt["identity_after"] = identity()
        assert receipt["identity_after"] == receipt["identity_before"]
        receipt["status"] = "encoded" if window["decisive_rate_gate"] else "rate_gate_failed"
        receipt["returncode"] = 0; receipt["end_utc"] = utc()
        dump(run / "command.json", receipt)
        print(json.dumps({"run": str(run), "status": receipt["status"], "mbps": actual,
                          "seconds": receipt["wall_seconds"]}), flush=True)
    except BaseException as e:
        receipt["status"] = "failed"; receipt["error"] = repr(e); receipt["end_utc"] = utc()
        dump(run / "command.json", receipt)
        raise

if __name__ == "__main__": main()
