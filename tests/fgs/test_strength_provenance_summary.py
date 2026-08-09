#!/usr/bin/env python3
import os
import unittest


os.sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import strength_provenance_summary as summary  # noqa: E402


class StrengthProvenanceSummaryTest(unittest.TestCase):
    def test_arm_stats_uses_canonical_amplitude_and_discloses_jensen_gap(self):
        records = [{"summary": {"arms": {"source": {
            "total_amplitude": 0.9,
            "texture_mae": 0.1,
            "texture_p95": 0.2,
            "base_amplitude": 0.3,
            "synth_amplitude": 0.8,
            "mean_of_ratios": {"total": 1.1},
            "jensen_gap": {"total": 0.2},
        }}}}]
        result = summary.arm_stats(records, "source")
        self.assertEqual(result["amplitude_mean"], 0.9)
        self.assertAlmostEqual(result["amplitude_mae"], 0.1)
        self.assertEqual(result["legacy_mean_of_ratios"], 1.1)
        self.assertEqual(result["jensen_gap_mean"], 0.2)

    def test_band_aggregation_weights_by_source_occupancy(self):
        rows = [
            {"range": [0.0, 0.125], "arm": "source", "blocks": 10,
             "amplitude": 0.5},
            {"range": [0.0, 0.125], "arm": "source", "blocks": 30,
             "amplitude": 1.0},
        ]
        result = summary.aggregate_bands(rows)[0]
        self.assertAlmostEqual(result["amplitude_mean"], 0.75)
        self.assertAlmostEqual(result["occupancy_weighted_amplitude"], 0.875)
        self.assertAlmostEqual(result["occupancy_weighted_mae"], 0.125)

    def test_base_delta_summary_keeps_nonidentical_scores_visible(self):
        rows = [
            {"arm": "texture-residual-all", "pixel_identical": False,
             "vmaf": 99.0, "vmaf_p1": 98.0, "psnr_y": 50.0, "ssim": 0.999},
            {"arm": "texture-residual-all", "pixel_identical": True},
        ]
        # The missing second treatment must remain explicit rather than
        # borrowing the first treatment's result.
        result = summary.summarize_base_deltas(rows)
        self.assertEqual(result["texture-residual-all"]["titles"], 2)
        self.assertEqual(result["texture-residual-all"]["pixel_identical_titles"], 1)
        self.assertEqual(result["texture-residual-all"]["vmaf_mean"], 99.0)
        self.assertEqual(result["texture-source-yu"]["titles"], 0)


if __name__ == "__main__":
    unittest.main()
