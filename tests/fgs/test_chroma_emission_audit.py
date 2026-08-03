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


if __name__ == "__main__":
    unittest.main()
