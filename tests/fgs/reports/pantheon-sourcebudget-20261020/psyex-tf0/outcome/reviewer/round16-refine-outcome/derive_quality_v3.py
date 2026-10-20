#!/usr/bin/env python3
"""Independent R16 midpoint-refinement full-window quality/control derivation from admitted outputs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path('/tmp/downloads/codex-work/pantheon-sourcebudget-20261020')
R8_RUN = ROOT / 'worker/psyex-r8/runs/e05-1440/psyex-1x1'
SCORES = ROOT / 'parent/scores/e05-1440'
R8 = {
    'assessment': (R8_RUN / 'assessment.json', 'cc3d2a383732d8d5c40b80ff49a54b76b6e199d4de830f3dd4adf4ed3b95620f'),
    'controls': (R8_RUN / 'controls.json', 'e38545478d03ebfd74d447e54178adfc03673bf7df3efbd42587a2c3ed598c1d'),
    'texture': (SCORES / 'psyex-psyex-1x1-texture.json', 'd4f62b4ba3df7aeeaa71db4407e6eb3320bed1ad3bf3fb9d9344b94bb88fe5b1'),
    'score_result': (SCORES / 'psyex-psyex-1x1-result.json', '763429a7684b5371b22bf05bd17c94dad907a57054c93f9e85305acf67222a06'),
    'metrics': (SCORES / 'metrics-cuda-psyex-psyex-1x1.json', '2e737d9e68edaffc46a0a4c105a5001f22feb87932e326938fc67b464b54253b'),
    'ssimu2': (SCORES / 'ssimu2-psyex-psyex-1x1.json', 'dd4e9cb0238280e255cd13a73ef239852dc1e896ca341b1d004ce36ff0908e90'),
    'butter': (SCORES / 'butter-psyex-psyex-1x1.json', '59120ee26f702bf969609a6d5a663b6943ff763b1e2b30f64554dd7227778906'),
}
MIDPOINT = (116, 118, 120, 122, 124)
EXPECTED_ADMIT_SHA = 'fd190fae6a20aa3cd2efd06e6d6fc9c32471d602272a214b7168667aab511cbb'
EXPECTED_SCORE_SHA = '53d4d9500de90af84a0c7e5f29652c46226a6493d87a84d6938b4e20d24f0058'
EXPECTED_ENCODER_SHA = '5804a1a5985d0676975abe28fba2d8c7a8d6af71c2f70d39dab11436bf2941e4'
EXPECTED_CONTRACT_SHA = '9ea9b3bd9dcf4c5a7f994e0eb12508448a93142ad9d7b7baec27f5ea21597d82'


def ident(path: Path) -> dict:
    path = path.resolve()
    with path.open('rb') as f:
        digest = hashlib.file_digest(f, 'sha256').hexdigest()
    return {'path': str(path), 'sha256': digest, 'size': path.stat().st_size}


def exact(path: Path, expected: str) -> dict:
    row = ident(path)
    assert row['sha256'] == expected, (row, expected)
    return row


def exact_record(row: dict) -> Path:
    path = Path(row['path'])
    actual = ident(path)
    assert actual['path'] == row['path'] and actual['sha256'] == row['sha256']
    if 'size' in row:
        assert actual['size'] == row['size']
    return path


def stats(values) -> dict:
    values = np.asarray(values, dtype=float)
    assert values.size and np.isfinite(values).all()
    return {
        'n': int(values.size), 'mean': float(values.mean()), 'min': float(values.min()),
        'p1': float(np.percentile(values, 1)), 'p5': float(np.percentile(values, 5)),
        'p95': float(np.percentile(values, 95)), 'p99': float(np.percentile(values, 99)),
        'max': float(values.max()),
    }


def texture_summary(data: dict) -> dict:
    assert len(data['frames']) == 240 and [row['frame'] for row in data['frames']] == list(range(240))
    out = {}
    for roi in ('shirt', 'background'):
        rows = [row['roi'][roi] for row in data['frames']]
        midpoint = {}
        for side in ('source', 'target'):
            midpoint[side] = {}
            for metric in ('hf_sigma', 'acf1'):
                value = float(np.mean([rows[index][side][metric] for index in MIDPOINT]))
                assert value == data['midpoint_summary'][roi][side][metric]
                midpoint[side][metric] = value
        hf_error = midpoint['target']['hf_sigma'] / midpoint['source']['hf_sigma'] - 1
        acf_error = abs(midpoint['target']['acf1'] - midpoint['source']['acf1'])
        out[roi] = {
            'midpoint_frames': list(MIDPOINT), 'midpoint': midpoint,
            'midpoint_hf_relative_error': hf_error, 'midpoint_acf1_abs_error': acf_error,
            'midpoint_screen_pass': abs(hf_error) <= .10 and acf_error <= .05,
            'hf_relative_error_240': stats([(row['target']['hf_sigma'] / row['source']['hf_sigma']) - 1 for row in rows]),
            'acf1_abs_error_240': stats([abs(row['target']['acf1'] - row['source']['acf1']) for row in rows]),
            'paired_hf_correlation_240': stats([row['paired_hf_correlation'] for row in rows]),
            'temporal_hf_corr_abs_error_239': stats([abs(row['target']['temporal_hf_corr'] - row['source']['temporal_hf_corr']) for row in rows[1:]]),
        }
    return out


def campaign(metrics_path: Path, ssimu2_path: Path, butter_path: Path) -> dict:
    metric = json.loads(metrics_path.read_text())
    frames = metric['frames']
    assert len(frames) == 240
    values = lambda key: [row['metrics'][key] for row in frames]
    ssimu2 = [row[0] for row in json.loads(ssimu2_path.read_text())]
    butter = json.loads(butter_path.read_text())
    assert len(ssimu2) == len(butter) == 240
    return {
        'ssimu2': stats(ssimu2), 'butter_2norm': stats([row[0] for row in butter]),
        'butter_max': stats([row[2] for row in butter]), 'vmaf': stats(values('vmaf')),
        'vmaf_neg': stats(values('vmaf_neg')), 'psnr_y': stats(values('psnr_y')),
        'cambi': stats(values('cambi')), 'cambi_full_reference': stats(values('cambi_full_reference')),
    }


def tile_key(row: dict) -> tuple:
    return row['frame'], row['x'], row['y']


def control_summary(old: dict, new: dict) -> dict:
    prior = {tile_key(row): row for row in old['tiles']}
    fresh = {tile_key(row): row for row in new['tiles']}
    assert len(prior) == len(fresh) == len(old['tiles']) == len(new['tiles']) == 12870
    assert set(prior) == set(fresh)
    for key in prior:
        for field in ('source', 'kind', 'outside_target', 'baseline'):
            assert prior[key][field] == fresh[key][field]
    out = {}
    selectors = [('all', lambda row: True)]
    for kind in ('quiet', 'edge', 'flat_texture', 'other'):
        selectors.append((kind, lambda row, kind=kind: row['kind'] == kind))
    selectors += [(name + '_outside', lambda row, select=select: select(row) and row['outside_target']) for name, select in selectors]
    for name, select in selectors:
        keys = [key for key in sorted(prior) if select(prior[key])]
        group = {'paired_tiles': len(keys)}
        for metric in ('mse', 'hf_abs_error', 'acf1_abs_error', 'hf_signed_excess'):
            pairs = []
            for key in keys:
                values = []
                for row in (prior[key], fresh[key]):
                    source, candidate = row['source'], row['candidate']
                    if metric == 'mse':
                        value = candidate['mse']
                    elif metric.startswith('hf_'):
                        value = candidate['hf_sigma'] - source['hf_sigma']
                        if metric == 'hf_abs_error':
                            value = abs(value)
                    else:
                        value = None if candidate['acf1'] is None or source['acf1'] is None else abs(candidate['acf1'] - source['acf1'])
                    values.append(value)
                if all(value is not None for value in values):
                    pairs.append(values)
            array = np.asarray(pairs, dtype=float).reshape((-1, 2))
            assert np.isfinite(array).all()
            group[metric] = {
                'evaluable_pairs': len(array),
                'R8': None if not len(array) else stats(array[:, 0]),
                'R16': None if not len(array) else stats(array[:, 1]),
                'R16_increased': int(np.count_nonzero(array[:, 1] > array[:, 0])) if len(array) else 0,
                'R16_decreased': int(np.count_nonzero(array[:, 1] < array[:, 0])) if len(array) else 0,
            }
            if metric == 'hf_signed_excess' and name == 'quiet' and len(array):
                index = int(np.argmax(array[:, 1]))
                key = keys[index]
                group[metric]['R16_sign_counts'] = {
                    'positive': int(np.count_nonzero(array[:, 1] > 0)),
                    'negative': int(np.count_nonzero(array[:, 1] < 0)),
                    'zero': int(np.count_nonzero(array[:, 1] == 0)),
                }
                group[metric]['R16_max_row'] = {'frame': key[0], 'x': key[1], 'y': key[2], 'value': float(array[index, 1])}
        out[name] = group
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    for name in ('command', 'admission', 'assessment', 'controls', 'texture', 'score-result', 'metrics', 'ssimu2', 'butter', 'metrics-receipt'):
        ap.add_argument('--' + name, type=Path, required=True)
        ap.add_argument('--' + name + '-sha', required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    assert not args.output.exists()
    script_before = ident(Path(__file__))
    current_paths = {name.replace('-', '_'): getattr(args, name.replace('-', '_')) for name in ('command', 'admission', 'assessment', 'controls', 'texture', 'score-result', 'metrics', 'ssimu2', 'butter', 'metrics-receipt')}
    inputs = {'R16_' + name: exact(path, getattr(args, name + '_sha')) for name, path in current_paths.items()}
    inputs.update({'R8_' + name: exact(path, digest) for name, (path, digest) in R8.items()})
    command = json.loads(current_paths['command'].read_text())
    admission = json.loads(current_paths['admission'].read_text())
    assessment = json.loads(current_paths['assessment'].read_text())
    controls = json.loads(current_paths['controls'].read_text())
    texture_new = json.loads(current_paths['texture'].read_text())
    score_new = json.loads(current_paths['score_result'].read_text())
    metrics_receipt = json.loads(current_paths['metrics_receipt'].read_text())
    old_assessment = json.loads(R8['assessment'][0].read_text())
    old_controls = json.loads(R8['controls'][0].read_text())
    texture_old = json.loads(R8['texture'][0].read_text())
    score_old = json.loads(R8['score_result'][0].read_text())
    assert metrics_receipt['status'] == 'complete' and metrics_receipt['returncode'] == 0
    assert metrics_receipt['inputs_before'] == metrics_receipt['inputs_after']
    assert command['status'] == 'encoded' and command['within_source_ceiling'] and command['matched_rate_comparable']
    assert command['executed_script']['sha256'] == EXPECTED_ENCODER_SHA
    assert command['contract']['sha256'] == EXPECTED_CONTRACT_SHA
    exact_record(command['contract'])
    assert command['calibration']['phase'] == 'midpoint-refinement'
    assert 1 <= int(command['calibration']['attempt']) <= 3
    assert command.get('calibration_response_within_bracket') is True
    assert 'synthetic_control_only' not in command
    assert admission['status'] == 'admitted' and admission['script']['sha256'] == EXPECTED_ADMIT_SHA
    exact_record(admission['script'])
    assert admission['original_receipt'] == admission['artifacts']['original_receipt'] == inputs['R16_command']
    assert assessment['script']['sha256'] == EXPECTED_SCORE_SHA
    exact_record(assessment['script'])
    assert assessment['runtime_admission']['path'] == inputs['R16_admission']['path']
    assert assessment['runtime_admission']['sha256'] == inputs['R16_admission']['sha256']
    assert assessment['actual_mbps'] == score_new['actual_mbps'] == command['actual_mbps']
    assert assessment['practical_rate_eligible'] and assessment['matched_comparison_eligible']
    assert assessment['all336_decoder_identity'] and assessment['all240_scored_planes_match']
    assert len(assessment['selected_packets']) == 240 and assessment['sorted_scored_positions'] == [96, 336]
    score_packet = json.loads(exact_record(assessment['packet_receipt']).read_text())
    command_packet = json.loads(exact_record(command['packet_window']).read_text())
    assert score_packet['selected_sorted_positions'] == command_packet['mkv']['selected_indices'] == [96, 336]
    assert len(score_packet['selected_packets']) == 240
    assert score_packet['actual_mbps'] == command_packet['actual_mbps'] == command['actual_mbps']
    assert score_packet['source_mbps'] == command_packet['source_mbps'] == command['source_mbps']
    assert score_packet['output']['path'] == command['mkv_output']['path']
    assert score_packet['output']['sha256'] == command['mkv_output']['sha256']
    assert score_packet['run_receipt']['path'] == inputs['R16_command']['path']
    assert score_packet['run_receipt']['sha256'] == inputs['R16_command']['sha256']
    assert assessment['controls'] == controls['summary'] and assessment['face'] == controls['face']
    assert abs(command['actual_mbps'] / old_assessment['actual_mbps'] - 1) <= .01
    assert texture_new['case'] == texture_old['case'] == 'e05-1440'
    assert texture_new['path'] == assessment['output']['path']
    for old_row, new_row in zip(texture_old['frames'], texture_new['frames']):
        assert old_row['frame'] == new_row['frame']
        for roi in ('shirt', 'background'):
            assert old_row['roi'][roi]['source'] == new_row['roi'][roi]['source']
    for key in ('source_control_provenance', 'source', 'baseline_encode_identity', 'baseline_ivf'):
        assert controls[key] == old_controls[key]

    result = {
        'status': 'complete', 'script': script_before, 'inputs': inputs,
        'rates_runtime': {
            'R8_actual_mbps': old_assessment['actual_mbps'], 'R16_actual_mbps': command['actual_mbps'],
            'R16_source_ratio': command['actual_mbps'] / command['source_mbps'],
            'R16_vs_R8_ratio': command['actual_mbps'] / old_assessment['actual_mbps'],
            'R8_two_pass_seconds': old_assessment['two_pass_wall_seconds'],
            'R16_two_pass_seconds': assessment['two_pass_wall_seconds'],
        },
        'texture': {'R8': texture_summary(texture_old), 'R16': texture_summary(texture_new)},
        'controls_paired': control_summary(old_controls, controls),
        'face': {'R8': old_controls['face']['candidate'], 'R16': controls['face']['candidate']},
        'campaign_tails_240': {
            'R8': campaign(R8['metrics'][0], R8['ssimu2'][0], R8['butter'][0]),
            'R16': campaign(current_paths['metrics'], current_paths['ssimu2'], current_paths['butter']),
        },
        'score_aggregates': {'R8': score_old, 'R16': score_new},
        'scope': 'Selected real midpoint-refinement encode; correlated fixed-window descriptive comparison. Midpoint gates remain HF +/-10% and ACF1 absolute error <=0.05. Tail/control summaries add no acceptance threshold and are not playback.',
    }
    assert ident(Path(__file__)) == script_before
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    if not __debug__:
        raise SystemExit('optimized Python prohibited')
    main()
