#!/usr/bin/env python3
"""CPU tests for the texture model-acceptance gate.  No GPU, no media.

The media-backed assertions live in the tier-2 local gate, which runs the real
Taxi Driver source against the labelled adversarial specimen.  What is checked
here is the part that can be checked without either: that the descriptors are
amplitude-independent, and that the gate's asymmetry actually holds -- gated
descriptors may only help a candidate, held-out descriptors may only veto it.
"""

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model_gate


def distance_dict(spectrum_tv, acf_rmse, anisotropy, diagonal):
    return {
        "gated": {"spectrum_tv": spectrum_tv, "acf_rmse": acf_rmse},
        "held_out": {"anisotropy_abs": anisotropy,
                     "diagonal_acf_lag1_abs": diagonal},
    }


class DescriptorTest(unittest.TestCase):
    def test_descriptors_ignore_amplitude(self):
        rng = np.random.default_rng(3)
        patches = rng.normal(size=(16, 32, 32))
        quiet = model_gate.describe(patches)
        loud = model_gate.describe(patches * 37.0)
        self.assertAlmostEqual(quiet["anisotropy"], loud["anisotropy"], places=9)
        self.assertAlmostEqual(quiet["diagonal_acf_lag1"],
                               loud["diagonal_acf_lag1"], places=9)
        for left, right in zip(quiet["acf"], loud["acf"]):
            self.assertAlmostEqual(left, right, places=9)
        for left, right in zip(quiet["radial_spectrum"],
                               loud["radial_spectrum"]):
            self.assertAlmostEqual(left, right, places=9)

    def test_white_noise_is_uncorrelated_on_every_axis(self):
        rng = np.random.default_rng(11)
        described = model_gate.describe(rng.normal(size=(64, 32, 32)))
        self.assertLess(abs(described["acf"][0]), 0.03)
        self.assertLess(abs(described["diagonal_acf_lag1"]), 0.03)

    def test_ar_synthesis_produces_correlated_grain(self):
        # One strong horizontal tap must show up as horizontal correlation and
        # must not be invisible to the diagonal descriptor either.
        coefficients = np.zeros(len(model_gate.AR_TAPS))
        coefficients[model_gate.AR_TAPS.index((0, -1))] = 0.7
        rng = np.random.default_rng(5)
        grain = model_gate.synthesize(coefficients, 24, rng)
        described = model_gate.describe(grain)
        self.assertGreater(described["acf"][0], 0.2)
        self.assertGreater(described["acf"][0], described["acf"][1])

    def test_synthesis_rejects_wrong_coefficient_count(self):
        rng = np.random.default_rng(1)
        with self.assertRaises(model_gate.ModelGateError):
            model_gate.synthesize(np.zeros(5), 2, rng)


class GateTest(unittest.TestCase):
    def test_rejects_a_gated_improvement_that_regresses_held_out(self):
        """The adversarial specimen, in distance form.

        This is the whole reason the module exists: 3x better on the
        descriptors it was fitted against, worse on the ones it was not.
        """
        incumbent = distance_dict(0.0550, 0.0376, 0.0076, 0.0021)
        candidate = distance_dict(0.0204, 0.0102, 0.0166, 0.0295)
        result = model_gate.evaluate(candidate, incumbent)
        self.assertEqual(result["verdict"], "REJECT")
        self.assertEqual(result["vetoes"],
                         ["anisotropy_abs", "diagonal_acf_lag1_abs"])
        self.assertEqual(result["gated_improvements"],
                         ["acf_rmse", "spectrum_tv"])
        self.assertIn("rejected anyway", result["reason"])

    def test_accepts_an_improvement_with_no_held_out_regression(self):
        incumbent = distance_dict(0.0550, 0.0376, 0.0076, 0.0021)
        candidate = distance_dict(0.0400, 0.0300, 0.0070, 0.0020)
        result = model_gate.evaluate(candidate, incumbent)
        self.assertEqual(result["verdict"], "ACCEPT")
        self.assertEqual(result["vetoes"], [])

    def test_a_single_held_out_regression_is_enough_to_veto(self):
        incumbent = distance_dict(0.0550, 0.0376, 0.0076, 0.0021)
        candidate = distance_dict(0.0100, 0.0100, 0.0070, 0.0295)
        result = model_gate.evaluate(candidate, incumbent)
        self.assertEqual(result["verdict"], "REJECT")
        self.assertEqual(result["vetoes"], ["diagonal_acf_lag1_abs"])

    def test_identical_models_are_accepted(self):
        same = distance_dict(0.0550, 0.0376, 0.0076, 0.0021)
        result = model_gate.evaluate(dict(same), same)
        self.assertEqual(result["verdict"], "ACCEPT")
        self.assertEqual(result["gated_improvements"], [])

    def test_floor_protects_a_near_zero_incumbent_distance(self):
        # Without the absolute floor, an incumbent that happens to sit at
        # 1e-9 would veto every candidate on ratio alone.
        incumbent = distance_dict(0.0550, 0.0376, 1e-9, 1e-9)
        candidate = distance_dict(0.0400, 0.0300, 0.0040, 0.0040)
        result = model_gate.evaluate(candidate, incumbent)
        self.assertEqual(result["verdict"], "ACCEPT")

    def test_floor_does_not_swallow_a_real_regression(self):
        incumbent = distance_dict(0.0550, 0.0376, 1e-9, 1e-9)
        candidate = distance_dict(0.0400, 0.0300, 0.0400, 0.0400)
        result = model_gate.evaluate(candidate, incumbent)
        self.assertEqual(result["verdict"], "REJECT")

    def test_malformed_distances_are_an_error(self):
        with self.assertRaises(model_gate.ModelGateError):
            model_gate.evaluate({"gated": {}}, distance_dict(0, 0, 0, 0))


class ModelLoadingTest(unittest.TestCase):
    TABLE = (
        "filmgrn1\n"
        "E 0 10010000 1 12345 1\n"
        "p 3 7 0 11 0 1 128 192 256 128 192 256\n"
        "sY 2 0 31 255 12\n"
        "sCb 0\n"
        "sCr 0\n"
        "cY 2 -7 -1 4 8 -2 -4 -7 3 17 -36 -27 4 4 -1 24 -79 97 19 -9 -7 8 -54 107\n"
        # lag 3 -> 24 luma taps and 25 chroma taps (the extra one is the
        # averaged-luma predictor); the parser enforces both counts.
        "cCb " + " ".join(["0"] * 25) + "\n"
        "cCr " + " ".join(["0"] * 25) + "\n"
    )

    def test_table_coefficients_are_rescaled_by_ar_coeff_shift(self):
        import tempfile
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".tbl", delete=False)
        try:
            handle.write(self.TABLE)
            handle.close()
            coefficients, _ = model_gate.load_model(handle.name)
        finally:
            os.unlink(handle.name)
        self.assertEqual(len(coefficients), len(model_gate.AR_TAPS))
        # ar_coeff_shift 7 -> divide the stored integers by 128. Skipping this
        # would synthesise from coefficients ~128x too large.
        self.assertAlmostEqual(coefficients[0], 2.0 / 128.0)
        self.assertAlmostEqual(coefficients[-1], 107.0 / 128.0)


if __name__ == "__main__":
    unittest.main()
