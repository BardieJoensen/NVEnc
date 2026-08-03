#!/usr/bin/env python3

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import strength_observation_replay as replay


class StrengthObservationReplayTest(unittest.TestCase):
    def test_fractional_solver_recovers_constant(self):
        means = np.linspace(0.0, 1023.0, 2000)
        solved = replay.fractional_strength_solve(
            means, np.full_like(means, 17.5), 1023)
        np.testing.assert_allclose(solved, 17.5, atol=1e-9)

    def test_fractional_solver_preserves_dense_linear_direction(self):
        means = np.linspace(0.0, 1023.0, 20000)
        strengths = 5.0 + 10.0 * means / 1023.0
        solved = replay.fractional_strength_solve(means, strengths, 1023)
        predicted = replay.evaluate_controls(solved, means, 1023)
        # libaom's alpha deliberately rounds the endpoint slope toward the
        # mean; the invariant is a smooth monotone fit, not exact interpolation.
        self.assertTrue(np.all(np.diff(solved) > 0.0))
        self.assertLess(float(np.sqrt(np.mean((predicted - strengths) ** 2))), 0.25)

    def test_fit_frame_selection_avoids_holdout_pairs(self):
        entries = [
            {"start": 0, "end": 50_000_000,
             "apply_grain": True, "update_parameters": True},
            {"start": 50_000_000, "end": 100_000_000,
             "apply_grain": True, "update_parameters": True},
        ]
        selected, forced = replay.choose_fit_frames(
            entries, 24, 1, 2, {3, 4, 15, 16})
        self.assertEqual(forced, [])
        self.assertEqual(set(selected), {0, 1})
        for frames in selected.values():
            self.assertEqual(len(frames), 2)
            self.assertTrue(all(
                frame not in {3, 4, 15, 16}
                and frame + 1 not in {3, 4, 15, 16}
                for frame in frames))

    def test_local_deadzone_target_is_bounded(self):
        source = np.asarray([100.0, 100.0, 100.0])
        base = np.asarray([0.0, 25.0, 100.0])
        global_target, local_target, report = replay.target_strengths(
            source, base, 29.0)
        self.assertTrue(np.all(local_target >= 0.0))
        self.assertTrue(np.all(local_target <= 10.0))
        self.assertGreater(local_target[0], local_target[-1])
        self.assertGreater(report["global_synthesis_fraction"], 0.0)
        self.assertEqual(global_target.shape, source.shape)

    def test_point_quantization_stays_within_av1_limits(self):
        controls = np.linspace(10.0, 30.0, 20)
        points = replay.quantized_points(controls, 10)
        self.assertEqual(len(points), 14)
        self.assertEqual(points[0][0], 0)
        self.assertEqual(points[-1][0], 255)
        self.assertTrue(all(
            left[0] < right[0] for left, right in zip(points, points[1:])))


if __name__ == "__main__":
    unittest.main()
