import copy
import tempfile
from pathlib import Path
import unittest

from production_compare import grain_arguments, reuse_baseline_encoding, sha


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


if __name__ == '__main__':
    unittest.main()
