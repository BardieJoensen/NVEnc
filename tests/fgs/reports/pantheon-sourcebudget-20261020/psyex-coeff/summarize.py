#!/usr/bin/env python3
"""Freeze a compact report from the admitted R11 result without recomputation."""
import hashlib, json, sys
from pathlib import Path
P=Path(__file__).resolve().parent
def ident(p):
    p=Path(p).resolve()
    with p.open("rb") as f: sha=hashlib.file_digest(f,"sha256").hexdigest()
    return dict(path=str(p),sha256=sha,size=p.stat().st_size)
def main():
    out=Path(sys.argv[1]); assert not out.exists()
    rp=P/"analysis-run-1/result.json"
    assert ident(rp)["sha256"]=="7ba42f09fbea1a3380c80291479ed0c47ad857e9b3196c4181163487bc05b5e4"
    r=json.loads(rp.read_text()); ad=json.loads((P/"admitted-1/admission.json").read_text())
    populations={}
    for roi in ("shirt","background","face"):
        selected=[u for u in r["units"] if roi in u["intersections"]]
        populations[roi]=dict(
            units=len(selected), pixels=sum(u["intersections"][roi]["pixels"] for u in selected),
            quantizer_invoked=sum(u["final_encdec_quantizer_invoked"] for u in selected),
            quantizer_invoked_pixels=sum(u["intersections"][roi]["pixels"] for u in selected if u["final_encdec_quantizer_invoked"]),
            qindex=sorted({u["actual_quantizer"]["actual_qindex"] for u in selected if u["actual_quantizer"]}),
            qm_level=sorted({u["actual_quantizer"]["qm_level"] for u in selected if u["actual_quantizer"]}),
            changed_stages={s: [u["unit"] for u in selected if any(c["stage"]==s and c["changed_from_previous"] is True for c in u["coefficients"])] for s in ("optimize_b","noise_normalization")},
        )
    files=["completed-build-pins.json","source-manifest.json","baseline-source-manifest.json",
           "coeff-r9-relative.patch","pc_impl.c","install_hooks.py","schema.json","build_runner.sh",
           "validate.py","validate-v1-storage-order-rejected.py","validation-execution-1.json",
           "validation-execution-2.json","validation-1.log","validation-2.log",
           "admitted-1/admission.json","admitted-1/tokens.json","analyze.py","run_analysis.py",
           "analysis-run-1/receipt.json","analysis-run-1/result.json","analysis-run-1/analysis.log",
           "fault_checks.py","fault-run-1/result.json","render.py","visuals-1/manifest.json",
           "runs/off-1/command.json","runs/on-1/command.json","runs/on-1/coeff.bin",
           "runs/on-1/boundary.bin"]
    summary=dict(
        status="admitted_and_analyzed",scope=r["scope"],script=ident(__file__),
        admission_flags={k:ad[k] for k in ("tokens","positive_units","shirt_positive_ids","terminal","actual_committed_owner","all336_exact","source_predictor_preloop_exact","final_dq_eob_iqm_exact")},
        fixed_roi=r["fixed_roi"],populations=populations,invocations=r["invocations"],
        numerically_changed=r["numerically_changed"],change_comparisons=r["change_comparisons"],
        stage_semantics=r["stage_semantics"],artifacts=[ident(P/f) for f in files],
        interpretation_limits=[
            "One E05 frame and one frozen R8 policy; not E04 or all encoders.",
            "Native raw/scalar inverses are local fixed-predictor diagnostics, not coherent re-encodes.",
            "All ROI intersections retained; no quiet controls occur in the fixed frame-120 control population.",
            "No entropy-rate inference from coefficient counts; R8 output bytes, packet rate and GPU/full-window results are reused exactly.",
            "Still inspection only; no actual motion/player/display acceptance."
        ])
    out.write_text(json.dumps(summary,indent=2,allow_nan=False)+"\n")
    print(json.dumps(ident(out)))
if __name__=="__main__":
    if not __debug__:raise SystemExit("optimized Python prohibited")
    main()
