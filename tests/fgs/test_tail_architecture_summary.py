#!/usr/bin/env python3
import os
import unittest


os.sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tail_architecture_summary as summary  # noqa: E402


class TailArchitectureSummaryTest(unittest.TestCase):
    def test_arm_stats_keeps_amplitude_and_texture_separate(self):
        records = [{"summary": {"arms": {"source": {
            "total_amplitude": value,
            "texture_mae": texture,
            "base_amplitude": 0.25,
            "synth_amplitude": 0.75,
        }}}} for value, texture in ((0.8, 0.1), (1.1, 0.2))]
        result = summary.arm_stats(records, "source")
        self.assertAlmostEqual(result["amplitude_mean"], 0.95)
        self.assertAlmostEqual(result["amplitude_mae"], 0.15)
        self.assertAlmostEqual(result["texture_mae"], 0.15)

    def test_band_summary_reports_occupancy_and_unweighted_results(self):
        rows = [
            {"range": [0.0, 0.125], "arm": "source", "blocks": 10,
             "amplitude": 0.5},
            {"range": [0.0, 0.125], "arm": "source", "blocks": 30,
             "amplitude": 1.0},
        ]
        result = summary.aggregate_bands(rows)[0]
        self.assertAlmostEqual(result["amplitude_mean"], 0.75)
        self.assertAlmostEqual(result["occupancy_weighted_amplitude"], 0.875)
        self.assertAlmostEqual(result["amplitude_mae"], 0.25)
        self.assertAlmostEqual(result["occupancy_weighted_mae"], 0.125)


if __name__ == "__main__":
    unittest.main()
