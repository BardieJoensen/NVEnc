import copy
import hashlib
import json
import unittest
import retention_candidate_evidence as evidence


class CandidateEvidenceTests(unittest.TestCase):
    def fixture(self):
        subject = dict(depth=10, identity=dict(frame=8, pts=400000, model=dict(seed=1729)),
                       hashes={k: [str(c)*64 for c in range(3)] for k in
                               ('source', 'pristine', 'rounded', 'reconstructed', 'decoded')},
                       fractions=[0, .25, .5])
        pixel = dict(subject, checks=[dict(measured=145, passed=145) for _ in range(3)])
        model = dict(subject=subject, subject_sha256=evidence.digest(subject),
                     checks=[dict(measured=14, passed=14) for _ in range(3)])
        return subject, pixel, model

    def encode(self, pixel, model):
        p = json.dumps(pixel).encode()
        model = dict(model, pixel_evidence_sha256=hashlib.sha256(p).hexdigest())
        return p, json.dumps(model).encode()

    def test_partial_facts_never_become_admission(self):
        subject, pixel, model = self.fixture()
        result = evidence.combine(*self.encode(pixel, model), subject)
        self.assertFalse(result['source_admission'])
        self.assertEqual([r['measured'] for r in result['checks']], [159]*3)
        self.assertEqual([r['unmeasured'] for r in result['checks']], [96]*3)

    def test_failure_and_missing_fact_remain_distinct(self):
        subject, pixel, model = self.fixture()
        pixel['checks'][0]['passed'] &= ~16
        model['checks'][1] = dict(measured=12, passed=12)
        result = evidence.combine(*self.encode(pixel, model), subject)
        self.assertEqual(result['checks'][0]['failed'], 16)
        self.assertEqual(result['checks'][1]['unmeasured'], 98)

    def test_changed_frame_fraction_model_or_any_plane_rejects(self):
        subject, pixel, model = self.fixture()
        changes = []
        for stage in subject['hashes']:
            for c in range(3):
                changed = copy.deepcopy(subject); changed['hashes'][stage][c] = 'f'*64
                changes.append(changed)
        for key in ('frame', 'pts'):
            changed = copy.deepcopy(subject); changed['identity'][key] += 1; changes.append(changed)
        changed = copy.deepcopy(subject); changed['identity']['model']['seed'] += 1; changes.append(changed)
        changed = copy.deepcopy(subject); changed['fractions'][1] = .5; changes.append(changed)
        for changed in changes:
            with self.assertRaises(ValueError):
                evidence.combine(*self.encode(pixel, model), changed)

    def test_record_bytes_and_model_subject_are_bound(self):
        subject, pixel, model = self.fixture(); p, m = self.encode(pixel, model)
        with self.assertRaises(ValueError): evidence.combine(p+b'\n', m, subject)
        changed = json.loads(m); changed['subject_sha256'] = '0'*64
        with self.assertRaises(ValueError): evidence.combine(p, json.dumps(changed).encode(), subject)

    def test_measurement_cannot_grant_unknown_quality_bits(self):
        for index, key in ((0, 'measured'), (1, 'passed')):
            subject, pixel, model = self.fixture()
            [pixel, model][index]['checks'][0][key] |= 32
            with self.assertRaises(ValueError):
                evidence.combine(*self.encode(pixel, model), subject)
        subject, pixel, model = self.fixture(); pixel['checks'][0]['measured'] = True
        with self.assertRaises(ValueError): evidence.combine(*self.encode(pixel, model), subject)


if __name__ == '__main__':
    unittest.main()
