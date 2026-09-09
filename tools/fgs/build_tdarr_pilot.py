#!/usr/bin/env python3
"""Prepare a separate, measured-source Tdarr pilot and rollback evidence.

This writes a new directory only. It does not install plugins, activate a flow,
change a container, or replace media. Review mode has no reachable replacement
or notification nodes. Promotion mode still requires all three acceptance gates.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil


FGS_OLD = '--av1-film-grain denoise=auto,chroma=auto,denoiser=bilateral'
FGS_NEW = FGS_OLD + ',retain=auto,retain-max=0.1'
BUDGET = 'fgsMeasuredBudget'
KEEP = 'fidelityKeepSource_001'
SELECT = 'fidelitySelect_001'
PREPARE = 'fidelityPrepare_001'
CHECK = 'fidelityCheck_001'
ACCEPT = 'fidelityAccepted_001'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def edge(source, output, target):
    return dict(id=f'fgs_{source}_{output}', source=source, sourceHandle=str(output),
                target=target, targetHandle=None, animated=True, type='smoothstep')


def preserve_fel(code):
    """Replace the known lossy FEL conversion branch with source preservation."""
    start = "    if (dvElType === 'FEL') {"
    stop = '\n\n  let hdr10plus = false;'
    if code.count(start) != 1 or code.count(stop) != 1:
        raise ValueError('Detector layout changed; review FEL preservation manually')
    first, last = code.index(start), code.index(stop)
    if 'only the per-pixel FEL refinement is lost.' not in code[first:last]:
        raise ValueError('Expected FEL conversion policy is absent; review detector')
    return code[:first] + """    if (dvElType === 'FEL') {
      return keepVideoOriginal('Dolby Vision FEL per-pixel enhancement cannot be preserved in this AV1 pilot');
    }
  }""" + code[last:]


def verify_graph(flow, promotion):
    nodes = {n['id']: n for n in flow['flowPlugins']}
    if len(nodes) != len(flow['flowPlugins']):
        raise ValueError('Duplicate flow node')
    routes = {}
    for e in flow['flowEdges']:
        if e['source'] not in nodes or e['target'] not in nodes:
            raise ValueError('Dangling flow edge')
        key = (e['source'], str(e['sourceHandle']))
        if key in routes:
            raise ValueError('Ambiguous flow output')
        routes[key] = e['target']
    seen, terminals = set(), set()

    def walk(node_id, prepared=False, checked=False, validated=False, encoded=False, ancestors=()):
        if node_id in ancestors:
            raise ValueError('Pilot flow contains a cycle')
        state = (node_id, prepared, checked, validated, encoded)
        if state in seen:
            return
        seen.add(state)
        node = nodes[node_id]
        if not node.get('fpEnabled', True):
            raise ValueError('Disabled nodes need explicit review')
        if node_id in ('videoSample_001', 'nvenccEncode_001') and not prepared:
            raise ValueError('Encoding is reachable without source/build preparation')
        if node_id == 'validateOutput_001' and not checked:
            raise ValueError('Final validator is reachable without a budget pass')
        if node_id in (ACCEPT, 'replaceOrig_001') and not (prepared and checked and validated and encoded):
            raise ValueError('Candidate acceptance bypasses required gates')
        if not promotion and (node['pluginName'] == 'replaceOriginalFile' or node_id.startswith('notify')):
            raise ValueError('Review pilot can mutate or notify a library')
        outgoing = [(out, target) for (src, out), target in routes.items() if src == node_id]
        if not outgoing:
            terminals.add(node_id)
        for output, target in outgoing:
            walk(target, prepared or (node_id == PREPARE and output == '1'),
                 checked or (node_id == CHECK and output == '1'),
                 validated or (node_id == 'validateOutput_001' and output == '1'),
                 encoded or (node_id == 'nvenccEncode_001' and output == '1'),
                 (*ancestors, node_id))
    walk('inputFile_001')
    for reject in (SELECT, PREPARE, CHECK, 'videoSample_001', 'sizeCheck_001', 'sizeCheckRelaxed_001'):
        if routes.get((reject, '2')) != KEEP:
            raise ValueError('A rejected candidate can continue outside the source-retention terminal')
    if not promotion and terminals != {KEEP, ACCEPT}:
        raise ValueError(f'Unexpected review terminals: {terminals}')
    return dict(reachable_nodes=len({s[0] for s in seen}), terminals=sorted(terminals),
                promotion_enabled=promotion, required_gates=['source/build', 'video budget', 'final validator'])


def build_flow(original, reference_path, promotion=False):
    flow = copy.deepcopy(original)
    flow['_id'] = 'FGSMeasuredPilot20260909' + ('Promote' if promotion else 'Review')
    flow['name'] = 'FGS measured fidelity pilot — ' + ('promotion' if promotion else 'review only')
    nodes = {n['id']: n for n in flow['flowPlugins']}
    encoder = nodes['nvenccEncode_001']['inputsDB']
    sampler = nodes['videoSample_001']['inputsDB']
    if encoder['cliArguments'] != sampler['encoderArguments']:
        raise ValueError('Sampler and full encode settings differ')
    if encoder['cliArguments'].count(FGS_OLD + ' ') != 1:
        raise ValueError('Unexpected source film-grain settings')
    encoder['cliArguments'] = encoder['cliArguments'].replace(FGS_OLD + ' ', FGS_NEW + ' ')
    sampler['encoderArguments'] = encoder['cliArguments']
    nodes['dvhdrDetect_001']['inputsDB']['code'] = preserve_fel(nodes['dvhdrDetect_001']['inputsDB']['code'])
    for node_id, phase, y in ((SELECT, 'select', 80), (PREPARE, 'prepare', 900), (CHECK, 'check', 1200)):
        nodes[node_id] = dict(id=node_id, name=f'Measured fidelity budget: {phase}',
            sourceRepo='Local', pluginName=BUDGET, version='1.0.0', fpEnabled=True,
            position=dict(x=1100, y=y), inputsDB=dict(phase=phase, referenceManifest=reference_path))
    nodes[KEEP] = dict(id=KEEP, name='Keep original and end pilot', sourceRepo='Community',
        pluginName='setWorkingFile', version='1.0.0', fpEnabled=True, position=dict(x=1400, y=900),
        inputsDB=dict(source='originalFile', customPath=''))
    nodes[ACCEPT] = dict(id=ACCEPT, name='Review accepted candidate; no library replacement',
        sourceRepo='Community', pluginName='customFunction', version='1.0.0', fpEnabled=True,
        position=dict(x=1100, y=1450), inputsDB=dict(code="""module.exports = async args => {
  const assert = require('node:assert/strict');
  assert.equal(args.variables.user.fidelityBudgetDecision.decision, 'within_budget');
  assert.equal(String(args.variables.user.videoAlreadyEncoded), '1');
  args.variables.user.fidelityTrialAccepted = true;
  args.jobLog('[fidelity-pilot] Candidate accepted for review: ' + args.inputFileObj._id);
  return {outputFileObj: args.inputFileObj, outputNumber: 1, variables: args.variables};
};"""))
    routes = {(e['source'], str(e['sourceHandle'])): e['target'] for e in flow['flowEdges']}
    if len(routes) != len(flow['flowEdges']):
        raise ValueError('Ambiguous source flow')
    first = routes[('inputFile_001', '1')]
    routes[('inputFile_001', '1')] = SELECT
    routes[(SELECT, '1')] = first
    routes[('mapQvbr_001', '1')] = PREPARE
    routes[(PREPARE, '1')] = 'videoSample_001'
    for source in ('sizeCheck_001', 'sizeCheckRelaxed_001'):
        if routes[(source, '1')] != 'validateOutput_001':
            raise ValueError('Source size routing changed')
        routes[(source, '1')] = CHECK
    routes[(CHECK, '1')] = 'validateOutput_001'
    # Measured trials never take a substitute FFmpeg video encode or stream-copy
    # replacement on a failed encode/saving/format decision.
    for key, target in list(routes.items()):
        if target in ('streamPolicyCheck_001', 'setOriginal_001'):
            routes[key] = KEEP
    for node in (SELECT, PREPARE, CHECK, 'videoSample_001', 'sizeCheck_001', 'sizeCheckRelaxed_001',
                 'postExecCheck_001', 'nvenccCheck_001'):
        routes[(node, '2')] = KEEP
    if not promotion:
        routes[('validateOutput_001', '1')] = ACCEPT
    reachable, pending = set(), ['inputFile_001']
    while pending:
        node = pending.pop()
        if node in reachable:
            continue
        reachable.add(node)
        pending.extend(target for (source, _), target in routes.items() if source == node)
    flow['flowPlugins'] = [n for key, n in nodes.items() if key in reachable]
    flow['flowEdges'] = [edge(source, output, target) for (source, output), target in routes.items() if source in reachable]
    return flow, verify_graph(flow, promotion)


def bundle(flow_path, expected_flow_sha, reference_path, candidate_image, output):
    raw = flow_path.read_bytes()
    if sha(raw) != expected_flow_sha:
        raise ValueError('Live flow differs from the reviewed snapshot')
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', candidate_image):
        raise ValueError('Candidate runtime must be an immutable image digest')
    reference = json.loads(reference_path.read_text())
    if reference.get('schema') != 'fgs_tdarr_budget_reference_v1':
        raise ValueError('Expected a measured reference manifest')
    output.mkdir()  # Never overwrite an earlier bundle.
    destination = '/flow-config/fgs-measured-reference.json'
    reports = {}
    for promotion in (False, True):
        name = 'pilot-promote.json' if promotion else 'pilot-review.json'
        flow, checks = build_flow(json.loads(raw), destination, promotion)
        (output / name).write_text(json.dumps(flow, indent=2) + '\n')
        reports[name] = checks
    (output / 'rollback-flow.json').write_bytes(raw)
    shutil.copyfile(reference_path, output / 'fgs-measured-reference.json')
    plugin = output / 'FlowPlugins/LocalFlowPlugins/video/fgsMeasuredBudget/1.0.0/index.js'
    plugin.parent.mkdir(parents=True)
    shutil.copyfile(Path(__file__).with_name('tdarr_size_budget.js'), plugin)
    manifest = dict(schema='fgs_tdarr_pilot_bundle_v1', candidate_image=candidate_image,
        candidate_sha256=reference['candidate_sha256'], baseline_flow_sha256=expected_flow_sha,
        activation='none; separate limited-source pilot, not a blanket production policy',
        graph_checks=reports,
        files={str(p.relative_to(output)): sha(p.read_bytes()) for p in output.rglob('*') if p.is_file()})
    (output / 'bundle.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--flow', type=Path, required=True)
    parser.add_argument('--expected-flow-sha256', required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--candidate-image', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(bundle(args.flow, args.expected_flow_sha256, args.reference,
                            args.candidate_image, args.output), indent=2))
