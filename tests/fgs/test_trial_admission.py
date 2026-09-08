import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from production_compare import identity, sha
from trial_admission import admit, byte_budget, validated_pair


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source.mkv'
        self.source.write_bytes(b'original source remains untouched')
        self.case = dict(name='sample', source=str(self.source),
                         identity=identity(self.source), sha256=sha(self.source),
                         frames=48, video_properties={'width': 768})
        self.build = 'c' * 64
        self.report = dict(complete=True, candidate_sha256=self.build,
                           baseline_sha256='b' * 64, manifest={'cases': [self.case]}, runs=[])
        for arm, size in [('old-default-a', 1000), ('new-auto-a', 1100)]:
            path = self.root / 'sample' / arm / 'output.mkv'
            path.parent.mkdir(parents=True)
            path.write_bytes(b'x' * size)
            self.report['runs'].append(dict(case='sample', arm=arm, frames=48,
                bytes=size, sha256=sha(path), command=[], video={'width': 768},
                scan=dict(complete=True, errors=0, packets=48,
                          criterion='synthesis_texture_v1', verdict='stable'),
                decoded_sha256={'0': 'd' * 64, '1': 'e' * 64},
                timeline_sha256={'0': 'f' * 64, '1': 'f' * 64}))
        self.report_path = self.root / 'report.json'
        # Decoder correctness is exercised by the real trial. These unit tests
        # exercise admission with small stand-in artifact payloads.
        mock = patch('trial_admission.probe_video_only')
        mock.start()
        self.addCleanup(mock.stop)

    def save(self):
        self.report_path.write_text(json.dumps(self.report))

    def run_gate(self):
        self.save()
        return admit(self.report_path, 'sample', self.build, self.root / 'admitted')

    def test_exact_budget_boundary_is_accepted_as_an_independent_copy(self):
        result = self.run_gate()
        self.assertEqual(result['decision'], 'stage_candidate')
        staged = Path(result['staged_output'])
        original = self.root / 'sample/new-auto-a/output.mkv'
        self.assertNotEqual(staged.stat().st_ino, original.stat().st_ino)
        original.write_bytes(b'changed experiment')
        self.assertEqual(staged.read_bytes(), b'x' * 1100)
        self.assertEqual(identity(self.source), self.case['identity'])

    def test_one_byte_over_budget_keeps_source_and_publishes_no_candidate(self):
        path = self.root / 'sample/new-auto-a/output.mkv'
        path.write_bytes(b'x' * 1101)
        self.report['runs'][1].update(bytes=1101, sha256=sha(path))
        result = self.run_gate()
        self.assertEqual(result['decision'], 'keep_source')
        self.assertIsNone(result['staged_output'])
        self.assertEqual(list((self.root / 'admitted').iterdir()),
                         [self.root / 'admitted/decision.json'])
        self.assertEqual(identity(self.source), self.case['identity'])

    def test_fractional_limit_rounds_down_to_whole_bytes(self):
        self.assertEqual(byte_budget(101, '0.5'), 101)
        self.assertEqual(byte_budget(1000, '10'), 1100)

    def test_invalid_or_unknown_budget_cannot_be_admitted(self):
        for limit in ['nan', 'Infinity', '-1', '100.001', '10junk']:
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                byte_budget(1000, limit)
        for size in [None, 0, -1, True, 1000.0]:
            with self.subTest(size=size), self.assertRaises(ValueError):
                byte_budget(size)

    def test_incomplete_trial_is_not_an_admission_receipt(self):
        self.report['complete'] = False
        with self.assertRaisesRegex(ValueError, 'complete successful'):
            self.run_gate()
        self.assertFalse((self.root / 'admitted').exists())

    def test_wrong_build_and_missing_baseline_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'expected build'):
            validated_pair(self.report, 'sample', 'a' * 64)
        self.report['runs'].pop(0)
        with self.assertRaisesRegex(ValueError, 'completed baseline'):
            self.run_gate()

    def test_missing_grain_decode_or_changed_timeline_is_rejected(self):
        report = copy.deepcopy(self.report)
        del report['runs'][1]['decoded_sha256']['1']
        with self.assertRaisesRegex(ValueError, 'Both full'):
            validated_pair(report, 'sample', self.build)
        self.report['runs'][1]['timeline_sha256']['0'] = 'a' * 64
        with self.assertRaisesRegex(ValueError, 'timestamps differ'):
            self.run_gate()

    def test_changed_input_or_candidate_is_rejected(self):
        self.source.write_bytes(b'changed original')
        with self.assertRaisesRegex(ValueError, 'source changed'):
            self.run_gate()
        self.source.write_bytes(b'original source remains untouched')
        self.case['identity'] = identity(self.source)
        (self.root / 'sample/new-auto-a/output.mkv').write_bytes(b'truncated')
        with self.assertRaisesRegex(ValueError, 'artifact changed'):
            self.run_gate()

    def test_failed_scan_or_color_change_cannot_pass_size_gate(self):
        report = copy.deepcopy(self.report)
        report['runs'][1]['scan']['errors'] = 1
        with self.assertRaisesRegex(ValueError, 'synthesis validation'):
            validated_pair(report, 'sample', self.build)
        self.report['runs'][1]['video']['width'] = 384
        with self.assertRaisesRegex(ValueError, 'properties changed'):
            self.run_gate()

    def test_duplicate_case_is_rejected(self):
        self.report['manifest']['cases'].append(self.case.copy())
        with self.assertRaisesRegex(ValueError, 'exactly once'):
            self.run_gate()

    def test_existing_admission_is_never_overwritten(self):
        self.run_gate()
        with self.assertRaises(FileExistsError):
            self.run_gate()


if __name__ == '__main__':
    unittest.main()
