#!/usr/bin/env python3
import hashlib, json, math
from pathlib import Path

ROOT = Path('/tmp/downloads/codex-work/pantheon-sourcebudget-20261020')
RESULT = ROOT/'parent/psyex-tf0-r16-refine/support-result-v2/result.json'
RESULT_SHA = 'f329a6416f3304130fb07a1cb153b88ad039b13e1392c868499cc70a4ad861bb'
ADMISSION_REVIEW = ROOT/'reviewer/round16-refine-outcome/admission-review.json'
STAGES = ROOT/'parent/psyex-tf0-r16-refine/r16-refine-tbr10042-observations/stages.json'
OUT = ROOT/'reviewer/round16-refine-outcome/support-review.json'

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

assert not OUT.exists()
assert digest(RESULT) == RESULT_SHA
data = json.loads(RESULT.read_text())
admission = json.loads(ADMISSION_REVIEW.read_text())
stages = json.loads(STAGES.read_text())
assert data['status'] == admission['status'] == stages['status'] == 'complete'
assert data['admission'] == admission['inputs']['admission'] == stages['admission']
assert data['source_boundaries']['original']['sha256'] == data['source_boundaries']['coding_input']['sha256']

verified = {}
for roi, summary in data['rois'].items():
    groups = {name: value for name, value in summary['groups'].items() if name != '_totals'}
    pixels = summary['coverage_pixels']
    assert pixels == summary['groups']['_totals']['pixels'] == admission['rois'][roi]['pixels']
    assert sum(group['pixels'] for group in groups.values()) == pixels
    assert sum(group['units'] for group in groups.values()) == summary['groups']['_totals']['units']
    invoked = sum(group['pixels'] for name, group in groups.items() if name.startswith('invoked_'))
    uninvoked = sum(group['pixels'] for name, group in groups.items() if name.startswith('uninvoked_'))
    positive = sum(group['pixels'] for name, group in groups.items() if name.endswith('_positive_eob'))
    assert invoked == admission['rois'][roi]['invoked_pixels']
    assert uninvoked == admission['rois'][roi]['uninvoked_pixels']
    assert positive == admission['rois'][roi]['positive_eob_pixels']
    qmap = {}
    for group in groups.values():
        for key, count in group['q_values'].items():
            qmap[key] = qmap.get(key, 0) + count
        assert group['sse']['raw_executed']['vs_raw_executed'] == 0
    assert qmap == admission['rois'][roi]['qindex_invoked_pixels']
    closures = {}
    for stage in ('raw_executed', 'scalar', 'final', 'preloop', 'postloop'):
        total = sum(group['sse'][stage]['vs_original'] for group in groups.values())
        observed = total / pixels
        expected = stages['fixed_roi'][roi]['stages'][stage]['mse']
        assert math.isclose(observed, expected, rel_tol=0, abs_tol=1e-12), (roi, stage, observed, expected)
        closures[stage] = {'sse': total, 'mse': observed}
    assert closures['final'] == closures['preloop']
    for name, group in groups.items():
        if name == 'uninvoked_zero_eob':
            assert group['sse']['scalar']['vs_raw_executed'] == 0
            assert group['sse']['final']['vs_raw_executed'] == 0
            assert group['sse']['preloop']['vs_raw_executed'] == 0
    verified[roi] = {
        'pixels': pixels,
        'units': summary['groups']['_totals']['units'],
        'invoked_pixels': invoked,
        'uninvoked_pixels': uninvoked,
        'positive_eob_pixels': positive,
        'qindex_invoked_pixels': qmap,
        'sse_closure': closures,
    }

assert len(data['rows']) == sum(row['units'] for row in verified.values())
output = {
    'status': 'complete',
    'support_result': {'path': str(RESULT), 'sha256': RESULT_SHA},
    'admission_review': {'path': str(ADMISSION_REVIEW), 'sha256': digest(ADMISSION_REVIEW)},
    'stages': {'path': str(STAGES), 'sha256': digest(STAGES)},
    'verified': verified,
    'checks': [
        'full fixed-ROI coverage and group partition',
        'invoked/uninvoked/EOB/qindex counts equal independent admission derivation',
        'additive per-group SSE closes exactly to every native stage MSE',
        'native final equals independently admitted preloop at the aggregate surface',
        'uninvoked scalar/final/preloop retain the raw predictor surface',
    ],
}
OUT.write_text(json.dumps(output, indent=2, allow_nan=False) + '\n')
