import copy
import unittest
import numpy as np
import retention_target_evidence as evidence


class TargetEvidenceTests(unittest.TestCase):
    def pair(self, n=25):
        return dict(blocks=16, observations=1600,
                    source=(np.eye(n)*1600).ravel().tolist(),
                    base=(np.eye(n)*400).ravel().tolist(),
                    sourceBase=(np.eye(n)*200).ravel().tolist())

    def test_valid_noise_and_exactly_copied_source(self):
        for n in (25, 26):
            pair = self.pair(n)
            self.assertTrue(evidence.target(pair, n)['valid'])
            pair['base'] = pair['sourceBase'] = pair['source']
            self.assertTrue(evidence.target(pair, n)['valid'])

    def test_invalid_oriented_source_base_is_not_symmetrized(self):
        pair = self.pair()
        pair['sourceBase'][1] = 5000
        result = evidence.target(pair, 25)
        self.assertFalse(result['valid'])
        self.assertTrue(result['missing_target']['valid'])
        self.assertFalse(result['joint_pair']['valid'])

    def test_positive_diagonal_does_not_hide_indefinite_target(self):
        pair = self.pair()
        base = np.eye(25)*1200
        base[0, 1] = base[1, 0] = 600
        pair['base'] = base.ravel().tolist()
        pair['sourceBase'] = np.zeros((25, 25)).ravel().tolist()
        result = evidence.target(pair, 25)
        self.assertTrue(result['joint_pair']['valid'])
        self.assertTrue(result['missing_target']['nonnegative_diagonal'])
        self.assertFalse(result['missing_target']['valid'])

    def test_negative_diagonal_and_asymmetry_reject(self):
        for kind in ('negative', 'asymmetric'):
            pair = self.pair()
            if kind == 'negative':
                pair['base'][0] = 1600.00000001
            else:
                pair['base'][1] = 10
            self.assertFalse(evidence.target(pair, 25)['valid'])

    def test_incomplete_is_unknown(self):
        for key, value in [('blocks', 15), ('observations', 1), ('blocks', True),
                           ('source', [float('nan')]*625), ('base', [0]*624)]:
            pair = self.pair(); pair[key] = value
            self.assertFalse(evidence.target(pair, 25)['measured'])

    def test_check_fold_and_native_luma_veto(self):
        pairs = dict(luma=[self.pair(), self.pair()],
                     colour=[[self.pair(26), self.pair(26)] for _ in range(2)])
        result = evidence.measure(pairs)
        self.assertFalse(result['source_admission'])
        self.assertTrue(all(c['valid'] for c in result['components']))
        changed = copy.deepcopy(pairs)
        changed['luma'][1]['base'][24*25+24] = 1700
        result = evidence.measure(changed)
        self.assertFalse(result['components'][0]['valid'])
        self.assertTrue(result['components'][1]['valid'])
        self.assertTrue(result['components'][2]['valid'])


if __name__ == '__main__':
    unittest.main()
