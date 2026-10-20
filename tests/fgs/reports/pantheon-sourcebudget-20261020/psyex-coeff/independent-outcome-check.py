#!/usr/bin/env python3
"""Independent compact stage-delta derivation from admitted R11 trace."""

import collections
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

ROOT = Path("/tmp/downloads/codex-work/pantheon-sourcebudget-20261020")
P11 = ROOT / "parent/psyex-coeff-r11"
P9 = ROOT / "parent/psyex-boundary-r9/admitted-1"
OUT = ROOT / "reviewer/round11-outcome/derived.json"
ROIS = {
    "shirt": (1200, 650, 200, 100),
    "background": (950, 50, 250, 180),
    "face": (160, 600, 500, 480),
}


def ident(path):
    path = Path(path).resolve()
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": str(path), "sha256": digest, "size": path.stat().st_size}


def overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x0, y0, x1, y1 = max(ax, bx), max(ay, by), min(ax + aw, bx + bw), min(ay + ah, by + bh)
    return None if x0 >= x1 or y0 >= y1 else (x0, y0, x1 - x0, y1 - y0)


def token_images(token):
    pred = token["predictor"]
    raw = token.get("raw_inverse", pred)
    if token["stages"]:
        scalar = token["stages"][0]["inverse"]
    else:
        scalar = pred
    optimized = scalar
    for stage in token["stages"]:
        if stage["stage"] in ("fast_opt", "requant_b", "optimize_b"):
            optimized = stage["inverse"]
    return {
        "predictor": pred,
        "raw_executed": raw,
        "scalar": scalar,
        "after_optimize": optimized,
        "final": token["reconstruction"],
    }


def error(reference, candidate):
    delta = candidate.astype(np.float64) / 4 - reference
    return {
        "mse": float(np.mean(delta * delta)),
        "mae": float(np.mean(np.abs(delta))),
        "max_abs": float(np.max(np.abs(delta))),
    }


def transition(before, after):
    delta = (after.astype(np.float64) - before.astype(np.float64)) / 4
    return {
        "changed_pixels": int(np.count_nonzero(delta)),
        "total_pixels": int(delta.size),
        "mse_between_stages": float(np.mean(delta * delta)),
        "mae_between_stages": float(np.mean(np.abs(delta))),
        "max_abs_between_stages": float(np.max(np.abs(delta))),
    }


def main():
    validator = P11 / "validate.py"
    assert ident(validator)["sha256"] == "258db37595666efa153d6fc526d42de371fe0a7f0b21bff7c3334e84238378f3"
    spec = importlib.util.spec_from_file_location("r11_validator", validator)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tokens, terminal = module.parse(P11 / "runs/on-1/coeff.bin")
    joins = {row["token"]: row for row in json.loads((P11 / "admitted-1/tokens.json").read_text())}
    assert set(tokens) == set(joins)

    original = np.fromfile(P9 / "original.yuv", dtype="<u2", count=1920 * 1080).reshape(1080, 1920).astype(np.float64) / 4
    coding_input = np.fromfile(P9 / "coding_input.yuv", dtype="<u2", count=1920 * 1080).reshape(1080, 1920).astype(np.float64) / 4
    postloop = np.fromfile(P9 / "postloop.yuv", dtype="<u2", count=1920 * 1080).reshape(1080, 1920).astype(np.float64) / 4
    frames = {roi: {stage: np.empty((h, w), dtype=np.uint16) for stage in ("predictor", "raw_executed", "scalar", "after_optimize", "final")} for roi, (_, _, w, h) in ROIS.items()}
    coverage = {roi: np.zeros(next(iter(stages.values())).shape, dtype=np.uint8) for roi, stages in frames.items()}
    groups = {roi: collections.Counter() for roi in ROIS}
    group_pixels = {roi: collections.Counter() for roi in ROIS}
    qindices = {roi: collections.Counter() for roi in ROIS}
    optimizer_changed = {roi: [] for roi in ROIS}
    noise_changed = {roi: [] for roi in ROIS}

    for token_id, token in tokens.items():
        begin = token["begin"]
        x, y, w, h = (begin[key] for key in ("x", "y", "w", "h"))
        visible_h = min(h, 1080 - y)
        box = (x, y, w, visible_h)
        images = token_images(token)
        quantized = bool(token["stages"])
        positive = bool(token["commit"]["eob"])
        group = "quant_positive" if quantized and positive else "quant_zero" if quantized else "no_quantizer"

        previous = None
        for stage in token["stages"]:
            changed = previous is not None and (
                not np.array_equal(stage["q"], previous["q"])
                or not np.array_equal(stage["dq"], previous["dq"])
                or stage["eob"] != previous["eob"]
            )
            if changed and stage["stage"] == "optimize_b":
                for roi, roi_box in ROIS.items():
                    if overlap(box, roi_box):
                        optimizer_changed[roi].append({"token": token_id, "unit": joins[token_id]["unit"], "xywh": list(box)})
            if changed and stage["stage"] == "noise_normalization":
                for roi, roi_box in ROIS.items():
                    if overlap(box, roi_box):
                        noise_changed[roi].append({"token": token_id, "unit": joins[token_id]["unit"]})
            previous = stage

        for roi, (rx, ry, rw, rh) in ROIS.items():
            cross = overlap(box, (rx, ry, rw, rh))
            if not cross:
                continue
            xx, yy, ww, hh = cross
            src = np.s_[yy - y : yy - y + hh, xx - x : xx - x + ww]
            dst = np.s_[yy - ry : yy - ry + hh, xx - rx : xx - rx + ww]
            assert not coverage[roi][dst].any()
            coverage[roi][dst] = 1
            for stage, image in images.items():
                frames[roi][stage][dst] = image[src]
            pixels = ww * hh
            groups[roi][group] += 1
            group_pixels[roi][group] += pixels
            if quantized:
                qindices[roi][token["info"]["actual_qindex"]] += 1

    result = {
        "status": "complete",
        "inputs": {
            "validator": ident(validator),
            "trace": ident(P11 / "runs/on-1/coeff.bin"),
            "admission": ident(P11 / "admitted-1/admission.json"),
            "token_manifest": ident(P11 / "admitted-1/tokens.json"),
            "original": ident(P9 / "original.yuv"),
            "coding_input": ident(P9 / "coding_input.yuv"),
            "postloop": ident(P9 / "postloop.yuv"),
        },
        "terminal": terminal,
        "regions": {},
        "representative_tokens": {},
    }
    for roi, (rx, ry, rw, rh) in ROIS.items():
        assert coverage[roi].all()
        ref = original[ry : ry + rh, rx : rx + rw]
        stages = frames[roi]
        source_error = {stage: error(ref, image) for stage, image in stages.items()}
        source_error["coding_input"] = error(ref, (coding_input[ry : ry + rh, rx : rx + rw] * 4).astype(np.uint16))
        source_error["postloop"] = error(ref, (postloop[ry : ry + rh, rx : rx + rw] * 4).astype(np.uint16))
        result["regions"][roi] = {
            "groups_units": dict(groups[roi]),
            "groups_pixels": dict(group_pixels[roi]),
            "actual_qindex_unit_counts": {str(key): value for key, value in sorted(qindices[roi].items())},
            "source_error": source_error,
            "transitions": {
                "raw_to_scalar": transition(stages["raw_executed"], stages["scalar"]),
                "scalar_to_optimizer": transition(stages["scalar"], stages["after_optimize"]),
                "optimizer_to_final": transition(stages["after_optimize"], stages["final"]),
            },
            "optimizer_changed_units": optimizer_changed[roi],
            "noise_changed_units": noise_changed[roi],
        }

    for token_id in (877, 409, 1083):
        token = tokens[token_id]
        result["representative_tokens"][str(token_id)] = {
            "unit": joins[token_id]["unit"],
            "begin": token["begin"],
            "actual_qindex": token["info"]["actual_qindex"],
            "raw_eob": token["raw_eob"],
            "raw_nonzero": int(np.count_nonzero(token["raw"])),
            "stages": [
                {
                    "stage": stage["stage"],
                    "eob": stage["eob"],
                    "q_nonzero": int(np.count_nonzero(stage["q"])),
                    "dq_nonzero": int(np.count_nonzero(stage["dq"])),
                    "q_l1": int(np.abs(stage["q"].astype(np.int64)).sum()),
                }
                for stage in token["stages"]
            ],
        }

    OUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    if not __debug__:
        raise RuntimeError("optimized Python is prohibited")
    main()
