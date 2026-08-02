#!/usr/bin/env python3
import unittest

import numpy as np

import av1_grain
import emission_audit


class EmissionAuditTests(unittest.TestCase):
    def test_entry_for_frame_uses_table_timebase(self):
        entries = [
            {"start": 0, "end": 1_000_000},
            {"start": 1_000_000, "end": 2_000_000},
        ]
        self.assertIs(entries[0], emission_audit.entry_for_frame(
            entries, 2, 24, 1))
        self.assertIs(entries[1], emission_audit.entry_for_frame(
            entries, 3, 24, 1))

    def test_side_data_preserves_bitstream_seed_and_luma_model(self):
        side_data = {
            "seed": "7391",
            "ar_coeff_lag": 1,
            "ar_coeff_shift": 6,
            "grain_scale_shift": 2,
            "scaling_shift": 11,
            "overlap_flag": 1,
            "limit_output_range": 1,
            "components": [{
                "y_points_value": "0 255",
                "y_points_scaling": "4 8",
                "ar_coeffs_y": "1 2 3 4",
            }],
        }
        entry = emission_audit.entry_from_side_data(side_data)
        self.assertEqual(entry["random_seed"], 7391)
        self.assertEqual(entry["scaling_points"]["y"], [[0, 4], [255, 8]])
        self.assertEqual(entry["ar_coeffs"]["y"], [1, 2, 3, 4])
        self.assertTrue(entry["limit_output_range"])

    def test_high_bit_depth_lut_interpolates_low_bits(self):
        lut = np.arange(256, dtype=np.int64) * 4
        pixels = np.asarray([0, 1, 2, 3, 4, 1020, 1023])
        self.assertEqual(
            av1_grain.scale_values(lut, pixels, 10).tolist(),
            [0, 1, 2, 3, 4, 1020, 1020])

    def test_lfsr_matches_known_first_step(self):
        register, value = av1_grain.random_number(7391, 8)
        self.assertEqual(register, 3695)
        self.assertEqual(value, 14)

    def test_oracle_seeds_are_repeatable_nonzero_and_spread(self):
        first = [emission_audit.oracle_seed(10, index) for index in range(32)]
        second = [emission_audit.oracle_seed(10, index) for index in range(32)]
        following = [emission_audit.oracle_seed(11, index) for index in range(32)]
        self.assertEqual(first, second)
        self.assertNotIn(0, first)
        self.assertGreaterEqual(len(set(first)), 31)
        self.assertNotEqual(first, following)


if __name__ == "__main__":
    unittest.main()
