#!/usr/bin/env python3
"""Summarize an admitted arm against preserved preset4, without acceptance claims."""
import hashlib
import json
import os
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(os.environ.get("PANTHEON_SOURCEBUDGET_ROOT",
                           "/tmp/downloads/codex-work/pantheon-sourcebudget-20261020"))
ARCHIVE = Path("/media/merged-storage/cold-storage/docker-apps/pantheon-causal-20261019")
case, tag = sys.argv[1:]
assert case in ("e04", "e05-1440")
run = ROOT / "worker/runs" / case / tag
scores = ROOT / "parent/scores" / case
out = ROOT / "parent/summary" / case / tag
paths = {
    "assessment": run / "assessment.json",
    "command": run / "command.json",
    "texture": scores / (tag + "-texture.json"),
    "metrics": scores / (tag + "-result.json"),
    "controls": run / "controls.json",
    "decoder_validation": run / "decoder-validation.json",
    "decode_identity": scores / (tag + "-decoded.decode-identity.json"),
    "score_identity": scores / (tag + "-score-identity.json"),
    "baseline_texture": ARCHIVE / case / "b-base-texture.json",
    "baseline_metrics": ARCHIVE / case / "b-base-result.json",
    "baseline_command": ARCHIVE / case / (
        "b-baseline-try2-command.json" if case == "e05-1440" else "b-baseline-command.json"),
}
data = {k: json.loads(p.read_text()) for k, p in paths.items()}
a, c, t, b = (data[k] for k in ("assessment", "command", "texture", "baseline_texture"))
def sha(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()

assert a["all336_decoder_identity"] and a["all240_scored_planes_match"]
assert 0 < a["relative_source_rate"] <= 1 and a["practical_rate_eligible"]
matched = .99 <= a["relative_source_rate"] <= 1
assert a["matched_comparison_eligible"] == matched
stack = c.get("encoder_stack", "SVT4.2-preset0")
assert stack in ("SVT4.2-preset0", "libaom-3.8.2-ffmpeg")
contrast = "implementation" if stack == "libaom-3.8.2-ffmpeg" else "preset"
assert a["comparison_kind"] == ("matched-source comparison" if matched else
                                f"under-cap practical screen; not a matched {contrast} comparison")
assert c["status"] == ("encoded" if matched else "rate_gate_failed") and c["returncode"] == 0
assert (c["case"], c["tag"]) == (case, tag)
assert sha(run / "out.mkv") == a["output"]["sha256"] == c["mkv_output"]["sha256"]
assert data["decoder_validation"]["output"]["sha256"] == a["output"]["sha256"]
assert data["decode_identity"]["input"]["sha256"] == a["output"]["sha256"]
decoder_flag = ("all336_allplanes_libaom_dav1d_NVDEC_exact" if stack == "libaom-3.8.2-ffmpeg"
                else "all336_allplanes_app_dav1d_NVDEC_exact")
assert data["decoder_validation"][decoder_flag]
if stack == "libaom-3.8.2-ffmpeg":
    assert a["encoder_stack"] == stack
    assert a["decoder_set"] == ["libdav1d", "libaom-av1", "av1_cuvid"]
    assert sha(run / "dav1d-decoded.yuv") == data["decoder_validation"]["decoded_raw"]["sha256"]
    assert c["passes"]["pass1"]["returncode"] == c["passes"]["pass2"]["returncode"] == 0
assert data["metrics"]["encode"] == str(run / "out.mkv")
assert abs(data["metrics"]["actual_mbps"] - a["actual_mbps"]) < 1e-10
assert a["baseline_actual_mbps"] == data["baseline_metrics"]["actual_mbps"]
assert abs(a["relative_baseline_rate"] - a["actual_mbps"]/a["baseline_actual_mbps"]) < 1e-12
assert abs(c["packet_window"]["actual_mbps"] - a["actual_mbps"]) < 1e-10
assert data["controls"]["summary"] == a["controls"] and data["controls"]["face"] == a["face"]
assert len(data["controls"]["tiles"]) == 12870
assert (t["case"], t["tag"], t["path"]) == (case, tag, str(scores / (tag + "-decoded.mkv")))
assert sha(scores / (tag + "-decoded.mkv")) == data["score_identity"]["distorted"]["sha256"]
assert sha(scores / "ref.mkv") == data["score_identity"]["reference"]["sha256"]
assert len(t["frames"]) == len(b["frames"]) == 240
assert t["roi_xywh"] == b["roi_xywh"]
for fresh, prior in zip(t["frames"], b["frames"]):
    assert fresh["frame"] == prior["frame"]
    for roi in t["roi_xywh"]:
        # Established texture reader uses float32 in both historical and new runs.
        assert fresh["roi"][roi]["source"] == prior["roi"][roi]["source"]

metrics = {}
for name, arm in (("preset4", "baseline_metrics"), (tag, "metrics")):
    d = data[arm]
    metrics[name] = {k: d[k] for k in (
        "actual_mbps", "vmaf", "vmaf_neg", "vmaf_p1_excluding_frame0",
        "ssimu2", "ssimu2_p5", "butter_max_p95", "psnr_y", "ssim")}
    metrics[name]["cambi_fr_mean"] = d["pooled"]["cambi_full_reference"]["mean"]
    metrics[name]["cambi_fr_max"] = d["pooled"]["cambi_full_reference"]["max"]

texture = {}
for name in t["roi_xywh"]:
    texture[name] = {
        "source": t["midpoint_summary"][name]["source"],
        "preset4": b["midpoint_summary"][name]["target"],
        tag: t["midpoint_summary"][name]["target"],
        "preset4_source_hf_correlation": b["midpoint_summary"][name]["paired_hf_correlation"],
        "candidate_screen": a["texture_screen"][name],
    }
    mid = t["midpoint_summary"][name]
    screen = a["texture_screen"][name]
    hf = mid["target"]["hf_sigma"] / mid["source"]["hf_sigma"] - 1
    acf = abs(mid["target"]["acf1"] - mid["source"]["acf1"])
    assert abs(screen["hf_relative_error"] - hf) < 1e-12
    assert abs(screen["acf1_abs_error"] - acf) < 1e-12
    assert screen["source_hf_correlation"] == mid["paired_hf_correlation"]
    assert screen["provisional_hf_acf_pass"] == (abs(hf) <= .1 and acf <= .05)

out.mkdir(parents=True, exist_ok=False)
fig, axes = plt.subplots(len(texture), 4, figsize=(19, 4 * len(texture)), squeeze=False)
fields = ("hf_sigma", "acf1", "paired_hf_correlation", "temporal_hf_corr")
for row, roi in enumerate(texture):
    for col, field in enumerate(fields):
        ax = axes[row, col]
        arms = [("source", t, "source"), ("preset4", b, "target"), (tag, t, "target")]
        if field == "paired_hf_correlation":
            arms = arms[1:]
        for label, trace, arm in arms:
            values = [
                r["roi"][roi][field] if field == "paired_hf_correlation"
                else r["roi"][roi][arm][field]
                for r in trace["frames"]
            ]
            ax.plot(range(240), [np.nan if v is None else v for v in values],
                    label=label, linewidth=1)
        ax.set_title(f"{roi}: {field}")
        ax.set_xlabel("Scored frame")
        ax.grid(alpha=.2)
        if col == 0:
            ax.legend(fontsize=8)
fig.suptitle("All scored frames; fixed-ROI temporal correlation is not motion compensated")
fig.tight_layout()
fig.savefig(out / "texture-temporal.png", dpi=140)
plt.close(fig)

result = {
    "case": case, "tag": tag, "encoder_stack": stack, "rate": a["actual_mbps"],
    "rate_ratio": a["relative_source_rate"],
    "baseline_rate_ratio": a["relative_baseline_rate"],
    "practical_rate_eligible": True, "matched_comparison_eligible": matched,
    "comparison_kind": a["comparison_kind"],
    "tune_policy": c.get("settings", {}).get("tune"),
    "decoder_set": a.get("decoder_set", ["SVT application reconstruction", "libdav1d", "av1_cuvid"]),
    "wall_seconds_336": c["wall_seconds"],
    "baseline_wall_seconds_336": data["baseline_command"]["seconds"],
    "runtime_ratio": c["wall_seconds"] / data["baseline_command"]["seconds"],
    "metrics": metrics, "texture": texture, "controls": a["controls"], "face": a["face"],
    "playback_observed": False,
    "scope": "Descriptive known-fixture comparison; no automatic perceptual acceptance.",
    "provenance": {
        k: {"path": str(p), "sha256": sha(p)}
        for k, p in paths.items()
    },
    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
}
(out / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
lines = [
    f"# {case}: {tag}",
    "",
    f"Actual scored rate {a['actual_mbps']:.7f} Mbps "
    f"({100*a['relative_source_rate']:.4f}% of original).",
    f"Rate status: {a['comparison_kind']}; "
    f"{100*a['relative_baseline_rate']:.4f}% of preserved preset4 packet rate.",
    f"Encode wall {c['wall_seconds']:.3f}s /336frames; "
    f"{result['runtime_ratio']:.2f}x preserved preset4 wall time; resource settings are in command.json.",
    "Host load was observed, not experimentally fixed. No playback was observed.",
    "",
    "| ROI | Source HF | Preset4 HF | Candidate HF | Source ACF1 | Preset4 ACF1 | Candidate ACF1 | HF/ACF screen |",
    "|---|---:|---:|---:|---:|---:|---:|---|",
]
for roi, q in texture.items():
    lines.append(
        f"| {roi} | {q['source']['hf_sigma']:.5f} | {q['preset4']['hf_sigma']:.5f} | "
        f"{q[tag]['hf_sigma']:.5f} | {q['source']['acf1']:.5f} | "
        f"{q['preset4']['acf1']:.5f} | {q[tag]['acf1']:.5f} | "
        f"{q['candidate_screen']['provisional_hf_acf_pass']} |")
lines += ["", "| Metric | Preset4 | Candidate |", "|---|---:|---:|"]
for key, value in metrics["preset4"].items():
    lines.append(f"| {key} | {value:.6f} | {metrics[tag][key]:.6f} |")
lines += ["", "Control summaries, face, provenance and source correlations are in summary.json.",
          "Its provenance links retain all12,870 raw controls and the complete GPU metric results and tails.",
          "All240-frame amplitude/ACF/source-correlation/temporal traces: texture-temporal.png.",
          "A passing numerical screen would still require clean/detail/banding/temporal review and actual playback.", ""]
(out / "SUMMARY.md").write_text("\n".join(lines))
print("\n".join(lines))
