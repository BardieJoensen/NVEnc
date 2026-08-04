#!/usr/bin/env python3
import unittest

import numpy as np

import correlation_target_report as target


class CorrelationTermsTests(unittest.TestCase):
    def test_horizontal_and_vertical_copy_is_fully_correlated(self):
        y, x = np.mgrid[:32, :32]
        patch = np.cos(2.0 * np.pi * x / 31.0) + np.cos(2.0 * np.pi * y / 31.0)
        numerator, energy, values = target.correlation_terms(patch[None])
        self.assertGreater(energy[0], 0.0)
        self.assertGreater(numerator[0], 0.0)
        self.assertGreater(values[0], 0.95)

    def test_checkerboard_is_negatively_correlated(self):
        y, x = np.mgrid[:32, :32]
        patch = ((x + y) % 2) * 2.0 - 1.0
        _numerator, _energy, values = target.correlation_terms(patch[None])
        self.assertAlmostEqual(values[0], -1.0, places=12)

    def test_upper_median_matches_nth_element(self):
        self.assertEqual(target.upper_median([1.0, 2.0, 3.0, 4.0]), 3.0)


class AggregateTests(unittest.TestCase):
    @staticmethod
    def summary(values, energies):
        values = np.asarray(values, dtype=np.float64)
        energies = np.asarray(energies, dtype=np.float64)
        return target.term_summary(values * energies, energies, values)

    def test_pooled_estimator_retains_energy_weighting(self):
        row = {
            "spatial_all": self.summary([0.1, 0.9], [9.0, 1.0]),
            "spatial_static": self.summary([0.1, 0.9], [9.0, 1.0]),
            "temporal_truth": self.summary([0.2, 0.2], [1.0, 1.0]),
            "luma_bands": {
                "0": {
                    "spatial_static": self.summary([0.1], [1.0]),
                    "temporal_truth": self.summary([0.2], [1.0]),
                },
            },
        }
        report = target.aggregate_report([row], 1)
        self.assertAlmostEqual(
            report["spatial_all"]["mean_of_frame_means"], 0.5)
        self.assertAlmostEqual(
            report["spatial_all"]["mean_of_frame_pooled"], 0.18)
        self.assertIsNone(report["routing_verdict"])


if __name__ == "__main__":
    unittest.main()
