#!/usr/bin/env python3
"""Prepare optional detail retention with a strict source-relative savings gate.

This is a separate policy from the measured old-encoder budget. Both size paths
require at least 5% savings against the original video plus identical retained
tracks. There is no full baseline encode or source hash pass. This builder only
writes a new bundle; the runtime must be pinned and verified before activation.
"""
import argparse
import json
from pathlib import Path
import re
import shutil

from build_tdarr_pilot import (
    ACCEPT, CHECK, DOVI, FGS_NEW, KEEP, PREPARE, SELECT,
    build_flow as measured_flow, edge, install_plugins, sha,
)

SIZE_NODES = ('sizeCheck_001', 'sizeCheckRelaxed_001')


def verify(flow, promotion=False):
    nodes = {n['id']: n for n in flow['flowPlugins']}
    routes = {(e['source'], str(e['sourceHandle'])): e['target'] for e in flow['flowEdges']}
    if len(nodes) != len(flow['flowPlugins']) or len(routes) != len(flow['flowEdges']):
        raise ValueError('Duplicate node or ambiguous route')
    if any(source not in nodes or target not in nodes for (source, _), target in routes.items()):
        raise ValueError('Dangling route')
    if any(n['pluginName'] == 'fgsMeasuredBudget' for n in nodes.values()):
        raise ValueError('Source-savings policy may not require a measured baseline')
    encoder = nodes['nvenccEncode_001']['inputsDB']['cliArguments']
    if encoder != nodes['videoSample_001']['inputsDB']['encoderArguments']:
        raise ValueError('Sample and full encoder settings differ')
    if (encoder.count(FGS_NEW + ' ') != 1
            or len(re.findall(r'(?:^|\s)--av1-film-grain(?:=|\s)', encoder)) != 1):
        raise ValueError('Expected the qualified automatic-retention settings')
    expected_sha = nodes[PREPARE]['inputsDB'].get('expectedEncoderSha256', '')
    if not re.fullmatch(r'[a-f0-9]{64}', expected_sha):
        raise ValueError('A qualified encoder SHA-256 is required')
    for name, phase in [(PREPARE, 'prepare'), (CHECK, 'check')]:
        n = nodes[name]
        if (n.get('sourceRepo') != 'Local' or n['pluginName'] != 'fgsSourceGuard'
                or n.get('version') != '1.0.0'
                or n['inputsDB'] != dict(phase=phase, expectedEncoderSha256=expected_sha)):
            raise ValueError('Source and build guards must use the same qualified encoder')
    for name in SIZE_NODES:
        n = nodes[name]
        if (n.get('sourceRepo') != 'Local' or n['pluginName'] != 'fgsSourceSize'
                or n.get('version') != '1.0.0' or n['inputsDB'] != {'maxPercent': '95'}):
            raise ValueError('Both source-size paths must require 5% savings')
        if routes.get((name, '1')) != CHECK:
            raise ValueError('Source saving must precede the final source/build check')
    if routes.get((CHECK, '1')) != DOVI:
        raise ValueError('Source/build check must precede Dolby Vision validation')
    guard = nodes[DOVI]
    if (guard.get('sourceRepo') != 'Local' or guard['pluginName'] != 'fgsDoviGuard'
            or guard.get('version') != '1.0.0' or guard['inputsDB']
            or routes.get((DOVI, '1')) != 'validateOutput_001'):
        raise ValueError('Expected the existing Dolby Vision normalization guard')
    for name in (PREPARE, CHECK, *SIZE_NODES, 'videoSample_001', 'postExecCheck_001', 'nvenccCheck_001'):
        if routes.get((name, '2')) != KEEP:
            raise ValueError('Rejected or failed video must retain its source')
    if any(source == KEEP for source, _ in routes):
        raise ValueError('Source retention must terminate the flow')
    if not promotion:
        accepted = nodes[ACCEPT]
        if (accepted['pluginName'] != 'fgsStageReview'
                or accepted['inputsDB'].get('acceptancePolicy') != 'source-size'):
            raise ValueError('Review staging must verify the actual source-size decision')
    visited, terminals = set(), set()

    def walk(name, prepared=False, encoded=False, sized=False, checked=False,
             dovi=False, validated=False, ancestors=()):
        if name in ancestors:
            raise ValueError('Flow contains a cycle')
        state = name, prepared, encoded, sized, checked, dovi, validated
        if state in visited:
            return
        visited.add(state)
        n = nodes[name]
        if not n.get('fpEnabled', True):
            raise ValueError('Disabled node needs explicit review')
        if name in ('videoSample_001', 'nvenccEncode_001') and not prepared:
            raise ValueError('Encoding bypasses source/build preparation')
        if name == CHECK and not (prepared and encoded and sized):
            raise ValueError('Source/build check bypasses preparation, encoding or savings')
        if name == DOVI and not checked:
            raise ValueError('Dolby Vision check bypasses the final source/build check')
        if name == 'validateOutput_001' and not (prepared and encoded and sized and checked and dovi):
            raise ValueError('Validation bypasses required source, encoding, savings or Dolby Vision checks')
        if (name == ACCEPT or n['pluginName'] == 'replaceOriginalFile') and not (
                prepared and encoded and sized and checked and dovi and validated):
            raise ValueError('Candidate acceptance bypasses required checks')
        if not promotion and (n['pluginName'] == 'replaceOriginalFile' or name.startswith('notify')):
            raise ValueError('Review flow may not replace or notify library files')
        outgoing = [(output, target) for (source, output), target in routes.items() if source == name]
        if not outgoing:
            terminals.add(name)
        for output, target in outgoing:
            walk(target, prepared or (name == PREPARE and output == '1'),
                 encoded or (name == 'nvenccEncode_001' and output == '1'),
                 sized or (name in SIZE_NODES and output == '1'),
                 checked or (name == CHECK and output == '1'),
                 dovi or (name == DOVI and output == '1'),
                 validated or (name == 'validateOutput_001' and output == '1'), (*ancestors, name))
    walk('inputFile_001')
    if not promotion and terminals != {KEEP, ACCEPT}:
        raise ValueError('Unexpected review terminals')
    return dict(reachable_nodes=len({s[0] for s in visited}), terminals=sorted(terminals),
        optional_retention=True, promotion_enabled=promotion, maximum_source_relative_ratio=0.95,
        measured_baseline_required=False, source_hash_pass=False,
        candidate_sha256=expected_sha,
        required_gates=['source/build preparation', 'successful NVEnc encode', 'source-relative savings',
                        'unchanged source/build',
                        'Dolby Vision normalization', 'existing final validator'])


def build_flow(original, candidate_sha, promotion=False):
    # Reuse the reviewed fidelity routing, including preservation on failed
    # encodes and unsupported FEL. Replace measured-baseline stages with cheap
    # source/build checks; the intermediate reference is never used.
    flow, _ = measured_flow(original, '', promotion)
    nodes = {n['id']: n for n in flow['flowPlugins']}
    routes = {(e['source'], str(e['sourceHandle'])): e['target'] for e in flow['flowEdges']}
    routes[('inputFile_001', '1')] = routes[(SELECT, '1')]
    for name, phase in [(PREPARE, 'prepare'), (CHECK, 'check')]:
        nodes[name]['name'] = 'Verify source and qualified encoder: ' + phase
        nodes[name]['pluginName'] = 'fgsSourceGuard'
        nodes[name]['inputsDB'] = dict(phase=phase, expectedEncoderSha256=candidate_sha)
    for name in SIZE_NODES:
        nodes[name]['inputsDB'] = {'maxPercent': '95'}
        nodes[name]['name'] = 'Output <= 95% with identical retained audio'
    removed = {SELECT}
    if any(target in removed for (source, _), target in routes.items() if source not in removed):
        raise ValueError('Unexpected dependency on a measured-only stage')
    flow['flowPlugins'] = [n for name, n in nodes.items() if name not in removed]
    flow['flowEdges'] = [edge(source, output, target) for (source, output), target in routes.items()
                         if source not in removed]
    flow['_id'] = 'FGSSourceSavings20260910' + ('Promote' if promotion else 'Review')
    flow['name'] = 'FGS detail retention with source savings — ' + ('promotion' if promotion else 'review only')
    if not promotion:
        nodes[ACCEPT]['name'] = 'Stage validated detail-retention candidate; retain original'
        nodes[ACCEPT]['inputsDB']['acceptancePolicy'] = 'source-size'
    return flow, verify(flow, promotion)


def bundle(flow_path, expected_flow_sha, candidate_image, candidate_sha, baseline_image, output):
    raw = flow_path.read_bytes()
    if sha(raw) != expected_flow_sha:
        raise ValueError('Original flow changed since review')
    if not all(re.fullmatch(r'sha256:[a-f0-9]{64}', value) for value in [candidate_image, baseline_image]):
        raise ValueError('Immutable local image IDs required')
    if not re.fullmatch(r'[a-f0-9]{64}', candidate_sha):
        raise ValueError('Candidate binary SHA-256 required')
    output.mkdir()
    checks = {}
    for promotion in (False, True):
        name = 'source-savings-promote.json' if promotion else 'source-savings-review.json'
        flow, checks[name] = build_flow(json.loads(raw), candidate_sha, promotion)
        (output / name).write_text(json.dumps(flow, indent=2) + '\n')
    (output / 'rollback-flow.json').write_bytes(raw)
    install_plugins(output / 'FlowPlugins')
    guard = output / 'FlowPlugins/LocalFlowPlugins/video/fgsSourceGuard/1.0.0'
    guard.mkdir(parents=True)
    shutil.copyfile(Path(__file__).with_name('tdarr_source_guard.js'), guard / 'index.js')
    shutil.copyfile(Path(__file__).with_name('tdarr_video_bytes.js'), guard / 'tdarr_video_bytes.js')
    for name, image in [('candidate-compose.json', candidate_image), ('rollback-compose.json', baseline_image)]:
        (output / name).write_text(json.dumps({'services': {'tdarr-node': {'image': image}}}, indent=2) + '\n')
    manifest = dict(schema='fgs_tdarr_source_savings_fidelity_v1', candidate_image=candidate_image,
        candidate_sha256=candidate_sha, baseline_image=baseline_image, baseline_flow_sha256=expected_flow_sha,
        activation='none', policy='Optional retain=auto,retain-max=0.1; require 5% savings versus original video with identical retained tracks on both size paths',
        source_guard='Source and encoder filesystem identities across the job; encoder SHA-256 at preparation; no full source content hash',
        limitation='No cap relative to a hypothetical encode by the previous encoder; no perceptual-quality guarantee',
        graph_checks=checks, files={str(p.relative_to(output)): sha(p.read_bytes()) for p in output.rglob('*') if p.is_file()})
    (output / 'bundle.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--flow', type=Path, required=True)
    p.add_argument('--expected-flow-sha256', required=True)
    p.add_argument('--candidate-image', required=True)
    p.add_argument('--candidate-sha256', required=True)
    p.add_argument('--baseline-image', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(bundle(a.flow, a.expected_flow_sha256, a.candidate_image,
                            a.candidate_sha256, a.baseline_image, a.output), indent=2))
