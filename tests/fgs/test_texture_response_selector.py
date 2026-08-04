#!/usr/bin/env python3
import unittest

import texture_response_selector as selector


class TextureResponseSelectorTests(unittest.TestCase):
    def test_affine_transfer_is_recovered_and_selects_closest_candidate(self):
        reports = []
        for title, offset in (("A", 0.00), ("B", 0.02), ("C", -0.01)):
            source = {axis: 0.50 + offset for axis in selector.AXES}
            base = {
                "variance": 1.0,
                "covariance": {axis: 0.20 for axis in selector.AXES},
            }
            desired = {"variance": 3.0}
            grid = []
            for weight, raw in ((0.0, 0.55), (0.75, 0.45)):
                exact = 0.8 * raw + 0.1
                played = (0.20 + exact * 3.0) / 4.0
                grid.append({
                    "base_covariance_weight": weight,
                    "best_quantized_model": {
                        "implied": {axis: raw for axis in selector.AXES},
                    },
                    "exact_synthesis": {
                        axis: exact for axis in selector.AXES},
                    "total_axis_mae_to_source": abs(played - source["h1"]),
                })
            reports.append({
                "source": f"/clips/clip_{title}.mkv",
                "source_truth": source,
                "base_leak": base,
                "desired_synthesis": desired,
                "response_grid": grid,
            })

        transfer = selector.fit_transfer(reports[:2])
        for axis in selector.AXES:
            self.assertAlmostEqual(transfer[axis][0], 0.8)
            self.assertAlmostEqual(transfer[axis][1], 0.1)
        result = selector.summarize(reports)
        self.assertEqual(len(result["titles"]), 3)
        self.assertTrue(all(
            row["selected_weight"] == 0.0 for row in result["titles"]))


if __name__ == "__main__":
    unittest.main()
