#!/usr/bin/env python3
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import delivery_jacobian  # noqa: E402


class DeliveryJacobianTests(unittest.TestCase):
    def test_damped_step_solves_identity_response(self):
        raw, bounded = delivery_jacobian.solve_damped_step(
            np.eye(2), np.asarray([0.2, -0.3]),
            regularization=0.0, max_log_step=1.0)
        np.testing.assert_allclose(raw, [0.2, -0.3])
        np.testing.assert_allclose(bounded, raw)

    def test_step_bound_is_applied_after_solve(self):
        raw, bounded = delivery_jacobian.solve_damped_step(
            np.eye(2), np.asarray([2.0, -3.0]),
            regularization=0.0, max_log_step=0.4)
        np.testing.assert_allclose(raw, [2.0, -3.0])
        np.testing.assert_allclose(bounded, [0.4, -0.4])

    def test_regularization_reduces_underdetermined_step(self):
        jacobian = np.asarray([[1.0, 1.0]])
        raw, _bounded = delivery_jacobian.solve_damped_step(
            jacobian, np.asarray([1.0]),
            regularization=1.0, max_log_step=1.0)
        np.testing.assert_allclose(raw, [1.0 / 3.0, 1.0 / 3.0])


if __name__ == "__main__":
    unittest.main()
