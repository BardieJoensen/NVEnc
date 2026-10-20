#!/usr/bin/env python3
"""Render fixed R12 ROIs from admitted native arrays; still diagnostics only."""
import hashlib, importlib.util, json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent;R11=P.parent/"psyex-coeff-r11"
def ident(p):
    p=Path(p).resolve()
    with p.open("rb") as f:s=hashlib.file_digest(f,"sha256").hexdigest()
    return dict(path=str(p),sha256=s,size=p.stat().st_size)
def main():
    rp=P/"run-1/result.json";assert ident(rp)["sha256"]=="9caf06214e249306788a6e58a22d134ed86284b4183fb38f815d8ccf236029d9"
    r=json.loads(rp.read_text());assert r["all_arms_C_runtime_exact"] and r["status"]=="admitted_diagnostic"
    ap=R11/"analyze.py";assert ident(ap)["sha256"]=="44b8037c2a922b7e893cd66c8488f3683c45b8859400ff6b082bd0910286f64e"
    sp=importlib.util.spec_from_file_location("r12_visual_helpers",ap);a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
    ad=json.loads(a.exact(r["r11_admission"]).read_text())
    v=a.mod(a.V,"r12_visual_parser",a.VSHA);u=a.mod(a.U,"r12_visual_units",a.USHA)
    tokens,_=v.parse(a.exact(ad["trace"]));frames,covered=a.make_mosaics(tokens)
    frames["original"]=u.load_luma(a.exact(r["original"]))
    frames["coding_input"]=u.load_luma(a.exact(r["coding_input"]))
    arms=("fp_baseline","b_same_q","fp_q32")
    with np.load(a.exact(r["array_file"]),allow_pickle=False) as data:
        for arm in arms:
            frame=np.full((1080,1920),np.nan)
            for row in r["units"]:
                z=row["begin"];x,y,w,h=(z[k] for k in ("x","y","w","h"));vh=min(h,1080-y)
                if row["invoked"]:
                    off=row["pixel_offset"];im=data[arm+"_inverse"][off:off+w*h].reshape(h,w)
                else:im=tokens[row["token"]]["predictor"]
                frame[y:y+vh,x:x+w]=im[:vh].astype("f8")/4
            assert np.isfinite(frame[covered]).all();frames[arm]=frame
    out=P/"visuals-1";out.mkdir(exist_ok=False)
    stages=("original","coding_input","raw_executed","fp_baseline","b_same_q","fp_q32")
    for roi,box in a.BOXES.items():
        x,y,w,h=box;im=Image.new("RGB",(3*w,2*(h+32)),"black");draw=ImageDraw.Draw(im)
        for i,s in enumerate(stages):
            xx=(i%3)*w;yy=(i//3)*(h+32)
            pix=np.clip(np.rint(a.crop(frames[s],box)),0,255).astype("u1")
            im.paste(Image.fromarray(pix),(xx,yy+32));draw.text((xx+3,yy+7),s,fill="white")
        im.save(out/(roi+"-native-luma.png"))
    fig,axes=plt.subplots(3,3,figsize=(12,9),constrained_layout=True)
    for ri,roi in enumerate(a.BOXES):
        for ci,(key,label) in enumerate((("hf_sigma","HF amplitude"),("acf1_abs_error","ACF1 error"),("hf_corr_source","HF source correlation"))):
            ax=axes[ri,ci];ax.plot(range(6),[r["fixed_roi"][roi]["stages"][s][key] for s in stages],marker="o")
            ax.set_xticks(range(6),stages,rotation=35,ha="right");ax.set_title(roi+": "+label);ax.grid(alpha=.25)
    fig.suptitle("E05 frame120: fixed local predictors and transforms; no encode/rate/playback inference")
    fig.savefig(out/"scalar-diagnostics.png",dpi=160);plt.close(fig)
    (out/"README.md").write_text("Fixed native-size luma crops. Rows: original/coding_input/raw_executed; FP baseline/B same-q/FPq32. Ten-bit luma divided by4 and rounded8bit solely for display, no contrast enhancement or resizing. Full raw/native arrays are authoritative. No quantizer owners retain original native predictors. Local diagnostic images do not propagate new references and are not encoded frames or playback acceptance.\n")
    manifest=dict(script=ident(__file__),result=ident(rp),arrays=r["array_file"],
                  files=[ident(f) for f in sorted(out.iterdir())])
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n");print(json.dumps(manifest))
if __name__=="__main__":
    if not __debug__:raise SystemExit("optimized Python prohibited")
    main()
