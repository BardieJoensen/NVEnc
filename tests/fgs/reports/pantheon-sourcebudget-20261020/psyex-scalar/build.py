#!/usr/bin/env python3
"""Read-only R11 object reuse, fresh private native helper and truthful receipts."""
import datetime as dt, hashlib, json, os, shlex, shutil, subprocess, time
from pathlib import Path
P=Path(__file__).resolve().parent
R11=P.parent/"psyex-coeff-r11"
def ident(p):
    p=Path(p).resolve()
    with p.open("rb") as f: sha=hashlib.file_digest(f,"sha256").hexdigest()
    return dict(path=str(p),sha256=sha,size=p.stat().st_size)
def main():
    for key in ("LD_PRELOAD","LD_LIBRARY_PATH","LD_AUDIT","CFLAGS","LDFLAGS","CC"):
        assert not os.environ.get(key),key
    assert shutil.disk_usage(P).free > 130*10**9
    pins_path=R11/"completed-build-pins.json"
    assert ident(pins_path)["sha256"]=="f32ace44e5e449ce0898b6566cc9bb3195a8daa2fcb0b9d7f20b0e0d8b3c54d8"
    pins=json.loads(pins_path.read_text())
    for key in ("app","library","source_manifest","manifest_after","build_ninja","cmakecache","runner","build_receipt","tools"):
        assert ident(pins[key]["path"])==pins[key],key
    manifest=json.loads(Path(pins["source_manifest"]["path"]).read_text())
    for name,size,sha in manifest:
        got=ident(R11/"source"/name); assert (got["size"],got["sha256"])==(size,sha),name
    lines=(R11/"build/build.ninja").read_text().splitlines()
    link=next(x for x in lines if x.startswith("build bin/libSvtAv1Enc.so.3.0.2: "))
    objects=[R11/"build"/x for x in link.split(": ",1)[1].split(" || ",1)[0].split()[1:]]
    assert len(objects)>200 and all(x.suffix==".o" for x in objects)
    idx=next(i for i,x in enumerate(lines) if x.startswith("build Source/Lib/Codec/CMakeFiles/CODEC.dir/full_loop.c.o: "))
    includes=shlex.split(next(x for x in lines[idx:idx+12] if x.startswith("  INCLUDES = ")).split(" = ",1)[1])
    defines=shlex.split(next(x for x in lines[idx:idx+12] if x.startswith("  DEFINES = ")).split(" = ",1)[1])
    cc=Path(shutil.which("cc")).resolve()
    out=P/"build-2";out.mkdir(exist_ok=False)
    exports=out/"exports.map";exports.write_text("{ global: rp_init; rp_fp_tables; rp_quant; rp_inverse; local: *; };\n")
    inputs=[Path(__file__),P/"native.c",exports,pins_path,R11/"build/build.ninja",cc]+objects
    before=[ident(x) for x in inputs]
    (out/"inputs-before.json").write_text(json.dumps(before,indent=2)+"\n")
    receipt=dict(status="prepared",started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                 source_manifest=pins["source_manifest"],inputs_before=ident(out/"inputs-before.json"),commands=[])
    def save():(out/"receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")
    save()
    try:
        commands=[
            ["/usr/bin/nice","-n","10","/usr/bin/taskset","-c","0-3",str(cc),"-std=gnu99","-O2","-fPIC","-fvisibility=hidden","-Wall","-Wextra","-Werror=implicit-function-declaration",*defines,*includes,"-c",str(P/"native.c"),"-o",str(out/"native.o")],
            ["/usr/bin/nice","-n","10","/usr/bin/taskset","-c","0-3",str(cc),"-shared","-flto=4","-Wl,--no-undefined","-Wl,--version-script="+str(exports),"-o",str(out/"native.so"),str(out/"native.o"),*[str(x) for x in objects],"-lm","-lpthread"]
        ]
        for i,cmd in enumerate(commands):
            log=out/f"command-{i}.log"; t=time.monotonic()
            with log.open("x") as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
            receipt["commands"].append(dict(argv=cmd,returncode=r.returncode,seconds=time.monotonic()-t,log=ident(log)));save()
            assert r.returncode==0,log
        after=[ident(x) for x in inputs];assert before==after
        for name,size,sha in manifest:
            got=ident(R11/"source"/name); assert (got["size"],got["sha256"])==(size,sha),name
        (out/"inputs-after.json").write_text(json.dumps(after,indent=2)+"\n")
        receipt.update(status="complete",inputs_after=ident(out/"inputs-after.json"),library=ident(out/"native.so"),object=ident(out/"native.o"))
    except BaseException as e:
        receipt.update(status="failed",error=repr(e));raise
    finally:
        receipt["ended_utc"]=dt.datetime.now(dt.timezone.utc).isoformat();save()
    print(json.dumps({k:receipt[k] for k in ("status","library","ended_utc")}))
if __name__=="__main__":
    if not __debug__:raise SystemExit("optimized Python prohibited")
    main()
