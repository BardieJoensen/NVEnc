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

    def test_late_source_protection_and_synthesis_recovery_have_distinct_reasons(self):
        result = self.analyze([
            'fgs-model frame=0 reliable=0 sourceFallback=1 quietSource=1 recoveryHeld=0 trace=1 sourceReasons=1024',
            'fgs-model frame=1 reliable=0 sourceFallback=0 quietSource=0 recoveryHeld=1 trace=1 sourceReasons=2048',
            'fgs-model frame=2 reliable=1 sourceFallback=0 quietSource=0 recoveryHeld=0 trace=1 sourceReasons=0',
        ], 3)
        self.assertTrue(result['complete'])
        self.assertEqual(result['counters']['source_preserved'], 2)
        self.assertEqual(result['counters']['fidelity_source_fallback'], 1)
        self.assertEqual(result['source_reasons']['source_support_rejected'], 1)
        self.assertEqual(result['source_reasons']['synthesis_recovery_hold'], 1)
        self.assertEqual(result['source_reasons']['recovery_hold'], 0)
        self.assertEqual(result['source_reason_overlap']['unknown_source_frames'], 0)

    def test_fresh_coupling_is_distinct_from_failed_fit(self):
        fields = dict(recovered='0', covariance='1', colourIndependent='1', trace='1',
                      covarianceAttempted='1', minFramesEligible='1', fitAttempted='1',
                      fitSucceeded='1', heldCb='254', heldCr='254', freshCb='5', freshCr='0')
        self.assertEqual(first_covariance_blocker(fields), 'fresh_colour_rejected')
        fields.update(fitSucceeded='0', freshCb='255', freshCr='255')
        self.assertEqual(first_covariance_blocker(fields), 'model_fit_rejected')
        fields.update(covariance='0', fitAttempted='0')
        self.assertEqual(first_covariance_blocker(fields), 'covariance_evidence_rejected')

    def test_equal_marginal_counts_can_hide_different_obstacles(self):
        def report(masks):
            return self.analyze([
                f'fgs-model frame={i} reliable={int(mask == 0)} '
                f'sourceFallback={int(mask != 0)} trace=1 sourceReasons={mask}'
                for i, mask in enumerate(masks)], 4)

        together = report([80, 80, 0, 0])
        separate = report([16, 16, 64, 64])
        self.assertEqual(together['source_reasons'], separate['source_reasons'])
        self.assertEqual(together['source_reason_overlap'], dict(
            unknown_source_frames=0, single_recorded_reason_frames=0,
            multiple_recorded_reason_frames=2, combinations=[dict(
                mask=80, reasons=['local_mismatch', 'covariance_recovery_rejected'], frames=2)]))
        self.assertEqual(separate['source_reason_overlap']['single_recorded_reason_frames'], 4)
        self.assertEqual(separate['source_reason_overlap']['multiple_recorded_reason_frames'], 0)

    def test_legacy_recovery_is_joined_to_later_checks_without_inventing_masks(self):
        result = self.analyze([
            'fgs-local-covariance frame=0 recovered=1 covariance=1 colourIndependent=1',
            'fgs-local-strength frame=0 recovered=1 points=14',
            'fgs-local-strength frame=0 mismatch=1 valid=1',
            'fgs-local-chroma frame=0 plane=2 source=1 independent=0',
            'fgs-model frame=0 reliable=0 sourceFallback=1',
            'fgs-local-covariance frame=1 recovered=1 covariance=1 colourIndependent=1',
            'fgs-local-strength frame=1 recovered=1 points=14',
            'fgs-model frame=1 reliable=1 sourceFallback=0',
            'fgs-model frame=2 reliable=0 sourceFallback=0',
        ], 3)
        failed, passed, unknown = sorted(result['decision_profiles'], key=lambda row: row['first_frame'])
        self.assertEqual(failed['covariance_first_blocker'], 'recovered')
        self.assertTrue(failed['local_mismatch_logged'])
        self.assertEqual(failed['rejected_restore_planes'], [2])
        self.assertEqual(failed['component_restore_checks'], {'2': dict(independent=False, reason=None)})
        self.assertEqual(failed['outcome'], 'source_preserved')
        self.assertIsNone(failed['source_reason_mask'])
        self.assertIsNone(failed['source_reasons'])
        self.assertIsNone(failed['covariance_colour_reasons'])
        self.assertEqual(passed['covariance_first_blocker'], 'recovered')
        self.assertEqual(passed['outcome'], 'reliable_model')
        self.assertFalse(passed['local_mismatch_logged'])
        self.assertIsNone(unknown['covariance_first_blocker'])
        self.assertEqual(result['source_reason_overlap']['unknown_source_frames'], 2)
        self.assertEqual(sum(row['frames'] for row in result['decision_profiles']), 3)

    def test_colour_subconditions_remain_attached_to_their_frames(self):
        lines = []
        for frame, reason in enumerate((6, 10, 6)):
            lines.extend([
                f'fgs-local-covariance frame={frame} recovered=0 covariance=0 colourIndependent=0 '
                'trace=1 covarianceAttempted=0 minFramesEligible=1 fitAttempted=0 fitSucceeded=0 '
                f'heldCb={reason} heldCr=254 freshCb=255 freshCr=255',
                f'fgs-model frame={frame} reliable=0 sourceFallback=1 trace=1 sourceReasons=64',
            ])
        result = self.analyze(lines, 3)
        first, second = result['decision_profiles']
        self.assertEqual(first['frames'], 2)
        self.assertEqual(first['covariance_colour_reasons']['heldCb'], 'insufficient_observations')
        self.assertEqual(second['covariance_colour_reasons']['heldCb'], 'spatial_correlation')
        self.assertEqual(first['longest_run']['frames'], 1)
        self.assertEqual(first['last_frame'], 2)
        self.assertEqual(result['source_reason_overlap']['combinations'][0]['frames'], 3)

    def test_component_reason_is_joined_and_unknown_frames_stay_separate(self):
        result = self.analyze([
            'fgs-local-chroma frame=0 plane=1 independent=0 trace=1 reason=5',
            'fgs-model frame=0 reliable=0 sourceFallback=1 trace=1 sourceReasons=32',
            'fgs-local-chroma frame=1 plane=1 independent=0 trace=1 reason=6',
            'fgs-model frame=1 reliable=0 sourceFallback=1 trace=1 sourceReasons=32',
            'fgs-local-chroma frame=2 plane=1 independent=1 trace=1 reason=0',
            'fgs-model frame=2 reliable=1 sourceFallback=0 trace=1 sourceReasons=0',
            'fgs-model frame=3 reliable=0 sourceFallback=0',
        ], 4)
        profiles = sorted(result['decision_profiles'], key=lambda row: row['first_frame'])
        self.assertEqual(profiles[0]['component_restore_checks']['1']['reason'], 'signalled_coupling')
        self.assertEqual(profiles[1]['component_restore_checks']['1']['reason'], 'insufficient_observations')
        self.assertEqual(profiles[2]['rejected_restore_planes'], [])
        self.assertTrue(profiles[2]['component_restore_checks']['1']['independent'])
        self.assertEqual(result['source_reason_overlap']['unknown_source_frames'], 1)
        self.assertEqual(result['source_reason_overlap']['single_recorded_reason_frames'], 2)

    def test_profile_runs_stop_at_gaps_and_include_the_final_run(self):
        result = self.analyze([
            f'fgs-model frame={frame} reliable=0 sourceFallback=1 trace=1 sourceReasons=16'
            for frame in (0, 1, 3, 4, 5)], 6)
        self.assertFalse(result['complete'])
        self.assertEqual(result['missing_frame_decisions'], 1)
        profile, = result['decision_profiles']
        self.assertEqual(profile['frames'], 5)
        self.assertEqual(profile['longest_run'], dict(first_frame=3, last_frame=5, frames=3))

    def test_profile_run_does_not_bridge_another_decision(self):
        result = self.analyze([
            f'fgs-model frame={frame} reliable=0 sourceFallback=1 trace=1 sourceReasons={mask}'
            for frame, mask in enumerate((16, 16, 80, 16, 16))], 5)
        profile = result['decision_profiles'][0]
        self.assertEqual(profile['frames'], 4)
        self.assertEqual(profile['longest_run'], dict(first_frame=0, last_frame=1, frames=2))

    def test_invalid_component_plane_cannot_enter_a_profile(self):
        for plane in ('0', '3', '-1'):
            with self.subTest(plane=plane), self.assertRaisesRegex(ValueError, 'plane'):
                self.analyze([
                    f'fgs-local-chroma frame=0 plane={plane} source=1 independent=0',
                    'fgs-model frame=0 reliable=0 sourceFallback=1',
                ])

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
            'fgs-model frame=0 reliable=0 sourceFallback=1 trace=1 sourceReasons=4096',
            'fgs-model frame=0 reliable=0 sourceFallback=0 recoveryHeld=1 trace=1 sourceReasons=0',
            'fgs-model frame=0 reliable=0 sourceFallback=1 trace=2 sourceReasons=1',
        ]:
            with self.subTest(line=line), self.assertRaises(ValueError):
                self.analyze([line])


if __name__ == '__main__':
    unittest.main()
