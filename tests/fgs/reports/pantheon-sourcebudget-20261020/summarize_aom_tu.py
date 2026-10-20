#!/usr/bin/env python3
"""Compact, hash-bound R6 diagnostic evidence; no candidate-quality inference."""
import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np

from aom_tu_binding import ROOT, identity

parser = argparse.ArgumentParser()
parser.add_argument("output", type=Path)
args = parser.parse_args()
here = Path(__file__).resolve().parent
experiment = ROOT / "parent/tu-observation"
paths = {
    "admission": experiment / "admission-trace-1/validation.json",
    "analysis": experiment / "analysis-trace-1.json",
    "plots": experiment / "plots-trace-1/plots.json",
    "prior_summary": ROOT / "parent/summary/e05-1440/aom-psnr-1x2/summary.json",
    "prior_texture": ROOT / "parent/scores/e05-1440/aom-psnr-1x2-texture.json",
}
bindings = {key: identity(path) for key, path in paths.items()}
data = {key: json.loads(path.read_text()) for key, path in paths.items()}
admission, analysis, plots, prior, texture = (
    data[k] for k in ("admission", "analysis", "plots", "prior_summary", "prior_texture"))
assert admission["status"] == "admitted"
assert admission["script"] == identity(here / "validate_aom_tu.py")
assert analysis["validation"] == bindings["admission"]
assert analysis["script"] == identity(here / "analyze_aom_tu.py")
assert plots["validation"] == bindings["admission"]
assert plots["analysis"] == bindings["analysis"]
assert plots["script"] == identity(here / "plot_aom_tu.py")
for value in (*admission["artifacts"].values(), *plots["plots"].values(),
              *analysis["dependencies"].values()):
    assert identity(value["path"]) == value
for value in prior["provenance"].values():
    assert identity(value["path"])["sha256"] == value["sha256"]
assert bindings["prior_texture"]["sha256"] == prior["provenance"]["texture"]["sha256"]
assert len(texture["frames"]) == 240
frame = texture["frames"][120]
assert frame["frame"] == 120
comparisons = {}
for roi in ("shirt", "background"):
    assert analysis["roi"][roi]["xywh"] == texture["roi_xywh"][roi]
    comparisons[roi] = {}
    for stage, old in (("source", "source"), ("postloop", "target")):
        fresh = analysis["roi"][roi]["stages"][stage]
        saved = frame["roi"][roi][old]
        differences = {}
        for key in ("mean", "hf_sigma", "acf1", "acf2", "acf3", "acf4", "acf8"):
            assert np.isclose(fresh[key], saved[key], atol=1e-6, rtol=1e-6), (
                roi, stage, key, fresh[key], saved[key])
            differences[key] = fresh[key] - saved[key]
        comparisons[roi][stage] = differences
records = json.loads(Path(admission["artifacts"]["tu_records"]["path"]).read_text())
executed = [r["metadata"] for r in records if r["metadata"]["status"] in (1, 5)]
run = json.loads(Path(admission["artifacts"]["run"]["path"]).read_text())
off = json.loads(Path(admission["artifacts"]["disabled_control"]["path"]).read_text())
assert run["exact_installed_ivf"] and off["exact_installed_ivf"]
assert run["output"]["sha256"] == off["output"]["sha256"]
original_run = json.loads(Path(prior["provenance"]["command"]["path"]).read_text())
assert original_run["ivf_sha256"] == run["output"]["sha256"]
result = {
    "scope": analysis["scope"],
    "input_frame": 216,
    "scored_frame": 120,
    "prior_midpoint_summary_frames": [116, 118, 120, 122, 124],
    "prior_single_frame_descriptor_differences_float64_minus_float32": comparisons,
    "script": identity(__file__),
    "provenance": bindings,
    "admission": admission,
    "roi": analysis["roi"],
    "tile_summary": analysis["tile_summary"],
    "complete_tile_and_TU_evidence": {
        "analysis_with_all_858_tiles": bindings["analysis"],
        "all_7382_records": admission["artifacts"]["tu_records"],
    },
    "exercised_record_counts": {
        key: dict(sorted(Counter(str(r[key]) for r in executed).items()))
        for key in ("base_qindex", "qindex", "coded_qindex", "delta_q", "segment_id",
                    "quant_idx", "quant_flags", "lossless", "reduced_tx_set")
    },
    "quantizer_scope": "qindex is captured x->qindex; coded_qindex is the captured "
                      "mbmi->current_qindex field and is not independently parsed syntax. "
                      "Skips are excluded. Do not infer effective AQ/delta-Q mode from defaults.",
    "unchanged_real_encode": {
        "actual_scored_mbps": prior["rate"],
        "rate_ratio_original": prior["rate_ratio"],
        "measured_two_pass_seconds_336": prior["wall_seconds_336"],
        "quality_reuse_basis": "Exact installed IVF; existing complete campaign.py GPU evidence.",
        "repair_status": "Previously failed both primary texture screens.",
    },
    "diagnostic_pass2_seconds": {
        "off": off["pass2_wall_seconds"],
        "trace": run["pass2_wall_seconds"],
        "scope": "Reused pass1; tracing runs, not candidate end-to-end cost or benchmark.",
    },
    "plots": plots,
    "playback_observed": False,
}
assert all(identity(path) == bindings[key] for key, path in paths.items())
with args.output.open("x") as stream:
    json.dump(result, stream, indent=2, allow_nan=False)
    stream.write("\n")
print(json.dumps(identity(args.output), indent=2))
