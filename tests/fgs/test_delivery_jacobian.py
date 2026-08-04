#!/usr/bin/env python3
import os
import sys
import unittest
from unittest import mock

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import delivery_jacobian  # noqa: E402


class DeliveryJacobianTests(unittest.TestCase):
    def test_damped_step_solves_identity_response(self):
        raw, bounded = delivery_jacobian.solve_damped_step(
            np.eye(2), np.asarray([0.2, -0.3]),
            regularization=0.0, max_log_step=1.0)
        np.testing.assert_allclose(raw, [0.2, -0.3])
        np.testing.assert_allclose(bounded, raw)

    def test_step_bound_is_applied_after_solve(self):
        raw, bounded = delivery_jacobian.solve_damped_step(
            np.eye(2), np.asarray([2.0, -3.0]),
            regularization=0.0, max_log_step=0.4)
        np.testing.assert_allclose(raw, [2.0, -3.0])
        np.testing.assert_allclose(bounded, [0.4, -0.4])

    def test_regularization_reduces_underdetermined_step(self):
        jacobian = np.asarray([[1.0, 1.0]])
        raw, _bounded = delivery_jacobian.solve_damped_step(
            jacobian, np.asarray([1.0]),
            regularization=1.0, max_log_step=1.0)
        np.testing.assert_allclose(raw, [1.0 / 3.0, 1.0 / 3.0])

    def test_postencode_target_uses_same_detrended_population(self):
        yy, xx = np.indices((32, 32))
        pattern = ((xx + yy) & 1).astype(np.float64) * 2.0 - 1.0
        source = {0: pattern * 8.0, 1: np.zeros_like(pattern)}
        encoded_base = {0: pattern * 4.0, 1: np.zeros_like(pattern)}
        contexts = [{
            "frame": 0,
            "blocks": [(0, 0)],
            "band_positions": [[0]],
        }]
        result = delivery_jacobian.postencode_target_ratios(
            source, encoded_base, contexts, band_count=1)
        self.assertEqual(result["counts"].tolist(), [1])
        self.assertAlmostEqual(result["post_leak_ratio"][0], 0.5)
        self.assertAlmostEqual(result["ratios"][0], np.sqrt(0.75))

    def test_response_evaluation_can_replay_measured_stream_seeds(self):
        context = {
            "frame": 3,
            "selected_blocks": [(0, 0)],
            "clean": (np.zeros((32, 32)), np.zeros((32, 32))),
            "selected_by_bin": {0: np.asarray([0])},
            "weights_by_bin": {0: np.asarray([1])},
            "selected_lookup": {0: 0},
            "band_positions": [[0]],
            "block_bins": np.asarray([0]),
        }
        entries = [{"start": 0, "end": 10_000_000}]
        stream_entries = {
            3: {"random_seed": 111},
            4: {"random_seed": 222},
        }
        seen = []

        def synthesize(_clean, _blocks, entry, _gaussian, _bits):
            seen.append(entry["random_seed"])
            return np.zeros((1, 32, 32))

        with mock.patch.object(
                delivery_jacobian.av1_grain, "synthesize_selected_luma",
                side_effect=synthesize), mock.patch.object(
                    delivery_jacobian, "selected_variances",
                    return_value=np.asarray([1.0])):
            delivery_jacobian.evaluate_entries(
                entries, [context], None, 10, 24, 1, True, 1, 1,
                seed_mode="stream", stream_entries=stream_entries)
        self.assertEqual(seen, [111, 222])


if __name__ == "__main__":
    unittest.main()
