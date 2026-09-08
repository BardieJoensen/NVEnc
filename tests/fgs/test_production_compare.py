import copy
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from production_compare import check_reuse_binaries, grain_arguments, identity, reuse_baseline_encoding, sha, verify_source


class BaselineReuseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.original = self.root/'old.mkv'
        self.original.write_bytes(b'completed encoded artifact')
        self.output = self.root/'new'; self.output.mkdir()
        self.case = dict(name='clip', source='/source', identity={'size':123}, sha256='source-hash',
                         frames=48, video_properties={'width':768})
        self.argv = ['/encoder', '-i', '/source', '--qvbr', '30', '-o', str(self.output/'output.mkv')]
        oldargv = self.argv[:-1] + [str(self.original)]
        self.prior = dict(complete=False, manifest={'cases':[self.case]}, runs=[dict(
            case='clip', arm='old-default-a', command=oldargv, frames=48,
            bytes=self.original.stat().st_size, sha256=sha(self.original), scan={'verdict':'stable'})])

    def test_repeated_unchanged_source_is_hashed_once(self):
        case = dict(name='source', source=str(self.original), identity=identity(self.original),
                    sha256=sha(self.original))
        verified = {}
        with patch('production_compare.sha', wraps=sha) as hasher:
            verify_source(case, verified)
            verify_source(case, verified)
            self.assertEqual(hasher.call_count, 1)
        bad = dict(case, sha256='a' * 64)
        with self.assertRaisesRegex(RuntimeError, 'Conflicting source hash'):
            verify_source(bad, verified)
        self.original.write_bytes(b'replaced during the study')
        with self.assertRaisesRegex(RuntimeError, 'identity changed'):
            verify_source(case, verified)

    def reuse(self, prior=None, case=None, argv=None):
        return reuse_baseline_encoding(prior or self.prior, case or self.case,
                                       argv or self.argv, self.output, self.root/'report.json')

    def test_completed_encode_from_stopped_trial_requires_fresh_validation(self):
        row = self.reuse()
        self.assertFalse(row['validation_reused'])
        self.assertNotIn('scan', row)
        self.assertEqual((self.output/'output.mkv').read_bytes(), self.original.read_bytes())

    def test_changed_quantizer_is_not_reused(self):
        argv = self.argv.copy(); argv[4] = '31'
        with self.assertRaisesRegex(RuntimeError, 'arguments changed'):
            self.reuse(argv=argv)

    def test_changed_source_is_not_reused(self):
        case = copy.deepcopy(self.case); case['sha256'] = 'changed'
        with self.assertRaisesRegex(RuntimeError, 'source changed'):
            self.reuse(case=case)

    def test_changed_output_is_not_reused(self):
        self.original.write_bytes(b'incomplete output')
        with self.assertRaisesRegex(RuntimeError, 'artifact changed'):
            self.reuse()

    def test_wrong_completed_frame_count_is_not_reused(self):
        prior = copy.deepcopy(self.prior); prior['runs'][0]['frames'] = 47
        with self.assertRaisesRegex(RuntimeError, 'artifact changed'):
            self.reuse(prior=prior)

    def test_candidate_ceiling_does_not_enter_baseline_command(self):
        argv = ['--av1-film-grain', 'denoise=auto,retain=0.2']
        self.assertEqual(grain_arguments(argv, False, ['retain-max=0.1']),
                         ['--av1-film-grain', 'denoise=auto'])
        self.assertEqual(grain_arguments(argv, True, ['retain-max=0.1']),
                         ['--av1-film-grain', 'denoise=auto,retain=auto,retain-max=0.1'])

    def test_completed_candidate_cannot_reuse_validation(self):
        self.prior['runs'][0].update(arm='new-auto-a', decoded_sha256={'0':'old'},
                                    timeline_sha256={'0':'old'}, video={'width':768})
        row = reuse_baseline_encoding(self.prior, self.case, self.argv,
                                      self.output, self.root/'report.json', 'new-auto-a')
        for field in ['scan', 'video', 'decoded_sha256', 'timeline_sha256']:
            self.assertNotIn(field, row)
        self.assertFalse(row['validation_reused'])

    def test_changed_candidate_binary_cannot_reuse_old_encodes(self):
        prior = dict(baseline_sha256='baseline', candidate_sha256='old-candidate')
        with self.assertRaisesRegex(RuntimeError, 'candidate encoder changed'):
            check_reuse_binaries(prior, 'baseline', 'new-candidate', True)
        check_reuse_binaries(prior, 'baseline', 'new-candidate', False)

    def test_candidate_changed_retention_ceiling_is_not_reused(self):
        self.prior['runs'][0]['arm'] = 'new-auto-a'
        argv = self.argv[:-2] + ['--av1-film-grain', 'retain=auto,retain-max=0.1'] + self.argv[-2:]
        with self.assertRaisesRegex(RuntimeError, 'arguments changed'):
            reuse_baseline_encoding(self.prior, self.case, argv,
                                    self.output, self.root/'report.json', 'new-auto-a')


if __name__ == '__main__':
    unittest.main()
