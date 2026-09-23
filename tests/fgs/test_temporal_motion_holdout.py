import unittest
import numpy as np
from temporal_motion_holdout_reference import diagnose
from temporal_stationarity_reference import diagnose as in_sample_diagnose


class MotionHoldoutTests(unittest.TestCase):
    def call(self, source, depth=8):
        return diagnose(source, source[-1], depth, list(range(8)), list(range(8)))

    def test_known_translation_generalizes_to_held_out_pairs(self):
        rng = np.random.default_rng(9392)
        picture = rng.uniform(100, 156, (3, 32, 32))
        source = np.array([np.roll(picture, t, axis=-1) for t in range(8)])
        r = self.call(source); m = r['held_out_motion']
        np.testing.assert_array_equal(m['proposed_offset'], [[0, -1]]*3)
        np.testing.assert_array_equal(m['validation_proposed_mse'], 0)
        for c in r['conflicts']: self.assertIn('held_out_translation_evidence', c)
        self.assertFalse(r['population_acceptance'])

    def test_validation_cannot_select_the_motion_proposal(self):
        rng = np.random.default_rng(19239)
        source = rng.uniform(100, 156, (8, 3, 32, 32))
        a = self.call(source)['held_out_motion']
        source[4:] = rng.uniform(32, 224, (4, 3, 32, 32))
        b = self.call(source)['held_out_motion']
        np.testing.assert_array_equal(a['proposed_offset'], b['proposed_offset'])
        np.testing.assert_array_equal(a['training_mse'], b['training_mse'])
        self.assertEqual(b['validation_searches'], 0)

    def test_incorrect_motion_is_not_refit_or_clipped_on_validation(self):
        rng = np.random.default_rng(3323)
        picture = rng.uniform(100, 156, (3, 32, 32))
        moving = np.array([np.roll(picture, t, axis=-1) for t in range(8)])
        # The training motion reverses later. Validation must not refit it.
        moving[4:] = np.array([np.roll(picture, -t, axis=-1) for t in range(4)])
        r = self.call(moving); m = r['held_out_motion']
        np.testing.assert_array_equal(m['proposed_offset'], [[0, -1]]*3)
        self.assertTrue(np.any(m['validation_improvement'] < 0))
        for c in r['conflicts']: self.assertNotIn('held_out_translation_evidence', c)

    def test_scalar_validation_and_native_depth(self):
        rng = np.random.default_rng(923044)
        source = rng.uniform(96, 160, (8, 3, 32, 32))
        a = self.call(source)['held_out_motion']; b = self.call(source*4, 10)['held_out_motion']
        for key in a: np.testing.assert_allclose(a[key], b[key], atol=1e-12)
        c = 1; dy, dx = a['proposed_offset'][c]
        def sample(t, y, x):
            return sum(source[t, c, y+j, x+i]*wy*wx
                       for j, wy in zip((-1, 0, 1), (1, 2, 1))
                       for i, wx in zip((-1, 0, 1), (1, 2, 1)))/16
        expected = sum((sample(7, y, x)-sample(6, y+dy, x+dx))**2
                       for y in range(5, 27, 2) for x in range(5, 27, 2))/121
        self.assertAlmostEqual(expected, a['validation_proposed_mse'][c, 1], places=11)

    def test_quiet_ties_and_missing_history(self):
        source = np.full((8, 3, 32, 32), 128)
        m = self.call(source)['held_out_motion']
        np.testing.assert_array_equal(m['proposed_offset'], 0)
        np.testing.assert_array_equal(m['validation_improvement'], 0)
        np.testing.assert_array_equal(m['validation_relative_defined'], False)
        with self.assertRaises(ValueError): self.call(source[:-1])

    def test_zero_validation_denominator_retains_absolute_failure(self):
        rng = np.random.default_rng(29812)
        picture = rng.uniform(100, 156, (3, 32, 32))
        source = np.array([np.roll(picture, t, axis=-1) for t in range(8)])
        source[4:] = picture
        r = self.call(source); m = r['held_out_motion']
        np.testing.assert_array_equal(m['proposed_offset'], [[0, -1]]*3)
        np.testing.assert_array_equal(m['validation_relative_defined'], False)
        self.assertTrue(np.all(m['validation_proposed_mse'] > 0))
        for c in r['conflicts']: self.assertNotIn('held_out_translation_evidence', c)

    def test_flat_independent_grain_does_not_reuse_spurious_matches(self):
        rng = np.random.default_rng(923100)
        source = np.floor(128+rng.normal(0, 2, (8, 3, 32, 32))+.5)
        old = in_sample_diagnose(source, source[-1], 8, list(range(8)), list(range(8)))
        self.assertTrue(any('small_translation_evidence' in c for c in old['conflicts']))
        r = self.call(source)
        self.assertTrue(all(not c for c in r['conflicts']))
        self.assertFalse(r['population_acceptance'])


if __name__ == '__main__': unittest.main()
