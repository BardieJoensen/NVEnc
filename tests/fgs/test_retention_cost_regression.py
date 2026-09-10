"""A texture pass for a different candidate must never qualify this run."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from production_compare import sha
from retention_cost_regression import brightness_errors, check, check_files
from directional_cost_regression import check as check_directional


class EvidenceBinding(unittest.TestCase):
    def test_programmatic_checks_require_binding(self):
        self.assertEqual(check({}, {}, {}),
                         ['Texture evidence belongs to a different controlled report'])
        self.assertEqual(check_directional({}, {}),
                         ['Texture evidence belongs to a different controlled report'])

    def test_exact_report_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report, previous, residual = [root / name for name in ['run.json', 'prior.json', 'texture.json']]
            report.write_text(json.dumps({'candidate_sha256': 'a' * 64}))
            previous.write_text('{}')
            residual.write_text(json.dumps({'report_sha256': sha(report)}))
            with patch('retention_cost_regression.check', return_value=[]) as check:
                self.assertEqual(check_files(report, previous, residual), [])
                check.assert_called_once()
            report.write_text(json.dumps({'candidate_sha256': 'b' * 64}))
            with patch('retention_cost_regression.check') as check:
                self.assertEqual(check_files(report, previous, residual),
                                 ['Texture evidence belongs to a different controlled report'])
                check.assert_not_called()

    def test_missing_binding_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report, previous, residual = [root / name for name in ['run.json', 'prior.json', 'texture.json']]
            for path in [report, previous, residual]:
                path.write_text('{}')
            self.assertEqual(check_files(report, previous, residual),
                             ['Texture evidence belongs to a different controlled report'])


class TransientBrightness(unittest.TestCase):
    def test_opposing_shifts_and_startup_are_not_averaged_away(self):
        trace = [dict(frame=i, band_mean_shift_8bit=[0.0] * 12) for i in range(10)]
        self.assertEqual(brightness_errors(trace, 10), [])
        trace[0]['band_mean_shift_8bit'][:2] = [0.6, -0.6]
        errors = brightness_errors(trace, 10)
        self.assertEqual(len(errors), 1)
        self.assertIn('frame 0', errors[0])

    def test_incomplete_and_nonfinite_trace_cannot_pass(self):
        self.assertTrue(brightness_errors([], 1))
        self.assertTrue(brightness_errors([dict(frame=0)], 1))
        self.assertTrue(brightness_errors([
            dict(frame=0, band_mean_shift_8bit=[float('nan')] * 12)], 1))


if __name__ == '__main__':
    unittest.main()
