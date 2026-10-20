#!/usr/bin/env python3
"""Scientific luma plots of admitted local diagnostic mosaics, not playback."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from aom_tu_binding import identity

parser = argparse.ArgumentParser()
parser.add_argument("validation", type=Path)
parser.add_argument("analysis", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
validation = json.loads(args.validation.read_text())
analysis = json.loads(args.analysis.read_text())
assert validation["status"] == "admitted"
assert analysis["validation"] == identity(args.validation)
assert analysis["script"] == identity(Path(__file__).with_name("analyze_aom_qmax_tu.py"))
bound = validation["artifacts"]["maps"]
assert identity(bound["path"]) == bound
maps = np.load(bound["path"], allow_pickle=False)
args.output.mkdir(parents=True, exist_ok=False)
artifacts = {}
stages = ("source", "predictor", "raw", "initial", "final", "postloop")
for name in ("shirt", "background", "face"):
    x, y, w, h = analysis["roi"][name]["xywh"]
    # Common fixed range. A data pixel remains a pixel; no adaptive enhancement.
    panel_w, panel_h = w, h
    margin, title_h, footer_h = 12, 45, 63
    total_w = 3 * (panel_w + margin) + margin
    total_h = 2 * (panel_h + title_h + margin) + footer_h
    figure = plt.figure(figsize=(total_w / 100, total_h / 100), dpi=100, facecolor="white")
    for i, stage in enumerate(stages):
        column, row = i % 3, i // 3
        left = margin + column * (panel_w + margin)
        bottom = total_h - (row + 1) * (panel_h + title_h + margin)
        axes = figure.add_axes([left / total_w, bottom / total_h,
                               panel_w / total_w, panel_h / total_h])
        axes.imshow(maps[stage][y:y+h, x:x+w].astype(float) / 4,
                    cmap="gray", vmin=16, vmax=235, interpolation="nearest")
        axes.set_axis_off()
        desc = analysis["roi"][name]["stages"][stage]
        acf = "n/a" if desc["acf1"] is None else f'{desc["acf1"]:.3f}'
        axes.set_title(f'{stage}\nHF {desc["hf_sigma"]:.3f} · ACF1 {acf}', fontsize=8)
    figure.text(.01, .01, f"{name} · input216/scored120 · native spatial grid\n"
                "10-bit luma ÷ 4 → fixed 16–235 gray; out-of-range clipped; no chroma.\n"
                "Raw/initial: local TU mosaics, no feedback; not coherent frames.\n"
                "Still only; no playback.",
                fontsize=8)
    path = args.output / (name + ".png")
    figure.savefig(path, dpi=100)
    plt.close(figure)
    artifacts[name] = identity(path)
receipt = {"validation": identity(args.validation), "analysis": identity(args.analysis),
           "script": identity(__file__), "plots": artifacts,
           "scope": "Native spatial sample grid; 10-bit limited-range luma divided by four, "
                    "displayed with fixed 16–235 gray mapping; out-of-range values clipped; "
                    "no chroma. Raw/initial are local counterfactual TU mosaics with no "
                    "prediction feedback, not coherent frames. Still only; no playback.",
           "stage_semantics": {
               "source": "Original input.",
               "predictor": "Captured final-decision predictor.",
               "raw": "Production inverse of unquantized forward coefficients.",
               "initial": "Production inverse of initial dequantized coefficients.",
               "final": "Production inverse of final dequantized coefficients; exact actual pre-loop.",
               "postloop": "Actual filtered R7 output, bound to ordinary decoded display.",
           }}
(args.output / "plots.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(artifacts, indent=2))
