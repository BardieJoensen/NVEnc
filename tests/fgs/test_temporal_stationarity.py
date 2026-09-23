import unittest
import numpy as np
from temporal_stationarity_reference import diagnose


class TemporalStationarityTests(unittest.TestCase):
    def setUp(self):
        self.rng = np.random.default_rng(923031)
        self.ids = list(range(8))
        self.clocks = [i/24 for i in self.ids]

    def call(self, source, depth=8):
        return diagnose(source, source[-1], depth, self.ids, self.clocks)

    def test_known_integer_translation_and_zero_noise(self):
        picture = self.rng.uniform(100, 156, (3, 32, 32))
        source = np.array([np.roll(picture, t, axis=-1) for t in range(8)])
        r = self.call(source)
        np.testing.assert_array_equal(r['motion']['offsets'],
                                     np.tile([0, -1], (7, 3, 1)))
        np.testing.assert_array_equal(r['motion']['best_mse'], 0)
        for c in r['conflicts']: self.assertIn('small_translation_evidence', c)
        self.assertFalse(r['population_acceptance'])

    def test_independent_scalar_motion_cost(self):
        source = self.rng.uniform(64, 192, (8, 3, 32, 32))
        r = self.call(source)
        # Scalar oracle with explicit weights/coordinates, not the vector helper.
        def smoothed(t, c, y, x):
            return sum(source[t, c, y+dy, x+dx]*wy*wx
                       for dy, wy in zip((-1, 0, 1), (1, 2, 1))
                       for dx, wx in zip((-1, 0, 1), (1, 2, 1)))/16
        pair, component = 3, 2
        for shifted in (False, True):
            dy, dx = r['motion']['offsets'][pair, component] if shifted else (0, 0)
            expected = sum((smoothed(pair+1, component, y, x)
                            -smoothed(pair, component, y+dy, x+dx))**2
                           for y in range(5, 27, 2) for x in range(5, 27, 2))/121
            actual = r['motion']['best_mse' if shifted else 'unshifted_mse']
            self.assertAlmostEqual(actual[pair, component], expected, places=11)

    def test_static_and_quiet_ties_preserve_zero_shift(self):
        for picture in [np.full((3, 32, 32), 128),
                        self.rng.uniform(100, 156, (3, 32, 32))]:
            r = self.call(np.repeat(picture[None], 8, axis=0))
            np.testing.assert_array_equal(r['motion']['offsets'], 0)
            np.testing.assert_array_equal(r['motion']['relative_improvement'], 0)
            self.assertFalse(r['stationarity_qualified'])

    def test_depth_offset_invariance(self):
        source = self.rng.uniform(64, 192, (8, 3, 32, 32))
        a = self.call(source); b = self.call(source*4, depth=10)
        c = self.call(source-32)
        for key in a['motion']:
            np.testing.assert_allclose(a['motion'][key], b['motion'][key], atol=1e-12)
            np.testing.assert_allclose(a['motion'][key], c['motion'][key], atol=1e-12)
        self.assertEqual(a['conflicts'], b['conflicts'])
        self.assertEqual(a['conflicts'], c['conflicts'])

    def test_exposure_and_temporal_correlation_conflict(self):
        source = 100+self.rng.normal(0, 2, (8, 3, 32, 32))
        source += 2*np.arange(8)[:, None, None, None]
        for c in self.call(source)['conflicts']: self.assertIn('mean_changed', c)
        noise = self.rng.normal(0, 2, (8, 3, 32, 32))
        for t in range(1, 8): noise[t] = .9*noise[t-1]+np.sqrt(1-.9**2)*noise[t]
        for c in self.call(128+noise)['conflicts']:
            self.assertIn('lag_energy_inconsistent', c)

    def test_invalid_history_does_not_enter_search(self):
        source = np.full((8, 3, 32, 32), 128)
        with self.assertRaises(ValueError):
            diagnose(source, source[-1], 8, self.ids, [0]*8)
        source = source.astype(float); source[0, 0, 0, 0] = np.nan
        with self.assertRaises(ValueError): self.call(source)

    def test_fast_zero_grain_motion_can_evade_every_diagnostic(self):
        # Retained development counterexample from the frozen synthetic study.
        # The spatially random picture is translated, never replaced by noise.
        rng = np.random.default_rng(923101)
        rng.normal(0, 2, (8, 3, 32, 32))
        picture = rng.uniform(-12, 12, (3, 32, 32))
        source = np.floor(np.array([128+np.roll(picture, t*7, axis=-1)
                                    for t in range(8)])*4+.5)
        r = self.call(source, depth=10)
        self.assertEqual(r['conflicts'][0], [])
        self.assertGreater(r['evidence']['source_residual_covariance'][0, 0], 40)
        self.assertFalse(r['population_acceptance'])
        self.assertFalse(r['stationarity_qualified'])

    def test_persistent_noise_is_indistinguishable_from_static_detail(self):
        rng = np.random.default_rng(923100)
        independent = rng.normal(0, 2, (8, 3, 32, 32))
        frozen = rng.normal(0, 2, (1, 3, 32, 32))
        y, x = np.mgrid[:32, :32]
        detail = np.array([6*np.cos((x+2*c)*np.pi/8)
                           +4*np.sin((y-c)*np.pi/8) for c in range(3)])
        r = self.call(128+detail+independent+frozen)
        self.assertTrue(all(not c for c in r['conflicts']))
        actual_noise = np.var(independent[-1]+frozen[0], axis=(1, 2), ddof=1)
        estimated = np.diag(r['evidence']['source_residual_covariance'])
        self.assertTrue(np.all(estimated < .6*actual_noise))
        self.assertFalse(r['population_acceptance'])


if __name__ == '__main__': unittest.main()
