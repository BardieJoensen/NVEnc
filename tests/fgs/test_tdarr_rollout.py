#!/usr/bin/env python3
"""The ordinary rollout must preserve normal policy and cannot bypass validation."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/fgs'))
import build_tdarr_rollout as rollout
from test_tdarr_pilot import fixture


def original():
    flow = fixture()
    for n in flow['flowPlugins']:
        if n['id'] in ('sizeCheck_001', 'sizeCheckRelaxed_001'):
            n['pluginName'] = 'policySizeGate'
            n['inputsDB'] = {'maxPercent': '120' if 'Relaxed' in n['id'] else '95'}
    return flow


class OrdinaryRolloutTests(unittest.TestCase):
    def test_an_already_deployed_flow_can_receive_a_later_encoder(self):
        deployed, _ = rollout.build_flow(original())
        saved = copy.deepcopy(deployed)
        rebuilt, checks = rollout.build_flow(deployed)
        self.assertEqual(deployed, saved)
        self.assertEqual(rebuilt, deployed)
        self.assertFalse(checks['optional_retention'])
        reviewed, _ = rollout.build_flow(deployed, review=True)
        self.assertFalse(any(n['pluginName'] == 'replaceOriginalFile' for n in reviewed['flowPlugins']))
        next(n for n in deployed['flowPlugins'] if n['id'] == rollout.DOVI)['pluginName'] = 'unrecognized'
        with self.assertRaises(ValueError):
            rollout.build_flow(deployed)

    def test_quality_sampling_saving_thresholds_and_stream_copy_routes_stay_unchanged(self):
        source = original()
        saved = copy.deepcopy(source)
        flow, checks = rollout.build_flow(source)
        self.assertEqual(source, saved)
        nodes = {n['id']: n for n in flow['flowPlugins']}
        for n in source['flowPlugins']:
            if n['id'] not in ('dvhdrDetect_001', 'sizeCheck_001', 'sizeCheckRelaxed_001'):
                self.assertEqual(nodes[n['id']], n)
            if n['id'] in ('sizeCheck_001', 'sizeCheckRelaxed_001'):
                self.assertEqual(nodes[n['id']]['inputsDB'], n['inputsDB'])
        routes = {(e['source'], e['sourceHandle']): e['target'] for e in flow['flowEdges']}
        for e in source['flowEdges']:
            if e['source'] not in ('sizeCheck_001', 'sizeCheckRelaxed_001') or e['sourceHandle'] != '1':
                self.assertEqual(routes[e['source'], e['sourceHandle']], e['target'])
        self.assertFalse(checks['optional_retention'])

    def test_review_cannot_replace_or_notify_and_rejection_returns_original(self):
        flow, checks = rollout.build_flow(original(), review=True)
        self.assertEqual(checks['terminals'], sorted([rollout.KEEP, rollout.REVIEW]))
        self.assertFalse(any(n['pluginName'] == 'replaceOriginalFile' for n in flow['flowPlugins']))
        for e in flow['flowEdges']:
            if e['source'] in ('sizeCheck_001', 'sizeCheckRelaxed_001', 'videoSample_001') and e['sourceHandle'] == '2':
                self.assertEqual(e['target'], rollout.KEEP)

    def test_bypassing_saving_dovi_or_final_validator_is_rejected(self):
        flow, _ = rollout.build_flow(original())
        for source, target in [('mainStart_001', 'validateOutput_001'),
                               ('sizeCheck_001', 'replaceOrig_001'),
                               (rollout.DOVI, 'replaceOrig_001')]:
            altered = copy.deepcopy(flow)
            next(e for e in altered['flowEdges'] if e['source'] == source and e['sourceHandle'] == '1')['target'] = target
            with self.assertRaises(ValueError):
                rollout.verify(altered)

    def test_optional_retention_or_changed_sampler_cannot_slip_into_ordinary_rollout(self):
        for change_sampler in (False, True):
            flow = original()
            for n in flow['flowPlugins']:
                if n['id'] == 'nvenccEncode_001':
                    n['inputsDB']['cliArguments'] += ' --retain=auto'
                if change_sampler and n['id'] == 'videoSample_001':
                    n['inputsDB']['encoderArguments'] += ' --retain=auto'
            with self.assertRaises(ValueError):
                rollout.build_flow(flow)


if __name__ == '__main__':
    unittest.main()
