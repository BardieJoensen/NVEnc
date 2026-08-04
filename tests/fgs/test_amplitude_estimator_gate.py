import math
import unittest

import amplitude_estimator_gate as gate


class AmplitudeEstimatorGateTests(unittest.TestCase):
    def test_plane_selection_is_explicit_and_validated(self):
        self.assertEqual(gate.parse_planes("u,v"), ("u", "v"))
        with self.assertRaises(ValueError):
            gate.parse_planes("")
        with self.assertRaises(ValueError):
            gate.parse_planes("y,x")
        with self.assertRaises(ValueError):
            gate.parse_planes("u,u")

    def test_synthesis_target_applies_amplitude_deadzone(self):
        self.assertAlmostEqual(
            gate.synthesis_target(0.5, 0.1), math.sqrt(1.0 - 0.4 ** 2))
        self.assertEqual(gate.synthesis_target(0.05, 0.1), 1.0)

    def test_deadzone_fit_recovers_shared_transfer(self):
        records = [
            {"pre_leak": pre, "post_leak": pre - 0.12, "weight": weight}
            for pre, weight in ((0.3, 1.0), (0.5, 4.0), (0.7, 2.0))
        ]
        self.assertAlmostEqual(gate.fit_deadzone(records), 0.12, places=4)

    def test_rate_fit_recovers_linear_plane_transfer(self):
        records = []
        for qvbr, theta in ((25.0, 0.20), (35.0, 0.30)):
            records.extend({
                "qvbr": qvbr,
                "pre_leak": pre,
                "post_leak": max(0.0, pre - theta),
                "weight": 1.0,
            } for pre in (0.4, 0.6))
        model = gate.fit_rate_deadzone(records)
        self.assertAlmostEqual(model["intercept"], -0.05, places=3)
        self.assertAlmostEqual(model["slope"], 0.01, places=4)
        self.assertAlmostEqual(gate.rate_theta(model, 30.0), 0.25, places=3)

    def test_error_summary_keeps_equal_band_and_weighted_views(self):
        records = [
            {"candidate": 0.9, "true_target": 1.0, "weight": 1.0,
             "truth_sigma_8bit": 2.0},
            {"candidate": 1.0, "true_target": 0.8, "weight": 3.0,
             "truth_sigma_8bit": 0.5},
        ]
        result = gate.error_summary(records, "candidate")
        self.assertEqual(result["bands"], 2)
        self.assertAlmostEqual(result["bias"], 0.05)
        self.assertAlmostEqual(result["mae"], 0.15)
        self.assertAlmostEqual(
            result["weighted_rmse"], math.sqrt((0.01 + 3.0 * 0.04) / 4.0))
        self.assertAlmostEqual(result["sigma8_mae"], 0.15)
        self.assertAlmostEqual(result["sigma8_max"], 0.2)


if __name__ == "__main__":
    unittest.main()
