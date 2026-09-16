import unittest
import numpy as np
from flicker_regression import assess, assess_with_codec_control


class DecodedFlashTests(unittest.TestCase):
    def setUp(self):
        self.source = np.full((8, 48, 48), 128, dtype=np.float32)
        self.patch = (8, 8, 16, 16)

    def test_unchanged_picture_passes(self):
        self.assertTrue(assess(self.source, self.source, self.patch)['passed'])

    def test_one_frame_overlay_fails(self):
        picture = self.source.copy()
        picture[3, 8:24, 8:24] += np.random.default_rng(7).normal(0, 2.7, (16, 16))
        self.assertFalse(assess(self.source, picture, self.patch)['passed'])

    def test_continuous_replacement_noise_also_fails(self):
        picture = self.source + np.random.default_rng(8).normal(0, 2, self.source.shape)
        self.assertFalse(assess(self.source, picture, self.patch)['passed'])

    def test_blank_or_shifted_picture_is_not_a_fix(self):
        self.assertFalse(assess(self.source, np.zeros_like(self.source), self.patch)['passed'])
        self.assertFalse(assess(self.source, self.source + 8, self.patch)['passed'])

    def test_missing_and_misaligned_evidence_rejected(self):
        with self.assertRaises(ValueError):
            assess(self.source, self.source[:1], self.patch)
        source = self.source.copy()
        source[:, 8:16, 8:24] += 10
        with self.assertRaises(ValueError):
            assess(source, source, self.patch)

    def test_nonfinite_data_rejected(self):
        picture = self.source.copy(); picture[0, 0, 0] = np.nan
        with self.assertRaises(ValueError):
            assess(self.source, picture, self.patch)

    def test_codec_control_explains_small_quantization_without_grain(self):
        pattern = np.indices((16, 16)).sum(axis=0) % 2 * 2 - 1
        base, plain = self.source.copy(), self.source.copy()
        base[:, 8:24, 8:24] += pattern * .31
        plain[:, 8:24, 8:24] += pattern * .29
        self.assertFalse(assess(self.source, base, self.patch)['passed'])
        self.assertTrue(assess_with_codec_control(self.source, base, base, plain, self.patch)['passed'])
        overlay = base.copy(); overlay[3, 8:24, 8:24] += pattern * .3
        self.assertFalse(assess_with_codec_control(self.source, overlay, base, plain, self.patch)['passed'])
        worse = base.copy(); worse[3, 8:24, 8:24] += pattern * .2
        self.assertFalse(assess_with_codec_control(self.source, worse, worse, plain, self.patch)['passed'])
        self.assertFalse(assess_with_codec_control(self.source, base+8, base+8, plain, self.patch)['passed'])


if __name__ == '__main__':
    unittest.main()
