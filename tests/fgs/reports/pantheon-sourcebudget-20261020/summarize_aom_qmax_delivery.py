#!/usr/bin/env python3
"""Compact admitted R7 delivery and actual-cost evidence, no quality inference."""
import json
from pathlib import Path
from aom_tu_binding import ROOT, identity

HERE = Path(__file__).resolve().parent
run_path = ROOT/'worker/aom-qmax-r7/runs/e05-1440/qmax-qmax8-r3-1/command.json'
validation_path = ROOT/'parent/qmax-observation/admission-trace-1/validation.json'
run = json.loads(run_path.read_text())
v = json.loads(validation_path.read_text())
assert run['status'] == 'diagnostic_encoded' and run['returncode'] == 0
assert v['status'] == 'admitted' and v['precision_delivery_pass']
binding = json.loads(Path(v['artifacts']['binding']['path']).read_text())
assert binding['inputs']['installed_command'] == identity(run_path)
trace = json.loads(Path(v['artifacts']['run']['path']).read_text())
off = json.loads(Path(v['artifacts']['disabled_control']['path']).read_text())
assert trace['exact_installed_ivf'] and off['exact_installed_ivf']
assert trace['output']['sha256'] == off['output']['sha256'] == run['ivf_sha256']
qvalues = [r['fields']['base_q_idx'] for r in binding['coded_quant_headers']]
result = {
    'question': 'Was finer actual quantization delivered, and at what real packet/time cost?',
    'scope': 'End-to-end known-fixture diagnostic; no fixed-decision causality or quality acceptance.',
    'script': identity(__file__),
    'provenance': {'run': identity(run_path), 'admission': identity(validation_path),
                   'binding': v['artifacts']['binding'], 'trace': v['artifacts']['run'],
                   'off': v['artifacts']['disabled_control'],
                   'decoder_validation': binding['inputs']['decoder_validation']},
    'actual_scored_mbps': run['actual_mbps'], 'source_scored_mbps': run['source_mbps'],
    'relative_source_rate': run['actual_mbps']/run['source_mbps'],
    'full_window_rates': run['full_window_rates'],
    'two_pass_wall_seconds': run['wall_seconds'],
    'pass_seconds': {k: val['seconds'] for k, val in run['passes'].items()},
    'private_off_pass2_seconds': off['pass2_wall_seconds'],
    'private_trace_pass2_seconds': trace['pass2_wall_seconds'],
    'private_runtime_scope': 'Instrumentation controls only; not a production speed comparison.',
    'coded_header_count': len(qvalues), 'coded_base_qindex_minmax': [min(qvalues), max(qvalues)],
    'coded_base_qindex_counts': {str(q): qvalues.count(q) for q in sorted(set(qvalues))},
    'selected_generation': v['selected_generation'], 'attempts': v['attempts'],
    'precision_delivery': v['precision_delivery'], 'precision_delivery_pass': True,
    'all336_three_decoder_all_planes_exact': True,
    'practical_rate_eligible': 0 < run['actual_mbps'] <= run['source_mbps'],
    'quality_assessed_here': False, 'playback_observed': False,
}
for record in result['provenance'].values():
    assert identity(record['path']) == record
(HERE/'aom-qmax-delivery.json').write_text(json.dumps(result, indent=2)+'\n')
