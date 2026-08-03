#!/usr/bin/env python3
import os
import sys
import unittest


HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import amplitude_matched_texture as replay  # noqa: E402


def entry(start=0, end=10_000_000, grain_shift=0):
    return {
        "start": start,
        "end": end,
        "apply_grain": True,
        "random_seed": 7,
        "update_parameters": True,
        "params": {
            "ar_coeff_lag": 1,
            "ar_coeff_shift": 7,
            "grain_scale_shift": grain_shift,
            "scaling_shift": 11,
            "chroma_scaling_from_luma": 1,
        },
        "scaling_points": {
            "y": [[0, 10], [255, 11]],
            "cb": [[0, 3], [255, 3]],
            "cr": [[0, 4], [255, 4]],
        },
        "ar_coeffs": {"y": [1, 2], "cb": [1, 2, 3], "cr": [4, 5, 6]},
    }


class TableTests(unittest.TestCase):
    def test_selects_updated_entry_at_timestamp(self):
        first = entry(0, 10_000_000)
        second = entry(10_000_000, 20_000_000)
        self.assertIs(replay.entry_at_seconds([first, second], 1.5), second)

    def test_static_table_is_luma_only_and_preserves_ar(self):
        source = entry(grain_shift=2)
        result = replay.static_luma_table(source, 99, 128, 12345)[0]
        self.assertEqual(result["start"], 0)
        self.assertEqual(result["end"], 99)
        self.assertEqual(result["random_seed"], 12345)
        self.assertEqual(result["scaling_points"]["y"], [[0, 128], [255, 128]])
        self.assertEqual(result["scaling_points"]["cb"], [])
        self.assertEqual(result["scaling_points"]["cr"], [])
        self.assertEqual(result["params"]["chroma_scaling_from_luma"], 0)
        self.assertEqual(result["ar_coeffs"], source["ar_coeffs"])
        self.assertNotEqual(result["scaling_points"], source["scaling_points"])

    def test_equivalent_scale_accounts_for_grain_shift(self):
        fine = entry(grain_shift=0)
        coarse = entry(grain_shift=2)
        self.assertEqual(replay.equivalent_scale(32, fine, coarse), 128)
        self.assertEqual(replay.equivalent_scale(128, coarse, fine), 32)

    def test_candidate_search_brackets_linear_prediction(self):
        self.assertEqual(
            replay.candidate_scales(128, fine_sigma=4.0, coarse_sigma=5.0),
            [101, 102, 103, 128])

    def test_rejects_invalid_static_scale(self):
        with self.assertRaisesRegex(ValueError, "outside 1..255"):
            replay.static_luma_table(entry(), 99, 0, 1)


if __name__ == "__main__":
    unittest.main()
