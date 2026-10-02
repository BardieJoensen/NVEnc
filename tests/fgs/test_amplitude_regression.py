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

    def test_independent_source_supported_grain_is_not_pixel_loss(self):
        # The same stationary picture and two independent noise realizations.
        # This is exactly the distinction a grain-synthesis check must make;
        # no encoder-produced positive or release candidate is used here.
        shape = (FRAMES, 256, 256)
        clean = np.full(shape, 80, dtype=np.float32)
        rng = np.random.default_rng(431)
        source = clean + rng.normal(0, .8, shape).astype(np.float32)
        restored = clean + rng.normal(0, .8, shape).astype(np.float32)
        result = assess(source, restored, clean, clean)
        self.assertFalse(result['legacy_pixelwise_on_check']['passed'])
        self.assertTrue(result['passed'])

    def test_grain_on_a_clean_source_is_rejected_below_absolute_cap(self):
        clean = np.full((FRAMES, 256, 256), 80, dtype=np.float32)
        noisy = clean + np.random.default_rng(433).normal(0, .8, clean.shape).astype(np.float32)
        result = assess(clean, noisy, clean, clean)
        self.assertTrue(result['synthesis_passed'])
        self.assertFalse(result['source_texture_check']['passed'])
        self.assertFalse(result['passed'])

    def test_too_much_grain_on_a_noisy_source_is_rejected(self):
        clean = np.full((FRAMES, 256, 256), 80, dtype=np.float32)
        rng = np.random.default_rng(439)
        source = clean + rng.normal(0, .8, clean.shape).astype(np.float32)
        noisy = clean + rng.normal(0, 1.8, clean.shape).astype(np.float32)
        result = assess(source, noisy, clean, clean)
        self.assertTrue(result['synthesis_passed'])
        self.assertFalse(result['source_texture_check']['passed'])
        self.assertFalse(result['passed'])

    def test_axial_stripes_cannot_hide_between_diagonal_and_coarse_checks(self):
        clean = np.full((FRAMES, 64, 64), 80, dtype=np.float32)
        y, x = np.indices(clean.shape[1:])
        # Every width and phase has zero mean inside the coarse 8x8 check.
        # Width 2/4 stripes can also be invisible to a native 2x2 Haar check.
        for direction, axis in (("horizontal", y), ("vertical", x)):
            for width in (1, 2, 4):
                for phase in range(2*width):
                    with self.subTest(direction=direction, width=width, phase=phase):
                        overlay = np.where(((axis+phase)//width) % 2, .8, -.8).astype(np.float32)
                        result = assess(clean, clean + overlay, clean, clean)
                        self.assertTrue(result['base_source_check']['passed'])
                        self.assertTrue(result['displayed_coarse_source_check']['passed'])
                        self.assertTrue(result['synthesis_passed'])
                        bands = result['source_texture_check']['bands']
                        self.assertTrue(bands['2px_diagonal']['passed'])
                        self.assertTrue(any(not band['passed'] for name, band in bands.items()
                                            if name.endswith(direction)))
                        self.assertFalse(result['passed'])

    def test_checkerboards_exercise_each_diagonal_scale(self):
        clean = np.full((FRAMES, 64, 64), 80, dtype=np.float32)
        y, x = np.indices(clean.shape[1:])
        for width in (1, 2, 4):
            with self.subTest(width=width):
                overlay = np.where((y//width + x//width) % 2, .8, -.8).astype(np.float32)
                result = assess(clean, clean + overlay, clean, clean)
                self.assertTrue(result['base_source_check']['passed'])
                self.assertTrue(result['displayed_coarse_source_check']['passed'])
                self.assertTrue(result['synthesis_passed'])
                bands = result['source_texture_check']['bands']
                self.assertEqual([name for name, band in bands.items() if not band['passed']],
                                 [f'{2*width}px_diagonal'])
                self.assertFalse(result['passed'])

    def test_directional_excess_cannot_cancel_against_missing_other_texture(self):
        clean = np.full((FRAMES, 64, 64), 80, dtype=np.float32)
        y, x = np.indices(clean.shape[1:])
        source = clean + np.where(y % 2, .8, -.8).astype(np.float32)
        wrong = clean + np.where(x % 2, .8, -.8).astype(np.float32)
        result = assess(source, wrong, clean, clean)
        self.assertTrue(result['base_source_check']['passed'])
        self.assertTrue(result['displayed_coarse_source_check']['passed'])
        self.assertFalse(result['source_texture_check']['bands']['2px_vertical']['passed'])
        self.assertFalse(result['passed'])

    def test_coarse_overlay_cannot_hide_in_a_correct_base(self):
        clean = np.full((FRAMES, 256, 256), 80, dtype=np.float32)
        y, x = np.indices((256, 256))
        overlay = np.where((x//32+y//32) % 2, .8, -.8).astype(np.float32)
        result = assess(clean, clean + overlay, clean, clean)
        self.assertTrue(result['base_source_check']['passed'])
        self.assertTrue(result['synthesis_passed'])
        self.assertFalse(result['displayed_coarse_source_check']['passed'])
        self.assertFalse(result['passed'])

    def test_new_blur_cannot_hide_behind_grain(self):
        rng = np.random.default_rng(443)
        y, x = np.indices((256, 256))
        picture = (80 + 2*((x//2) % 2)).astype(np.float32)
        source = np.repeat(picture[None], FRAMES, axis=0)
        blurred = np.full(source.shape, 81, dtype=np.float32)
        noisy = blurred + rng.normal(0, .8, source.shape).astype(np.float32)
        result = assess(source, noisy, blurred, source)
        self.assertFalse(result['base_source_check']['passed'])
        self.assertFalse(result['passed'])

    def test_no_source_texture_coverage_is_not_synthesis_clearance(self):
        noise = np.random.default_rng(449).normal(0, .05, self.source.shape).astype(np.float32)
        result = assess(self.source, self.source + noise, self.source, self.source)
        self.assertTrue(result['synthesis_passed'])
        self.assertEqual(max(result['source_texture_check']['source_flat_tile_counts']), 0)
        self.assertFalse(result['source_texture_check']['passed'])
        self.assertFalse(result['passed'])


if __name__ == "__main__":
    unittest.main()
