#!/usr/bin/env python3
"""Offline routing regressions: rejected or unvalidated output cannot promote."""
import copy
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location('pilot', Path(__file__).resolve().parents[2] / 'tools/fgs/build_tdarr_pilot.py')
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


def fixture():
    routes = [
        ('inputFile_001', 1, 'dvhdrDetect_001'),
        ('dvhdrDetect_001', 1, 'mapQvbr_001'),
        ('mapQvbr_001', 1, 'videoSample_001'),
        ('videoSample_001', 1, 'postExecCheck_001'),
        ('videoSample_001', 2, 'streamPolicyCheck_001'),
        ('postExecCheck_001', 1, 'nvenccEncode_001'),
        ('postExecCheck_001', 2, 'mainStart_001'),
        ('mainStart_001', 1, 'sizeCheck_001'),
        ('nvenccEncode_001', 1, 'nvenccCheck_001'),
        ('nvenccCheck_001', 1, 'dvhdrGate_001'),
        ('nvenccCheck_001', 2, 'mainStart_001'),
        ('dvhdrGate_001', 1, 'sizeCheckRelaxed_001'),
        ('dvhdrGate_001', 2, 'sizeCheck_001'),
        ('sizeCheck_001', 1, 'validateOutput_001'),
        ('sizeCheck_001', 2, 'setOriginal_001'),
        ('sizeCheckRelaxed_001', 1, 'validateOutput_001'),
        ('sizeCheckRelaxed_001', 2, 'setOriginal_001'),
        ('setOriginal_001', 1, 'streamPolicyCheck_001'),
        ('streamPolicyCheck_001', 1, 'scReplace_001'),
        ('validateOutput_001', 1, 'replaceOrig_001'),
        ('replaceOrig_001', 1, 'notifyEmby_001'),
    ]
    nodes = {name: dict(id=name, pluginName='customFunction', fpEnabled=True, inputsDB={})
             for source, _, target in routes for name in (source, target)}
    for name in ('replaceOrig_001', 'scReplace_001'):
        nodes[name]['pluginName'] = 'replaceOriginalFile'
    nodes['nvenccEncode_001']['inputsDB'] = dict(cliArguments=pilot.FGS_OLD + ' -o output.mkv')
    nodes['videoSample_001']['inputsDB'] = dict(encoderArguments=pilot.FGS_OLD + ' -o output.mkv')
    nodes['dvhdrDetect_001']['inputsDB'] = dict(code="""  if (dv) {
    if (dvElType === 'FEL') {
      // only the per-pixel FEL refinement is lost.
    }
  }

  let hdr10plus = false;""")
    return dict(_id='production', name='Production', flowPlugins=list(nodes.values()),
                flowEdges=[pilot.edge(*r) for r in routes])


class PilotRoutingTests(unittest.TestCase):
    def test_review_contains_no_replacement_or_notification(self):
        original = fixture()
        before = copy.deepcopy(original)
        flow, report = pilot.build_flow(original, '/reference.json')
        self.assertEqual(original, before)
        self.assertEqual(report['terminals'], sorted([pilot.KEEP, pilot.ACCEPT]))
        ids = {n['id'] for n in flow['flowPlugins']}
        self.assertNotIn('replaceOrig_001', ids)
        self.assertNotIn('scReplace_001', ids)
        self.assertNotIn('mainStart_001', ids)
        self.assertNotIn('notifyEmby_001', ids)

    def test_promotion_requires_every_gate_on_every_path(self):
        flow, report = pilot.build_flow(fixture(), '/reference.json', True)
        self.assertTrue(report['promotion_enabled'])
        for source, target in [
            ('mapQvbr_001', 'nvenccEncode_001'),
            ('sizeCheck_001', 'validateOutput_001'),
            (pilot.CHECK, 'replaceOrig_001'),
            (pilot.SELECT, 'replaceOrig_001'),
        ]:
            changed = copy.deepcopy(flow)
            next(e for e in changed['flowEdges'] if e['source'] == source and e['sourceHandle'] == '1')['target'] = target
            with self.assertRaises(ValueError):
                pilot.verify_graph(changed, True)

    def test_rejection_cannot_enter_the_stream_policy_fallback(self):
        flow, _ = pilot.build_flow(fixture(), '/reference.json')
        next(e for e in flow['flowEdges'] if e['source'] == pilot.CHECK and e['sourceHandle'] == '2')['target'] = pilot.ACCEPT
        with self.assertRaises(ValueError):
            pilot.verify_graph(flow, False)

    def test_unknown_layout_or_divergent_sampler_is_refused(self):
        flow = fixture()
        next(n for n in flow['flowPlugins'] if n['id'] == 'videoSample_001')['inputsDB']['encoderArguments'] += ' --qvbr 51'
        with self.assertRaisesRegex(ValueError, 'settings differ'):
            pilot.build_flow(flow, '/reference.json')
        with self.assertRaises(ValueError):
            pilot.preserve_fel('new unrelated detector')

    def test_fel_conversion_is_replaced_with_preservation(self):
        flow, _ = pilot.build_flow(fixture(), '/reference.json')
        code = next(n for n in flow['flowPlugins'] if n['id'] == 'dvhdrDetect_001')['inputsDB']['code']
        self.assertIn("return keepVideoOriginal('Dolby Vision FEL", code)
        self.assertNotIn('refinement is lost', code)

    def test_duplicate_routes_and_cycles_are_refused(self):
        flow, _ = pilot.build_flow(fixture(), '/reference.json')
        flow['flowEdges'].append(copy.deepcopy(flow['flowEdges'][0]))
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            pilot.verify_graph(flow, False)
        flow['flowEdges'].pop()
        flow['flowEdges'].append(pilot.edge(pilot.KEEP, 1, 'inputFile_001'))
        with self.assertRaisesRegex(ValueError, 'cycle'):
            pilot.verify_graph(flow, False)


if __name__ == '__main__':
    unittest.main()
