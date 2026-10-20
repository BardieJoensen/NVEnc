#!/usr/bin/env python3
"""Compare H264 QP state descriptively; prediction and transforms are not fixed."""
import hashlib
import json
import os
from pathlib import Path
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("PANTHEON_SOURCEBUDGET_ROOT",
                           "/tmp/downloads/codex-work/pantheon-sourcebudget-20261020"))
ARCHIVE = Path("/media/merged-storage/cold-storage/docker-apps/pantheon-rd-20261019")
d = ROOT / "parent/original-qp/e05-1440/preroll"
def fingerprint(p):
    with p.open("rb") as f:
        h = hashlib.file_digest(f, "sha256").hexdigest()
    return {"path": str(p), "sha256": h}
selection = json.loads((d / "selection.json").read_text())
assert selection["all336_original_planes_match_fixture"]
assert fingerprint(d / "fixture-qp-state.i8")["sha256"] == selection["state"]["sha256"]
assert fingerprint(d / "export/receipt.json")["sha256"] == selection["export"]["sha256"]
original_export = json.loads((d / "export/receipt.json").read_text())
assert fingerprint(d / "extract.json")["sha256"] == selection["input_validation"]["sha256"]
extraction = json.loads((d / "extract.json").read_text())
assert extraction["all336_original_planes_match_fixture"]
assert original_export["input"]["sha256"] == extraction["copy"]["sha256"]
assert fingerprint(d / "original.mkv")["sha256"] == extraction["copy"]["sha256"]
assert original_export["unique_complete_grids"] and original_export["rows"] == 384*8160
vpath = ROOT / "fixtures/e05-1440/validity.json"
v = json.loads(vpath.read_text())
maps = {"original": np.fromfile(d / "fixture-qp-state.i8", dtype="i1").reshape(336, 68, 120)}
rates = {"original": v["source_mbps"]}
provenance = {"original": fingerprint(d / "selection.json"), "source_validity": fingerprint(vpath)}
frames = {"original": original_export["probe"]["frames"][48:384]}
for label, folder, tag in (
    ("x264_2x", "search11-validated", "x264-search11-2x0"),
    ("x264_4x", "search11-4x-validated", "x264-search11-4x1"),
):
    p = ARCHIVE / "parent/h264-qp" / folder
    r = json.loads((p / "receipt.json").read_text())
    auditpath = ARCHIVE / "parent/crosscodec/e05-1440" / tag / "packet-window-audit.json"
    audit = json.loads(auditpath.read_text())
    assert fingerprint(p / "qp-state.i8")["sha256"] == r["map"]["sha256"]
    assert r["unique_complete_grids"] and r["rows"] == 336*8160
    assert r["input"]["sha256"] == audit["output"]["sha256"] and audit["within_1pct"]
    maps[label] = np.fromfile(p / "qp-state.i8", dtype="i1").reshape(336, 68, 120)
    rates[label] = audit["actual_mbps"]
    provenance[label] = {"receipt": fingerprint(p / "receipt.json"), "rate": fingerprint(auditpath)}
    frames[label] = r["probe"]["frames"]

def weights(box):
    xx, yy, w, h = box
    xs, ys = np.arange(120)*16, np.arange(68)*16
    wx = np.maximum(0, np.minimum(xs+16, xx+w)-np.maximum(xs, xx))
    wy = np.maximum(0, np.minimum(ys+16, min(yy+h, 1080))-np.maximum(ys, yy))
    out = wy[:, None]*wx[None, :]
    assert out.sum() == w*h
    return out

boxes = {"shirt": [1200,650,200,100], "background": [950,50,250,180],
         "face": [160,600,500,480], "whole": [0,0,1920,1080]}
series, summary = {}, {}
for roi, box in boxes.items():
    w = weights(box)
    series[roi] = {}
    summary[roi] = {}
    for label, data in maps.items():
        s = np.einsum("fyx,yx->f", data, w)/w.sum()
        series[roi][label] = s[96:336].tolist()
        summary[roi][label] = {
            "all240": float(s[96:336].mean()),
            "midpoint5": float(s[[212,214,216,218,220]].mean()),
            "frame120": float(s[216]),
        }
output = {
    "scope": "Same H2648-bit QP_Y state conventions, including skipped MBs; coefficients, scaling matrices and residual execution are unobserved. Different picture types, predictors, transforms, filters and rates prevent causal attribution from QP alone.",
    "rates_mbps": rates, "summary": summary, "series_all240": series, "boxes": boxes,
    "midpoint_scored_frames": [116,118,120,122,124],
    "keyframe_input_positions": {k: [i for i,f in enumerate(fs) if f["key_frame"]] for k,fs in frames.items()},
    "picture_types_all336": {k: [f["pict_type"] for f in fs] for k,fs in frames.items()},
    "provenance": provenance, "script": fingerprint(Path(__file__)),
}
(d / "comparison.json").write_text(json.dumps(output, indent=2)+"\n")
print(json.dumps({k: output[k] for k in ("scope", "rates_mbps", "summary", "keyframe_input_positions")}, indent=2))
