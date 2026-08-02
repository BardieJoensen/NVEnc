#!/usr/bin/env python3
import unittest

import numpy as np

import source_fit
import strength_selection_report


class SourceFitFlatSelectionTests(unittest.TestCase):
    def test_flat_scores_api_matches_full_metrics(self):
        rng = np.random.default_rng(7)
        frame = rng.normal(512.0, 8.0, (96, 128))
        score, sigma = source_fit.flat_scores(frame, 10)
        full_score, full_sigma, strict = source_fit.flat_metrics(frame, 10)
        np.testing.assert_array_equal(score, full_score)
        np.testing.assert_array_equal(sigma, full_sigma)
        self.assertEqual(score.shape, strict.shape)

    def test_production_selection_contains_every_eligible_strict_block(self):
        rng = np.random.default_rng(11)
        frame = rng.normal(512.0, 6.0, (128, 160))
        blocks, score, sigma = source_fit.production_flat_blocks(frame, 10)
        _score, _sigma, strict = source_fit.flat_metrics(frame, 10)
        eligible_strict = ((sigma >= 2.0) & (sigma <= 200.0)
                           & (score > 0.0) & strict)
        selected = np.zeros(score.shape, dtype=bool)
        for row, col in blocks:
            selected[row, col] = True
        self.assertTrue(np.all(selected[eligible_strict]))

    def test_production_selection_adds_top_decile(self):
        rng = np.random.default_rng(19)
        frame = rng.normal(512.0, 12.0, (320, 320))
        blocks, score, sigma = source_fit.production_flat_blocks(frame, 10)
        eligible_candidates = int(((sigma >= 2.0) & (sigma <= 200.0)
                                   & (score >= 0.5)).sum())
        self.assertGreaterEqual(len(blocks), min(score.size // 10, eligible_candidates))


class TemporalLeakTests(unittest.TestCase):
    def test_temporal_leak_ignores_static_base_error(self):
        """Spatial base energy is not necessarily retained grain.

        A static denoiser error is deliberately added only to the clean base.
        Spatial subtraction must under-predict the missing grain because it
        subtracts that error. Consecutive-frame base differencing cancels it and
        recovers the known retained-grain fraction.
        """
        rng = np.random.default_rng(23)
        shape = (64, 64)
        retain = 0.35
        picture = np.full(shape, 512.0)
        y, x = np.mgrid[:shape[0], :shape[1]]
        static_error = 12.0 * np.sin(x * 2.0 * np.pi / 9.0)
        grain_a = rng.normal(0.0, 20.0, shape)
        grain_b = rng.normal(0.0, 20.0, shape)
        source = picture + grain_a
        next_source = picture + grain_b
        clean = picture + static_error + retain * grain_a
        next_clean = picture + static_error + retain * grain_b
        blocks = [(row, col) for row in range(2) for col in range(2)]

        row = strength_selection_report.measure(
            source, next_source, clean, next_clean, blocks)

        self.assertAlmostEqual(row["temporal_leak_ratio"], retain, delta=0.03)
        self.assertAlmostEqual(
            row["temporal_target_ratio"], np.sqrt(1.0 - retain * retain),
            delta=0.03)
        self.assertLess(row["amplitude_ratio"],
                        row["temporal_target_ratio"] - 0.10)


if __name__ == "__main__":
    unittest.main()
