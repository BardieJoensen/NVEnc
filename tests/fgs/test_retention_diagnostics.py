import tempfile
from pathlib import Path
import unittest

from retention_diagnostics import analyze_log, first_covariance_blocker


class DiagnosticsTests(unittest.TestCase):
    def analyze(self, lines, frames=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'encode.log'
            path.write_text('\n'.join(lines) + '\n')
            return analyze_log(path, frames, '24000/1001')

    def test_legacy_does_not_invent_coupling_or_fit_failure(self):
        result = self.analyze([
            'fgs-local-covariance frame=0 blocks=100 recovered=0 covariance=1 colourIndependent=0',
            'fgs-model frame=0 reliable=0 sourceFallback=1',
            'fgs-local-covariance frame=1 blocks=100 recovered=0 covariance=1 colourIndependent=1',
            'fgs-model frame=1 reliable=0 sourceFallback=1',
            'fgs-model frame=2 reliable=1 sourceFallback=0',
        ], 3)
        self.assertTrue(result['complete'])
        self.assertEqual(result['covariance_first_blocker'],
                         {'held_colour_unknown': 1, 'model_or_fresh_colour_unknown': 1})
        self.assertEqual(result['source_reasons'], {'legacy_unattributed': 2})
        self.assertEqual(result['colour_checks'], {})
        self.assertEqual(result['counters']['legacy_calls_avoidable_from_held_colour'], 1)
        self.assertEqual(result['longest_source_runs'][0]['frames'], 2)

    def test_precise_skipped_covariance_and_overlapping_reasons(self):
        result = self.analyze([
            'fgs-local-covariance frame=0 blocks=100 recovered=0 covariance=0 colourIndependent=0 '
            'trace=1 covarianceAttempted=0 minFramesEligible=1 fitAttempted=0 fitSucceeded=0 '
            'heldCb=6 heldCr=10 freshCb=255 freshCr=255',
            'fgs-model frame=0 reliable=0 sourceFallback=1 trace=1 sourceReasons=80',
            'fgs-model frame=1 reliable=0 sourceFallback=1 trace=1 sourceReasons=256',
            'fgs-model frame=2 reliable=1 sourceFallback=0 trace=1 sourceReasons=0',
        ], 3)
        self.assertEqual(result['colour_checks']['heldCb:insufficient_observations'], 1)
        self.assertEqual(result['colour_checks']['heldCr:spatial_correlation'], 1)
        self.assertEqual(result['source_reasons']['recovery_hold'], 1)
        self.assertEqual(result['source_reasons']['local_mismatch'], 1)
        self.assertEqual(result['source_reasons']['covariance_recovery_rejected'], 1)
        self.assertEqual(result['counters']['covariance_calls_skipped'], 1)
        self.assertEqual(result['counters']['covariance_calls'], 0)

    def test_legacy_short_early_return_is_not_a_fidelity_failure(self):
        result = self.analyze(['fgs-model frame=0 pts=0 reliable=0 reset=0 flat=0/2000 window=0'], 1)
        self.assertTrue(result['complete'])
        self.assertEqual(result['counters']['legacy_early_flat_rejection'], 1)
        self.assertEqual(result['counters']['fidelity_source_fallback'], 0)

    def test_fresh_coupling_is_distinct_from_failed_fit(self):
        fields = dict(recovered='0', covariance='1', colourIndependent='1', trace='1',
                      covarianceAttempted='1', minFramesEligible='1', fitAttempted='1',
                      fitSucceeded='1', heldCb='254', heldCr='254', freshCb='5', freshCr='0')
        self.assertEqual(first_covariance_blocker(fields), 'fresh_colour_rejected')
        fields.update(fitSucceeded='0', freshCb='255', freshCr='255')
        self.assertEqual(first_covariance_blocker(fields), 'model_fit_rejected')
        fields.update(covariance='0', fitAttempted='0')
        self.assertEqual(first_covariance_blocker(fields), 'covariance_evidence_rejected')

    def test_incomplete_and_restarted_logs_cannot_qualify(self):
        result = self.analyze(['fgs-model frame=0 reliable=0 sourceFallback=0',
                               'fgs-model frame=2 reliable=1 sourceFallback=0'], 3)
        self.assertFalse(result['complete'])
        self.assertEqual(result['missing_frame_decisions'], 1)
        with self.assertRaisesRegex(ValueError, 'order restarted'):
            self.analyze(['fgs-model frame=1 reliable=1 sourceFallback=0',
                          'fgs-model frame=0 reliable=1 sourceFallback=0'])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.analyze(['fgs-model frame=0 reliable=1 sourceFallback=0'] * 2)

    def test_contradictory_or_unknown_diagnostics_rejected(self):
        for line in [
            'fgs-model frame=0 reliable=1 sourceFallback=1',
            'fgs-model frame=0 reliable=1 sourceFallback=0 trace=1 sourceReasons=64',
            'fgs-model frame=0 reliable=0 sourceFallback=1 trace=1 sourceReasons=1024',
            'fgs-model frame=0 reliable=0 sourceFallback=1 trace=2 sourceReasons=1',
        ]:
            with self.subTest(line=line), self.assertRaises(ValueError):
                self.analyze([line])


if __name__ == '__main__':
    unittest.main()
