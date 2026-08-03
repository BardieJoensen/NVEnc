#!/usr/bin/env python3
import unittest

import numpy as np

import chroma_population_trace


class ChromaPopulationTraceTests(unittest.TestCase):
    def test_history_window_is_bounded_at_zero(self):
        self.assertEqual(chroma_population_trace.history_frames(2, 4), [0, 1, 2])
        self.assertEqual(chroma_population_trace.history_frames(6, 4), [3, 4, 5, 6])

    def test_empty_bins_are_linearly_filled(self):
        strength = np.asarray([2.0, 0.0, 0.0, 8.0, 0.0])
        counts = np.asarray([1, 0, 0, 1, 0])
        np.testing.assert_allclose(
            chroma_population_trace.fill_strength(strength, counts),
            [2.0, 4.0, 6.0, 8.0, 8.0])

    def test_smoothing_preserves_endpoints(self):
        np.testing.assert_allclose(
            chroma_population_trace.smooth_strength([2.0, 10.0, 6.0]),
            [2.0, 7.0, 6.0])

    def test_shape_fit_removes_only_global_scale(self):
        result = chroma_population_trace.fit_shape(
            [1.0, 2.0, 4.0], [3.0, 6.0, 12.0], [5, 5, 5])
        self.assertAlmostEqual(result["scale"], 3.0)
        self.assertAlmostEqual(result["weighted_relative_rmse"], 0.0)
        self.assertAlmostEqual(result["cosine"], 1.0)
        np.testing.assert_allclose(result["predicted"], [3.0, 6.0, 12.0])


if __name__ == "__main__":
    unittest.main()
