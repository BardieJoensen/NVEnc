#!/usr/bin/env python3

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import filmgrn


NVENC_STYLE = """filmgrn1
E 0 100 1 12345 1
p 1 8 0 9 0 1 128 192 256 128 192 256
sY 2 0 10 255 20
sCb 0
sCr 0
cY 1 2 3 4
cCb 1 2 3 4 5
cCr -1 -2 -3 -4 -5
"""

AOM_STYLE = """filmgrn1
E 0 9223372036854775807 1 7391 1
\tp 1 8 0 9 0 1 128 192 256 128 192 256
\tsY 2  0 12 255 24
\tsCb 0
\tsCr 0
\tcY 1 2 3 4
\tcCb 1 2 3 4 5
\tcCr -1 -2 -3 -4 -5
"""


class FilmGrainTableTest(unittest.TestCase):
    def test_parses_nvenc_and_aom_whitespace(self):
        nvenc = filmgrn.representative(filmgrn.parse(NVENC_STYLE))
        aom = filmgrn.representative(filmgrn.parse(AOM_STYLE))
        self.assertEqual(nvenc["random_seed"], 12345)
        self.assertEqual(aom["random_seed"], 7391)
        self.assertEqual(aom["scaling_points"]["y"], [[0, 12], [255, 24]])

    def test_compares_effective_scaling(self):
        nvenc = filmgrn.representative(filmgrn.parse(NVENC_STYLE))
        aom = filmgrn.representative(filmgrn.parse(AOM_STYLE))
        comparison = filmgrn.compare(nvenc, aom)
        self.assertAlmostEqual(comparison["scaling"]["y"]["rms_ratio"], 5.0 / 6.0)
        self.assertAlmostEqual(comparison["scaling"]["y"]["relative_rmse"], 1.0 / 6.0)
        self.assertAlmostEqual(comparison["coefficients"]["y"]["cosine"], 1.0)

    def test_rejects_coefficient_count_mismatch(self):
        with self.assertRaises(filmgrn.FilmGrainTableError):
            filmgrn.parse(NVENC_STYLE.replace("cY 1 2 3 4", "cY 1 2 3"))


if __name__ == "__main__":
    unittest.main()
