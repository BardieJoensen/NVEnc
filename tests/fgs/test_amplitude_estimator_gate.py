import math
import unittest

import amplitude_estimator_gate as gate


class AmplitudeEstimatorGateTests(unittest.TestCase):
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

    def test_error_summary_keeps_equal_band_and_weighted_views(self):
        records = [
            {"candidate": 0.9, "true_target": 1.0, "weight": 1.0},
            {"candidate": 1.0, "true_target": 0.8, "weight": 3.0},
        ]
        result = gate.error_summary(records, "candidate")
        self.assertEqual(result["bands"], 2)
        self.assertAlmostEqual(result["bias"], 0.05)
        self.assertAlmostEqual(result["mae"], 0.15)
        self.assertAlmostEqual(
            result["weighted_rmse"], math.sqrt((0.01 + 3.0 * 0.04) / 4.0))


if __name__ == "__main__":
    unittest.main()
