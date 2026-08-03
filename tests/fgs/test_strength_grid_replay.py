#!/usr/bin/env python3

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import filmgrn
import strength_grid_replay


TABLE = """filmgrn1
E 0 100 1 12345 1
p 1 8 0 9 0 1 128 192 256 128 192 256
sY 3 0 10 134 20 255 30
sCb 2 0 40 255 50
sCr 2 0 60 255 70
cY 1 2 3 4
cCb 1 2 3 4 5
cCr -1 -2 -3 -4 -5
E 100 200 1 12346 0
"""


class StrengthGridReplayTest(unittest.TestCase):
    def test_endpoint_grid_maps_to_hard_interval_centres(self):
        self.assertEqual(
            strength_grid_replay.interval_center_from_endpoint(0), 6)
        self.assertEqual(
            strength_grid_replay.interval_center_from_endpoint(255), 250)
        mapped = [
            strength_grid_replay.interval_center_from_endpoint(value)
            for value in range(256)
        ]
        self.assertTrue(all(left <= right for left, right in zip(mapped, mapped[1:])))

    def test_only_luma_coordinates_move(self):
        entries = filmgrn.parse(TABLE)
        adjusted, report = strength_grid_replay.remap_luma(entries)
        self.assertEqual(adjusted[0]["scaling_points"]["y"], [
            [6, 10], [134, 20], [250, 30]
        ])
        self.assertEqual(
            adjusted[0]["scaling_points"]["cb"],
            entries[0]["scaling_points"]["cb"])
        self.assertEqual(
            adjusted[0]["scaling_points"]["cr"],
            entries[0]["scaling_points"]["cr"])
        self.assertEqual(adjusted[0]["ar_coeffs"], entries[0]["ar_coeffs"])
        self.assertEqual(adjusted[0]["params"], entries[0]["params"])
        self.assertEqual(adjusted[1], entries[1])
        self.assertEqual(report["updated_entries"], 1)
        self.assertEqual(report["luma_points"], 3)

    def test_round_trip_remains_valid_filmgrn1(self):
        adjusted, _report = strength_grid_replay.remap_luma(
            filmgrn.parse(TABLE))
        self.assertEqual(filmgrn.parse(filmgrn.dumps(adjusted)), adjusted)


if __name__ == "__main__":
    unittest.main()

