#!/usr/bin/env python3
"""Admit PSYEX app reconstruction against three decoders on all336 planes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

import sys
REPORT = Path('/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020')
sys.path.insert(0,str(REPORT))
import validate_aom_qmax_decoders as shared

ROOT = shared.ROOT
HERE = REPORT
SHARED_SHA = "bb2e0256100ad70e02753c0fc19c0cc62f2ed189f08d50335b3ab421983b5ca9"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tag")
    ap.add_argument("receipt_sha256", help="Explicit immutable encoded receipt binding")
    a = ap.parse_args()
    assert "/" not in a.tag and a.tag not in ("", ".", "..")
    assert shared.identity(HERE / "validate_aom_qmax_decoders.py")["sha256"] == SHARED_SHA
    for k in ("LD_PRELOAD", "LD_LIBRARY_PATH", "LD_AUDIT", "SVT_PSYEX_OBS_FD"):
        assert not os.environ.get(k)
    assert shutil.disk_usage(ROOT).free >= 130 * 2**30
    run = ROOT / "worker/psyex-r16-tf0-budget/runs/e05-1440" / a.tag
    inputs = {n: shared.identity(run / n) for n in ("command.json", "out.ivf", "out.mkv", "recon.yuv")}
    assert inputs["command.json"]["sha256"] == a.receipt_sha256
    parent = json.loads((run / "command.json").read_text())
    assert parent["status"] == "encoded" and parent["returncode"] == 0
    for name, field in (("out.ivf", "ivf_output"), ("out.mkv", "mkv_output"), ("recon.yuv", "recon")):
        assert inputs[name] == parent[field]
    assert parent["identity_before"] == parent["identity_after"]
    for p, h in parent["identity_after"].items(): assert shared.identity(p)["sha256"] == h
    v = run / "decoder-validation"
    v.mkdir(exist_ok=False)
    receipt = {"status": "started", "started_utc": shared.utc(), "inputs": inputs, "commands": [],
               "scope": "All336-frame sample/cadence/color identity; no quality or playback claim."}
    def save(): (v / "decoder-validation.json").write_text(json.dumps(receipt, indent=2)+"\n")
    save()
    try:
        shutil.copyfile(__file__, v / "measured-validator.py")
        receipt["script"] = shared.identity(v / "measured-validator.py")
        receipt["source_script"] = shared.identity(__file__)
        receipt["shared_helper"] = shared.identity(HERE / "validate_aom_qmax_decoders.py")
        receipt["identity_before"] = shared.tools()
        receipt["launch_tools_before"] = {p:shared.identity(p) for p in ("/usr/bin/nice","/usr/bin/taskset")}
        for tool in ("ffmpeg", "ffprobe"):
            assert receipt["identity_before"][tool]["file"]["sha256"] == parent["identity_before"]["/usr/bin/"+tool]
        probe = shared.capture(["/usr/bin/ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_streams", "-show_packets", "-of", "json", str(run / "out.mkv")])
        (v / "probe.json").write_text(json.dumps(probe, indent=2)+"\n")
        receipt["probe"] = shared.identity(v / "probe.json")
        data = json.loads(probe["stdout"])
        assert len(data["streams"]) == 1
        s = data["streams"][0]
        assert [s[k] for k in ("codec_name","width","height","pix_fmt")] == ["av1",1920,1080,"yuv420p10le"]
        assert [s[k] for k in ("color_range","color_space","color_transfer","color_primaries")] == ["tv","bt709","bt709","bt709"]
        assert (s["time_base"],s["r_frame_rate"]) == ("1/1000","24/1")
        pp = data["packets"]
        assert len(pp) == 336 and all(p["stream_index"] == 0 for p in pp)
        assert [p["pts"] for p in pp] == [(i*1000+12)//24 for i in range(336)]
        base = ["/usr/bin/nice","-n","10","/usr/bin/taskset","-c","8-11","/usr/bin/ffmpeg",
                "-hide_banner","-v","error","-n","-threads","4"]
        tail = ["-map","0:v:0","-frames:v","336","-pix_fmt","yuv420p10le",
                "-c:v","rawvideo","-threads","4","-f","framemd5"]
        specs = [
            ("dav1d", ["-c:v","libdav1d","-filmgrain","0","-i",str(run/"out.mkv")]),
            ("libaom", ["-c:v","libaom-av1","-i",str(run/"out.mkv")]),
            ("nvdec", ["-hwaccel","cuda","-hwaccel_output_format","cuda","-c:v","av1_cuvid",
                       "-i",str(run/"out.mkv"),"-vf","hwdownload,format=p010le,format=yuv420p10le"]),
        ]
        app = shared.raw_hashes(run / "recon.yuv")
        for name, middle in specs:
            out = v / (name+".framemd5")
            argv = base + middle + tail + [str(out)]
            row = {"name":name,"argv":argv,"started_utc":shared.utc()}
            receipt["commands"].append(row); save()
            t = time.monotonic()
            log = v / (name+".log")
            with log.open("w") as f:
                proc = subprocess.run(argv, cwd=v, stdout=f, stderr=subprocess.STDOUT)
            row.update(returncode=proc.returncode, seconds=time.monotonic()-t,
                       log=shared.identity(log), finished_utc=shared.utc())
            if out.exists(): row["output"] = shared.identity(out)
            save()
            assert proc.returncode == 0
            assert app == shared.parse_framemd5(out), f"App/{name} mismatch"
        receipt["identity_after"] = shared.tools()
        assert receipt["identity_before"] == receipt["identity_after"]
        receipt["launch_tools_after"] = {p:shared.identity(p) for p in receipt["launch_tools_before"]}
        assert receipt["launch_tools_before"] == receipt["launch_tools_after"]
        assert inputs == {n:shared.identity(run/n) for n in inputs}
        for field in ("script","source_script","shared_helper","probe"):
            assert receipt[field] == shared.identity(receipt[field]["path"])
        for row in receipt["commands"]:
            for field in ("log","output"): assert row[field] == shared.identity(row[field]["path"])
        receipt.update(status="admitted", all336_allplanes_app_dav1d_libaom_NVDEC_exact=True,
                       hashes=app, recon=inputs["recon.yuv"], finished_utc=shared.utc())
        save()
        print(json.dumps({"status":"admitted","frames":len(app),"tag":a.tag}))
    except BaseException as e:
        receipt.update(status="failed",error=repr(e),finished_utc=shared.utc()); save()
        raise

if __name__ == "__main__": main()
