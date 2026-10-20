#!/usr/bin/env python3
"""Native-size luma stills and quantitative stage plot; no playback claim."""
import hashlib, importlib.util, json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

P = Path(__file__).resolve().parent
def load(path, name, expected):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m

def main():
    a = load(P / "analyze.py", "r11_render_analysis", "44b8037c2a922b7e893cd66c8488f3683c45b8859400ff6b082bd0910286f64e")
    ad = json.loads((P / "admitted-1/admission.json").read_text())
    result_path = P / "analysis-run-1/result.json"
    assert a.ident(result_path)["sha256"] == "7ba42f09fbea1a3380c80291479ed0c47ad857e9b3196c4181163487bc05b5e4"
    result = json.loads(result_path.read_text())
    v = a.mod(a.V, "r11_render_validator", a.VSHA)
    u = a.mod(a.U, "r11_render_helpers", a.USHA)
    tokens, _ = v.parse(a.exact(ad["trace"]))
    frames, _ = a.make_mosaics(tokens)
    dec = json.loads(a.exact(ad["decoder_admission"]).read_text())
    frames.update({k: u.load_luma(a.exact(dec["r9_stages"][k])) for k in ("original", "coding_input", "postloop")})
    stages = ("original", "coding_input", "raw_executed", "scalar", "final", "postloop")
    out = P / "visuals-1"; out.mkdir(exist_ok=False)
    for name, box in a.BOXES.items():
        x, y, w, h = box
        panel = Image.new("RGB", (w * 3, (h + 32) * 2), "black")
        draw = ImageDraw.Draw(panel)
        for i, stage in enumerate(stages):
            im = np.clip(np.rint(a.crop(frames[stage], box)), 0, 255).astype("uint8")
            xx, yy = (i % 3) * w, (i // 3) * (h + 32)
            panel.paste(Image.fromarray(im), (xx, yy + 32))
            draw.text((xx + 3, yy + 7), stage, fill="white")
        panel.save(out / (name + "-native-luma.png"))
    fig, axes = plt.subplots(3, 3, figsize=(12, 9), constrained_layout=True)
    for ri, roi in enumerate(a.BOXES):
        for ci, (key, label) in enumerate((("hf_sigma", "HF amplitude"), ("acf1_abs_error", "ACF1 absolute error"), ("hf_corr_source", "HF source correlation"))):
            ax = axes[ri, ci]
            values = [result["fixed_roi"][roi]["stages"][s][key] for s in stages]
            ax.plot(range(len(stages)), values, marker="o")
            ax.set_xticks(range(len(stages)), stages, rotation=35, ha="right")
            ax.set_title(roi + ": " + label); ax.grid(alpha=0.25)
    fig.suptitle("E05 frame 120: native local stage diagnostics; no rate or playback inference")
    fig.savefig(out / "stage-descriptors.png", dpi=160); plt.close(fig)
    (out / "README.md").write_text(
        "Native-size fixed-ROI luma stills: rows original/coding_input/raw_executed, "
        "then scalar/final/postloop. Ten-bit luma divided by four and rounded to eight-bit "
        "solely for display; no contrast enhancement or spatial resampling. Raw and scalar "
        "are local fixed-predictor diagnostics; skipped calls retain their actual predictor. "
        "The complete raw data, including padded transform domains, remains authoritative. "
        "These stills and descriptor plots are not motion/player/display acceptance.\n"
    )
    manifest = dict(script=a.ident(__file__), admission=a.ident(P / "admitted-1/admission.json"),
                    result=a.ident(result_path), files=[a.ident(f) for f in sorted(out.iterdir())])
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest))

if __name__ == "__main__":
    if not __debug__: raise SystemExit("optimized Python prohibited")
    main()
