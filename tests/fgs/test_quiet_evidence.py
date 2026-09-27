import unittest
import numpy as np
from quiet_evidence_reference import measure


class QuietEvidenceTests(unittest.TestCase):
    def picture(self, depth=8, width=130, height=66, level=128):
        return [np.full((height//(2 if c else 1), width//(2 if c else 1)),
                        level*(1 << (depth-8)), dtype=np.int32) for c in range(3)]

    def model(self, strength=None, **kw):
        return dict(apply=True, restricted=True, matrix=1,
                    strength=[0, 0, 0] if strength is None else strength, **kw)

    def test_both_grids_cover_all_borders_and_detect_one_changed_code(self):
        for depth in (8, 10):
            source = self.picture(depth)
            for c in range(3):
                base = [p.copy() for p in source]; base[c][-1, -1] += 1
                result = measure(source, base, source, source, depth, self.model())
                self.assertFalse(result['source_admission'])
                self.assertFalse(result['components'][c]['quiet_pass'])
                for k in ('fine', 'coarse'):
                    r = result['components'][c][k]
                    self.assertEqual(r['samples'], source[c].size)
                    self.assertEqual(r['quiet_samples'], source[c].size)
                    self.assertEqual(r['changed_quiet'], 1)

    def test_small_island_and_gradient_cannot_hide_in_global_variance(self):
        source = self.picture(width=128, height=128)
        source[0][::2] += 4; source[0][1::2] -= 4
        model = self.model([32, 0, 0])
        full = measure(source, source, source, source, 8, model)
        self.assertEqual(full['components'][0]['fine']['quiet_samples'], 0)
        self.assertEqual(full['components'][0]['coarse']['quiet_samples'], 0)
        source[0][8:16, 8:16] = 128
        island = measure(source, source, source, source, 8, model)
        self.assertEqual(island['components'][0]['fine']['quiet_samples'], 64)
        self.assertFalse(island['components'][0]['quiet_pass'])
        source[0][:] = 48+np.arange(128)
        ramp = measure(source, source, source, source, 8, model)
        self.assertEqual(ramp['components'][0]['fine']['quiet_samples'], 0)
        self.assertEqual(ramp['components'][0]['coarse']['quiet_samples'], source[0].size)
        self.assertFalse(ramp['components'][0]['quiet_pass'])

    def test_endpoint_is_ambiguous_for_nonzero_and_exact_for_zero(self):
        for depth in (8, 10):
            source = self.picture(depth, level=16)
            for strength in (0, 1):
                result = measure(source, source, source, source, depth, self.model([strength]*3))
                for c in result['components']:
                    self.assertEqual(c['range']['measured'], strength == 0)
                    self.assertEqual(c['range']['pass'], strength == 0)
                    self.assertEqual(c['range']['ambiguous'], c['range']['samples'] if strength else 0)

    def test_zero_strength_clamp_and_inactive_component(self):
        source = self.picture(10, level=0); decoded = [p+64 for p in source]
        result = measure(source, source, source, decoded, 10, self.model())
        for c in result['components']:
            self.assertEqual(c['range']['failed'], c['range']['samples'])
            self.assertFalse(c['quiet_pass'])
        model = self.model(); model['apply'] = False
        result = measure(source, source, source, source, 10, model)
        self.assertTrue(all(c['quiet_pass'] and c['range']['pass'] for c in result['components']))

    def test_weak_native_ten_bit_noise_is_not_truncated_before_classification(self):
        source = self.picture(10, width=128, height=128)
        source[0][::2] += 1
        result = measure(source, source, source, source, 10, self.model([1, 0, 0]))
        self.assertFalse(result['components'][0]['quiet_pass'])
        self.assertEqual(result['components'][0]['fine']['quiet_samples'], source[0].size)

    def test_unsupported_scope_and_invalid_native_planes(self):
        source = self.picture()
        for field, value in [('matrix', 0), ('matrix', True), ('apply', 1), ('restricted', 'yes'),
                             ('strength', [0, 256, 0]), ('strength', [0, True, 0])]:
            model = self.model(); model[field] = value
            with self.assertRaises(ValueError): measure(source, source, source, source, 8, model)
        bad = [p.copy() for p in source]; bad[2][-1, -1] = 256
        with self.assertRaises(ValueError): measure(source, source, source, bad, 8, self.model())


if __name__ == '__main__':
    unittest.main()
