#!/usr/bin/env python3
"""Compact R12 result and artifact identities, without rerunning metrics."""
import hashlib,json,sys
from pathlib import Path
P=Path(__file__).resolve().parent
def ident(p):
    p=Path(p).resolve()
    with p.open("rb") as f:s=hashlib.file_digest(f,"sha256").hexdigest()
    return dict(path=str(p),sha256=s,size=p.stat().st_size)
def main():
    out=Path(sys.argv[1]);assert not out.exists()
    rp=P/"run-1/result.json";assert ident(rp)["sha256"]=="9caf06214e249306788a6e58a22d134ed86284b4183fb38f815d8ccf236029d9"
    r=json.loads(rp.read_text());assert r["controls"]==json.loads((P/"run-1/baseline-control.json").read_text())
    files=["native.c","build.py","build-2/receipt.json","build-2/inputs-before.json",
           "build-2/inputs-after.json","build-2/native.so","experiment.py","run.py",
           "run-1-execution.json","run-1.log","run-1/receipt.json","run-1/baseline-control.json",
           "run-1/native-arrays.npz","run-1/result.json","render.py","visuals-1/manifest.json"]
    pops={}
    for roi in r["fixed_roi"]:
        rows=[u for u in r["units"] if roi in u["intersections"]]
        pops[roi]=dict(units=len(rows),pixels=sum(u["intersections"][roi]["pixels"] for u in rows),
            invoked_units=sum(u["invoked"] for u in rows),
            invoked_pixels=sum(u["intersections"][roi]["pixels"] for u in rows if u["invoked"]),
            changed_from_fp={arm:sum(u["intersections"][roi]["changed_from_fp"][arm] for u in rows) for arm in ("b_same_q","fp_q32")})
    d={k:r[k] for k in ("status","scope","controls","all_arms_C_runtime_exact","generated_fp_tables","original","coding_input","fixed_roi","semantics")}
    d.update(populations=pops,artifacts=[ident(P/f) for f in files],summarizer=ident(__file__),
             limitation="No encoded output changed. No new packet rate, GPU/full-window result, motion playback or repair qualification.")
    out.write_text(json.dumps(d,indent=2,allow_nan=False)+"\n");print(json.dumps(ident(out)))
if __name__=="__main__":
    if not __debug__:raise SystemExit("optimized Python prohibited")
    main()
