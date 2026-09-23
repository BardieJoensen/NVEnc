import unittest
import numpy as np
from persistent_detail_reference import moments, reference


class PersistentDetailTests(unittest.TestCase):
    limits = dict(relative_projected_contrast_change=.02, absolute_projected_rms_8bit=.125,
                  absolute_mean_error_8bit=.125, minimum_source_history_correlation=.5,
                  minimum_history_history_correlation=.8)
    def setUp(self):
        rng = np.random.default_rng(924091)
        y, x = np.mgrid[:64, :64]
        self.detail = 128+8*np.cos(x*np.pi/8)+6*((y % 2)*2-1)
        self.source = np.rint(self.detail+rng.normal(0, 2, (8, 64, 64))).astype(np.int32)

    def call(self, source, base, depth=8):
        return moments(source, base, depth, list(range(8)), list(range(8)))

    def test_independent_scalar_covariance_oracle(self):
        base = np.rint(self.detail).astype(np.int32);m = self.call(self.source, base)
        fields = [self.source[-1], base, self.source[:3].mean(axis=0), self.source[3:7].mean(axis=0)]
        for i in range(4):
            for j in range(4):
                a, b = fields[i].ravel().tolist(), fields[j].ravel().tolist()
                am, bm = sum(a)/len(a), sum(b)/len(b)
                expected = sum((u-am)*(v-bm) for u, v in zip(a, b))/len(a)
                self.assertAlmostEqual(m['covariance'][i, j], expected, places=10)

    def test_alternating_rows_survive_native_detail_check(self):
        y, x = np.mgrid[:64, :64]
        picture = np.array(128+8*((y % 2)*2-1)+np.zeros_like(x), dtype=np.int32)
        source = np.repeat(picture[None], 8, axis=0);base = np.full_like(picture, 128)
        # The co-located 2x2 average loses all evidence of this persistent defect.
        np.testing.assert_array_equal(picture.reshape(32,2,32,2).mean(axis=(1,3)), 128)
        result = reference(self.call(source, base), self.limits)
        self.assertTrue(result['anchors_supported']);self.assertFalse(result['within_limits'])
        np.testing.assert_allclose(result['contrast_loss'], 1)

    def test_exact_source_and_native_depth(self):
        a = self.call(self.source, self.source[-1])
        b = self.call(self.source*4, self.source[-1]*4, 10)
        np.testing.assert_array_equal(a['covariance'], b['covariance'])
        result = reference(a, self.limits)
        self.assertTrue(result['within_limits']);self.assertEqual(result['contrast_loss'], [0., 0.])

    def test_loss_of_persistent_grain_is_protected_as_detail(self):
        rng = np.random.default_rng(2240)
        frozen = np.rint(rng.normal(0, 4, (64, 64))).astype(np.int32)
        source = np.repeat((128+frozen)[None], 8, axis=0)
        base = np.rint(128+.5*frozen).astype(np.int32)
        result = reference(self.call(source, base), self.limits)
        self.assertTrue(result['anchors_supported']);self.assertFalse(result['within_limits'])
        self.assertTrue(all(x > .4 for x in result['contrast_loss']))

    def test_quiet_and_missing_history_are_not_admission(self):
        source = np.full((8,32,32),128,dtype=np.uint8)
        self.assertFalse(reference(self.call(source,source[-1]),self.limits)['anchors_supported'])
        for ids in [list(range(7)), [0,1,2,3,4,5,7,8], np.arange(8,0,-1,dtype=np.uint64)]:
            with self.assertRaises(ValueError):moments(source,source[-1],8,ids,list(range(8)))
        with self.assertRaises(ValueError):self.call(source.astype(float),source[-1])
        bad=self.source.copy();bad[0,0,0]=-1
        with self.assertRaises(ValueError):self.call(bad,bad[-1])

    def test_one_pixel_border_has_mean_but_no_contrast_anchor(self):
        source = np.full((8,1,1), 130, dtype=np.uint8)
        measured = self.call(source, np.array([[128]], dtype=np.uint8))
        np.testing.assert_array_equal(measured['covariance'], 0)
        result = reference(measured, self.limits)
        self.assertEqual(result['mean_error'], 2)
        self.assertFalse(result['anchors_supported'])


if __name__ == '__main__': unittest.main()
