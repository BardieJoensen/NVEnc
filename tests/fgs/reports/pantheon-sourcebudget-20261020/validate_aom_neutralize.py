#!/usr/bin/env python3
"""Admit a controlled source-pixel contrast with dynamic coded-event coverage."""
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(os.environ.get('PANTHEON_SOURCEBUDGET_ROOT',
    '/tmp/downloads/codex-work/pantheon-sourcebudget-20261020'))
HERE = Path(__file__).resolve().parent
BASE = ROOT / 'parent/source-neutralize'
# Filled only after independent patch/build review, before measurement admission.
APPROVED_BUILD_SHA = '4ce837abcd6ffc55a1e8a17520dfb2c6079732899d035266a01955d0e21d0a8d'
tag, coverage_dir, *control_tag = sys.argv[1:]
assert re.fullmatch(r'[A-Za-z0-9_.-]+', tag)
coverage_dir = Path(coverage_dir).resolve()
out = BASE / (tag + '-validated.json')
assert not out.exists()

def read(path): return json.loads(Path(path).read_text())
def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
def identity(path): return {'path': str(path), 'sha256': sha(path)}
def bound(row): assert sha(row['path']) == row['sha256'], row['path']
def bind_tree(node):
    if isinstance(node, dict):
        if 'path' in node and 'sha256' in node: bound(node)
        for value in node.values(): bind_tree(value)
    elif isinstance(node, list):
        for value in node: bind_tree(value)

installed_path = ROOT / 'worker/runs/e05-1440/aom-psnr-1x2/command.json'
installed = read(installed_path)
assert installed['ivf_sha256'] == 'ab233b3874583fbbb75f9bd9e91a63ff19efeae9a57e7639ca4fc499c7662052'
assert sha(installed_path.parent / 'out.ivf') == installed['ivf_sha256']
run_path = BASE / 'runs' / tag / 'command.json'
run = read(run_path)
assert run['tag'] == tag and run['status'] == 'encoded' and run['returncode'] == 0
assert run['request_kbps'] == 11671, 'Initial source-pixel contrast only; calibrated arms need distinct admission.'
arm = run['arm']; assert arm in ('off', 'on')
for name in ('source_command', 'input', 'input_after', 'build_receipt', 'library',
             'ldd_output', 'stats_original', 'stats_before', 'stats_after',
             'script', 'ffmpeg', 'output', 'log', 'trace'): bound(run[name])
assert run['build_receipt']['sha256'] == APPROVED_BUILD_SHA
assert run['source_command']['sha256'] == sha(installed_path)
assert run['script']['sha256'] == sha(HERE / 'replay_aom_neutralize.py')
assert run['ffmpeg']['sha256'] == installed['ffmpeg']['sha256']
assert run['input']['sha256'] == installed['input']['sha256']
assert run['input'] == run['input_after']
assert run['stats_original']['sha256'] == installed['passes']['pass1']['pass1_stats_snapshot']['sha256']
assert run['stats_before']['sha256'] == run['stats_after']['sha256'] == run['stats_original']['sha256']
actual, expected = list(run['command']), list(installed['commands']['pass2'])
assert Path(actual[-1]).resolve() == Path(run['output']['path']).resolve()
assert Path(actual[actual.index('-passlogfile')+1]+'-0.log').resolve() == Path(run['stats_before']['path']).resolve()
assert Path(actual[actual.index('-i')+1]).resolve() == Path(run['input']['path']).resolve()
assert actual[actual.index('-b:v')+1] == str(run['request_kbps'])+'k'
for command in (actual, expected):
    command[command.index('-passlogfile')+1] = 'LOCAL_STATS'
    command[command.index('-b:v')+1] = 'RATE_CALIBRATION'
    command[-1] = 'LOCAL_OUTPUT'
assert actual == expected
assert run['exact_installed_ivf'] == (run['output']['sha256'] == installed['ivf_sha256'])
build = read(run['build_receipt']['path']); bind_tree(build)
assert run['library'] == {k: build['library'][k] for k in ('path','sha256','size')}
assert build['status'] == 'build_complete' and build['execution']['configure_returncode'] == build['execution']['build_returncode'] == 0
assert build['source_manifest_before']['sha256'] == build['source_manifest_after']['sha256'] == build['reviewed_source_manifest']['sha256']
manifest = read(build['source_manifest_after']['path'])
assert len(manifest) == 1344
for name, digest in manifest.items():
    assert sha(Path(build['workspace']) / 'source' / name) == digest, name
library = Path(run['library']['path']).resolve()
loaded = re.findall(r'^\s*libaom\.so\.3 => (\S+)', Path(run['ldd_output']['path']).read_text(), re.M)
assert len(loaded) == 1 and Path(loaded[0]).resolve() == library
assert Path(run['environment_overrides']['LD_LIBRARY_PATH']).resolve() == library.parent
assert run['environment_overrides']['AOM_NEUTRALIZE_SOURCE'] == ('1' if arm == 'on' else '0')
fd = run['environment_overrides']['AOM_TRACE_FD']; assert int(fd) >= 3 and str(int(fd)) == fd
if arm == 'off':
    assert not control_tag and run['request_kbps'] == 11671 and run['exact_installed_ivf']
else:
    assert len(control_tag) == 1
    control_path = BASE / (control_tag[0] + '-validated.json')
    control = read(control_path)
    assert control['status'] == 'admitted' and control['arm'] == 'off'
    assert control['provenance']['build']['sha256'] == APPROVED_BUILD_SHA
    bind_tree(control['provenance'])

input_path = ROOT / 'parent/source-boundary/input-planes.json'
assert sha(input_path) == 'd4e7e47ac1c042bd3bbfcba559b55964e8389999cddd6c1b330c9a9c706146de'
inputs = read(input_path)
for name in ('source', 'historical', 'script'): bound(inputs[name])
assert inputs['all336_whole_md5_equal_historical'] and inputs['source_unchanged']
assert inputs['source']['sha256'] == run['input']['sha256']
assert [f['source_index'] for f in inputs['frames']] == list(range(336))
by_hash = {f['whole_md5']: f for f in inputs['frames']}; assert len(by_hash) == 336
coverage_receipt = read(coverage_dir / 'receipt.json'); bind_tree(coverage_receipt)
assert coverage_receipt['input_ivf']['sha256'] == run['output']['sha256']
assert coverage_receipt['ffmpeg']['sha256'] == installed['ffmpeg']['sha256']
parser_record = coverage_receipt['files']['parse_trace_headers.py']
assert parser_record['sha256'] == '6adfc1947424e3e7f607e144b1cd31a5670022fba3544999620ed059abdfa5d2'
coverage_execution = read(coverage_dir / 'command.json')
assert coverage_execution['returncode'] == 0
if arm == 'on':
    assert {k: coverage_execution['run'][k] for k in ('path','sha256')} == identity(run_path)
coverage = read(coverage_dir / 'parsed-events.json')
assert coverage_receipt['files']['parsed-events.json']['sha256'] == sha(coverage_dir / 'parsed-events.json')
assert coverage_receipt['status'] == 'pass' and coverage_receipt['summary'] == coverage['summary']
assert coverage['summary']['all_packets_exactly_one_display_action']
expected_keys = collections.Counter(tuple(e['hook_match_key']) for e in coverage['events'] if not e['show_existing_frame'])
assert len(expected_keys) == sum(expected_keys.values()) > 0
stages = {'selected': {}, 'effective': {}}
for line in Path(run['trace']['path']).read_bytes().splitlines(keepends=True):
    assert line.endswith(b'\n') and len(line) < 2048
    row = json.loads(line); assert row['record_version'] == 5
    stage = row['stage']; assert stage in stages
    assert [row[k] for k in ('bit_depth','highbd','width','height','uv_width','uv_height')] == [10,1,1920,1080,960,540]
    assert row['subsampling'] == [1,1] and row['frame_parallel_level'] == 0
    for field in ('strides_a','strides_b'):
        assert len(row[field]) == 2 and row[field][0] >= 1920 and row[field][1] >= 960
    src = by_hash[row['unfiltered_md5']]
    assert row['unfiltered_plane_md5'] == src['plane_md5']
    assert len(row['source_plane_md5']) == len(row['neq']) == len(row['maxabs']) == 3
    assert row['source_ptr_equal'] in (0,1)
    for p,count in enumerate((1920*1080,960*540,960*540)):
        assert 0 <= row['neq'][p] <= count and 0 <= row['maxabs'][p] <= 1023
        assert (row['source_plane_md5'][p] == src['plane_md5'][p]) == (row['neq'][p] == 0) == (row['maxabs'][p] == 0)
    unchanged = sum(row['neq']) == 0
    assert unchanged == (row['source_md5'] == src['whole_md5'])
    assert not row['source_ptr_equal'] or unchanged
    key = (row['unfiltered_md5'],row['gf_frame_index'],row['update_type'],row['frame_parallel_level'])
    assert key not in stages[stage], ('ambiguous stage pairing', stage, key)
    stages[stage][key] = row | {'source_index': src['source_index'], 'unchanged': unchanged}
assert stages['selected'].keys() == stages['effective'].keys()
assert len(stages['effective']) == sum(expected_keys.values())
actual_keys = collections.Counter()
for pair_key, row in stages['effective'].items():
    selected = stages['selected'][pair_key]
    assert row['show_frame'] in (0,1) and row['showable_frame'] in (0,1)
    assert 0 <= row['order_hint'] < 128
    key = (row['source_index'],row['frame_type'],row['show_frame'],
           0 if row['show_frame'] else row['showable_frame'],row['order_hint'],
           255 if row['frame_type']==0 and row['show_frame'] else row['refresh_frame_flags'])
    actual_keys[key] += 1; row['hook_match_key'] = key
    if arm == 'on':
        assert row['unchanged'] and row['source_ptr_equal']
    else:
        for field in ('source_md5','source_plane_md5','unfiltered_md5','unfiltered_plane_md5','neq','maxabs','source_ptr_equal'):
            assert selected[field] == row[field], field
assert actual_keys == expected_keys
assert {r['source_index'] for r in stages['effective'].values()} == set(range(336))
assert any(not r['unchanged'] for r in stages['selected'].values()), 'No realized sample intervention'
summary = {}
for stage, mapping in stages.items():
    rows = list(mapping.values())
    summary[stage] = {'events':len(rows),'changed_events':sum(not r['unchanged'] for r in rows),
        'different_pointer_events':sum(not r['source_ptr_equal'] for r in rows),
        'unequal_samples':[sum(r['neq'][p] for r in rows) for p in range(3)],
        'maxabs':[max(r['maxabs'][p] for r in rows) for p in range(3)]}
result = {'status':'admitted','arm':arm,'summary':summary,
    'exact_installed_ivf':run['exact_installed_ivf'],
    'all336_source_indices_bound':True,'all_coded_events_matched':True,'selected_effective_bijection':True,
    'events':{stage:sorted(rows.values(),key=lambda r:(r['source_index'],r['gf_frame_index'],r['update_type'])) for stage,rows in stages.items()},
    'provenance':{'script':identity(__file__),'run':identity(run_path),'build':identity(run['build_receipt']['path']),
        'inputs':identity(input_path),'coverage_receipt':identity(coverage_dir/'receipt.json'),
        'coverage':identity(coverage_dir/'parsed-events.json')},
    'scope':'Coding-source sample contrast retaining upstream filtering and analysis; no quality or feasibility admission.',
    'playback_observed':False}
if arm=='on': result['provenance']['control'] = identity(control_path)
out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':result['status'],'arm':arm,'summary':summary,'output':str(out)},indent=2))
