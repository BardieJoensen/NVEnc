#!/usr/bin/env python3
"""R16 TF-off budget runner derived from the verified R8/R15 execution path."""
from __future__ import annotations
if not __debug__: raise SystemExit("optimized Python is rejected")
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
R8ROOT = ROOT / "worker/psyex-r8"
PSYROOT = ROOT / "worker/psyex-r16-calibration-refine"
FIX = ROOT / "fixtures/e05-1440"
BUILD = R8ROOT / "build"
RUNROOT = PSYROOT / "runs"
APP = BUILD / "bin/SvtAv1EncApp"
LIB = BUILD / "bin/libSvtAv1Enc.so.3.0.2"
INPUT_SHA = "232abb5ffee869be4bedf682aa103c166eb473bb3fdad5daf28956cca60148d4"
MANIFEST_SHA = "8cf0314d5ee329b662c32021020c8299ef47bb87681d87508328c1b28eeb5c69"
BUILD_RUNNER_SHA = "4cf939e20445e130970fdf09983a774e1f71adf1ea6240038cc557fe9ef66a7b"
APP_SHA = "f4867ae287fa34cc50f927b7aa52611973adbc7231785117e5d32ce077b2461c"
LIB_SHA = "cd408a2f31f871cf9da924dd943607e2b8aa2e5366e513fc82d959434414f20b"
CONTRACT = Path("/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020/ROUND16_RATE_REFINEMENT.md")
CONTRACT_SHA = "9ea9b3bd9dcf4c5a7f994e0eb12508448a93142ad9d7b7baec27f5ea21597d82"
R8_COMMAND = R8ROOT / "runs/e05-1440/psyex-1x1/command.json"
R8_COMMAND_SHA = "ceea9943cb7b0fd31331a7505089ac72bb06dc78c7e150589f0972d469cfa138"
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
    "--enable-tf": "0", "--tf-strength": "1", "--kf-tf-strength": "1",
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

def load_legacy_runner():
    old_runner = PSYROOT.parent / "psyex-r16-tf0-budget" / "encode_r16.py"
    assert old_runner.is_file()
    assert sha(old_runner) == "2c14604755be12ae1f8fe996cc93ea9486963f629e44bc3a1a7d21d40076469b"
    import importlib.util
    spec = importlib.util.spec_from_file_location("frozen_r16_old_for_validation", old_runner)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod

def validate_legacy_endpoint(path, digest):
    mod=load_legacy_runner()
    d,deps=mod.validate_chain(path,digest)
    assert d["settings"]==POLICY and d["source_mbps"]==9.6765224 and d["status"]=="encoded" and d["returncode"]==0
    return d,deps

def validate_refine(path, expected_sha, active=None, memo=None):
    """Validate one new refinement node and its DAG, reconstructing every bracket."""
    active=set() if active is None else active; memo={} if memo is None else memo
    path=Path(path).resolve(); digest=str(expected_sha)
    if path in active: raise AssertionError("refinement receipt cycle")
    if path in memo:
        assert memo[path][0]==digest
        return memo[path][1],memo[path][2]
    assert path.is_file() and sha(path)==digest
    active.add(path)
    d=json.loads(path.read_text())
    assert d.get("status")=="encoded" and d.get("returncode")==0 and d.get("case")=="e05-1440"
    assert d.get("contract",{}).get("sha256")==CONTRACT_SHA and d.get("settings")==POLICY
    assert float(d.get("source_mbps"))==9.6765224 and float(d.get("practical_ceiling_mbps"))==9.6765224
    live_sha=sha(Path(__file__).resolve())
    assert d.get("script",{}).get("sha256")==live_sha and d.get("executed_script",{}).get("sha256")==live_sha
    assert d.get("source_commit")=="59d1a025698f2ca7b4c4b0e833937dd15e382494"
    validity=d["validity"]; assert ident(validity["path"])==validity
    validity_data=json.loads(Path(validity["path"]).read_text())
    assert validity_data["source_mbps"]==9.6765224 and validity_data["fps"]==24
    before=d.get("identity_before",{}); after=d.get("identity_after",{}); assert before and before==after
    paths=[]
    for q,qsha in after.items(): assert sha(q)==qsha; paths.append(Path(q).resolve())
    assert d.get("input",{}).get("sha256")==INPUT_SHA and d.get("binary",{}).get("sha256")==APP_SHA and d.get("library",{}).get("sha256")==LIB_SHA
    assert d.get("r8_command_receipt",{}).get("sha256")==R8_COMMAND_SHA and sha(d["r8_command_receipt"]["path"])==R8_COMMAND_SHA
    for c in (d["commands"]["pass1"],d["commands"]["pass2"]):
        assert c[c.index("--tbr")+1]==str(d["request_kbps"]) and "--min-qp" not in c and "--max-qp" not in c
    pw=d.get("packet_window",{}); assert pw.get("path") and sha(pw["path"])==pw["sha256"]
    pj=json.loads(Path(pw["path"]).read_text()); packets=pj["mkv"]["packets"]
    assert len(packets)==336 and pj["mkv"]["selected_indices"]==[96,336]
    measured=sum(int(x["size"]) for x in packets[96:336])*8/10/1e6
    assert all(abs(measured-float(v))<1e-10 for v in
               (d["actual_mbps"],pj["actual_mbps"],pj["mkv"]["actual_mbps"]))
    assert pj["source_mbps"]==9.6765224
    assert d["within_source_ceiling"]==(measured<=9.6765224) and d["matched_rate_comparable"]==(9.579757176<=measured<=9.6765224)
    cal=d.get("calibration",{}); attempt=int(cal.get("attempt",0)); assert 1<=attempt<=3 and cal.get("target_interval")==[9.579757176,9.6765224]
    assert cal.get("phase")=="midpoint-refinement" and cal.get("request_kbps")==d["request_kbps"]
    bracket=d.get("bracket"); assert bracket and set(bracket)=={"low","high"}
    if attempt==1:
        assert "previous_receipt" not in cal and cal.get("low")==bracket["low"] and cal.get("high")==bracket["high"]
        assert bracket["low"]["phase"]==bracket["high"]["phase"]=="old"
        assert d["request_kbps"]==10042 and cal.get("formula")=="floor((low.request_kbps + high.request_kbps)/2)"
        canon_low=ROOT/"worker/psyex-r16-tf0-budget/runs/e05-1440/r16-tf0-tbr10014/command.json"; canon_high=ROOT/"worker/psyex-r16-tf0-budget/runs/e05-1440/r16-tf0-tbr10070/command.json"
        assert Path(bracket["low"]["path"]).resolve()==canon_low.resolve() and bracket["low"]["sha256"]=="02bc209310beb0c88d72c9ca40deb621ce07b2694dfd52bc9ddc5db5219deadd"
        assert Path(bracket["high"]["path"]).resolve()==canon_high.resolve() and bracket["high"]["sha256"]=="690beb605f882ddb9748f4e23f4aabc604cca1027f019b5ad09004b9b31b442a"
        low,ld=validate_legacy_endpoint(canon_low,bracket["low"]["sha256"]); high,hd=validate_legacy_endpoint(canon_high,bracket["high"]["sha256"]); paths += ld+hd
        assert bracket["low"]["request_kbps"]==10014 and abs(bracket["low"]["actual_mbps"]-low["actual_mbps"])<1e-12
        assert bracket["high"]["request_kbps"]==10070 and abs(bracket["high"]["actual_mbps"]-high["actual_mbps"])<1e-12
    else:
        prev=cal.get("previous_receipt"); assert isinstance(prev,dict) and cal.get("formula")=="floor((low.request_kbps + high.request_kbps)/2)"
        pd,pp=validate_refine(prev["path"],prev["sha256"],active,memo); paths += pp
        assert int(pd["calibration"]["attempt"])+1==attempt and ident(prev["path"])==prev
        oldb=pd["bracket"]; assert float(oldb["low"]["actual_mbps"]) <= float(pd["actual_mbps"]) <= float(oldb["high"]["actual_mbps"])
        assert not (9.579757176 <= float(pd["actual_mbps"]) <= 9.6765224)
        updated={"phase":"refinement","path":prev["path"],"sha256":prev["sha256"],
                 "request_kbps":pd["request_kbps"],"actual_mbps":pd["actual_mbps"]}
        if float(pd["actual_mbps"]) < 9.579757176:
            assert cal.get("bracket_transition")=="raise_low" and bracket["low"]==updated and bracket["high"]==oldb["high"]
        else:
            assert cal.get("bracket_transition")=="lower_high" and bracket["high"]==updated and bracket["low"]==oldb["low"]
    assert float(bracket["low"]["actual_mbps"]) < 9.579757176 and float(bracket["high"]["actual_mbps"]) > 9.6765224
    lo=int(bracket["low"]["request_kbps"]); hi=int(bracket["high"]["request_kbps"]); assert lo < d["request_kbps"] < hi and d["request_kbps"]==(lo+hi)//2
    assert float(bracket["low"]["actual_mbps"]) <= measured <= float(bracket["high"]["actual_mbps"])
    paths += [path,Path(d["r8_command_receipt"]["path"]).resolve(),Path(pw["path"]).resolve(),Path(__file__).resolve()]
    result=(d,list(dict.fromkeys(paths))); active.remove(path); memo[path]=(digest,*result); return result

def validate_chain(path, expected_sha, *args, **kwargs):
    """Public new-node validator; legacy endpoints use validate_legacy_endpoint."""
    return validate_refine(path, expected_sha, *args, **kwargs)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tag"); ap.add_argument("request_kbps", type=int)
    ap.add_argument("--previous-receipt", type=Path)
    ap.add_argument("--previous-receipt-sha")
    ap.add_argument("--low-receipt", type=Path)
    ap.add_argument("--low-receipt-sha")
    ap.add_argument("--high-receipt", type=Path)
    ap.add_argument("--high-receipt-sha")
    ap.add_argument("--preview", action="store_true")
    a = ap.parse_args()
    assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", a.tag)
    assert 1 <= a.request_kbps <= 100000, "request must be a positive integer kbps"
    for k in ("LD_LIBRARY_PATH", "LD_PRELOAD", "LD_AUDIT", "SVT_PSYEX_OBS_FD"):
        assert not os.environ.get(k), f"Inherited override {k}"
    assert shutil.disk_usage(ROOT).free >= 130 * (1 << 30)
    assert sha(CONTRACT) == CONTRACT_SHA
    assert sha(R8_COMMAND) == R8_COMMAND_SHA
    assert sha(R8ROOT / "measured-runner.sh") == BUILD_RUNNER_SHA
    assert sha(R8ROOT / "source-manifest-before.tsv") == sha(R8ROOT / "source-manifest-after.tsv") == MANIFEST_SHA
    build_log = (R8ROOT / "build-receipt.log").read_text()
    assert build_log.count("final_status=build_complete\n") == 1
    assert build_log.endswith("exit_code=0\n")
    # Bind every build artifact to the successful reviewed build's manifest.
    build_records = {}
    for row in (R8ROOT / "build-artifact-hashes.txt").read_text().splitlines():
        digest, name = row.split(maxsplit=1)
        name = name.lstrip("*")
        assert sha(name) == digest, f"Build artifact drift: {name}"
        build_records[name] = digest
    assert str(APP) in build_records and str(LIB) in build_records
    assert sha(APP) == APP_SHA and sha(LIB) == LIB_SHA
    assert sha(R8ROOT / "cpuinfo-audit.json") == "697dd77268d11f1f8a1a5003f6f6e05e1206d3686904fa3b1f05e5b499a43190"
    assert sha(R8ROOT / "cpuinfo-manifest.json") == "2374575a0aba9b941152770a2374ec048eb540868366bbbb46df846896a4a63f"
    cpuinfo_files = json.loads((R8ROOT / "cpuinfo-manifest.json").read_text())
    assert len(cpuinfo_files) == 570
    for rel, size, digest in cpuinfo_files:
        p = R8ROOT / "source/third_party/cpuinfo" / rel
        assert p.stat().st_size == size and sha(p) == digest
    inp = FIX / "input10.y4m"
    assert sha(inp) == INPUT_SHA
    with inp.open("rb") as f:
        header = f.readline().decode("ascii")
    assert all(x in header.split() for x in ("W1920", "H1080", "F24:1", "C420p10"))
    validity = json.loads((FIX / "validity.json").read_text())
    assert validity["fps"] == 24 and validity["source_mbps"] == 9.6765224
    assert R8_COMMAND.is_file() and sha(R8_COMMAND) == R8_COMMAND_SHA
    r8_receipt = json.loads(R8_COMMAND.read_text())
    assert r8_receipt.get("status") == "encoded" and r8_receipt.get("returncode") == 0
    hist = json.loads((FIX / "historical-input-validation.json").read_text())
    assert hist["all336_exact_Y4M_bytes_match_prior"] and hist["input"]["sha256"] == INPUT_SHA
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PANTHEON_", "SVT_PSYEX_"))}
    env["LD_LIBRARY_PATH"] = str(BUILD / "bin")
    ld = capture(["/usr/bin/ldd", APP], env=env)
    assert ld["returncode"] == 0
    m = re.search(r"libSvtAv1Enc\.so\.3\s+=>\s+(\S+)", ld["stdout"])
    assert m and Path(m.group(1)).resolve() == LIB.resolve()
    old_endpoint = validate_legacy_endpoint
    source = float(validity["source_mbps"])
    previous_paths=[]; bracket_transition=None
    if a.previous_receipt is None:
        assert a.previous_receipt_sha is None and a.low_receipt and a.high_receipt
        assert a.low_receipt_sha=="02bc209310beb0c88d72c9ca40deb621ce07b2694dfd52bc9ddc5db5219deadd"
        assert a.high_receipt_sha=="690beb605f882ddb9748f4e23f4aabc604cca1027f019b5ad09004b9b31b442a"
        assert a.low_receipt.resolve()==ROOT/"worker/psyex-r16-tf0-budget/runs/e05-1440/r16-tf0-tbr10014/command.json"
        assert a.high_receipt.resolve()==ROOT/"worker/psyex-r16-tf0-budget/runs/e05-1440/r16-tf0-tbr10070/command.json"
        low, lowdeps = old_endpoint(a.low_receipt, a.low_receipt_sha)
        high, highdeps = old_endpoint(a.high_receipt, a.high_receipt_sha)
        assert low["actual_mbps"] < 9.579757176 and high["actual_mbps"] > source
        assert low["request_kbps"] == 10014 and high["request_kbps"] == 10070
        assert a.request_kbps == (low["request_kbps"] + high["request_kbps"]) // 2 == 10042
        previous_paths = lowdeps + highdeps + [a.low_receipt.resolve(), a.high_receipt.resolve()]
        bracket={"low":{"phase":"old","path":str(a.low_receipt.resolve()),"sha256":a.low_receipt_sha,"request_kbps":low["request_kbps"],"actual_mbps":low["actual_mbps"]},"high":{"phase":"old","path":str(a.high_receipt.resolve()),"sha256":a.high_receipt_sha,"request_kbps":high["request_kbps"],"actual_mbps":high["actual_mbps"]}}
        calibration={"phase":"midpoint-refinement","attempt":1,"low":bracket["low"],"high":bracket["high"],"target_interval":[9.579757176,9.6765224],"formula":"floor((low.request_kbps + high.request_kbps)/2)","request_kbps":a.request_kbps}
    else:
        assert a.previous_receipt_sha and a.previous_receipt.is_file() and not (a.low_receipt or a.high_receipt or a.low_receipt_sha or a.high_receipt_sha)
        prior, lineage_paths = validate_refine(a.previous_receipt,a.previous_receipt_sha)
        assert int(prior["calibration"]["attempt"])+1 <= 3
        oldbr=prior.get("bracket"); assert oldbr and oldbr.get("low") and oldbr.get("high")
        lowrate=float(oldbr["low"]["actual_mbps"]); highrate=float(oldbr["high"]["actual_mbps"]); prate=float(prior["actual_mbps"])
        assert lowrate <= prate <= highrate
        if 9.579757176 <= prate <= 9.6765224: raise AssertionError("previous node already matched; no next request")
        if prate < 9.579757176:
            low={"phase":"refinement","path":str(a.previous_receipt.resolve()),"sha256":a.previous_receipt_sha,"request_kbps":prior["request_kbps"],"actual_mbps":prate}; high=oldbr["high"]; bracket_transition="raise_low"
        else:
            low=oldbr["low"]; high={"phase":"refinement","path":str(a.previous_receipt.resolve()),"sha256":a.previous_receipt_sha,"request_kbps":prior["request_kbps"],"actual_mbps":prate}; bracket_transition="lower_high"
        expected=(int(low["request_kbps"])+int(high["request_kbps"]))//2
        assert int(low["request_kbps"]) < expected < int(high["request_kbps"]) and a.request_kbps==expected
        previous_paths=lineage_paths
        bracket={"low":low,"high":high}
        calibration={"phase":"midpoint-refinement","attempt":int(prior["calibration"]["attempt"])+1,"previous_receipt":ident(a.previous_receipt),"bracket_transition":bracket_transition,"target_interval":[9.579757176,9.6765224],"formula":"floor((low.request_kbps + high.request_kbps)/2)","request_kbps":a.request_kbps}
    run = RUNROOT / "e05-1440" / a.tag
    run.mkdir(parents=True, exist_ok=False)
    receipt = {"status": "prepared", "created_utc": utc(), "case": "e05-1440",
               "tag": a.tag, "request_kbps": a.request_kbps, "settings": POLICY,
               "source_mbps": validity["source_mbps"], "practical_ceiling_mbps": validity["source_mbps"],
               "build_records": build_records, "ldd": ld, "library_environment": env["LD_LIBRARY_PATH"],
               "source_commit": "59d1a025698f2ca7b4c4b0e833937dd15e382494",
               "contract": ident(CONTRACT),
               "r8_command_receipt": ident(R8_COMMAND),
               "calibration": calibration,
               "bracket": bracket,
               "input": ident(inp), "input_header": header, "binary": ident(APP), "library": ident(LIB),
               "validity": ident(FIX / "validity.json"),
               "historical_input_validation": ident(FIX / "historical-input-validation.json"),
               "runner_readme": ident(PSYROOT / "README.md"),
               "source_audit": ident(PSYROOT / "source-audit.md"),
               "build_receipt": ident(R8ROOT / "build-receipt.log"),
               "build_manifest": ident(R8ROOT / "build-artifact-hashes.txt"),
               "cpuinfo_audit": ident(R8ROOT / "cpuinfo-audit.json"),
               "cpuinfo_manifest": ident(R8ROOT / "cpuinfo-manifest.json"),
               "practical_scope": "TF-off bundle at normal rate allocation; practical acceptance remains at or below the untouched original packet ceiling; no isolated TF causality or playback claim."}
    try:
        shutil.copy2(__file__, run / "measured-runner.py")
        receipt["script"] = ident(run / "measured-runner.py")
        receipt["executed_script"] = ident(Path(__file__).resolve())
        identity_paths = [inp, APP, LIB, R8_COMMAND, Path(__file__).resolve(), run / "measured-runner.py", *previous_paths,
                          FIX / "validity.json", FIX / "historical-input-validation.json", CONTRACT, PSYROOT / "README.md", PSYROOT / "source-audit.md",
                          R8ROOT / "build-artifact-hashes.txt", R8ROOT / "build-receipt.log",
                          R8ROOT / "cpuinfo-audit.json", R8ROOT / "cpuinfo-manifest.json",
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
        def normalized(cmd):
            out=[]; skip=False
            for v in cmd:
                if skip: skip=False; continue
                if v in ("--stats", "-b", "-o"):
                    out.extend([v, "<fresh>"]); skip=True
                elif v == "--tbr":
                    out.extend([v, "<request>"]); skip=True
                elif v == "--enable-tf":
                    out.extend([v, "<tf-off>"]); skip=True
                else: out.append(v)
            return out
        for pass_name in ("pass1", "pass2"):
            r8cmd = r8_receipt["commands"][pass_name]
            assert normalized(commands[pass_name]) == normalized(r8cmd), pass_name
            assert r8cmd[r8cmd.index("--enable-tf") + 1] == "1"
            assert commands[pass_name][commands[pass_name].index("--enable-tf") + 1] == "0"
        assert all("--min-qp" not in c and "--max-qp" not in c for c in commands.values())
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
            "QP scale compress strength": "1.00",
            "Noise Normalization Strength": "1",
            "PSY-RD Strength": "1.00",
            "spy-rd": "non", "noise adaptive filtering": "off",
        }
        for key, expected in effective.items():
            values = re.findall(r"SVT \[config\]: " + re.escape(key) + r"\s*:\s*([^\n]+)", log)
            assert len(values) == 1 and values[0].strip() == expected, (key, values, expected)
        # TF=0 intentionally suppresses the TF-strength and keyframe-TF lines.
        # The public QP bounds are not printed by this build, so retain the exact
        # argv plus source audit; a later trace must establish realized TU q.
        assert not [line for line in log.splitlines() if "SVT [config]: temporal filtering strength" in line]
        assert not [line for line in log.splitlines() if "SVT [config]: Keyframe TF Strength" in line]
        receipt["effective_log_settings"] = effective
        receipt["effective_diagnostic"] = {
            "enable_tf_requested": 0, "tf_strength_lines_absent": True,
            "public_qp_bounds_requested": False,
            "realized_tu_q_unverified": True,
        }
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
            matched_rate_comparable=.99 * validity["source_mbps"] <= actual <= validity["source_mbps"])
        dump(run / "packet-window.json", window)
        receipt["packet_window"] = ident(run / "packet-window.json")
        receipt["actual_mbps"], receipt["full_mbps"] = actual, window["mkv"]["full_mbps"]
        receipt["calibration_response_within_bracket"] = bracket["low"]["actual_mbps"] <= actual <= bracket["high"]["actual_mbps"]
        receipt["wall_seconds"] = sum(p["seconds"] for p in receipt["passes"].values())
        receipt["resource_after"] = {"loadavg": Path("/proc/loadavg").read_text(),
                                     "free_bytes": shutil.disk_usage(ROOT).free}
        receipt["identity_after"] = identity()
        assert receipt["identity_after"] == receipt["identity_before"]
        receipt["status"] = "encoded"
        receipt["within_source_ceiling"] = window["mkv"]["actual_mbps"] <= validity["source_mbps"]
        receipt["matched_rate_comparable"] = bool(window["matched_rate_comparable"])
        receipt["returncode"] = 0; receipt["end_utc"] = utc()
        dump(run / "command.json", receipt)
        print(json.dumps({"run": str(run), "status": receipt["status"], "mbps": actual,
                          "seconds": receipt["wall_seconds"]}), flush=True)
    except BaseException as e:
        receipt["status"] = "failed"; receipt["error"] = repr(e); receipt["end_utc"] = utc()
        dump(run / "command.json", receipt)
        raise

if __name__ == "__main__": main()
