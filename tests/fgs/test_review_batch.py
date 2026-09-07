#!/usr/bin/env python3
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/fgs'))
import review_batch as batch


class BatchContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = self.root/'manifest.json'
        self.binary = self.root/'binary'
        self.binary.write_bytes(b'known inspector')
        (self.root/'source.mkv').write_bytes(b'known fixture')
        self.case = dict(name='control', file='source.mkv', sha256=batch.review.sha(self.root/'source.mkv'))

    def save(self, cases):
        self.manifest.write_text(json.dumps(dict(schema='fgs_review_batch_v1', cases=cases)))

    def test_invalid_names_duplicate_cases_and_misspelled_options_fail_before_work(self):
        for cases in ([dict(self.case, name='../escape')], [self.case, self.case],
                      [dict(self.case, sample_period_seconds=1)], [dict(self.case, duration=float('nan'))],
                      [dict(self.case, assume_bt709='false')]):
            self.save(cases)
            with self.assertRaises(ValueError):
                batch.requests(self.manifest, self.binary, self.root/'out')

    def test_changed_pinned_source_is_not_accepted_even_after_complete_measurement(self):
        self.save([self.case])
        def replaced(args):
            args.file.write_bytes(b'replacement')
            return dict(summary={'frames':8}, request={'source_signature':batch.review.signature(args.file)})
        with patch.object(batch.review, 'inspect', side_effect=replaced):
            result = batch.batch(self.manifest, self.binary, self.root/'out')
        self.assertTrue(result['finished'])
        self.assertEqual(result['completed'], 0)
        self.assertEqual(result['errors'], 1)
        self.assertIn('source changed', result['cases'][0]['error'])

    def test_checksum_mismatch_does_not_start_native_measurement(self):
        self.save([dict(self.case, sha256='0'*64)])
        with patch.object(batch.review, 'inspect') as inspect:
            result = batch.batch(self.manifest, self.binary, self.root/'out')
            inspect.assert_not_called()
        self.assertEqual(result['errors'], 1)


if __name__ == '__main__':
    unittest.main()
