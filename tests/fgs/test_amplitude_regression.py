import unittest

import numpy as np

from amplitude_regression import FRAMES, assess


class AmplitudeRegressionTest(unittest.TestCase):
    def setUp(self):
        y, x = np.indices((64, 96))
        picture = (40 + x + y / 2).astype(np.float32)
        self.source = np.repeat(picture[None, :, :], FRAMES, axis=0)

    def test_excessive_grain_rejected_without_flat_source_patches(self):
        # Every 16x16 block contains real structure. The old flat-patch-only
        # criterion has no witness, while the full-picture mismatch is severe.
        tiles = self.source[0].reshape(4, 16, 6, 16).transpose(0, 2, 1, 3)
        self.assertGreater(tiles.std(axis=(-2, -1)).min(), .3)
        noise = np.random.default_rng(20260916).normal(0, 10, self.source.shape).astype(np.float32)
        self.assertFalse(assess(self.source, self.source + noise, self.source, self.source)["passed"])

    def test_small_compression_difference_keeps_positive_control(self):
        noise = np.random.default_rng(7).normal(0, .5, self.source.shape).astype(np.float32)
        self.assertTrue(assess(self.source, self.source + noise, self.source + noise, self.source + noise)["passed"])

    def test_missing_frame_or_invalid_pixel_is_not_clearance(self):
        with self.assertRaises(ValueError):
            assess(self.source, self.source[:-1], self.source[:-1], self.source)
        invalid = self.source.copy()
        invalid[7, 4, 5] = np.nan
        with self.assertRaises(ValueError):
            assess(self.source, invalid, self.source, self.source)

    def test_wrong_picture_without_synthesis_is_rejected(self):
        wrong = self.source + 15
        self.assertFalse(assess(self.source, wrong, wrong, self.source)["passed"])

    def test_plain_compression_is_not_classified_as_added_grain(self):
        reference = self.source + 5
        result = assess(self.source, reference, reference, reference)
        self.assertTrue(result['passed'])
        self.assertFalse(result['provisional_absolute_source_check']['candidate_passed'])
        self.assertFalse(result['provisional_absolute_source_check']['reference_passed'])

    def test_new_source_loss_without_synthesis_still_fails(self):
        reference = self.source + 5
        wrong = self.source + 6
        result = assess(self.source, wrong, wrong, reference)
        self.assertTrue(result['synthesis_passed'])
        self.assertFalse(result['source_comparison_passed'])
        self.assertFalse(result['passed'])

    def test_small_persistent_error_is_not_hidden_by_peak_margin(self):
        reference = self.source + 5
        wrong = self.source + 5.1
        self.assertFalse(assess(self.source, wrong, wrong, reference)['passed'])


if __name__ == "__main__":
    unittest.main()
