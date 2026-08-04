#!/usr/bin/env python3
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import delivery_response  # noqa: E402


class DeliveryResponseTests(unittest.TestCase):
    def test_parse_positive_ints_sorts_deduplicates_and_rejects_zero(self):
        self.assertEqual(
            delivery_response.parse_positive_ints("16,4,16,8"),
            [4, 8, 16])
        self.assertEqual(delivery_response.parse_positive_ints(""), [])
        with self.assertRaises(ValueError):
            delivery_response.parse_positive_ints("0,8")

    def test_deterministic_sampling_is_repeatable_and_bounded(self):
        blocks = [(row, col) for row in range(4) for col in range(4)]
        positions = np.arange(len(blocks))
        first = delivery_response.deterministic_sample_positions(
            positions, blocks, 10, 5, 3)
        second = delivery_response.deterministic_sample_positions(
            positions, blocks, 10, 5, 3)
        np.testing.assert_array_equal(first, second)
        self.assertEqual(len(first), 5)
        self.assertEqual(len(set(first.tolist())), 5)

    def test_response_population_features_measure_boundary_exposure(self):
        middle = np.full((32, 64), 128 << 2, dtype=np.uint16)
        boundary = middle.copy()
        boundary[:, 32:] = 16 << 2
        features = delivery_response.response_population_features(
            (boundary, boundary), [(0, 0), (0, 1)], bits=10,
            limited_range=True)
        self.assertEqual(features.shape, (2, 3))
        self.assertGreater(features[1, 2], features[0, 2])
        self.assertAlmostEqual(features[0, 1], 0.0)

    def test_representatives_are_deterministic_bounded_and_weighted(self):
        blocks = [(0, index) for index in range(12)]
        features = np.column_stack((
            np.arange(12, dtype=np.float64),
            np.arange(12, dtype=np.float64) ** 2,
            np.zeros(12, dtype=np.float64),
        ))
        first, first_weights = delivery_response.representative_sample_positions(
            np.arange(12), features, blocks, frame=3, limit=4, salt=2)
        second, second_weights = delivery_response.representative_sample_positions(
            np.arange(12), features, blocks, frame=3, limit=4, salt=2)
        np.testing.assert_array_equal(first, second)
        np.testing.assert_array_equal(first_weights, second_weights)
        self.assertLessEqual(len(first), 4)
        self.assertEqual(int(first_weights.sum()), 12)
        self.assertTrue(np.all(first_weights > 0))

    def test_constant_representative_population_collapses_safely(self):
        blocks = [(0, index) for index in range(6)]
        selected, weights = delivery_response.representative_sample_positions(
            np.arange(6), np.ones((6, 3)), blocks,
            frame=0, limit=4, salt=0)
        self.assertEqual(len(selected), 1)
        self.assertEqual(weights.tolist(), [6])

    def test_representative_weights_recover_population_mean(self):
        blocks = [(0, index) for index in range(8)]
        features = np.arange(8, dtype=np.float64)[:, None]
        selected, weights = delivery_response.representative_sample_positions(
            np.arange(8), features, blocks, frame=0, limit=3, salt=0)
        # A response constant inside each assigned feature cell is integrated
        # exactly by the selected medoid and its represented population.
        normalized = (features[:, 0] - features[:, 0].mean()) / features[:, 0].std()
        centers = normalized[selected]
        assignment = np.argmin(
            (normalized[:, None] - centers[None, :]) ** 2, axis=1)
        response = np.asarray([2.0, 5.0, 11.0])[assignment]
        selected_response = response[selected]
        self.assertAlmostEqual(
            float(np.average(selected_response, weights=weights)),
            float(np.mean(response)))

    def test_sampled_bin_response_uses_only_matching_positions(self):
        variances = np.asarray([1.0, 3.0, 20.0, 24.0])
        bins = np.asarray([2, 2, 7, 7])
        blocks = [(0, index) for index in range(4)]
        response, samples = delivery_response.sampled_bin_responses(
            variances, bins, blocks, frame=0, limit=8, salt=0)
        self.assertEqual(samples, 4)
        self.assertAlmostEqual(response[2], 2.0)
        self.assertAlmostEqual(response[7], 22.0)
        self.assertTrue(np.isnan(response[0]))

    def test_sparse_summary_retains_each_selection_for_table_replay(self):
        references = [{
            "range": [0.0, 0.5], "seed_mean_sigma": 2.0,
            "pre_encode_leak": 0.0,
        }]
        summary = delivery_response.summarize_sparse(
            references, np.asarray([[4.0], [9.0]]), np.asarray([1]),
            qvbr=29.0, sample_limit=4, sampled_blocks=1)
        self.assertEqual(
            summary["bands"][0]["predicted_sigma"]["values"],
            [2.0, 3.0])
        self.assertEqual(len(summary["bands"][0]
                             ["linearized_post_correction_target_error"]
                             ["values"]), 2)

    def test_analyzer_bin_matches_twenty_equal_native_ranges(self):
        self.assertEqual(delivery_response.analyzer_bin_from_native(0, 10), 0)
        self.assertEqual(delivery_response.analyzer_bin_from_native(511, 10), 9)
        self.assertEqual(delivery_response.analyzer_bin_from_native(1023, 10), 19)

    def test_native_to_8bit_clamps_to_legal_range(self):
        self.assertEqual(delivery_response.native_to_8bit(0, 10, 16, 235), 16)
        self.assertEqual(delivery_response.native_to_8bit(400, 10, 16, 235), 100)
        self.assertEqual(delivery_response.native_to_8bit(1023, 10, 16, 235), 235)

    def test_response_fixture_does_not_start_above_range_maximum(self):
        codes, base, blocks = delivery_response.response_fixture(10, 16, 235)
        row, col = blocks[-1]
        self.assertEqual(codes[-1], 235)
        self.assertEqual(int(base[row * 32, col * 32]), 940)

    def test_uniform_response_uses_only_codes_in_each_analyzer_bin(self):
        response = np.arange(256, dtype=np.float64)
        codes = np.arange(16, 236, dtype=np.int64)
        result = delivery_response.uniform_bin_response(response, codes)
        self.assertAlmostEqual(result[1], np.mean(np.arange(16, 26)))
        self.assertAlmostEqual(result[18], np.mean(np.arange(230, 236)))

    def test_correction_residual_is_zero_for_exact_prediction(self):
        self.assertEqual(
            delivery_response.correction_residual(0.97, 4.0, 4.0), 0.0)
        self.assertAlmostEqual(
            delivery_response.correction_residual(0.97, 4.0, 4.4),
            0.97 * (4.0 / 4.4 - 1.0))


if __name__ == "__main__":
    unittest.main()
