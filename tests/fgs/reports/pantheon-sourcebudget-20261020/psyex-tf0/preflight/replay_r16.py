#!/usr/bin/env python3
"""Byte-neutral R11 coefficient/boundary replay of a completed R16 pass2 arm."""
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
OBS=ROOT/"parent/psyex-coeff-r11"
HERE=ROOT/"worker/psyex-r16-tf0-budget"
OUTROOT=HERE/"replays"
APP=OBS/"build/bin/SvtAv1EncApp"
LIB=OBS/"build/bin/libSvtAv1Enc.so.3.0.2"
PINS=OBS/"completed-build-pins.json"
ORIGINAL=None
ORIGINAL_SHA=None
EXPECTED_ENCODER_SCRIPT_SHA="2c14604755be12ae1f8fe996cc93ea9486963f629e44bc3a1a7d21d40076469b"
EXPECTED_CONTRACT_SHA="5ed81849c12af6daeb206e2184fa7ad0ddacb4b6d7d3ec35fab3b845c9901c71"
EXPECTED_PINS_SHA="f32ace44e5e449ce0898b6566cc9bb3195a8daa2fcb0b9d7f20b0e0d8b3c54d8"
ENCODER_SOURCE=HERE/"encode_r16.py"

def sha(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""):h.update(b)
    return h.hexdigest()

def ident(p):
    p=Path(p);return {"path":str(p),"sha256":sha(p),"size":p.stat().st_size}

def utc():return dt.datetime.now(dt.timezone.utc).isoformat()

def load_encoder_module():
    import importlib.util
    assert sha(ENCODER_SOURCE)==EXPECTED_ENCODER_SCRIPT_SHA
    spec=importlib.util.spec_from_file_location("r16_encoder_lineage",ENCODER_SOURCE)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def ivf_population(path):
    b=Path(path).read_bytes()
    assert len(b)>=32 and b[:4]==b"DKIF"
    n=struct.unpack_from("<I",b,24)[0]; pos=32; pts=[]
    for _ in range(n):
        assert pos+12<=len(b); size,pt=struct.unpack_from("<IQ",b,pos); pos+=12
        assert pos+size<=len(b); pos+=size; pts.append(pt)
    assert pos==len(b) and n==336 and len(set(pts))==336 and pts==sorted(pts)
    return {"count":n,"pts_first":pts[0],"pts_last":pts[-1]}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode",choices=["off","on"]);ap.add_argument("tag")
    ap.add_argument("--original-receipt",required=True)
    ap.add_argument("--original-receipt-sha",required=True)
    ap.add_argument("--pins",default=str(PINS))
    a=ap.parse_args()
    if not __debug__: raise SystemExit("optimized Python is rejected")
    assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*",a.tag)
    assert a.pins==str(PINS), "only finalized parent pins are accepted"
    global ORIGINAL, ORIGINAL_SHA
    ORIGINAL=Path(a.original_receipt).resolve(); ORIGINAL_SHA=a.original_receipt_sha
    assert ORIGINAL.is_file() and sha(ORIGINAL)==ORIGINAL_SHA
    for k in ("LD_PRELOAD","LD_LIBRARY_PATH","LD_AUDIT","SVT_PANTHEON_BOUNDARY_FD","SVT_PANTHEON_COEFF_FD","SVT_PSYEX_OBS_PASS"):
        assert not os.environ.get(k), k
    assert shutil.disk_usage(ROOT).free>=130*2**30
    assert PINS.is_file(), "missing finalized build pins"
    pins=json.loads(PINS.read_text())
    assert pins.get("status")=="build_complete" and pins.get("returncode") == 0
    for key in ("app","library","build_receipt","source_manifest","patch","helper","schema"):
        x=pins[key]; p=Path(x["path"]); assert p.is_file() and ident(p)==x, key
    blog=Path(pins["build_receipt"]["path"]).read_text()
    assert blog.count("final_status=build_complete\n")==1 and blog.rstrip().endswith("exit_code=0"), "build receipt not complete"
    global APP,LIB
    APP=Path(pins["app"]["path"]); LIB=Path(pins["library"]["path"])
    assert sha(ORIGINAL)==ORIGINAL_SHA
    lineage_mod=load_encoder_module()
    original,lineage_paths=lineage_mod.validate_chain(ORIGINAL,ORIGINAL_SHA)
    for dep in lineage_paths:
        assert Path(dep).is_file()
    assert original["status"]=="encoded" and original["returncode"]==0
    assert original.get("case")=="e05-1440" and isinstance(original.get("request_kbps"), int) and original["request_kbps"] > 0
    assert original.get("commands", {}).get("pass2") and original["commands"].get("pass2")[original["commands"]["pass2"].index("--pass") + 1] == "2"
    assert original.get("contract", {}).get("sha256") == EXPECTED_CONTRACT_SHA
    assert original.get("r8_command_receipt", {}).get("path")
    assert original.get("settings",{}).get("--enable-tf")=="0"
    assert "--min-qp" not in original.get("settings",{}) and "--max-qp" not in original.get("settings",{})
    assert original.get("r8_command_receipt", {}).get("sha256") == "ceea9943cb7b0fd31331a7505089ac72bb06dc78c7e150589f0972d469cfa138"
    assert original.get("identity_before") == original.get("identity_after"), "R16 original identity drift"
    source_mbps=float(original["source_mbps"]); actual_mbps=float(original["actual_mbps"])
    assert .99*source_mbps <= actual_mbps <= source_mbps, "selected R16 receipt is not matched/original-cap eligible"
    for c in (original["commands"]["pass1"], original["commands"]["pass2"]):
        assert c[c.index("--tbr")+1] == str(original["request_kbps"])
    assert original.get("executed_script",{}).get("sha256")==EXPECTED_ENCODER_SCRIPT_SHA
    assert original.get("contract",{}).get("sha256")==EXPECTED_CONTRACT_SHA
    assert sha(PINS)==EXPECTED_PINS_SHA, "finalized R11 pins changed"
    assert APP.is_file() and LIB.is_file()
    assert pins["app"]["sha256"]==sha(APP) and pins["library"]["sha256"]==sha(LIB)
    build_files={x["path"]:x["sha256"] for x in pins.values() if isinstance(x,dict) and "path" in x and "sha256" in x}
    assert build_files[str(APP)]==pins["app"]["sha256"] and build_files[str(LIB)]==pins["library"]["sha256"]
    for key,x in pins.items():
        if isinstance(x,dict) and {"path","sha256","size"} <= set(x):
            assert ident(x["path"])==x, key
    for key in ("input","ivf_output","recon","stats","stats_snapshot"):
        assert sha(original[key]["path"])==original[key]["sha256"],key
    assert original["stats"]["sha256"]==original["stats_snapshot"]["sha256"]
    run=OUTROOT/a.tag;run.mkdir(parents=True,exist_ok=False)
    receipt={"status":"prepared","mode":a.mode,"tag":a.tag,"case":"e05-1440","created_utc":utc(),
        "original_receipt":ident(ORIGINAL),"unmodified_ivf":original["ivf_output"],
        "unmodified_recon":original["recon"],"app":ident(APP),"library":ident(LIB),
        "build_artifacts":build_files,"build_receipt":pins["build_receipt"],
        "patch":pins["patch"],"schema":pins["schema"],"pins":ident(PINS),
        "scope":"R16 coefficient and boundary observation neutrality only; output decisions may not be inferred from replay timing."}
    def save():(run/"command.json").write_text(json.dumps(receipt,indent=2)+"\n")
    save();fd=None; cfd=None
    try:
        shutil.copyfile(__file__,run/"measured-runner.py")
        stats=run/"pass.stats";shutil.copyfile(original["stats"]["path"],stats)
        cmd=list(original["commands"]["pass2"])
        assert len(cmd)>6 and cmd[6]==original["binary"]["path"] and cmd[cmd.index("--pass")+1]=="2"
        cmd[6]=str(APP)
        for flag,value in {"--stats":str(stats),"-b":str(run/"out.ivf"),"-o":str(run/"recon.yuv")}.items():
            assert cmd.count(flag)==1
            cmd[cmd.index(flag)+1]=value
        receipt["argv"]=cmd
        receipt["script"]=ident(run/"measured-runner.py");receipt["source_script"]=ident(__file__)
        paths=[APP,LIB,ENCODER_SOURCE,Path(__file__).resolve(),run/"measured-runner.py",stats,
               ORIGINAL,Path(original["input"]["path"]),PINS,*lineage_paths,
               *[Path(k) for k in original.get("identity_after",{})],
               Path(pins["build_receipt"]["path"]),Path(pins["patch"]["path"]),Path(pins["schema"]["path"]),
               Path("/usr/bin/nice"),Path("/usr/bin/taskset"),Path("/usr/bin/ldd")]
        paths.extend(Path(x["path"]) for x in pins.values() if isinstance(x,dict) and "path" in x)
        paths=list(dict.fromkeys(paths))
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
            coeff=run/"coeff.bin"
            cfd=os.open(coeff,os.O_CREAT|os.O_EXCL|os.O_APPEND|os.O_WRONLY,0o644)
            env["SVT_PANTHEON_BOUNDARY_FD"]=str(fd); env["SVT_PANTHEON_COEFF_FD"]=str(cfd)
        receipt["environment"]={k:env[k] for k in ("LD_LIBRARY_PATH","SVT_PANTHEON_BOUNDARY_FD","SVT_PANTHEON_COEFF_FD") if k in env}
        receipt["stats"]=ident(stats);receipt["status"]="running";receipt["start_utc"]=utc()
        receipt["resource_before"]={"free_bytes":shutil.disk_usage(ROOT).free,"loadavg":Path("/proc/loadavg").read_text()}
        save();t=time.monotonic()
        with (run/"encode.log").open("w") as log:
            p=subprocess.run(cmd,cwd=run,env=env,stdout=log,stderr=subprocess.STDOUT,
                             pass_fds=tuple(x for x in (fd,cfd) if x is not None))
        receipt.update(returncode=p.returncode,seconds=time.monotonic()-t,end_utc=utc(),
                       log=ident(run/"encode.log"))
        if fd is not None:
            os.close(fd); fd=None
        if cfd is not None:
            os.close(cfd); cfd=None
        for name in ("out.ivf","recon.yuv"):
            if (run/name).exists():receipt[name]=ident(run/name)
        if trace.exists():receipt["observation"]=ident(trace)
        if (run/"coeff.bin").exists():receipt["coefficient_observation"]=ident(run/"coeff.bin")
        save()
        assert p.returncode==0
        assert receipt["out.ivf"]["sha256"]==original["ivf_output"]["sha256"],"IVF differs from unmodified"
        assert receipt["recon.yuv"]["sha256"]==original["recon"]["sha256"],"App reconstruction differs"
        assert ident(stats)==receipt["stats"] and sha(stats)==original["stats"]["sha256"]
        receipt["ivf_population"] = ivf_population(run/"out.ivf")
        if a.mode=="on":
            assert 64<trace.stat().st_size<=1<<30
            with trace.open("rb") as f: header=struct.unpack("<8Q",f.read(64))
            assert header[:6]==(0x31594342504e5450,1,1,0,216,0)
            receipt["observed_target_source_index"] = header[4]
            coeff=run/"coeff.bin"; assert 64<coeff.stat().st_size<=1<<30
            with coeff.open("rb") as f: cheader=struct.unpack("<8Q",f.read(64))
            assert cheader[0]==0x314346504e5450 and cheader[1]==1 and cheader[2]==10 and cheader[4]==216
        else:
            assert not trace.exists() and not (run/"coeff.bin").exists()
        receipt["identity_after"]=identities();assert receipt["identity_before"]==receipt["identity_after"]
        receipt.update(status="neutral",exact_unmodified_ivf=True,exact_unmodified_reconstruction=True)
        save();print(json.dumps({"tag":a.tag,"mode":a.mode,"status":"neutral","seconds":receipt["seconds"]}))
    except BaseException as e:
        receipt.update(status="failed",error=repr(e),end_utc=utc());save();raise
    finally:
        if fd is not None:
            os.close(fd); fd=None
        if cfd is not None:
            os.close(cfd); cfd=None

if __name__=="__main__":main()
