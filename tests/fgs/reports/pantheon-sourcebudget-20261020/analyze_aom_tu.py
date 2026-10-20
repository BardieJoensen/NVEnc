#!/usr/bin/env python3
"""Describe admitted fixed-predictor mosaics; never score them as legal encodes."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from scipy.ndimage import maximum_filter, minimum_filter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pantheon-independent-20261019"))
from texture import BOXES, corr, desc
from investigate import high_pass

STAGES = ("source", "predictor", "raw", "initial", "final", "preloop", "postloop")


def identity(path):
    path = Path(path).resolve()
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": str(path), "sha256": digest, "size": path.stat().st_size}


def error_stats(a, source):
    error = a - source
    sg = np.abs(np.diff(source, axis=1))
    ag = np.abs(np.diff(a, axis=1))
    edge = sg > 12
    return {
        **desc(a), "mse": float(np.mean(error * error)),
        "mae": float(np.mean(np.abs(error))),
        "bias": float(error.mean()),
        "maximum_absolute_error": float(np.abs(error).max()),
        "exact_pixel_fraction": float(np.mean(error == 0)),
        "absolute_error_p95": float(np.percentile(np.abs(error), 95)),
        "hf_corr_source": corr(high_pass(a), high_pass(source)),
        "strong_horizontal_edge_pixels": int(edge.sum()),
        "strong_horizontal_edge_gradient_mae":
            float(np.abs(ag[edge] - sg[edge]).mean()) if edge.any() else None,
        "strong_horizontal_edge_gradient_ratio":
            float(ag[edge].sum() / sg[edge].sum()) if edge.any() else None,
    }


def masked_hf(a, source, mask):
    """Mask is on the high-pass lattice; ACF uses only valid endpoint pairs."""
    hp, sh = high_pass(a), high_pass(source)
    assert hp.shape == mask.shape
    if not mask.any():
        return {"pixels": 0, "hf_sigma": None, "acf1": None, "hf_corr_source": None}
    mean = hp[mask].mean()
    centered = hp - mean
    variance = float(np.mean(centered[mask] ** 2))
    h = mask[:, :-1] & mask[:, 1:]
    v = mask[:-1, :] & mask[1:, :]
    covariance = [
        float((centered[:, :-1] * centered[:, 1:])[h].mean()) if h.any() else None,
        float((centered[:-1, :] * centered[1:, :])[v].mean()) if v.any() else None,
    ]
    return {
        "pixels": int(mask.sum()), "horizontal_pairs": int(h.sum()),
        "vertical_pairs": int(v.sum()), "hf_sigma": float(np.sqrt(variance * 8 / 5)),
        "acf1": sum(covariance) / (2 * variance)
        if variance > 1e-18 and all(x is not None for x in covariance) else None,
        "hf_corr_source": corr(hp[mask], sh[mask]),
    }


def summarize_tiles(rows):
    result = {}
    for kind in ("all", "quiet", "edge", "flat_texture", "other"):
        pool = [r for r in rows if kind == "all" or r["kind"] == kind]
        stages = {}
        for stage in STAGES:
            vals = [r["stages"][stage] for r in pool]
            acf = [
                abs(r["stages"][stage]["acf1"] - r["stages"]["source"]["acf1"])
                for r in pool if r["stages"][stage]["acf1"] is not None
                and r["stages"]["source"]["acf1"] is not None
            ]
            delta_hf = [r["stages"][stage]["hf_sigma"]
                        - r["stages"]["source"]["hf_sigma"] for r in pool]
            stages[stage] = {
                "mse_mean": float(np.mean([r["mse"] for r in vals])) if vals else None,
                "mse_p95": float(np.percentile([r["mse"] for r in vals], 95))
                if vals else None,
                "hf_abs_error_mean": float(np.mean(np.abs(delta_hf))) if vals else None,
                "acf1_abs_error_mean": float(np.mean(acf)) if acf else None,
                "positive_hf_error_tiles": sum(v > 0 for v in delta_hf),
                "positive_hf_error_max": max([0.0, *delta_hf]),
            }
        result[kind] = {"tiles": len(pool), "stages": stages}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("validation", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    admission = json.loads(args.validation.read_text())
    assert admission["status"] == "admitted" and admission["schema"] == 1
    for bound in admission["artifacts"].values():
        assert identity(bound["path"]) == bound, bound
    arrays = np.load(admission["artifacts"]["maps"]["path"], allow_pickle=False)
    tu_records = json.loads(Path(admission["artifacts"]["tu_records"]["path"]).read_text())
    for key in (*STAGES, "exercised", "owner", "qindex", "tx_width", "tx_height",
                "status", "final_eob"):
        assert arrays[key].shape == (1080, 1920), key
    assert np.array_equal(arrays["final"], arrays["preloop"])
    maps = {key: arrays[key].astype(np.float64) / 4 for key in STAGES}
    assert all(np.isfinite(x).all() for x in maps.values())
    source = maps["source"]
    exercised = arrays["exercised"].astype(bool)
    owners = arrays["owner"]
    assert np.all(owners >= 0)
    # Distinguish all exercised neighborhoods from those wholly within one TU.
    valid = minimum_filter(exercised.astype(np.uint8), 3, mode="constant") > 0
    same_owner = minimum_filter(owners, 3, mode="constant", cval=-1) == maximum_filter(
        owners, 3, mode="constant", cval=-1)
    masks = {"exercised_neighborhood": valid, "same_TU_exercised": valid & same_owner}
    frozen = json.loads(Path(admission["artifacts"]["frozen_controls"]["path"]).read_text())
    rows = [r for r in frozen["tiles"] if r["frame"] == 120]
    assert len(rows) == 858 and len({(r["x"], r["y"]) for r in rows}) == 858
    tiles = []
    for row in rows:
        x, y = row["x"], row["y"]
        sl = np.s_[y:y + 32, x:x + 32]
        stats = desc(source[sl])
        for key, value in row["source"].items():
            if value is None:
                assert stats[key] is None
            else:
                assert np.isclose(stats[key], value, rtol=1e-10, atol=1e-10), (x, y, key)
        tiles.append({
            "x": x, "y": y, "kind": row["kind"],
            "outside_target": row["outside_target"],
            "exercised_pixel_fraction": float(exercised[sl].mean()),
            "stages": {key: error_stats(a[sl], source[sl]) for key, a in maps.items()},
        })
    boxes = {**BOXES["e05-1440"], "face": [160, 600, 500, 480],
             "full_frame": [0, 0, 1920, 1080]}
    roi = {}
    for name, (x, y, w, h) in boxes.items():
        sl = np.s_[y:y + h, x:x + w]
        q = arrays["qindex"][sl][exercised[sl]]
        groups = {}
        for tw, th in sorted(set(zip(arrays["tx_width"][sl][exercised[sl]].tolist(),
                                     arrays["tx_height"][sl][exercised[sl]].tolist()))):
            mask = exercised[sl] & (arrays["tx_width"][sl] == tw) & (arrays["tx_height"][sl] == th)
            e = (maps["raw"][sl] - source[sl])[mask]
            groups[f"{tw}x{th}"] = {
                "pixels": int(mask.sum()), "raw_forward_mse": float(np.mean(e * e)),
                "raw_forward_mae": float(np.mean(np.abs(e))),
            }
        roi[name] = {
            "xywh": [x, y, w, h], "exercised_pixel_fraction": float(exercised[sl].mean()),
            "status_pixel_counts": {
                str(int(v)): int(np.count_nonzero(arrays["status"][sl] == v))
                for v in np.unique(arrays["status"][sl])
            },
            "exercised_final_EOB_zero_pixels":
                int(np.count_nonzero(exercised[sl] & (arrays["final_eob"][sl] == 0))),
            "executed_qindex": {"min": int(q.min()), "max": int(q.max()),
                                "pixel_weighted_mean": float(q.mean())} if q.size else None,
            "stages": {key: error_stats(a[sl], source[sl]) for key, a in maps.items()},
            "masked_hf": {mask_name: {
                key: masked_hf(a[sl], source[sl], mask[sl][1:-1, 1:-1])
                for key, a in maps.items()} for mask_name, mask in masks.items()},
            "raw_forward_error_by_exercised_transform_size": groups,
        }
        strata = {}
        for label, condition in (
            ("full_transform_le32", (arrays["tx_width"] <= 32) & (arrays["tx_height"] <= 32)),
            ("reduced_transform_any64", (arrays["tx_width"] == 64) | (arrays["tx_height"] == 64)),
        ):
            eligible = exercised & condition
            mask = eligible[sl]
            hf_mask = ((minimum_filter(eligible.astype(np.uint8), 3, mode="constant") > 0)
                       & same_owner)[sl][1:-1, 1:-1]
            strata[label] = {
                "pixels": int(mask.sum()),
                "intersecting_TUs": int(np.unique(owners[sl][mask]).size),
                "stages": {stage: {
                    "mse_to_source": float(np.mean((a[sl][mask] - source[sl][mask]) ** 2))
                    if mask.any() else None,
                    "mae_to_source": float(np.mean(np.abs(a[sl][mask] - source[sl][mask])))
                    if mask.any() else None,
                    "masked_hf": masked_hf(a[sl], source[sl], hf_mask),
                } for stage, a in maps.items()},
                "stage_deltas": {f"{a}_to_{b}": {
                    "mse": float(np.mean((maps[a][sl][mask] - maps[b][sl][mask]) ** 2))
                    if mask.any() else None,
                    "mae": float(np.mean(np.abs(maps[a][sl][mask] - maps[b][sl][mask])))
                    if mask.any() else None,
                } for a, b in (("raw", "initial"), ("initial", "final"))},
            }
        roi[name]["transform_support_strata"] = strata
        contained = [r for r in tu_records if
                     r["metadata"]["x"] >= x and r["metadata"]["y"] >= y and
                     r["metadata"]["x"] + r["metadata"]["width"] <= x + w and
                     r["metadata"]["y"] + r["metadata"]["height"] <= y + h]
        roi[name]["fully_contained_record_summary"] = {
            "scope": "Coefficient proxies use whole contained records; never prorated to pixels or bits.",
            "records": len(contained),
            "status_counts": {k: sum(str(r["metadata"]["status"]) == k for r in contained)
                              for k in admission["status_legend"]},
            "quantizer_path_counts": {
                str(k): sum(r["metadata"]["quant_idx"] == k for r in contained)
                for k in sorted({r["metadata"]["quant_idx"] for r in contained})},
            "pixel_stage_changes": {label: {
                "records_with_change": sum(r["pixel_deltas"][label]["changed_full_TU_pixels"] > 0
                                          for r in contained),
                "changed_pixels": sum(r["pixel_deltas"][label]["changed_full_TU_pixels"]
                                      for r in contained),
                "total_pixels": sum(r["pixel_deltas"][label]["full_TU_pixels"] for r in contained),
            } for label in ("raw_to_initial", "initial_to_final")},
            "coefficient_stage_changes_not_bits": {label: {
                "records_with_change": sum(r["coefficient_proxies_not_bits"].get(label, {}).get("nonzero", 0) > 0
                                          for r in contained),
                **{stat: sum(r["coefficient_proxies_not_bits"].get(label, {}).get(stat, 0)
                             for r in contained) for stat in ("nonzero", "l1", "l2_squared")},
            } for label in ("raw_to_initial_dq", "initial_to_final_dq")},
        }
        if name in BOXES["e05-1440"]:
            ref = roi[name]["stages"]["source"]
            roi[name]["descriptive_texture_screens_not_repair_gates"] = {
                stage: {
                    "amplitude_relative_error": values["hf_sigma"] / ref["hf_sigma"] - 1,
                    "acf1_absolute_error": abs(values["acf1"] - ref["acf1"])
                    if values["acf1"] is not None and ref["acf1"] is not None else None,
                    "pass": abs(values["hf_sigma"] / ref["hf_sigma"] - 1) <= .1
                    and values["acf1"] is not None and ref["acf1"] is not None
                    and abs(values["acf1"] - ref["acf1"]) <= .05,
                } for stage, values in roi[name]["stages"].items()
            }
    report = {
        "scope": "One fixed-predictor luma diagnostic; mosaics are not legal encodes. "
                 "No bitrate, perceptual acceptance, temporal or playback claim.",
        "validation": identity(args.validation), "script": identity(__file__),
        "dependencies": {p.name: identity(p) for p in (
            HERE.parent / "pantheon-independent-20261019/texture.py",
            HERE.parent / "pantheon-independent-20261019/investigate.py",
            HERE.parents[1] / "matched_rate_sweep.py",
        )},
        "roi": roi, "tile_summary": summarize_tiles(tiles), "tiles": tiles,
        "status_legend": admission["status_legend"],
        "complete_per_record_evidence": admission["artifacts"]["tu_records"],
        "all_window_quality": "Reused only by exact IVF identity in admission; "
                              "previously measured through campaign.py GPU paths.",
    }
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({k: {"exercised": v["exercised_pixel_fraction"],
                         "HF": {s: d["hf_sigma"] for s, d in v["stages"].items()}}
                      for k, v in roi.items() if k != "full_frame"}, indent=2))


if __name__ == "__main__":
    main()
