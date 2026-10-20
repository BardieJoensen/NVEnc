#!/usr/bin/env python3
"""Record the actual bounded R12 subprocess command and immutable identities."""
import datetime as dt, hashlib, json, subprocess, time
from pathlib import Path
P=Path(__file__).resolve().parent
PY=P.parents[1]/"analysis-venv/bin/python"
EXPECTED="87eb15f8a7c082bb875f91edb790ed66a8e592db9d64bc5f554943040f705ee2"
def ident(p):
    p=Path(p).resolve()
    with p.open("rb") as f: sha=hashlib.file_digest(f,"sha256").hexdigest()
    return dict(path=str(p),sha256=sha,size=p.stat().st_size)
def main():
    out=P/"run-1";log=P/"run-1.log";receipt_path=P/"run-1-execution.json"
    assert not out.exists() and not log.exists() and not receipt_path.exists()
    assert ident(P/"experiment.py")["sha256"]==EXPECTED
    paths=[Path(__file__),P/"experiment.py",P/"native.c",P/"build.py",P/"build-2/receipt.json",P/"build-2/native.so",PY]
    argv=["/usr/bin/nice","-n","10","/usr/bin/taskset","-c","8-11",str(PY),str(P/"experiment.py"),str(out)]
    receipt=dict(status="prepared",argv=argv,started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                 inputs_before=[ident(p) for p in paths])
    def save():receipt_path.write_text(json.dumps(receipt,indent=2)+"\n")
    save();start=time.monotonic()
    try:
        with log.open("x") as f:r=subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT)
        receipt.update(returncode=r.returncode,seconds=time.monotonic()-start,log=ident(log))
        assert r.returncode==0
        receipt["inputs_after"]=[ident(p) for p in paths];assert receipt["inputs_before"]==receipt["inputs_after"]
        inner=json.loads((out/"receipt.json").read_text());assert inner["status"]=="complete"
        receipt.update(status="complete",inner_receipt=ident(out/"receipt.json"),result=ident(out/"result.json"))
    except BaseException as e:
        receipt.update(status="failed",error=repr(e));raise
    finally:
        receipt["ended_utc"]=dt.datetime.now(dt.timezone.utc).isoformat();save()
    print(json.dumps(receipt))
if __name__=="__main__":
    if not __debug__:raise SystemExit("optimized Python prohibited")
    main()
