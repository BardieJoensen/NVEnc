import unittest
import numpy as np
from temporal_population_reference import measure


class TemporalPopulationTests(unittest.TestCase):
    def setUp(self):
        self.rng = np.random.default_rng(772039)
        self.ids = list(range(10, 18))
        self.clocks = [100+i*41 for i in range(8)]
        self.noise = self.rng.normal(0, 2, (8, 3, 32, 32))
        self.source = 128+self.noise
        self.base = 128+self.noise[-1]*np.array([.1, .25, .75])[:, None, None]

    def call(self, source=None, base=None, **kwargs):
        return measure(self.source if source is None else source,
                       self.base if base is None else base,
                       kwargs.get('depth', 8), kwargs.get('ids', self.ids),
                       kwargs.get('clocks', self.clocks))

    def test_independent_scalar_oracle_and_orientation(self):
        r = self.call()
        a = self.noise[:3].mean(axis=0); b = self.noise[3:7].mean(axis=0)
        x = self.noise[-1]; y = self.base-128
        # Explicit independent scalar sample covariance, not the module helper.
        def cov(p, q):
            pp = p.ravel().tolist(); qq = q.ravel().tolist()
            pm = sum(pp)/len(pp); qm = sum(qq)/len(qq)
            return sum((v-pm)*(w-qm) for v, w in zip(pp, qq))/(len(pp)-1)
        for i in range(3):
            for j in range(3):
                expected = .5*(cov(x[i]-a[i], y[j]-b[j])+cov(x[i]-b[i], y[j]-a[j]))
                self.assertAlmostEqual(r['source_base_residual_covariance'][i, j], expected, places=12)
        self.assertGreater(np.max(np.abs(r['source_base_residual_covariance']
                                        -r['source_base_residual_covariance'].T)), .001)

    def test_static_detail_cancels_without_flat_patch_selection(self):
        y, x = np.mgrid[:32, :32]
        detail = (12*((x//4+y//4)%2)-6)[None, :, :]
        original = self.call(); textured = self.call(self.source+detail, self.base+detail)
        for key in ['source_residual_covariance', 'base_residual_covariance',
                    'source_base_residual_covariance', 'lag_difference_covariance']:
            np.testing.assert_allclose(original[key], textured[key], atol=2e-13, rtol=0)

    def test_depth_scaling_and_common_offset(self):
        a = self.call(); b = self.call(self.source*4, self.base*4, depth=10)
        c = self.call(self.source-32, self.base-32)
        for key in a:
            if isinstance(a[key], np.ndarray):
                np.testing.assert_allclose(a[key], b[key], atol=1e-12)
                np.testing.assert_allclose(a[key], c[key], atol=1e-12)

    def test_quiet_constant_and_exact_source_base(self):
        r = self.call(np.full_like(self.source, 128), np.full_like(self.base, 128))
        for key, value in r.items():
            if isinstance(value, np.ndarray): self.assertFalse(value.any(), key)
        r = self.call(base=self.source[-1])
        np.testing.assert_array_equal(r['base_residual_covariance'], r['source_residual_covariance'])
        self.assertFalse(r['removed_structure_covariance'].any())

    def test_detail_loss_is_not_noise_fidelity(self):
        y, x = np.mgrid[:32, :32]; detail = (16*((x//4+y//4)%2)-8)[None, :, :]
        r = self.call(self.source+detail, self.base)
        self.assertTrue(np.all(np.diag(r['removed_structure_covariance']) > 60))
        self.assertFalse(r['stationarity_qualified'])

    def test_motion_without_noise_can_fool_stationary_hypothesis(self):
        y, x = np.mgrid[:32, :32]
        frames = np.array([128+16*np.sin((x-t)*np.pi/8)+np.zeros_like(y) for t in range(8)])
        source = np.repeat(frames[:, None], 3, axis=1)
        r = self.call(source, source[-1])
        # Mandatory negative: a positive temporal estimate alone is not proof
        # of grain. A pure moving pattern has no grain but gives a large result.
        self.assertGreater(np.diag(r['source_residual_covariance'])[0], 50)
        lag = r['lag_difference_covariance'][:, 0, 0]
        self.assertGreater(lag[2], lag[0]*4)
        self.assertTrue(r['hypothesis_only']); self.assertFalse(r['stationarity_qualified'])

    def test_signed_estimates_are_not_regularized(self):
        z = self.rng.normal(0, 2, (3, 32, 32))
        source = np.array([128+z]*3+[128-z]*4+[np.full_like(z, 128)])
        r = self.call(source, source[-1])
        self.assertTrue(np.all(np.diag(r['source_residual_covariance']) < 0))

    def test_bad_history_and_layout_reject(self):
        for kwargs in [dict(ids=range(7)), dict(ids=[0,1,2,4,5,6,7,8]),
                       dict(ids=[float(x) for x in self.ids]),
                       dict(clocks=[0]*8), dict(clocks=np.arange(8, 0, -1, dtype=np.uint64)),
                       dict(clocks=[0,1,2,3,4,5,6,np.nan]),
                       dict(depth=12)]:
            with self.assertRaises(ValueError): self.call(**kwargs)
        with self.assertRaises(ValueError): self.call(self.source[:-1])
        for value in [-1, 256, np.nan, np.inf]:
            source = self.source.copy(); source[0,0,0,0] = value
            with self.assertRaises(ValueError): self.call(source)


if __name__ == '__main__': unittest.main()
