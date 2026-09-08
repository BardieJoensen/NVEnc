#!/usr/bin/env python3

import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import quality_metrics


class QualityMetricsTest(unittest.TestCase):
    def test_detail_projection_does_not_cancel_reversing_texture(self):
        yy, xx = np.mgrid[:64, :64]
        detail = 20 * ((xx // 2 + yy // 2) % 2 * 2 - 1)
        ideal = [128 + detail, 128 - detail]
        softened = [128 + detail // 2, 128 - detail // 2]
        with tempfile.TemporaryDirectory() as tmp:
            def write(name, frames):
                path = Path(tmp) / name
                with path.open('wb') as handle:
                    for frame in frames:
                        handle.write(frame.astype(np.uint8).tobytes())
                        handle.write(bytes([128]) * (64 * 64 // 2))
                return path
            reference = write('ideal.yuv', ideal)
            candidate = write('soft.yuv', softened)
            identity = quality_metrics.separation_metrics(reference, reference, reference, 64, 64, 8)
            damaged = quality_metrics.separation_metrics(reference, reference, candidate, 64, 64, 8)
        self.assertAlmostEqual(identity['frame_detail_transfer_gain'], 1.0)
        self.assertAlmostEqual(damaged['frame_detail_transfer_gain'], 0.5)
        # The old static-picture projection loses its denominator here.
        self.assertAlmostEqual(damaged['detail_transfer_gain'], 1.0)

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

    def test_spatial_autocorrelation_separates_grain_scale(self):
        rng = np.random.default_rng(11)
        white = rng.normal(size=(128, 128))
        coarse = (white + np.roll(white, 1, 0) + np.roll(white, 1, 1)) / 3.0
        white_acf = quality_metrics.spatial_autocorrelation([white])
        coarse_acf = quality_metrics.spatial_autocorrelation([coarse])
        self.assertLess(abs(white_acf[0]), 0.03)
        self.assertGreater(coarse_acf[0], 0.3)
        self.assertGreater(coarse_acf[0], coarse_acf[1])


if __name__ == "__main__":
    unittest.main()
