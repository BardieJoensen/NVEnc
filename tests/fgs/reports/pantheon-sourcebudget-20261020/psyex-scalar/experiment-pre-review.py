#!/usr/bin/env python3
"""R12 exact native controls and fixed-decision scalar diagnostic, never an encode."""
import argparse, ctypes as C, datetime as dt, hashlib, importlib.util, json, sys, time
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent; R11=P.parent/"psyex-coeff-r11"
ASHA="44b8037c2a922b7e893cd66c8488f3683c45b8859400ff6b082bd0910286f64e"
ADSHA="f9aba0b6b1d5d8b73c606698130a64e46ec0bc7f55a6d7363ea113bd45e1548a"
BSHA="4b56e9cbd1450f68ec42d02a70d6db2e082db065c6314f34ef17443ef6cb7df5"
LSHA="07fe2554623523d8e6dfe5218d94a89cdb2437bb2221123a86678090af6f2228"
ARMS=("fp_baseline","b_same_q","fp_q32")
def ident(p):
    p=Path(p).resolve()
    with p.open("rb") as f: sha=hashlib.file_digest(f,"sha256").hexdigest()
    return dict(path=str(p),sha256=sha,size=p.stat().st_size)
def exact(d):
    assert ident(d["path"])==d,d
    return Path(d["path"])
def load(path,name,sha):
    assert ident(path)["sha256"]==sha
    s=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def ptr(a,dtype,shape=None):
    assert isinstance(a,np.ndarray) and a.dtype==np.dtype(dtype) and a.flags.c_contiguous
    if shape is not None:assert a.shape==shape
    return C.c_void_p(a.ctypes.data)
class Native:
    def __init__(self,path):
        self.lib=C.CDLL(str(path))
        self.lib.rp_init.argtypes=[];self.lib.rp_init.restype=C.c_uint64
        self.lib.rp_fp_tables.argtypes=[C.c_int,C.c_int,C.c_void_p];self.lib.rp_fp_tables.restype=C.c_int
        self.lib.rp_quant.argtypes=[C.c_int,C.c_int,C.c_void_p,C.c_int,*([C.c_void_p]*5),C.c_int,*([C.c_void_p]*3)]
        self.lib.rp_quant.restype=C.c_int
        self.lib.rp_inverse.argtypes=[*([C.c_int]*7),*([C.c_void_p]*3)];self.lib.rp_inverse.restype=C.c_int
        self.flags=int(self.lib.rp_init())
    def tables(self,q):
        out=np.zeros((3,8),dtype="<i2")
        assert self.lib.rp_fp_tables(q,0,ptr(out,"<i2"))==0
        return out
    def quant(self,t,mode,tables):
        z=t["begin"];n=z["n"]
        qm=np.frombuffer(t["qm"],dtype="u1");iqm=np.frombuffer(t["iqm"],dtype="u1")
        assert qm.size==iqm.size and qm.size in (0,n)
        q=np.zeros(n,dtype="<i4");dq=np.zeros(n,dtype="<i4");eob=np.zeros(1,dtype="<u2")
        rc=self.lib.rp_quant(mode,z["tx"],ptr(t["raw"],"<i4",(n,)),n,
            ptr(tables,"<i2",(7,8)),ptr(t["scan"],"<i2",(n,)),ptr(t["iscan"],"<i2",(n,)),
            ptr(qm,"u1") if qm.size else None,ptr(iqm,"u1") if iqm.size else None,
            t["info"]["log_scale"],ptr(q,"<i4"),ptr(dq,"<i4"),ptr(eob,"<u2"))
        assert rc==0,("quant",z["token"],mode,rc)
        nz=np.flatnonzero(q[t["scan"]]);assert int(eob[0])==(int(nz[-1])+1 if nz.size else 0)
        assert np.all(dq[q==0]==0)
        return dict(q=q,dq=dq,eob=int(eob[0]))
    def inverse(self,t,dq,eob,dispatch):
        z=t["begin"];w,h,n=z["w"],z["h"],z["n"];out=np.zeros((h,w),dtype="<u2")
        rc=self.lib.rp_inverse(dispatch,z["tx"],z["type"],w,h,n,eob,
            ptr(dq,"<i4",(n,)),ptr(t["predictor"],"<u2",(h,w)),ptr(out,"<u2"))
        assert rc==0,("inverse",z["token"],dispatch,rc)
        assert np.all(out<=1023)
        if eob==0:assert np.array_equal(out,t["predictor"])
        return out
    def paired(self,t,mode,tables):
        direct=self.quant(t,mode,tables);runtime=self.quant(t,mode+2,tables)
        assert direct["eob"]==runtime["eob"],("C/runtime eob",t["begin"]["token"],mode)
        for k in ("q","dq"):assert np.array_equal(direct[k],runtime[k]),("C/runtime "+k,t["begin"]["token"],mode)
        di=self.inverse(t,direct["dq"],direct["eob"],0)
        ri=self.inverse(t,runtime["dq"],runtime["eob"],1)
        assert np.array_equal(di,ri),("C/runtime inverse",t["begin"]["token"],mode)
        return dict(**runtime,inverse=ri)
def main():
    ap=argparse.ArgumentParser();ap.add_argument("out",type=Path);args=ap.parse_args()
    out=args.out;out.mkdir(exist_ok=False)
    receipt=dict(status="prepared",argv=sys.argv,python=ident(sys.executable),
                 started_utc=dt.datetime.now(dt.timezone.utc).isoformat())
    start=time.monotonic()
    def save():(out/"receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")
    save()
    try:
        a=load(R11/"analyze.py","r12_metric_logic",ASHA)
        adp=R11/"admitted-1/admission.json";assert ident(adp)["sha256"]==ADSHA
        ad=json.loads(adp.read_text());assert ad["status"]=="admitted"
        for k in ("all336_exact","source_predictor_preloop_exact","final_dq_eob_iqm_exact","actual_committed_owner"):assert ad[k] is True
        for k in ("pins","trace","boundary","decoder_admission","targets","token_manifest","script"):exact(ad[k])
        bp=P/"build-2/receipt.json";assert ident(bp)["sha256"]==BSHA
        build=json.loads(bp.read_text());assert build["status"]=="complete"
        for c in build["commands"]:assert c["returncode"]==0;exact(c["log"])
        bbefore=json.loads(exact(build["inputs_before"]).read_text())
        assert bbefore==json.loads(exact(build["inputs_after"]).read_text())
        for d in bbefore:exact(d)
        lib=exact(build["library"]);assert build["library"]["sha256"]==LSHA
        v=a.mod(a.V,"r12_r11_validator",a.VSHA);u=a.mod(a.U,"r12_unit_helpers",a.USHA);h=u.helper()
        r9path=a.R/"parent/psyex-boundary-r9/analysis-1.json"
        assert ident(r9path)["sha256"]=="b2d4a19ac93eeab29cb78870cea45f03165f7741f22584955081498553ed5bc5"
        inherited=json.loads(r9path.read_text())["metric_helpers"]
        for d in inherited.values():exact(d)
        tokens,terminal=v.parse(exact(ad["trace"]));assert terminal==ad["terminal"] and len(tokens)==2907
        joins=json.loads(exact(ad["token_manifest"]).read_text());jmap={r["token"]:r for r in joins}
        assert set(tokens)==set(jmap)
        dec=json.loads(exact(ad["decoder_admission"]).read_text())
        refs={s:u.load_luma(exact(dec["r9_stages"][s])) for s in ("original","coding_input","postloop")}
        assert dec["r9_stages"]["original"]["sha256"]=="c2798d9c00f53bdbe7041575249b353a478a8f5557bc4dd5b61d9ae03f13ea12"
        assert dec["r9_stages"]["coding_input"]["sha256"]=="b8ad2257c0bab9febd99eeefc05156f64c059bf028a19e72443a24af7af92b68"
        units=json.loads(exact(dec["artifacts"]["units"]).read_text())
        dependency_paths=[Path(__file__),P/"native.c",P/"build.py",bp,lib,adp,R11/"analyze.py",a.V,a.U,u.HELPER,
                          exact(ad["trace"]),exact(ad["token_manifest"]),exact(ad["decoder_admission"]),r9path]
        dependency_paths += [exact(d) for d in inherited.values()]
        dependency_paths += [exact(dec["r9_stages"][s]) for s in refs]
        before=[ident(p) for p in dependency_paths];receipt["inputs_before"]=before;save()
        native=Native(lib);receipt["runtime_cpu_flags"]=native.flags;save()
        invoked={k:t for k,t in tokens.items() if t["stages"]};assert len(invoked)==2187
        baseline={};qtables={}
        # All baseline controls complete before computing either novel arm.
        for key,t in invoked.items():
            assert t["stages"][0]["stage"]=="scalar_fp" and t["info"]["depth"]==10
            assert t["info"]["seg_delta"]==0 and t["info"]["actual_qindex"]>32
            qindex=t["info"]["actual_qindex"];fp=native.tables(qindex)
            assert np.array_equal(fp,t["tables"][[0,1,6]]),("native FP table mismatch",key,qindex)
            qtables[str(qindex)]=fp.tolist()
            base=native.paired(t,0,t["tables"]);capture=t["stages"][0]
            assert base["eob"]==capture["eob"],("baseline EOB",key)
            for field in ("q","dq","inverse"):
                assert np.array_equal(base[field],capture[field]),("baseline mismatch",key,field)
            rawc=native.inverse(t,t["raw"],t["raw_eob"],0)
            rawr=native.inverse(t,t["raw"],t["raw_eob"],1)
            assert np.array_equal(rawc,rawr) and np.array_equal(rawr,t["raw_inverse"]),("raw inverse",key)
            baseline[key]=base
        control=dict(status="exact_baseline",invoked=len(invoked),unchanged_owners=len(tokens)-len(invoked),
                     actual_qindex=sorted(map(int,qtables)),native_fp_tables=qtables,runtime_cpu_flags=native.flags,
                     checks=["generated FP tables equal captured","all baseline q/DQ/EOB/inverse exact",
                             "raw inverse C/runtime/capture exact","baseline C/runtime quantizer exact"],
                     scope="same-q B and q32 outcomes still require independent C/runtime agreement")
        (out/"baseline-control.json").write_text(json.dumps(control,indent=2)+"\n")
        receipt["baseline_control"]=ident(out/"baseline-control.json");save()
        newtables=native.tables(32);qtables["32"]=newtables.tolist()
        results={name:{} for name in ARMS};results["fp_baseline"]=baseline
        for key,t in invoked.items():
            results["b_same_q"][key]=native.paired(t,1,t["tables"])
            table=t["tables"].copy();table[[0,1,6]]=newtables
            results["fp_q32"][key]=native.paired(t,0,table)
        # Preserve complete native arrays with offsets, plus unchanged owner metadata.
        arrays={};rows=[];co=po=0
        for name in ARMS:
            arrays[name+"_q"]=np.concatenate([results[name][k]["q"] for k in invoked])
            arrays[name+"_dq"]=np.concatenate([results[name][k]["dq"] for k in invoked])
            arrays[name+"_inverse"]=np.concatenate([results[name][k]["inverse"].ravel() for k in invoked])
        for key,t in tokens.items():
            z=t["begin"];j=jmap[key];uid=j["unit"]
            row=dict(token=key,unit=uid,category=units[uid]["category"],begin=z,invoked=key in invoked)
            assert j["begin"]==z
            if key in invoked:
                row.update(coefficient_offset=co,pixel_offset=po,actual_qindex=t["info"]["actual_qindex"],
                           actual_tables=t["tables"].tolist(),qm_level=t["info"]["qm_level"],
                           arms={name:dict(eob=results[name][key]["eob"],qindex=32 if name=="fp_q32" else t["info"]["actual_qindex"],
                                          q=a.coeff_stats(results[name][key]["q"]),dq=a.coeff_stats(results[name][key]["dq"])) for name in ARMS})
                co+=z["n"];po+=z["w"]*z["h"]
            rows.append(row)
        np.savez_compressed(out/"native-arrays.npz",**arrays)
        frames,covered=a.make_mosaics(tokens)
        frames={k:frames[k] for k in ("predictor","raw_executed","final")}
        frames.update(refs)
        for name in ARMS:
            frame=np.full((1080,1920),np.nan)
            for key,t in tokens.items():
                z=t["begin"];x,y,w,hh=(z[k] for k in ("x","y","w","h"));vh=min(hh,1080-y)
                im=results[name][key]["inverse"] if key in invoked else t["predictor"]
                frame[y:y+vh,x:x+w]=im[:vh].astype("f8")/4
            assert np.isfinite(frame[covered]).all()
            frames[name]=frame
        fullroi={roi:dict(xywh=list(box),stages={name:a.descriptor(u,h,a.crop(refs["original"],box),a.crop(f,box)) for name,f in frames.items()}) for roi,box in a.BOXES.items()}
        for row in rows:
            z=row["begin"];x,y,w,hh=(z[k] for k in ("x","y","w","h"));vh=min(hh,1080-y)
            row["intersections"]={}
            for roi,box in a.BOXES.items():
                ov=u.overlap(x,y,w,vh,*box)
                if not ov:continue
                ref=a.crop(refs["original"],ov)
                row["intersections"][roi]=dict(xywh=list(ov),pixels=ov[2]*ov[3],
                    stages={name:a.descriptor(u,h,ref,a.crop(f,ov)) for name,f in frames.items()},
                    changed_from_fp={name:int(np.count_nonzero(a.crop(frames[name],ov)!=a.crop(frames["fp_baseline"],ov))) for name in ARMS})
        aggregates={}
        for roi in a.BOXES:
            aggregates[roi]={}
            for pop in ("all","invoked","not_invoked","final_positive","quantized_zero"):
                selected=[r for r in rows if roi in r["intersections"] and
                    (pop=="all" or (pop=="invoked" and r["invoked"]) or (pop=="not_invoked" and not r["invoked"]) or
                     (pop=="final_positive" and r["category"]==4) or (pop=="quantized_zero" and r["invoked"] and r["category"]!=4))]
                weights=[r["intersections"][roi]["pixels"] for r in selected];st={}
                for name in frames:
                    ds=[r["intersections"][roi]["stages"][name] for r in selected]
                    st[name]={key:u.stat([d.get(key) for d in ds],weights) for key in ("hf_sigma","hf_sigma_abs_error","acf1_abs_error","hf_corr_source")}
                    st[name]["mse"]=u.stat([d["pixel_error"]["mse"] for d in ds],weights)
                    st[name]["gradient_mae"]=u.stat([d["gradient_mae"] for d in ds],[d["gradient_support"] for d in ds])
                aggregates[roi][pop]=dict(units=len(selected),pixels=sum(weights),stages=st)
        after=[ident(p) for p in dependency_paths];assert before==after
        for d in bbefore:exact(d)
        result=dict(status="admitted_diagnostic",scope="single-frame fixed local decisions; no encode, bitrate, repair or playback inference",
                    script=ident(__file__),build_receipt=ident(bp),library=ident(lib),r11_admission=ident(adp),
                    controls=control,all_arms_C_runtime_exact=True,generated_fp_tables=qtables,
                    original=dec["r9_stages"]["original"],coding_input=dec["r9_stages"]["coding_input"],
                    array_file=ident(out/"native-arrays.npz"),fixed_roi=fullroi,aggregates=aggregates,units=rows,
                    semantics=dict(same_q_b="bundled native scalar algorithm, captured B tables; not one parameter",
                                   q32="internal qindex32, only FP quant/round/dequant rows changed; QM fixed",
                                   unchanged="720 no-final-quantizer owners retain actual predictors",
                                   metrics="original referenced; fixed whole ROI primary, weighted TU descriptors nonlinear",
                                   rates="coefficient counts are not coded bits; all local images diagnostic only"))
        (out/"result.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
        receipt.update(status="complete",inputs_after=after,result=ident(out/"result.json"))
    except BaseException as e:
        receipt.update(status="failed",error=repr(e));raise
    finally:
        receipt.update(seconds=time.monotonic()-start,ended_utc=dt.datetime.now(dt.timezone.utc).isoformat());save()
    print(json.dumps(dict(status=receipt["status"],result=receipt["result"],seconds=receipt["seconds"])))
if __name__=="__main__":
    if not __debug__:raise SystemExit("optimized Python prohibited")
    main()
