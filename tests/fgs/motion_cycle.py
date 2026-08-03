#!/usr/bin/env python3
"""Audit forward/backward consistency of traced degrain motion vectors.

This is a separator diagnostic, not a quality metric.  It joins the exact
block traces for frames t-1, t and t+1, follows each t -> reference vector,
samples the reverse vector field at that endpoint, and reports the residual::

    cycle_error = |v(t -> r) + v(r -> t)|

The trace is opt-in and output-invariant.  Generate all three traces with the
same centred-motion settings and enough pre-roll for scene analysis, then run::

    python3 tests/fgs/motion_cycle.py PREV.log CENTRE.log NEXT.log \
      --center-frame 268 --output cycle.json

For the generated ``coarse_detail_occl`` control, ``--fixture`` also labels
the background pixels which are hidden in the selected reference.  That is a
known-negative disocclusion region; it lets the diagnostic prove it can fail
instead of merely describing good content.

The trace stores one vector per overlapping block, so the reverse field is
bilinearly sampled on the block grid.  Border samples clamp to the edge, just
as the degrain renderer mirrors reference coordinates at frame boundaries.
"""
import argparse
import json
import math
import os

import numpy as np

from motion_confidence import _reference, parse_trace


QUANTILES = (0.0, 0.5, 0.75, 0.9, 0.95, 0.99, 1.0)


def _layout_signature(summary):
    layout = summary["layout"]
    return tuple(int(layout[name]) for name in (
        "blocks", "blocks_x", "blocks_y", "directions",
        "block_size", "overlap", "step", "pel"))


def load_triplet(previous_path, center_path, following_path, center_frame):
    """Load and validate three consecutive, layout-compatible traces."""
    traces = {
        center_frame - 1: parse_trace(previous_path, center_frame - 1),
        center_frame: parse_trace(center_path, center_frame),
        center_frame + 1: parse_trace(following_path, center_frame + 1),
    }
    signatures = {_layout_signature(summary)
                  for summary, _blocks in traces.values()}
    if len(signatures) != 1:
        raise RuntimeError("motion-cycle traces have incompatible layouts")
    directions = next(iter(signatures))[3]
    if directions != 2:
        raise RuntimeError(
            f"motion-cycle audit requires one previous and one next vector; "
            f"trace has {directions} directions")
    return traces


def _reference_fields(summary, blocks, side):
    """Return dense dx/dy, SAD and validity grids for one reference side."""
    layout = summary["layout"]
    shape = (int(layout["blocks_y"]), int(layout["blocks_x"]))
    vectors = np.full((*shape, 2), np.nan, dtype=np.float64)
    sad = np.full(shape, np.nan, dtype=np.float64)
    valid = np.zeros(shape, dtype=bool)
    for row in blocks.values():
        reference = _reference(row, side, 1)
        if reference is None:
            continue
        by, bx = int(row["block_y"]), int(row["block_x"])
        vectors[by, bx] = (int(reference["dx"]), int(reference["dy"]))
        sad[by, bx] = float(reference["sad"])
        valid[by, bx] = bool(reference["valid_motion"])
    return vectors, sad, valid


def _bilinear(field, valid, grid_x, grid_y):
    """Sample a block-grid field, clamping renderer-mirrored borders."""
    height, width = field.shape[:2]
    grid_x = min(max(float(grid_x), 0.0), width - 1.0)
    grid_y = min(max(float(grid_y), 0.0), height - 1.0)
    x0, y0 = int(math.floor(grid_x)), int(math.floor(grid_y))
    x1, y1 = min(x0 + 1, width - 1), min(y0 + 1, height - 1)
    fx, fy = grid_x - x0, grid_y - y0
    coordinates = ((y0, x0), (y0, x1), (y1, x0), (y1, x1))
    weights = ((1.0 - fx) * (1.0 - fy), fx * (1.0 - fy),
               (1.0 - fx) * fy, fx * fy)
    active = [(coordinate, weight)
              for coordinate, weight in zip(coordinates, weights)
              if weight > 0.0]
    if not active or any(not valid[coordinate] for coordinate, _ in active):
        return None
    return sum((field[coordinate] * weight
                for coordinate, weight in active), np.zeros(2))


def cycle_records(traces, center_frame):
    """Return one forward/backward consistency record per block and side."""
    center_summary, center_blocks = traces[center_frame]
    layout = center_summary["layout"]
    step = int(layout["step"])
    pel = max(1, int(layout["pel"]))
    sad_limit = max(1, int(center_summary["sad_limit"]))
    fields = {}
    for frame, (summary, blocks) in traces.items():
        for side in ("prev", "next"):
            fields[frame, side] = _reference_fields(summary, blocks, side)

    records = []
    for block, row in sorted(center_blocks.items()):
        bx, by = int(row["block_x"]), int(row["block_y"])
        pair = [_reference(row, side, 1) for side in ("prev", "next")]
        pair_valid = all(reference is not None
                         and bool(reference["valid_motion"])
                         and not bool(reference["disabled"])
                         and bool(reference["under_sad"])
                         for reference in pair)
        pair_sad_ratio = max(
            (float(reference["sad"]) / sad_limit
             for reference in pair if reference is not None),
            default=float("nan"))
        for side, reference_frame, reverse_side in (
                ("prev", center_frame - 1, "next"),
                ("next", center_frame + 1, "prev")):
            reference = _reference(row, side, 1)
            if reference is None or not bool(reference["valid_motion"]):
                continue
            dx = float(reference["dx"])
            dy = float(reference["dy"])
            endpoint_x = bx + dx / (pel * step)
            endpoint_y = by + dy / (pel * step)
            reverse_vectors, reverse_sad, reverse_valid = fields[
                reference_frame, reverse_side]
            reverse = _bilinear(
                reverse_vectors, reverse_valid, endpoint_x, endpoint_y)
            reverse_sad_value = _bilinear(
                reverse_sad[..., None], reverse_valid,
                endpoint_x, endpoint_y)
            if reverse is None or reverse_sad_value is None:
                continue
            residual = np.array((dx, dy)) + reverse
            current_sad_ratio = float(reference["sad"]) / sad_limit
            reverse_sad_ratio = float(reverse_sad_value[0]) / sad_limit
            records.append({
                "block": int(block),
                "block_x": bx,
                "block_y": by,
                "side": side,
                "cycle_error_px": float(np.linalg.norm(residual) / pel),
                "motion_magnitude_px": float(math.hypot(dx, dy) / pel),
                "current_sad_ratio": current_sad_ratio,
                "reverse_sad_ratio": reverse_sad_ratio,
                "pair_sad_ratio": pair_sad_ratio,
                "current_admitted": bool(reference["selected"]),
                "paired_admitted": bool(pair_valid),
                "roundtrip_under_sad": bool(
                    reference["under_sad"] and reverse_sad_ratio < 1.0),
            })
    return records


def _fixture_mask(spec, frame):
    # Imported lazily so the generic audit has no fixture-generation side
    # effects and remains usable beside an installed NVEncC binary.
    import fgs_kat as kat

    mask = np.zeros((kat.H, kat.W), dtype=bool)
    for x, y, width, height in kat.occluder_field(spec, frame):
        x0 = max(kat.BAND_W, int(round(x)))
        x1 = min(kat.W - kat.BAND_W, int(round(x)) + width)
        y0 = max(32, int(round(y)))
        y1 = min(kat.H // 2 - 32, int(round(y)) + height)
        if x1 > x0 and y1 > y0:
            mask[y0:y1, x0:x1] = True
    return mask


def label_fixture_disocclusion(records, summary, fixture, center_frame):
    """Label current background hidden by the selected fixture reference."""
    import fgs_kat as kat

    if fixture not in kat.TESTS:
        raise ValueError(f"unknown FGS fixture: {fixture}")
    spec = kat.TESTS[fixture]
    if not spec.get("occluders"):
        raise ValueError(f"fixture {fixture} has no disocclusion ground truth")
    kat.apply_spec(spec)
    masks = {frame: _fixture_mask(spec, frame)
             for frame in (center_frame - 1, center_frame, center_frame + 1)}
    layout = summary["layout"]
    step = int(layout["step"])
    margin = max(0, (int(layout["block_size"]) - step) // 2)
    current = masks[center_frame]
    for record in records:
        reference_frame = center_frame - 1 \
            if record["side"] == "prev" else center_frame + 1
        x0 = record["block_x"] * step + margin
        y0 = record["block_y"] * step + margin
        x1 = min(kat.W, x0 + step)
        y1 = min(kat.H, y0 + step)
        # A current background pixel hidden by foreground in the reference has
        # no valid static-background correspondence in that reference.
        unavailable = (~current[y0:y1, x0:x1]
                       & masks[reference_frame][y0:y1, x0:x1])
        fraction = float(unavailable.mean()) if unavailable.size else 0.0
        record["unavailable_fraction"] = fraction
        record["known_disocclusion"] = fraction > 0.0


def _quantiles(values):
    values = np.asarray(values, dtype=np.float64)
    if not len(values):
        return None
    return {str(quantile): float(value) for quantile, value in zip(
        QUANTILES, np.quantile(values, QUANTILES))}


def _subset_report(records, predicate):
    selected = [record for record in records if predicate(record)]
    return {
        "records": len(selected),
        "fraction": len(selected) / max(1, len(records)),
        "cycle_error_px": _quantiles(
            [record["cycle_error_px"] for record in selected]),
        "mean_cycle_error_px": (
            float(np.mean([record["cycle_error_px"] for record in selected]))
            if selected else None),
    }


def _auc(labels, scores):
    """Tie-correct Mann-Whitney ROC AUC without a scipy dependency."""
    labels = np.asarray(labels, dtype=bool)
    scores = np.asarray(scores, dtype=np.float64)
    positives = int(labels.sum())
    negatives = len(labels) - positives
    if not positives or not negatives:
        return None
    order = np.argsort(scores, kind="stable")
    ranks = np.empty(len(scores), dtype=np.float64)
    start = 0
    while start < len(scores):
        end = start + 1
        while end < len(scores) and scores[order[end]] == scores[order[start]]:
            end += 1
        ranks[order[start:end]] = 0.5 * (start + end - 1) + 1.0
        start = end
    rank_sum = float(ranks[labels].sum())
    return ((rank_sum - positives * (positives + 1) / 2.0)
            / (positives * negatives))


def build_report(previous_path, center_path, following_path, center_frame,
                 label="", fixture=""):
    traces = load_triplet(
        previous_path, center_path, following_path, center_frame)
    center_summary, _ = traces[center_frame]
    records = cycle_records(traces, center_frame)
    if fixture:
        label_fixture_disocclusion(
            records, center_summary, fixture, center_frame)
    report = {
        "question": (
            "Can forward/backward motion-vector cycle error identify unsafe "
            "centred temporal references after the existing paired SAD gate?"),
        "label": label,
        "center_frame": center_frame,
        "trace_paths": {
            "previous": os.path.abspath(previous_path),
            "center": os.path.abspath(center_path),
            "following": os.path.abspath(following_path),
        },
        "layout": center_summary["layout"],
        "sad_limit": int(center_summary["sad_limit"]),
        "all": _subset_report(records, lambda _record: True),
        "paired_admitted": _subset_report(
            records, lambda record: record["paired_admitted"]),
        "roundtrip_under_sad": _subset_report(
            records, lambda record: record["roundtrip_under_sad"]),
        "interpretation_limit": (
            "Cycle consistency can reject contradictory vector pairs, but a "
            "symmetric wrong match or a zero-vector match can have zero cycle "
            "error. A shipping decision requires a rendered source-referenced "
            "A/B, not this trace alone."),
    }
    if fixture:
        labels = [record["known_disocclusion"] for record in records]
        report["fixture"] = fixture
        report["known_disocclusion"] = {
            "records": int(sum(labels)),
            "fraction": float(np.mean(labels)),
            "cycle_error_auc": _auc(
                labels, [record["cycle_error_px"] for record in records]),
            "current_sad_auc": _auc(
                labels, [record["current_sad_ratio"] for record in records]),
            "paired_sad_auc": _auc(
                labels, [record["pair_sad_ratio"] for record in records]),
            "cycle": _subset_report(
                records, lambda record: record["known_disocclusion"]),
            "control": _subset_report(
                records, lambda record: not record["known_disocclusion"]),
            "after_paired_sad": {
                "known": _subset_report(
                    records, lambda record: record["paired_admitted"]
                    and record["known_disocclusion"]),
                "control": _subset_report(
                    records, lambda record: record["paired_admitted"]
                    and not record["known_disocclusion"]),
            },
        }
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("previous_trace")
    parser.add_argument("center_trace")
    parser.add_argument("following_trace")
    parser.add_argument("--center-frame", type=int, required=True)
    parser.add_argument("--label", default="")
    parser.add_argument("--fixture", default="")
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    report = build_report(
        args.previous_trace, args.center_trace, args.following_trace,
        args.center_frame, args.label, args.fixture)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        temporary = f"{args.output}.tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            handle.write(rendered)
            handle.write("\n")
        os.replace(temporary, args.output)
    print(rendered)


if __name__ == "__main__":
    main()
