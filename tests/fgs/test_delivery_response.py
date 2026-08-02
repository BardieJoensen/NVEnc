#!/usr/bin/env python3
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import delivery_response  # noqa: E402


class DeliveryResponseTests(unittest.TestCase):
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
