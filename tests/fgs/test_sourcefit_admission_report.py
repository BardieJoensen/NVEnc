#!/usr/bin/env python3
import unittest
from unittest import mock

import numpy as np

import sourcefit_admission_report as admission


class FrameSelectionTests(unittest.TestCase):
    def test_entry_pairs_stay_wholly_inside_interval(self):
        times = [index * 0.04 for index in range(10)]
        entry = {"start": 800_000, "end": 2_500_000}
        selected = admission.entry_frame_pairs(entry, times, 3)
        self.assertEqual(selected, [2, 4, 5])
        for frame in selected:
            self.assertGreaterEqual(times[frame], 0.08)
            self.assertLess(times[frame + 1], 0.25)

    def test_sparse_interval_reports_no_pair(self):
        times = [0.0, 0.04, 0.08]
        entry = {"start": 100_000, "end": 300_000}
        self.assertEqual(admission.entry_frame_pairs(entry, times, 3), [])


class EvidenceTests(unittest.TestCase):
    def test_selected_patches_cancel_static_picture(self):
        rng = np.random.default_rng(7)
        y, x = np.mgrid[:32, :32]
        picture = 400.0 + 0.3 * x + 0.2 * y
        grain_a = rng.normal(0.0, 8.0, (32, 32))
        grain_b = rng.normal(0.0, 8.0, (32, 32))
        selected = admission.selected_patches(
            picture + grain_a, picture + grain_b, [(0, 0)], 10, 8)
        self.assertEqual(selected["patches"].shape, (1, 32, 32))
        self.assertAlmostEqual(
            selected["sigma_8bit"][0], 2.0, delta=0.2)
        self.assertLess(abs(selected["cross_frame_correlations"][0]), 0.1)

    def test_model_patch_generation_preserves_requested_shape(self):
        entry = {
            "params": {"ar_coeff_lag": 3, "ar_coeff_shift": 7},
            "ar_coeffs": {"y": [0] * 24},
        }
        patches = admission.model_patches(entry, 4, 1, 4.0, 10)
        self.assertEqual(patches.shape, (4, 32, 32))

    def test_measure_pair_converts_unsigned_decoder_storage_before_subtraction(self):
        source = np.full((32, 32), 100, dtype=np.uint16)
        next_source = np.full((32, 32), 101, dtype=np.uint16)
        with mock.patch.object(
                admission, "select_flat",
                return_value=([(0, 0)], np.ones((1, 1)), np.ones((1, 1)))), \
             mock.patch.object(
                 admission, "static_flat_blocks", return_value=[]) as static:
            admission.measure_pair(
                0, source, next_source, 10, "top10", 0.1,
                0.8, 1.3, 8, 8, 16, 4)
        self.assertEqual(static.call_args.args[0].dtype, np.float64)
        self.assertEqual(static.call_args.args[1].dtype, np.float64)

    def test_patch_sample_is_deterministic_and_keeps_endpoints(self):
        patches = np.arange(10 * 4).reshape(10, 2, 2)
        sampled = admission.patch_sample(patches, 4)
        np.testing.assert_array_equal(sampled[0], patches[0])
        np.testing.assert_array_equal(sampled[-1], patches[-1])
        np.testing.assert_array_equal(
            sampled, admission.patch_sample(patches, 4))

    def test_empty_aggregate_never_manufactures_a_route(self):
        row = {
            "status": "INSUFFICIENT_COVERAGE",
            "coverage": {
                "requested_pairs": 3,
                "usable_pairs": 0,
                "static_blocks": 0,
            },
        }
        result = admission.aggregate_entries([row], 8)
        self.assertIsNone(result["model_fidelity"])
        self.assertIsNone(result["routing_verdict"])
        self.assertEqual(result["coverage"]["insufficient_entries"], 1)


if __name__ == "__main__":
    unittest.main()
