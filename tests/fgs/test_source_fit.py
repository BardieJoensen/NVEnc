#!/usr/bin/env python3
import unittest

import numpy as np

import source_fit


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


if __name__ == "__main__":
    unittest.main()
