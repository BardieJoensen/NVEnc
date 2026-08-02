#!/usr/bin/env python3
import tempfile
import unittest

import numpy as np

import qvbr_leak_fit


class QvbrLeakFitTests(unittest.TestCase):
    def test_deadzone_fit_recovers_theta(self):
        pre = np.asarray([0.20, 0.30, 0.50, 0.80])
        post = np.maximum(0.0, pre - 0.15)
        self.assertAlmostEqual(qvbr_leak_fit.fit_deadzone(pre, post), 0.15)

    def test_target_is_variance_closure(self):
        self.assertAlmostEqual(qvbr_leak_fit.target_from_leak(0.6), 0.8)

    def test_qlookup_parser_and_interpolation(self):
        values = ", ".join(str(index * 8) for index in range(256))
        source = f"static const int16_t ac_qlookup_10_QTX[QINDEX_RANGE] = {{{values}}};"
        with tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8") as handle:
            handle.write(source)
            handle.flush()
            lookup = qvbr_leak_fit.parse_qlookup(handle.name)
        self.assertEqual(qvbr_leak_fit.quantizer_step(12.5, lookup), 12.5)


if __name__ == "__main__":
    unittest.main()
