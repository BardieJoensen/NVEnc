#!/usr/bin/env python3
"""Describe admitted R16 native stages; no counterfactual encode or playback."""
import argparse
import json
from pathlib import Path
import numpy as np
import importlib.util
import hashlib

P = Path(__file__).resolve().parent
ROOT = P.parents[1]

def ident(path):
    path = Path(path).resolve()
    with path.open("rb") as f:
        sha = hashlib.file_digest(f, "sha256").hexdigest()
    return dict(path=str(path), size=path.stat().st_size, sha256=sha)

def exact(row):
    assert ident(row["path"]) == row
    return Path(row["path"])

def module(path, name, sha):
    assert ident(path)["sha256"] == sha
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("admission", type=Path)
    ap.add_argument("admission_sha")
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    assert not args.output.exists()
    script = ident(__file__)
    assert ident(args.admission)["sha256"] == args.admission_sha
    ad = json.loads(args.admission.read_text())
    assert ad["status"] == "admitted"
    assert ad["script"]["sha256"] == "fd190fae6a20aa3cd2efd06e6d6fc9c32471d602272a214b7168667aab511cbb"
    exact(ad["script"])
    for key in (
        "actual_committed_owner", "all336_exact",
        "all_traced_roi_owners_source_predictor_preloop_exact",
        "all_traced_positive_units_dq_iqm_exact_with_all_traced_eob_q_exact",
    ):
        assert ad[key] is True
    for row in ad["artifacts"].values():
        exact(row)
    a = module(
        ROOT / "parent/psyex-coeff-r11/analyze.py", "r16_stage_helpers",
        "44b8037c2a922b7e893cd66c8488f3683c45b8859400ff6b082bd0910286f64e",
    )
    p = module(
        ROOT / "parent/psyex-real-r15/parsers.py", "r16_stage_parsers",
        "45f11c246037e1a58a2762235a62db9a0bcb71e85fe992cfcc35897fa24983e3",
    )
    u = a.mod(a.U, "r16_stage_units", a.USHA)
    h = u.helper()
    prior_boundary = ROOT / "parent/psyex-boundary-r9/analysis-1.json"
    assert ident(prior_boundary)["sha256"] == "b2d4a19ac93eeab29cb78870cea45f03165f7741f22584955081498553ed5bc5"
    helpers = json.loads(prior_boundary.read_text())["metric_helpers"]
    for row in helpers.values():
        exact(row)
    binding = json.loads(exact(ad["artifacts"]["syntax_binding"]).read_text())
    tokens, terminal = p.parse_coeff(exact(ad["trace"]), binding["target_coded_event"]["coded_ordinal"])
    assert terminal == ad["terminal"] and len(tokens) == ad["tokens"]
    dec = json.loads(exact(ad["decoder_admission"]).read_text())
    refs = {
        name: u.load_luma(exact(dec["r9_stages"][name]))
        for name in ("original", "coding_input", "preloop", "postloop")
    }
    refs["predictor"] = u.load_luma(exact(dec["artifacts"]["predictor"]))
    frames, covered = a.make_mosaics(tokens)
    assert np.array_equal(frames["predictor"][covered], refs["predictor"][covered])
    assert np.array_equal(frames["final"][covered], refs["preloop"][covered])
    frames.update({name: refs[name] for name in ("original", "coding_input", "preloop", "postloop")})
    rois = {}
    for name, box in a.BOXES.items():
        stages = {
            stage: a.descriptor(u, h, a.crop(refs["original"], box), a.crop(frame, box))
            for stage, frame in frames.items()
        }
        changes = {}
        for t in tokens.values():
            z = t["begin"]
            if not u.overlap(z["x"], z["y"], z["w"], min(z["h"], 1080-z["y"]), *box):
                continue
            previous = None
            for stage in t["stages"]:
                name_s = stage["stage"]
                row = changes.setdefault(name_s, dict(calls=0, compared=0, numerically_changed=0))
                row["calls"] += 1
                if previous is not None:
                    row["compared"] += 1
                    row["numerically_changed"] += int(
                        stage["eob"] != previous["eob"]
                        or not np.array_equal(stage["q"], previous["q"])
                        or not np.array_equal(stage["dq"], previous["dq"])
                    )
                previous = stage
        rois[name] = dict(xywh=list(box), stages=stages, stage_changes=changes,
                          actual_quantization=ad["quantization"][name])
    assert ident(__file__) == script
    for row in helpers.values():
        exact(row)
    out = dict(
        status="complete", script=script, admission=ident(args.admission),
        helpers={"stage": ident(a.__file__), "units": ident(u.__file__), **helpers},
        parser=ident(p.__file__), fixed_roi=rois, covered_pixels=int(covered.sum()),
        stage_change_semantics="numerically_changed counts changed q/DQ/EOB state, not necessarily changed reconstruction pixels",
        scope="Single admitted frame216/scored120; original-referenced actual stage descriptors. raw_executed is a fixed-predictor local diagnostic retaining predictor on uninvoked support. No isolated TF, matched-rate, full-window, repair or playback claim.",
        units="native10bit luma divided by4 once; descriptor code unchanged from R11",
    )
    with args.output.open("x") as f:
        json.dump(out, f, indent=2, allow_nan=False)
        f.write("\n")
    print(json.dumps(dict(status="complete", result=ident(args.output))))

if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python prohibited")
    main()
