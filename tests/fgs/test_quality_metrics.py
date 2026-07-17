#!/usr/bin/env python3

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import quality_metrics


class QualityMetricsTest(unittest.TestCase):
    def test_spectrum_identity(self):
        rng = np.random.default_rng(7)
        image = rng.normal(size=(64, 64))
        spectrum = quality_metrics.radial_spectrum([image], size=64)
        self.assertAlmostEqual(quality_metrics.spectrum_similarity(spectrum, spectrum), 1.0)
        self.assertAlmostEqual(sum(spectrum), 1.0)

    def test_spectrum_separates_white_and_correlated_noise(self):
        rng = np.random.default_rng(9)
        white = rng.normal(size=(64, 64))
        correlated = (white + np.roll(white, 1, 0) + np.roll(white, 1, 1)) / 3.0
        white_spectrum = quality_metrics.radial_spectrum([white], size=64)
        correlated_spectrum = quality_metrics.radial_spectrum([correlated], size=64)
        self.assertLess(quality_metrics.spectrum_similarity(
            white_spectrum, correlated_spectrum), 0.95)
        self.assertLess(quality_metrics.high_frequency_fraction(correlated_spectrum),
                        quality_metrics.high_frequency_fraction(white_spectrum))

    def test_highpass_detects_edges_not_flat_regions(self):
        image = np.zeros((32, 32))
        image[:, 16:] = 10.0
        filtered = quality_metrics.highpass(image)
        self.assertEqual(float(filtered[:, :14].max()), 0.0)
        self.assertGreater(float(np.abs(filtered[:, 15:17]).max()), 0.0)


if __name__ == "__main__":
    unittest.main()
