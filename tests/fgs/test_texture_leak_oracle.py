#!/usr/bin/env python3
import unittest

import numpy as np

import texture_leak_oracle as oracle


class AxisCovarianceTests(unittest.TestCase):
    @staticmethod
    def finished(variance, covariances):
        return {
            "variance": variance,
            "sigma": np.sqrt(variance),
            "covariance": dict(zip(oracle.AXES, covariances)),
            **{
                axis: covariance / variance
                for axis, covariance in zip(oracle.AXES, covariances)
            },
        }

    def test_subtraction_uses_covariance_not_correlation(self):
        base = self.finished(4.0, (3.2, 3.2, 2.0, 2.0))
        missing = self.finished(9.0, (1.8, 1.8, -0.9, -0.9))
        source = self.finished(
            13.0,
            tuple(base["covariance"][axis] + missing["covariance"][axis]
                  for axis in oracle.AXES))
        target = oracle.subtract_axis_moments(source, base)
        self.assertTrue(target["valid"])
        self.assertAlmostEqual(target["variance"], 9.0)
        self.assertAlmostEqual(target["lag1"], 0.2)
        self.assertAlmostEqual(target["lag2"], -0.1)

    def test_subtraction_rejects_non_positive_missing_energy(self):
        source = self.finished(4.0, (1.0, 1.0, 0.0, 0.0))
        base = self.finished(5.0, (1.0, 1.0, 0.0, 0.0))
        target = oracle.subtract_axis_moments(source, base)
        self.assertFalse(target["valid"])
        self.assertIn("variance", target["reason"])

    def test_mixture_closes_source_covariance(self):
        base = self.finished(4.0, (3.2, 3.2, 2.0, 2.0))
        target = {
            "valid": True,
            "variance": 9.0,
            "h1": 0.2, "v1": 0.2, "h2": -0.1, "v2": -0.1,
        }
        source = self.finished(13.0, (5.0, 5.0, 1.1, 1.1))
        mixed = oracle.mix_with_base(base, target, target, source)
        for axis in oracle.AXES:
            self.assertAlmostEqual(mixed[axis], source[axis])
        self.assertAlmostEqual(mixed["sigma_over_source"], 1.0)

    def test_replace_luma_model_preserves_curve_and_chroma(self):
        entry = {
            "params": {"ar_coeff_lag": 2, "ar_coeff_shift": 8,
                       "scaling_shift": 11},
            "scaling_points": {"y": [[0, 5]], "cb": [], "cr": []},
            "ar_coeffs": {"y": [1], "cb": [2], "cr": [3]},
        }
        replaced = oracle.replace_luma_model(entry, {
            "shift": 6,
            "coefficients": list(range(24)),
        })
        self.assertEqual(replaced["params"]["ar_coeff_shift"], 6)
        self.assertEqual(replaced["params"]["scaling_shift"], 11)
        self.assertEqual(replaced["ar_coeffs"]["y"], list(range(24)))
        self.assertEqual(replaced["ar_coeffs"]["cb"], [2])
        self.assertEqual(replaced["scaling_points"], entry["scaling_points"])
        self.assertEqual(entry["ar_coeffs"]["y"], [1])


class ArSystemTests(unittest.TestCase):
    def test_axis_moments_expose_runtime_sparse_tap_ratios(self):
        system = oracle.empty_ar_system()
        system["observations"] = 10
        system["btb"] = 100.0
        taps = oracle.ar_acf.ar_taps(oracle.LAG)
        expected = {
            "h1": 0.4, "v1": 0.3, "h2": -0.2, "v2": -0.1,
        }
        for axis, value in expected.items():
            system["atb"][taps.index(oracle.AXIS_TAPS[axis])] = value * 100.0
        result = oracle.ar_system_axis_moments(system)
        self.assertTrue(result["valid"])
        self.assertEqual(result["observations"], 10)
        self.assertAlmostEqual(result["variance"], 10.0)
        for axis, value in expected.items():
            self.assertAlmostEqual(result[axis], value)

    def test_sample_hash_and_strata_match_frozen_cuda_values(self):
        self.assertEqual(oracle.fgs_sample_hash(0), 0)
        self.assertEqual(oracle.fgs_sample_hash(1), 1753845952)
        self.assertEqual(oracle.fgs_sample_hash(63), 3550727198)
        self.assertEqual(
            oracle.fgs_stratified_sample_offset(32, 3, 3, 0, 0), 3)
        self.assertEqual(
            oracle.fgs_stratified_sample_offset(32, 3, 3, 7, 0), 25)

    def test_cuda64_accumulates_exactly_one_observation_per_thread(self):
        y, x = np.mgrid[:32, :32]
        previous = np.zeros((32, 32), dtype=np.uint16)
        current = (100 + x * 2 + y * 3 + ((x * y) % 17)).astype(np.uint16)
        system = oracle.empty_ar_system()
        oracle.accumulate_ar_system_cuda64(
            system, current, previous, [(0, 0)])
        self.assertEqual(system["observations"], 64)
        self.assertGreater(system["btb"], 0.0)
        np.testing.assert_allclose(system["ata"], system["ata"].T)

    def test_identical_system_subtraction_has_no_energy(self):
        source = oracle.empty_ar_system()
        source["ata"] += np.eye(source["ata"].shape[0])
        source["atb"] += 1.0
        source["btb"] = 10.0
        source["observations"] = 20
        target = oracle.subtract_ar_system(source, source)
        solved = oracle.solve_covariance_system(target)
        self.assertFalse(solved["valid"])

    def test_covariance_weight_interpolates_source_and_difference(self):
        source = oracle.empty_ar_system()
        base = oracle.empty_ar_system()
        source["ata"] += np.eye(source["ata"].shape[0]) * 10.0
        source["atb"] += 4.0
        source["btb"] = 100.0
        source["observations"] = 20
        base["ata"] += np.eye(base["ata"].shape[0]) * 2.0
        base["atb"] += 1.0
        base["btb"] = 20.0
        base["observations"] = 20
        half = oracle.covariance_difference_system(source, base, 0.5)
        np.testing.assert_allclose(
            half["ata"], source["ata"] - 0.5 * base["ata"])
        np.testing.assert_allclose(
            half["atb"], source["atb"] - 0.5 * base["atb"])
        self.assertEqual(half["btb"], 90.0)
        with self.assertRaises(ValueError):
            oracle.covariance_difference_system(source, base, 1.1)

    def test_quantized_oracle_rejects_coefficients_outside_int8(self):
        coefficients = np.zeros(len(oracle.ar_acf.ar_taps(oracle.LAG)))
        coefficients[0] = 2.1
        target = {axis: 0.0 for axis in oracle.AXES}
        rows, best = oracle.quantized_oracles(
            coefficients, target, bit_depth=10, seeds=2, sigma=1.0)
        self.assertTrue(all(not row["feasible"] for row in rows))
        self.assertIsNone(best)


if __name__ == "__main__":
    unittest.main()
