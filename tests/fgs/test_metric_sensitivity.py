#!/usr/bin/env python3
import os
import sys
import unittest
from unittest import mock


HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import metric_sensitivity  # noqa: E402


def entry(scale, ar=(1, 2), seed=7):
    return {
        "random_seed": seed,
        "params": {"ar_coeff_lag": 1, "scaling_shift": 9},
        "ar_coeffs": {"y": list(ar)},
        "limit_output_range": True,
        "scaling_points": {"y": [[0, scale], [255, scale]]},
    }


class IsolationTests(unittest.TestCase):
    def run_check(self, pre_entries, post_entries, hashes=("same", "same")):
        with mock.patch.object(
                metric_sensitivity, "aligned_frame_count",
                return_value=(
                    2, {"width": 64, "height": 64},
                    {"width": 64, "height": 64})), mock.patch.object(
                metric_sensitivity, "grain_off_hash",
                side_effect=list(hashes)), mock.patch.object(
                metric_sensitivity, "probe_grain_entries",
                side_effect=[pre_entries, post_entries]):
            return metric_sensitivity.require_isolated("pre", "post")

    def test_accepts_only_luma_curve_changes(self):
        result = self.run_check(
            {0: entry(10), 1: entry(11)},
            {0: entry(12), 1: entry(13)})
        self.assertEqual(result["changed_luma_curves"], 2)
        self.assertEqual(result["grain_off_sha256"], "same")

    def test_rejects_changed_grain_off_base(self):
        with self.assertRaisesRegex(RuntimeError, "grain-off SHA-256 differs"):
            self.run_check(
                {0: entry(10), 1: entry(11)},
                {0: entry(12), 1: entry(13)}, hashes=("left", "right"))

    def test_rejects_changed_ar_model(self):
        with self.assertRaisesRegex(RuntimeError, "non-scaling frame fields differ"):
            self.run_check(
                {0: entry(10), 1: entry(11)},
                {0: entry(12), 1: entry(13, ar=(2, 3))})

    def test_rejects_no_treatment_change(self):
        same = {0: entry(10), 1: entry(11)}
        with self.assertRaisesRegex(RuntimeError, "no luma scaling curve changed"):
            self.run_check(same, same)


if __name__ == "__main__":
    unittest.main()
