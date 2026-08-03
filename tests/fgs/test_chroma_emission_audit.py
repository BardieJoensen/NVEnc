#!/usr/bin/env python3
import unittest

import numpy as np

import chroma_emission_audit


class ChromaEmissionAuditTests(unittest.TestCase):
    def test_counterfactuals_separate_spatial_and_luma_predictors(self):
        entry = {
            "scaling_points": {"y": [[0, 1]], "cb": [[0, 1]], "cr": []},
            "ar_coeffs": {"y": [], "cb": list(range(1, 26)), "cr": []},
        }
        no_luma = chroma_emission_audit.counterfactual_entry(
            entry, "cb", "no_luma")
        no_spatial = chroma_emission_audit.counterfactual_entry(
            entry, "cb", "no_spatial")
        white = chroma_emission_audit.counterfactual_entry(
            entry, "cb", "white")
        self.assertEqual(no_luma["ar_coeffs"]["cb"][:24], list(range(1, 25)))
        self.assertEqual(no_luma["ar_coeffs"]["cb"][-1], 0)
        self.assertEqual(no_spatial["ar_coeffs"]["cb"][:24], [0] * 24)
        self.assertEqual(no_spatial["ar_coeffs"]["cb"][-1], 25)
        self.assertEqual(white["ar_coeffs"]["cb"], [0] * 25)
        self.assertEqual(entry["ar_coeffs"]["cb"][-1], 25)

    def test_empty_band_accumulation_is_typed_and_combinable(self):
        count = 2
        fields = {
            "variance": {
                name: np.ones(count) for name in chroma_emission_audit.VARIANCE_FIELDS
            },
            "scale_sq": np.ones(count),
            "block_mean_scale_sq": np.ones(count),
            "index_sum": np.ones(count, dtype=np.int64),
            "index_count": 4,
            "index_min": np.zeros(count, dtype=np.int64),
            "index_max": np.ones(count, dtype=np.int64),
            "nonzero": np.ones(count, dtype=np.int64),
            "pixel_count": 8,
            "mismatches": np.zeros(count, dtype=np.int64),
            "max_abs_error": np.zeros(count, dtype=np.int64),
        }
        empty = chroma_emission_audit.accumulate(fields, [])
        full = chroma_emission_audit.accumulate(fields)
        self.assertEqual(empty["blocks"], 0)
        combined = chroma_emission_audit.combine([empty, full])
        self.assertEqual(combined["blocks"], count)
        self.assertEqual(combined["pixel_count"], count * 8)

    def test_centered_curve_moves_only_selected_chroma_coordinates(self):
        entry = {
            "scaling_points": {
                "y": [[0, 10], [255, 20]],
                "cb": [[0, 30], [134, 40], [255, 50]],
                "cr": [[0, 60], [255, 70]],
            },
            "ar_coeffs": {"y": [1], "cb": [2], "cr": [3]},
        }
        changed = chroma_emission_audit.centered_curve_entry(entry, "cb")
        self.assertEqual(
            changed["scaling_points"]["cb"],
            [[6, 30], [134, 40], [250, 50]])
        self.assertEqual(changed["scaling_points"]["y"], entry["scaling_points"]["y"])
        self.assertEqual(changed["scaling_points"]["cr"], entry["scaling_points"]["cr"])
        self.assertEqual(changed["ar_coeffs"], entry["ar_coeffs"])
        self.assertEqual(entry["scaling_points"]["cb"][0][0], 0)

    def test_unsmoothing_reverses_exact_three_point_filter(self):
        raw = np.asarray([4.0, 20.0, 8.0])
        smoothed = np.asarray([
            raw[0], (raw[0] + 2.0 * raw[1] + raw[2]) / 4.0, raw[-1]
        ])
        entry = {
            "scaling_points": {
                "y": [[0, 1]],
                "cb": [[0, int(smoothed[0])], [128, int(smoothed[1])],
                       [255, int(smoothed[2])]],
                "cr": [[0, 1]],
            },
            "ar_coeffs": {"y": [], "cb": [], "cr": []},
        }
        changed = chroma_emission_audit.unsmoothed_curve_entry(
            entry, "cb", bins=3, max_points=3)
        self.assertEqual(changed["scaling_points"]["cb"], [
            [0, 4], [128, 20], [255, 8]
        ])
        self.assertEqual(changed["scaling_points"]["cr"], [[0, 1]])

    def test_point_reduction_preserves_endpoints(self):
        points = [[float(index), float(index * index)] for index in range(7)]
        reduced = chroma_emission_audit.reduce_points(points, 4)
        self.assertEqual(len(reduced), 4)
        self.assertEqual(reduced[0], points[0])
        self.assertEqual(reduced[-1], points[-1])

    def test_population_curve_uses_reconstructed_bins_and_is_plane_local(self):
        entry = {
            "scaling_points": {
                "y": [[0, 1]], "cb": [[0, 2]], "cr": [[0, 3]],
            },
            "ar_coeffs": {"y": [1], "cb": [2], "cr": [3]},
        }
        population = {
            "shape_fit": {"scale": 4.0},
            "bins": [
                {"filled_sigma": 1.0},
                {"filled_sigma": 2.0},
                {"filled_sigma": 3.0},
            ],
        }
        changed = chroma_emission_audit.population_curve_entry(
            entry, "cr", population, centered=True, max_points=3)
        self.assertEqual(changed["scaling_points"]["cr"], [
            [43, 4], [128, 8], [213, 12]
        ])
        self.assertEqual(changed["scaling_points"]["cb"], [[0, 2]])
        self.assertEqual(changed["ar_coeffs"], entry["ar_coeffs"])


if __name__ == "__main__":
    unittest.main()
