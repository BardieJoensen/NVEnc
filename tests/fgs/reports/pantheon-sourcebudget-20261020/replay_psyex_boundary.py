#!/usr/bin/env python3
"""Byte-neutral R8 observation replay of a bound unmodified pass2 command."""
import struct
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import datetime as dt

ROOT=Path(os.environ.get("PANTHEON_SOURCEBUDGET_ROOT","/tmp/downloads/codex-work/pantheon-sourcebudget-20261020"))
OBS=ROOT/"parent/psyex-boundary-r9"
APP=OBS/"build/bin/SvtAv1EncApp"
LIB=OBS/"build/bin/libSvtAv1Enc.so.3.0.2"
ORIGINAL=ROOT/"worker/psyex-r8/runs/e05-1440/psyex-1x1"
ORIGINAL_SHA="ceea9943cb7b0fd31331a7505089ac72bb06dc78c7e150589f0972d469cfa138"
RUNNER_SHA="933ef9a3607a6e8e0b46f4bb1c31e0d885cac11590bf18b6ecc3ebd6bb54ca75"
SOURCE_SHA="12f345e1f738b97fd00d9b9b2978864c53df995ad7590374edc21d31004124ce"
PATCH_SHA="69c61c844532966496bc313cb2beaeb6d867bae5f93b5139c2774f4f0d069f3e"
SCHEMA_SHA="c9f4cf3095d91ab280738aa8c9cd4f5d21326bbd98a895ab0d51e00c5676477a"

def sha(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""):h.update(b)
    return h.hexdigest()

def ident(p):
    p=Path(p);return {"path":str(p),"sha256":sha(p),"size":p.stat().st_size}

def utc():return dt.datetime.now(dt.timezone.utc).isoformat()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode",choices=["off","on"]);ap.add_argument("tag")
    ap.add_argument("app_sha256");ap.add_argument("library_sha256")
    a=ap.parse_args()
    assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*",a.tag)
    for k in ("LD_PRELOAD","LD_LIBRARY_PATH","LD_AUDIT","SVT_PANTHEON_BOUNDARY_FD","SVT_PSYEX_OBS_PASS"):
        assert not os.environ.get(k), k
    assert shutil.disk_usage(ROOT).free>=130*2**30
    assert sha(ORIGINAL/"command.json")==ORIGINAL_SHA
    original=json.loads((ORIGINAL/"command.json").read_text())
    assert original["status"]=="encoded" and original["returncode"]==0
    assert sha(APP)==a.app_sha256 and sha(LIB)==a.library_sha256
    assert sha(OBS/"measured-runner.sh")==RUNNER_SHA
    assert sha(OBS/"source-manifest-before.json")==sha(OBS/"source-manifest-after.json")==SOURCE_SHA
    assert sha(OBS/"boundary.patch")==PATCH_SHA and sha(OBS/"schema.json")==SCHEMA_SHA
    blog=(OBS/"build-receipt.log").read_text()
    assert blog.count("final_status=build_complete\n")==1 and blog.endswith("exit_code=0\n")
    build_files={}
    for line in (OBS/"build-artifact-hashes.txt").read_text().splitlines():
        digest,p=line.split(maxsplit=1);p=p.lstrip("*")
        assert sha(p)==digest, p
        build_files[p]=digest
    assert build_files[str(APP)]==a.app_sha256 and build_files[str(LIB)]==a.library_sha256
    for key in ("input","ivf_output","recon","stats","stats_snapshot"):
        assert sha(original[key]["path"])==original[key]["sha256"],key
    run=OBS/"runs"/a.tag;run.mkdir(parents=True,exist_ok=False)
    receipt={"status":"prepared","mode":a.mode,"tag":a.tag,"case":"e05-1440","created_utc":utc(),
        "original_receipt":ident(ORIGINAL/"command.json"),"unmodified_ivf":original["ivf_output"],
        "unmodified_recon":original["recon"],"app":ident(APP),"library":ident(LIB),
        "build_artifacts":build_files,"build_receipt":ident(OBS/"build-receipt.log"),
        "patch":ident(OBS/"boundary.patch"),"schema":ident(OBS/"schema.json"),
        "scope":"Boundary observation neutrality only; trace framing and stage admission are separate; timing is replay cost."}
    def save():(run/"command.json").write_text(json.dumps(receipt,indent=2)+"\n")
    save();fd=None
    try:
        shutil.copyfile(__file__,run/"measured-runner.py")
        stats=run/"pass.stats";shutil.copyfile(original["stats"]["path"],stats)
        cmd=list(original["commands"]["pass2"])
        assert cmd[6]==original["binary"]["path"] and cmd[cmd.index("--pass")+1]=="2"
        cmd[6]=str(APP)
        for flag,value in {"--stats":str(stats),"-b":str(run/"out.ivf"),"-o":str(run/"recon.yuv")}.items():
            assert cmd.count(flag)==1
            cmd[cmd.index(flag)+1]=value
        receipt["argv"]=cmd
        receipt["script"]=ident(run/"measured-runner.py");receipt["source_script"]=ident(__file__)
        paths=[APP,LIB,Path(__file__).resolve(),run/"measured-runner.py",stats,
               ORIGINAL/"command.json",Path(original["input"]["path"]),OBS/"build-receipt.log",
               OBS/"build-artifact-hashes.txt",OBS/"boundary.patch",OBS/"schema.json",
               Path("/usr/bin/nice"),Path("/usr/bin/taskset"),Path("/usr/bin/ldd")]
        def identities():return {str(p):sha(p) for p in paths}
        receipt["identity_before"]=identities()
        env={k:v for k,v in os.environ.items() if not k.startswith(("PANTHEON_","SVT_PSYEX_","SVT_PANTHEON_"))}
        env["LD_LIBRARY_PATH"]=str(OBS/"build/bin")
        ld=subprocess.run(["/usr/bin/ldd",str(APP)],env=env,capture_output=True,text=True)
        receipt["ldd"]={"argv":["/usr/bin/ldd",str(APP)],"returncode":ld.returncode,"stdout":ld.stdout,"stderr":ld.stderr}
        found=re.search(r"libSvtAv1Enc\.so\.3\s+=>\s+(\S+)",ld.stdout)
        assert ld.returncode==0 and found and Path(found.group(1)).resolve()==LIB.resolve()
        trace=run/"boundary.bin"
        if a.mode=="on":
            fd=os.open(trace,os.O_CREAT|os.O_EXCL|os.O_APPEND|os.O_WRONLY,0o644)
            env["SVT_PANTHEON_BOUNDARY_FD"]=str(fd)
        receipt["environment"]={k:env[k] for k in ("LD_LIBRARY_PATH","SVT_PANTHEON_BOUNDARY_FD") if k in env}
        receipt["stats"]=ident(stats);receipt["status"]="running";receipt["start_utc"]=utc()
        receipt["resource_before"]={"free_bytes":shutil.disk_usage(ROOT).free,"loadavg":Path("/proc/loadavg").read_text()}
        save();t=time.monotonic()
        with (run/"encode.log").open("w") as log:
            p=subprocess.run(cmd,cwd=run,env=env,stdout=log,stderr=subprocess.STDOUT,
                             pass_fds=() if fd is None else (fd,))
        receipt.update(returncode=p.returncode,seconds=time.monotonic()-t,end_utc=utc(),
                       log=ident(run/"encode.log"))
        if fd is not None:os.close(fd);fd=None
        for name in ("out.ivf","recon.yuv"):
            if (run/name).exists():receipt[name]=ident(run/name)
        if trace.exists():receipt["observation"]=ident(trace)
        save()
        assert p.returncode==0
        assert receipt["out.ivf"]["sha256"]==original["ivf_output"]["sha256"],"IVF differs from unmodified"
        assert receipt["recon.yuv"]["sha256"]==original["recon"]["sha256"],"App reconstruction differs"
        assert ident(stats)==receipt["stats"] and sha(stats)==original["stats"]["sha256"]
        if a.mode=="on":
            assert 64<trace.stat().st_size<=512*2**20
            with trace.open("rb") as f: header=struct.unpack("<8Q",f.read(64))
            assert header[:6]==(0x31594342504e5450,1,1,0,216,0)
            # Full framing/generation/sample admission is a separate validator.
        else:assert not trace.exists()
        receipt["identity_after"]=identities();assert receipt["identity_before"]==receipt["identity_after"]
        receipt.update(status="neutral",exact_unmodified_ivf=True,exact_unmodified_reconstruction=True)
        save();print(json.dumps({"tag":a.tag,"mode":a.mode,"status":"neutral","seconds":receipt["seconds"]}))
    except BaseException as e:
        receipt.update(status="failed",error=repr(e),end_utc=utc());save();raise
    finally:
        if fd is not None:os.close(fd)

if __name__=="__main__":main()
