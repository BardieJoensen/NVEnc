#!/usr/bin/env python3
import unittest

import sourcefit_admission_compare as compare


def summary(lag1, lag2, acf, spectrum, anisotropy):
    return {
        "coverage": {"measured_entries": 2, "table_entries": 2},
        "film_like_evidence": {"cross_frame_correlation": 0.05},
        "model_fidelity": {
            "lag1_delta": lag1,
            "lag2_delta": lag2,
            "acf_rmse": acf,
            "spectrum_total_variation": spectrum,
            "anisotropy_abs": anisotropy,
            "diagonal_acf_lag1_abs": 0.02,
        },
    }


def report(table, model_summary, source="/tmp/source.mkv"):
    return {
        "source": source,
        "table": table,
        "bits": 10,
        "dimensions": [1920, 1080],
        "settings": {
            "flat_selector": "production",
            "flat_fraction": 0.1,
            "static_ratio": [0.8, 1.3],
            "minimum_pair_blocks": 8,
            "minimum_band_blocks": 16,
            "luma_bins": 8,
            "texture_blocks_per_pair": 16,
            "texture_blocks_per_pair_band": 4,
        },
        "summary": model_summary,
    }


class ComparisonTests(unittest.TestCase):
    def test_reports_each_descriptor_without_manufacturing_route(self):
        source = report("/tmp/source.tbl", summary(0.02, -0.04, 0.05, 0.1, 0.01))
        residual = report("/tmp/residual.tbl", summary(0.2, -0.3, 0.2, 0.4, 0.08))
        result = compare.compare_reports(source, residual)
        self.assertAlmostEqual(
            result["source_fit"]["texture_errors"]["lag_mean_abs"], 0.03)
        self.assertAlmostEqual(
            result["residual_minus_source_error"]["lag_mean_abs"], 0.22)
        self.assertAlmostEqual(
            result["residual_minus_source_error"]["acf_rmse"], 0.15)
        self.assertIsNone(result["routing_verdict"])

    def test_negative_improvement_is_preserved(self):
        source = report("/tmp/source.tbl", summary(0.3, 0.2, 0.3, 0.5, 0.1))
        residual = report("/tmp/residual.tbl", summary(0.1, 0.1, 0.2, 0.4, 0.05))
        result = compare.compare_reports(source, residual)
        self.assertLess(
            result["residual_minus_source_error"]["lag_mean_abs"], 0.0)
        self.assertIsNone(result["routing_verdict"])

    def test_mismatched_sources_are_rejected(self):
        source = report("/tmp/source.tbl", summary(0, 0, 0, 0, 0))
        residual = report(
            "/tmp/residual.tbl", summary(0, 0, 0, 0, 0),
            source="/tmp/other.mkv")
        with self.assertRaisesRegex(ValueError, "same source"):
            compare.compare_reports(source, residual)


if __name__ == "__main__":
    unittest.main()
