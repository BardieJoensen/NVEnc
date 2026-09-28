import unittest

import numpy as np

from component_population_reference import diagnose_component, diagnose_selected_component
from test_component_population import prepared
from test_aligned_population import scene


def stationary(depth=8, seed=8227):
    rng = np.random.default_rng(seed)
    source, clean = [], []
    scale = 1 << (depth-8)
    for c in range(3):
        y, x = np.indices((256, 256) if c else (512, 512))
        pattern = np.rint((100+8*np.sin(x/17)+5*np.cos(y/13))*scale)
        clean.append(np.broadcast_to(pattern, (8, *pattern.shape)).astype(np.uint16))
        source.append(np.rint(clean[-1]+rng.normal(0, 2*scale, clean[-1].shape)).astype(np.uint16))
    return source, clean


def choice(result):
    r = result['registration']
    return {k: r[k] for k in ('dx', 'dy', 'source_model', 'training_mse',
            'training_zero_mse', 'training_shifted_mse', 'training_improvement',
            'training_correlation', 'proposal_dx', 'proposal_dy')}


class ComponentSelectionTests(unittest.TestCase):
    def test_noise_does_not_require_a_spurious_translation(self):
        source, clean = stationary()
        p = prepared(source, [s[-1] for s in clean])
        old = diagnose_component(p, 0, 192, 192)
        result = diagnose_selected_component(p, 0, 192, 192)
        self.assertEqual(old['reason'], 'motion_not_independently_supported')
        self.assertEqual(result['registration']['source_model'], 'stationary')
        self.assertTrue(result['registration_supported'])
        self.assertFalse(result['evidence']['conflicts'])
        self.assertFalse(result['persistent_detail_conflict'])
        noise = (source[0][-1, 192:256, 192:256].astype(float)
                 - clean[0][-1, 192:256, 192:256])
        expected = np.var(noise, ddof=1)
        self.assertLessEqual(abs(result['evidence']['source_residual_variance']-expected), .08*expected)
        for key in ('source_admission', 'detail_admission', 'joint_admission'):
            self.assertFalse(result[key])

    def test_qualified_motion_still_uses_native_translation(self):
        source, clean = scene(sigma=2.)
        p = prepared(source, [s[-1] for s in clean])
        for c in range(3):
            pos = 96 if c else 192
            old = diagnose_component(p, c, pos, pos)
            new = diagnose_selected_component(p, c, pos, pos)
            self.assertEqual(new['registration']['source_model'], 'translation')
            self.assertTrue(new['registration_supported'])
            self.assertEqual(new['history_coordinates'], old['history_coordinates'])
            self.assertEqual(new['evidence'], old['evidence'])
            self.assertEqual(new['persistent'], old['persistent'])

    def test_candidate_and_other_components_cannot_select_source_model(self):
        source, clean = stationary()
        a = diagnose_selected_component(prepared(source, [s[-1] for s in clean]), 0, 192, 192)
        source[1][:] = 128
        source[2][:] = 128
        b = diagnose_selected_component(prepared(source, [s[-1] for s in source]), 0, 192, 192)
        self.assertEqual(choice(a), choice(b))
        self.assertEqual(a['aligned_native_sha256'], b['aligned_native_sha256'])
        self.assertEqual(a['stationary_consistency'], b['stationary_consistency'])
        self.assertNotEqual(a['candidate_native_sha256'], b['candidate_native_sha256'])

    def test_slow_source_change_cannot_masquerade_as_extra_grain(self):
        source, clean = stationary(seed=927670)
        for c in range(3):
            noise = source[c].astype(np.int32)-clean[c]
            for t in range(8):
                clean[c][t] = np.roll(clean[c][t], t, axis=1)
            source[c] = (clean[c].astype(np.int32)+noise).astype(np.uint16)
        result = diagnose_selected_component(prepared(source, [s[-1] for s in clean]), 0, 192, 192)
        self.assertEqual(result['registration']['source_model'], 'stationary')
        self.assertTrue(result['registration_supported'])
        self.assertIn('stationary_and_linear_predictions_disagree', result['evidence']['conflicts'])
        # Independent matrix least-squares calculation, not the implementation's
        # closed-form coefficients. Both histories exclude the current frame.
        pixels = source[0][:, 192:256, 192:256].astype(float)
        predicted = []
        for ids in ([0, 2, 4, 6], [1, 3, 5]):
            design = np.column_stack((np.ones(len(ids)), ids))
            coefficients = np.linalg.lstsq(design, pixels[ids].reshape(len(ids), -1), rcond=None)[0]
            predicted.append((np.array([1., 7.]) @ coefficients).reshape(64, 64))
        a, b = pixels[-1]-predicted[0], pixels[-1]-predicted[1]
        expected = float(np.sum((a-a.mean())*(b-b.mean()))/(a.size-1))
        actual = result['stationary_consistency']
        self.assertAlmostEqual(actual['linear_residual_variance'], expected, places=11)
        self.assertEqual(actual['constant_residual_variance'], result['evidence']['source_residual_variance'])
        self.assertFalse(actual['within_limits'])

    def test_validation_can_reject_but_never_reselect(self):
        source, clean = scene(sigma=2.)
        before = diagnose_selected_component(prepared(source, [s[-1] for s in clean]), 0, 192, 192)
        reverse, _ = scene(-7, sigma=2.)
        source[0][4:] = reverse[0][4:]
        after = diagnose_selected_component(prepared(source, [s[-1] for s in source]), 0, 192, 192)
        self.assertEqual(choice(before), choice(after))
        self.assertEqual(after['registration']['source_model'], 'translation')
        self.assertFalse(after['registration_supported'])
        self.assertEqual(after['reason'], 'motion_not_independently_supported')
        self.assertEqual(after['registration']['validation_searches'], 0)

        source, clean = stationary()
        before = diagnose_selected_component(prepared(source, [s[-1] for s in clean]), 0, 192, 192)
        source[0][4:] = reverse[0][4:]
        after = diagnose_selected_component(prepared(source, [s[-1] for s in source]), 0, 192, 192)
        self.assertEqual(choice(before), choice(after))
        self.assertFalse(after['registration_supported'] and not after['evidence']['conflicts'])

    def test_visible_border_has_exact_samples_and_independent_moments(self):
        source, clean = scene(0, sigma=2.)
        # Both axes end inside a canonical tile; no crop, padding or wrap.
        source = [s[:, :255, :254] if c else s[:, :510, :508] for c, s in enumerate(source)]
        clean = [s[:, :255, :254] if c else s[:, :510, :508] for c, s in enumerate(clean)]
        p = prepared(source, [s[-1] for s in clean])
        for c in range(3):
            pos = 224 if c else 448
            old = diagnose_component(p, c, pos, pos)
            self.assertEqual(old['reason'], 'partial_current_border')
            result = diagnose_selected_component(p, c, pos, pos)
            self.assertTrue(result['registration_supported'])
            pixels = source[c][:, pos:, pos:].astype(float)
            first, second = pixels[:3].mean(axis=0), pixels[3:7].mean(axis=0)
            a, b = pixels[-1]-first, pixels[-1]-second
            expected = sum((x-a.mean())*(y-b.mean()) for x, y in zip(a.ravel(), b.ravel()))/(a.size-1)
            self.assertAlmostEqual(result['evidence']['source_residual_variance'], expected, places=11)
            self.assertEqual(result['evidence']['samples'], pixels[0].size)
            self.assertEqual(result['history_coordinates'],
                [[pos, pos, pixels.shape[2], pixels.shape[1]]]*8)

    def test_small_border_or_missing_shifted_history_remains_unknown(self):
        source, _ = scene(7)
        result = diagnose_selected_component(prepared(source, [s[-1] for s in source]), 0, 64, 192)
        self.assertEqual(result['reason'], 'insufficient_full_history_overlap')
        # One chroma pixel at a doubly partial border cannot supply a variance.
        source = [np.pad(s, ((0, 0), (0, 1 if c else 2), (0, 1 if c else 2)), mode='edge')
                  for c, s in enumerate(source)]
        result = diagnose_selected_component(prepared(source, [s[-1] for s in source]), 1, 256, 256)
        self.assertEqual(result['reason'], 'insufficient_visible_support')
        self.assertIsNone(result['evidence'])

    def test_flat_noise_and_removed_persistent_rows_are_not_admitted(self):
        source, clean = scene(0, sigma=2.)
        lines = np.where(np.arange(512) % 2, 16, -16)[None, :, None]
        source[0] = (source[0].astype(np.int32)+lines).astype(np.uint16)
        result = diagnose_selected_component(prepared(source, [s[-1] for s in clean]), 0, 192, 192)
        self.assertTrue(result['registration_supported'])
        self.assertTrue(result['persistent_detail_conflict'])
        rng = np.random.default_rng(8229)
        for s in source:
            s[:] = np.rint(128+rng.normal(0, 2, s.shape)).astype(np.uint16)
        result = diagnose_selected_component(prepared(source, [s[-1] for s in source]), 0, 192, 192)
        self.assertFalse(result['registration_supported'])
        self.assertEqual(result['reason'], 'stationary_source_anchors_missing')

    def test_depth_normalization_and_immutable_context(self):
        source, clean = stationary()
        p = prepared(source, [s[-1] for s in clean])
        a = diagnose_selected_component(p, 0, 192, 192)
        b = diagnose_selected_component(prepared([s*4 for s in source], [s[-1]*4 for s in clean], 10), 0, 192, 192)
        self.assertEqual(choice(a), choice(b))
        self.assertEqual(a['evidence'], b['evidence'])
        source[0][:] = 0
        self.assertEqual(a, diagnose_selected_component(p, 0, 192, 192))


if __name__ == '__main__':
    unittest.main()
