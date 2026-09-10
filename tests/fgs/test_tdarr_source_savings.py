#!/usr/bin/env python3
"""Reject guard bypasses and accidental legacy size allowances in fidelity flows."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/fgs'))
import build_tdarr_source_savings as savings
from test_tdarr_pilot import fixture, pilot

SHA = 'a' * 64


class SourceSavingsTests(unittest.TestCase):
    def test_review_and_promotion_preserve_input_and_require_savings(self):
        original = fixture()
        saved = copy.deepcopy(original)
        for promotion in [False, True]:
            flow, checks = savings.build_flow(original, SHA, promotion)
            self.assertEqual(original, saved)
            self.assertTrue(checks['optional_retention'])
            self.assertFalse(checks['measured_baseline_required'])
            self.assertFalse(checks['source_hash_pass'])
            self.assertEqual(checks['maximum_source_relative_ratio'], .95)
            self.assertEqual(checks['promotion_enabled'], promotion)
            self.assertFalse(any(n['pluginName'] == 'fgsMeasuredBudget' for n in flow['flowPlugins']))
        flow, _ = savings.build_flow(original, SHA)
        self.assertFalse(any(n['pluginName'] == 'replaceOriginalFile' or n['id'].startswith('notify')
                             for n in flow['flowPlugins']))
        detector = next(n for n in flow['flowPlugins'] if n['id'] == 'dvhdrDetect_001')
        self.assertIn("return keepVideoOriginal('Dolby Vision FEL", detector['inputsDB']['code'])

    def test_each_acceptance_gate_is_required(self):
        flow, _ = savings.build_flow(fixture(), SHA, True)
        for source, target in [
            ('mapQvbr_001', 'videoSample_001'),
            ('videoSample_001', 'sizeCheck_001'),
            ('nvenccCheck_001', savings.DOVI),
            ('sizeCheck_001', savings.DOVI),
            ('sizeCheck_001', 'validateOutput_001'),
            (savings.DOVI, 'replaceOrig_001'),
        ]:
            with self.subTest(source=source):
                changed = copy.deepcopy(flow)
                next(e for e in changed['flowEdges'] if e['source'] == source and e['sourceHandle'] == '1')['target'] = target
                with self.assertRaises(ValueError):
                    savings.verify(changed, True)

    def test_failure_and_rejection_paths_keep_the_original(self):
        flow, _ = savings.build_flow(fixture(), SHA)
        for source in (savings.PREPARE, savings.CHECK, *savings.SIZE_NODES,
                       'videoSample_001', 'postExecCheck_001', 'nvenccCheck_001'):
            with self.subTest(source=source):
                changed = copy.deepcopy(flow)
                next(e for e in changed['flowEdges'] if e['source'] == source and e['sourceHandle'] == '2')['target'] = savings.ACCEPT
                with self.assertRaises(ValueError):
                    savings.verify(changed)

    def test_legacy_120_percent_allowance_and_disabled_guards_are_rejected(self):
        flow, _ = savings.build_flow(fixture(), SHA)
        for name in savings.SIZE_NODES:
            changed = copy.deepcopy(flow)
            next(n for n in changed['flowPlugins'] if n['id'] == name)['inputsDB']['maxPercent'] = '120'
            with self.assertRaises(ValueError):
                savings.verify(changed)
        for name in (savings.PREPARE, savings.CHECK, *savings.SIZE_NODES,
                     savings.DOVI, 'validateOutput_001', 'nvenccEncode_001'):
            changed = copy.deepcopy(flow)
            next(n for n in changed['flowPlugins'] if n['id'] == name)['fpEnabled'] = False
            with self.assertRaises(ValueError):
                savings.verify(changed)

    def test_sampler_and_encoder_must_use_the_qualified_mode(self):
        flow, _ = savings.build_flow(fixture(), SHA)
        changed = copy.deepcopy(flow)
        next(n for n in changed['flowPlugins'] if n['id'] == 'videoSample_001')['inputsDB']['encoderArguments'] += ' --qvbr 51'
        with self.assertRaises(ValueError):
            savings.verify(changed)
        for change in ('old-mode', 'duplicate-option'):
            changed = copy.deepcopy(flow)
            for n in changed['flowPlugins']:
                for key in ('cliArguments', 'encoderArguments'):
                    if key in n['inputsDB']:
                        text = n['inputsDB'][key]
                        n['inputsDB'][key] = (text.replace(pilot.FGS_NEW, pilot.FGS_OLD)
                            if change == 'old-mode' else text + ' --av1-film-grain=retain=0')
            with self.assertRaises(ValueError):
                savings.verify(changed)

    def test_same_qualified_encoder_is_required_at_both_job_boundaries(self):
        flow, _ = savings.build_flow(fixture(), SHA)
        for change in ('bad-sha', 'different-sha', 'wrong-phase', 'wrong-plugin'):
            changed = copy.deepcopy(flow)
            node = next(n for n in changed['flowPlugins'] if n['id'] == savings.CHECK)
            if change == 'bad-sha':
                node['inputsDB']['expectedEncoderSha256'] = ''
            if change == 'different-sha':
                node['inputsDB']['expectedEncoderSha256'] = 'b' * 64
            if change == 'wrong-phase':
                node['inputsDB']['phase'] = 'prepare'
            if change == 'wrong-plugin':
                node['pluginName'] = 'fgsMeasuredBudget'
            with self.assertRaises(ValueError):
                savings.verify(changed)

    def test_review_receipt_requires_source_size_evidence(self):
        flow, _ = savings.build_flow(fixture(), SHA)
        next(n for n in flow['flowPlugins'] if n['id'] == savings.ACCEPT)['inputsDB']['acceptancePolicy'] = 'measured'
        with self.assertRaises(ValueError):
            savings.verify(flow)

    def test_source_retention_cannot_continue_to_other_processing(self):
        flow, _ = savings.build_flow(fixture(), SHA)
        flow['flowEdges'].append(pilot.edge(savings.KEEP, 1, savings.DOVI))
        with self.assertRaises(ValueError):
            savings.verify(flow)


if __name__ == '__main__':
    unittest.main()
