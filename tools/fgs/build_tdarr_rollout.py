#!/usr/bin/env python3
"""Bundle ordinary Tdarr reliability changes at the existing retention setting.

The measured optional-retention flow stays separate. No baseline encode, source
hash pass, or sampled old-encoder size estimate is added to ordinary jobs.
This tool only writes a new bundle; activation is a separate operation.
"""
import argparse
import copy
import json
from pathlib import Path
import re

from build_tdarr_pilot import FGS_OLD, check_size_validation_path, edge, install_plugins, preserve_fel, sha

DOVI = 'rolloutDovi_001'
KEEP = 'rolloutKeep_001'
REVIEW = 'rolloutReview_001'


def verify(flow, review=False):
    nodes = {n['id']: n for n in flow['flowPlugins']}
    routes = {(e['source'], str(e['sourceHandle'])): e['target'] for e in flow['flowEdges']}
    if len(nodes) != len(flow['flowPlugins']) or len(routes) != len(flow['flowEdges']):
        raise ValueError('Duplicate node or ambiguous route')
    for (source, _), target in routes.items():
        if source not in nodes or target not in nodes:
            raise ValueError('Dangling route')
    encoder = nodes['nvenccEncode_001']['inputsDB']['cliArguments']
    if encoder != nodes['videoSample_001']['inputsDB']['encoderArguments']:
        raise ValueError('Sample and full encoder settings differ')
    if encoder.count(FGS_OLD + ' ') != 1 or 'retain=' in encoder:
        raise ValueError('Ordinary flow must retain the existing default settings')
    for node_id in ('sizeCheck_001', 'sizeCheckRelaxed_001'):
        if nodes[node_id]['pluginName'] != 'fgsSourceSize' or routes[(node_id, '1')] != DOVI:
            raise ValueError('Source saving must precede the Dolby Vision guard')
    if routes.get((DOVI, '1')) != 'validateOutput_001':
        raise ValueError('Dolby Vision check must precede the existing validator')
    seen, terminals = set(), set()

    def walk(node_id, sized=False, dovi=False, validated=False, ancestors=()):
        if node_id in ancestors:
            raise ValueError('Flow contains a cycle')
        state = node_id, sized, dovi, validated
        if state in seen:
            return
        seen.add(state)
        n = nodes[node_id]
        if not n.get('fpEnabled', True):
            raise ValueError('Disabled node needs explicit review')
        if node_id == 'validateOutput_001' and not (sized and dovi):
            raise ValueError('AV1 validation bypasses saving or Dolby Vision checks')
        if node_id in ('replaceOrig_001', REVIEW) and not (sized and dovi and validated):
            raise ValueError('Encoded candidate bypasses required acceptance checks')
        if review and (n['pluginName'] == 'replaceOriginalFile' or node_id.startswith('notify')):
            raise ValueError('Review graph may not replace library files or notify')
        outgoing = [(output, target) for (source, output), target in routes.items() if source == node_id]
        if not outgoing:
            terminals.add(node_id)
        for output, target in outgoing:
            walk(target, sized or (node_id in ('sizeCheck_001', 'sizeCheckRelaxed_001') and output == '1'),
                 dovi or (node_id == DOVI and output == '1'),
                 validated or (node_id == 'validateOutput_001' and output == '1'), (*ancestors, node_id))
    walk('inputFile_001')
    return dict(reachable_nodes=len({s[0] for s in seen}), terminals=sorted(terminals),
                optional_retention=False, review=review,
                required_encoded_gates=['source-relative saving', 'Dolby Vision normalization', 'existing final validator'])


def build_flow(original, review=False):
    flow = copy.deepcopy(original)
    nodes = {n['id']: n for n in flow['flowPlugins']}
    nodes['dvhdrDetect_001']['inputsDB']['code'] = preserve_fel(nodes['dvhdrDetect_001']['inputsDB']['code'])
    for node_id in ('sizeCheck_001', 'sizeCheckRelaxed_001'):
        n = nodes[node_id]
        if (n['pluginName'] != 'policySizeGate'
                and not (n['pluginName'] == 'fgsSourceSize' and n.get('sourceRepo') == 'Local'
                         and n.get('version') == '1.0.0')):
            raise ValueError('Unexpected original size policy')
        n.update(sourceRepo='Local', pluginName='fgsSourceSize', version='1.0.0')
    routes = {(e['source'], str(e['sourceHandle'])): e['target'] for e in flow['flowEdges']}
    if len(routes) != len(flow['flowEdges']):
        raise ValueError('Ambiguous original routing')
    for node_id in ('sizeCheck_001', 'sizeCheckRelaxed_001'):
        check_size_validation_path(nodes, routes, node_id)
        routes[(node_id, '1')] = DOVI
    nodes[DOVI] = dict(id=DOVI, name='Check AV1 Dolby Vision normalization', sourceRepo='Local',
        pluginName='fgsDoviGuard', version='1.0.0', fpEnabled=True,
        position=dict(x=1100, y=1300), inputsDB={})
    routes[(DOVI, '1')] = 'validateOutput_001'
    if review:
        flow['_id'] = 'FGSOrdinaryReview20260909'
        flow['name'] = 'FGS reliability rollout — review only'
        nodes[KEEP] = dict(id=KEEP, name='Keep original', sourceRepo='Community',
            pluginName='setWorkingFile', version='1.0.0', fpEnabled=True,
            position=dict(x=1400, y=900), inputsDB=dict(source='originalFile', customPath=''))
        nodes[REVIEW] = dict(id=REVIEW, name='Stage validated ordinary candidate', sourceRepo='Local',
            pluginName='fgsStageReview', version='1.0.0', fpEnabled=True,
            position=dict(x=1100, y=1450), inputsDB=dict(outputDirectory='/fgs-review', acceptancePolicy='source-size'))
        routes[('validateOutput_001', '1')] = REVIEW
        # Stream-policy-only changes were already tested separately. In this
        # review graph, skipped or rejected video always returns its original.
        for key, target in list(routes.items()):
            if target in ('streamPolicyCheck_001', 'setOriginal_001'):
                routes[key] = KEEP
    reachable, pending = set(), ['inputFile_001']
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        reachable.add(name)
        pending.extend(target for (source, _), target in routes.items() if source == name)
    flow['flowPlugins'] = [n for name, n in nodes.items() if name in reachable]
    flow['flowEdges'] = [edge(source, output, target) for (source, output), target in routes.items() if source in reachable]
    return flow, verify(flow, review)


def bundle(flow_path, expected_flow_sha, candidate_image, candidate_sha, baseline_image, output):
    raw = flow_path.read_bytes()
    if sha(raw) != expected_flow_sha:
        raise ValueError('Original flow changed since review')
    if not all(re.fullmatch(r'sha256:[a-f0-9]{64}', image) for image in (candidate_image, baseline_image)):
        raise ValueError('Immutable local image IDs required')
    if not re.fullmatch(r'[a-f0-9]{64}', candidate_sha):
        raise ValueError('Candidate binary SHA-256 required')
    output.mkdir()
    checks = {}
    for review in (False, True):
        name = 'ordinary-review.json' if review else 'ordinary-production.json'
        flow, checks[name] = build_flow(json.loads(raw), review)
        (output / name).write_text(json.dumps(flow, indent=2) + '\n')
    (output / 'rollback-flow.json').write_bytes(raw)
    install_plugins(output / 'FlowPlugins')
    for name, image in [('candidate-compose.json', candidate_image), ('rollback-compose.json', baseline_image)]:
        (output / name).write_text(json.dumps({'services': {'tdarr-node': {'image': image}}}, indent=2) + '\n')
    manifest = dict(schema='fgs_tdarr_ordinary_rollout_v1', candidate_image=candidate_image,
        candidate_sha256=candidate_sha, baseline_image=baseline_image, baseline_flow_sha256=expected_flow_sha,
        activation='none', policy='Existing retain=0 and source-relative 95%/120% rules; measured optional-retention pilot remains separate',
        graph_checks=checks, files={str(p.relative_to(output)): sha(p.read_bytes()) for p in output.rglob('*') if p.is_file()})
    (output / 'bundle.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--flow', type=Path, required=True)
    parser.add_argument('--expected-flow-sha256', required=True)
    parser.add_argument('--candidate-image', required=True)
    parser.add_argument('--candidate-sha256', required=True)
    parser.add_argument('--baseline-image', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(bundle(args.flow, args.expected_flow_sha256, args.candidate_image,
                            args.candidate_sha256, args.baseline_image, args.output), indent=2))
