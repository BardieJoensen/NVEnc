import unittest
import numpy as np
import retention_pixel_evidence as evidence


class PixelEvidenceTests(unittest.TestCase):
    def picture(self, depth=8):
        rng = np.random.default_rng(20260924)
        scale = 1 << (depth-8)
        return [(80*scale+rng.integers(-4*scale, 4*scale+1, size=shape)).astype(np.int32)
                for shape in ((128, 128), (64, 64), (64, 64))]

    def test_identical_picture_does_not_invent_other_proofs(self):
        for depth in (8, 10):
            s = self.picture(depth)
            r = evidence.measure(s, s, s, s, s, depth, [0, .25, .75])
            self.assertTrue(r['spatial']['full_pass'])
            self.assertFalse(r['source_admission'])
            self.assertFalse(r['model_association_proven'])
            self.assertEqual([c['passed'] for c in r['checks']], [145]*3)
            self.assertEqual([c['unmeasured'] for c in r['checks']], [110]*3)

    def test_one_native_border_pixel_cannot_hide(self):
        for component in range(3):
            s = self.picture(); b = [p.copy() for p in s]; b[component][-1, -1] += 1
            r = evidence.measure(s, s, b, s, s, 8, [0, 0, 0])
            self.assertEqual(r['rounding'][component]['mismatch_samples'], 1)
            self.assertFalse(r['checks'][component]['passed'] & 1)
            self.assertNotEqual(r['hashes']['source'][component], r['hashes']['rounded'][component])

    def test_zero_variance_is_unmeasured_not_failed_or_passed(self):
        s = [np.full_like(a, 80) for a in self.picture()]
        r = evidence.measure(s, s, s, s, s, 8, [0, 0, 0])
        self.assertEqual([c['measured'] for c in r['checks']], [1]*3)
        self.assertEqual([c['passed'] for c in r['checks']], [1]*3)
        self.assertEqual([c['unmeasured'] for c in r['checks']], [254]*3)

    def test_rounding_is_native_not_eight_bit(self):
        s = self.picture(10); b = [np.full_like(a, 320) for a in s]
        fractions = [0, .25, .75]
        retained = [np.rint(base+np.float32(f)*(source-base)).astype(np.int32)
                    for source, base, f in zip(s, b, fractions)]
        r = evidence.measure(s, b, retained, retained, s, 10, fractions)
        self.assertEqual([c['mismatch_samples'] for c in r['rounding']], [0, 0, 0])
        changed = [a.copy() for a in retained]; changed[1][0, 0] ^= 1
        r = evidence.measure(s, b, changed, retained, s, 10, fractions)
        self.assertEqual(r['rounding'][1]['mismatch_samples'], 1)

    def test_noise_loss_and_mean_are_independent(self):
        s = self.picture(); out = [a.copy() for a in s]; out[1][:] = 80
        r = evidence.measure(s, s, s, s, out, 8, [0, 0, 0])
        self.assertFalse(r['checks'][1]['passed'] & 128)
        self.assertFalse(r['checks'][1]['passed'] & 16)
        out = [a.copy() for a in s]; out[1] += 1
        r = evidence.measure(s, s, s, s, out, 8, [0, 0, 0])
        self.assertTrue(r['checks'][1]['passed'] & 128)
        self.assertFalse(r['checks'][1]['passed'] & 16)

    def test_native_luma_alternation_is_not_averaged_away(self):
        s = self.picture(); out = [a.copy() for a in s]
        out[0][::2] += 3; out[0][1::2] -= 3
        r = evidence.measure(s, s, s, s, out, 8, [0, 0, 0])
        self.assertFalse(r['checks'][0]['passed'] & 16)

    def test_invalid_inputs(self):
        s = self.picture()
        for fractions in ([0, 0], [0, True, 0], [0, np.nan, 0], [0, 1.01, 0],
                          [0, '0', 0], [0, [], 0], None):
            with self.assertRaises(ValueError):
                evidence.measure(s, s, s, s, s, 8, fractions)
        for bad in ([a.astype(float) for a in s], [s[0], s[1][:-1], s[2]],
                    [s[0]-100, s[1], s[2]]):
            with self.assertRaises(ValueError):
                evidence.measure(s, bad, s, s, s, 8, [0, 0, 0])


if __name__ == '__main__':
    unittest.main()
