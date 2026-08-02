#!/usr/bin/env python3
import json
import os
import sys
import tempfile
import unittest

import numpy as np


HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import motion_confidence  # noqa: E402


def reference(slot, delta, side, dx=0, dy=0, sad=10, selected=1):
    return {
        "slot": slot, "delta": delta, "side": side,
        "dx": dx, "dy": dy, "sad": sad,
        "src_avg": 0, "ref_avg": 0,
        "disabled": 0 if selected else 1,
        "valid_motion": 1, "under_sad": 1,
        "selected": selected, "mix": 0.2 if selected else 0.0,
    }


def block(index, x, y, nearest=(0, 0), far=(0, 0), selected=1):
    return {
        "type": "degrain_block_trace", "version": 1, "frame": 7,
        "block": index, "block_x": x, "block_y": y,
        "source_mix": 0.6, "reference_mix": 0.4,
        "refs": [
            reference(0, 1, "next", selected=0),
            reference(1, 1, "prev", *nearest, selected=selected),
            reference(2, 2, "next", selected=0),
            reference(3, 2, "prev", *far, selected=selected),
        ],
    }


class MotionConfidenceTests(unittest.TestCase):
    def test_parse_requires_complete_exact_frame_trace(self):
        summary = {
            "type": "degrain_block_trace_summary", "version": 1,
            "frame": 7, "sad_limit": 100, "stride": 1,
            "layout": {"blocks": 2, "blocks_x": 2, "blocks_y": 1,
                       "directions": 4, "block_size": 32, "overlap": 16,
                       "step": 16, "pel": 1},
        }
        rows = [block(0, 0, 0), block(1, 1, 0)]
        with tempfile.NamedTemporaryFile("w", encoding="utf-8") as handle:
            handle.write("prefix " + json.dumps(
                summary, separators=(",", ":")) + "\n")
            for row in rows:
                handle.write("degrain: " + json.dumps(
                    row, separators=(",", ":")) + "\n")
            handle.flush()
            parsed_summary, parsed = motion_confidence.parse_trace(
                handle.name, expected_frame=7)
        self.assertEqual(parsed_summary["frame"], 7)
        self.assertEqual(sorted(parsed), [0, 1])

    def test_derives_temporal_and_spatial_vector_disagreement(self):
        summary = {
            "sad_limit": 100,
            "layout": {"blocks_x": 3, "blocks_y": 3, "pel": 1},
        }
        rows = {}
        for y in range(3):
            for x in range(3):
                index = y * 3 + x
                nearest = (10, 0) if (x, y) == (1, 1) else (0, 0)
                far = (25, 0) if (x, y) == (1, 1) else (0, 0)
                rows[index] = block(index, x, y, nearest, far)
        features = motion_confidence.derive_trace_features(summary, rows)[4]
        self.assertAlmostEqual(features["temporal_vector_error"], 5.0)
        self.assertAlmostEqual(features["spatial_vector_error"], 10.0)
        self.assertAlmostEqual(features["nearest_sad_ratio"], 0.1)
        self.assertAlmostEqual(features["neighbor_invalid_fraction"], 0.0)

    def test_risk_curve_separates_labelled_previous_blend(self):
        rng = np.random.default_rng(4)
        count = 4000
        previous = rng.normal(0.0, 100.0, count)
        following = rng.normal(0.0, 100.0, count)
        risk = np.concatenate((np.zeros(count // 2), np.ones(count // 2)))
        error = 0.2 * previous * risk
        data = {
            "error": error,
            "previous": previous,
            "following": following,
            "moving": np.ones(count, dtype=bool),
            "reference_mix": risk,
        }
        report = motion_confidence._feature_report(
            data, "reference_mix", data["moving"])
        half = next(row for row in report["safest_fraction"]
                    if row["fraction"] == 0.5)
        self.assertLess(abs(half["kept"]["lag_asymmetry"]), 0.01)
        self.assertAlmostEqual(
            half["rejected"]["lag_asymmetry"], 0.2, places=2)


if __name__ == "__main__":
    unittest.main()
